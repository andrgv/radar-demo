/* Generated from firmware/main.c SHA256 12175f6a919a2cbd93612f80abc283df6861045d499a399564bdef391aef9f41. Do not edit; rerun tools/prepare_qualification.py. */
#include "cybsp.h"
#include "cyhal.h"
#include "xensiv_bgt60cutrxx_mtb.h"
#include "xensiv_bgt60cutrxx_regs.h"
#include "radar_fifo_read.h"
#include "../../firmware/vendor/presence_detection_tracking.h"
#include <string.h>

#define CHIRPS 17u
#define SAMPLES 64u
#define RECEIVERS 3u
#define FRAME_WORDS (CHIRPS * SAMPLES * RECEIVERS / 2u)
#define HEADER_BYTES 48u
#define PAYLOAD_BYTES (FRAME_WORDS * 4u)
#define PACKET_BYTES (HEADER_BYTES + PAYLOAD_BYTES + 4u)
#define PROFILE_ID (RADAR_SCOPE_OUTPUT ? 0x33515301u : ((RADAR_HPF_KHZ == 100) ? 0x33514801u : 0x33514802u))

static xensiv_bgt60cutrxx_mtb_t sensor;
static cyhal_uart_t uart;
static uint8_t uart_rx[64];
static cyhal_timer_t timer;
static uint32_t packets[2][PACKET_BYTES / 4u];
static volatile bool transmitting;
static uint32_t sequence;
static uint32_t dropped;
static uint32_t errors;
static bool enabled;

static xensiv_bgt60cutrxx_mtb_iface_config_t interface = {
    .selpin = CYBSP_SPI_CS, .rstpin = CYBSP_GPIOA5,
    .irqpin = CYBSP_GPIO10, .irq_priority = 3,
    .spi_mosi = CYBSP_SPI_MOSI, .spi_miso = CYBSP_SPI_MISO,
    .spi_clk = CYBSP_SPI_CLK, .spi_speed_hz = 18750000u
};


#ifndef RADAR_SCOPE_OUTPUT
#define RADAR_SCOPE_OUTPUT 0
#endif
#ifndef RADAR_HPF_KHZ
#define RADAR_HPF_KHZ 350
#endif
#if RADAR_HPF_KHZ != 100 && RADAR_HPF_KHZ != 350
#error "Qualification supports only 100 or 350 kHz HPF1"
#endif
static int32_t qualification_set_hpf(void)
{
    const uint32_t mask = 0x00000300u;
    const uint32_t selection = (RADAR_HPF_KHZ == 100) ? 0u : 0x00000100u;
    for (uint16_t address = BGT60CUTR13B_REG_CS_IDX0_RX1;
         address <= BGT60CUTR13B_REG_CS_IDX0_RX3; address += 4u) {
        uint32_t original = 0, actual = 0;
        if (xensiv_bgt60cutrxx_get_reg(&sensor.dev, address, &original) != 0) return -1;
        const uint32_t expected = (original & ~mask) | selection;
        if (xensiv_bgt60cutrxx_set_reg(&sensor.dev, address, expected) != 0) return -1;
        if (xensiv_bgt60cutrxx_get_reg(&sensor.dev, address, &actual) != 0 || actual != expected) return -1;
    }
    return 0;
}

#if RADAR_SCOPE_OUTPUT
static int32_t qualification_scope_output(void)
{
    uint32_t original = 0, actual = 0;
    /* FIFO/error status is polled over SPI. Do not turn each chirp into an MCU ISR. */
    cyhal_gpio_enable_event(CYBSP_GPIO10, CYHAL_GPIO_IRQ_RISE, interface.irq_priority, false);
    if (xensiv_bgt60cutrxx_get_reg(&sensor.dev, BGT60CUTR13B_REG_IO_CTRL, &original) != 0) return -1;
    uint32_t expected = (original & ~BGT60CUTR13B_IO_CTRL_DMUX0_SEL_msk) |
        (BGT60CUTR13B_IO_CTRL_DMUX0_SEL_CHIRP_ACTIVE << BGT60CUTR13B_IO_CTRL_DMUX0_SEL_pos);
    if (xensiv_bgt60cutrxx_set_reg(&sensor.dev, BGT60CUTR13B_REG_IO_CTRL, expected) != 0) return -1;
    if (xensiv_bgt60cutrxx_get_reg(&sensor.dev, BGT60CUTR13B_REG_IO_CTRL, &actual) != 0 || actual != expected) return -1;
    if (xensiv_bgt60cutrxx_get_reg(&sensor.dev, BGT60CUTR13B_REG_IO_DIO4, &original) != 0) return -1;
    expected = (original & ~(BGT60CUTR13B_IO_DIO4_MAP_msk | BGT60CUTR13B_IO_DIO4_PULSE_LEN_msk)) |
        (BGT60CUTR13B_IO_DIO4_MAP_DMUX0 << BGT60CUTR13B_IO_DIO4_MAP_pos) |
        BGT60CUTR13B_IO_DIO4_EN_msk | BGT60CUTR13B_IO_DIO4_STREN_msk;
    if (xensiv_bgt60cutrxx_set_reg(&sensor.dev, BGT60CUTR13B_REG_IO_DIO4, expected) != 0) return -1;
    if (xensiv_bgt60cutrxx_get_reg(&sensor.dev, BGT60CUTR13B_REG_IO_DIO4, &actual) != 0 || actual != expected) return -1;
    return 0;
}
#endif

static uint32_t crc32(const uint8_t *bytes, size_t length)
{
    uint32_t crc = 0xffffffffu;
    for (size_t index = 0; index < length; ++index) {
        crc ^= bytes[index];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}

static void uart_event(void *argument, cyhal_uart_event_t event)
{
    (void)argument;
    if (event & CYHAL_UART_IRQ_TX_DONE) transmitting = false;
}

static int32_t stop_capture(void)
{
    return xensiv_bgt60cutrxx_soft_reset(&sensor.dev, RESET_FSM);
}

static int32_t capture(uint32_t *packet)
{
    int32_t status = stop_capture();
    status |= xensiv_bgt60cutrxx_soft_reset(&sensor.dev, RESET_FIFO);
    status |= xensiv_bgt60cutrxx_set_irq_clear(&sensor.dev,
        BGT60CUTR13B_IR_CLEAR_THRESHOLD_MSK | BGT60CUTR13B_IR_CLEAR_FIFO_UF_CLR_MSK |
        BGT60CUTR13B_IR_CLEAR_FIFO_OF_CLR_MSK);
    uint32_t start = cyhal_timer_read(&timer);
    status |= xensiv_bgt60cutrxx_trigger_sequence0(&sensor.dev);
    uint32_t words = 0;
    while (status == 0 && words < FRAME_WORDS) {
        uint32_t irq = 0;
        uint32_t available = 0;
        status = xensiv_bgt60cutrxx_get_irq_status(&sensor.dev, &irq);
        if (irq & (BGT60CUTR13B_IR_STAT_FIFO_UF_ERR_MSK | BGT60CUTR13B_IR_STAT_FIFO_OF_ERR_MSK)) {
            status = -1;
            break;
        }
        status |= xensiv_bgt60cutrxx_get_fifo_level(&sensor.dev, &available);
        uint32_t count = available / 2u;
        if (count > 192u) count = 192u;
        if (count > FRAME_WORDS - words) count = FRAME_WORDS - words;
        if (count && status == 0) {
            status = xensiv_bgt60cutrxx_get_fifo(&sensor.dev,
                packet + HEADER_BYTES / 4u + words, count);
            words += count;
        }
        if ((uint32_t)(cyhal_timer_read(&timer) - start) > 200000u) {
            status = -1;
            break;
        }
    }
    status |= stop_capture();
    uint32_t final_irq = 0;
    status |= xensiv_bgt60cutrxx_get_irq_status(&sensor.dev, &final_irq);
    if (final_irq & (BGT60CUTR13B_IR_STAT_FIFO_UF_ERR_MSK | BGT60CUTR13B_IR_STAT_FIFO_OF_ERR_MSK)) status = -1;
    if (status != 0) return status;
    packet[0] = 0x33445247u;
    packet[1] = 1u | (HEADER_BYTES << 16);
    packet[2] = PAYLOAD_BYTES;
    packet[3] = sequence;
    packet[4] = start;
    packet[5] = PROFILE_ID;
    packet[6] = CHIRPS | (SAMPLES << 16);
    packet[7] = RECEIVERS | (16u << 8) | ((3u | ((RADAR_HPF_KHZ == 100) ? 4u : 0u)) << 16);
    packet[8] = dropped;
    packet[9] = errors;
    packet[10] = cyhal_timer_read(&timer) - start; /* acquisition path elapsed, NOT chirp spacing */
    packet[11] = crc32((uint8_t *)packet, HEADER_BYTES - 4u);
    packet[(PACKET_BYTES - 4u) / 4u] = crc32((uint8_t *)packet, PACKET_BYTES - 4u);
    return 0;
}

int main(void)
{
    if (cybsp_init() != CY_RSLT_SUCCESS) return 1;
    __enable_irq();
    cyhal_uart_cfg_t uart_config = { .data_bits = 8, .stop_bits = 1,
        .parity = CYHAL_UART_PARITY_NONE, .rx_buffer = uart_rx,
        .rx_buffer_size = sizeof(uart_rx) };
    if (cyhal_uart_init(&uart, CYBSP_DEBUG_UART_TX, CYBSP_DEBUG_UART_RX,
        NC, NC, NULL, &uart_config) != CY_RSLT_SUCCESS) return 2;
    uint32_t actual_baud;
    if (cyhal_uart_set_baud(&uart, 2000000u, &actual_baud) != CY_RSLT_SUCCESS) return 3;
    cyhal_uart_register_callback(&uart, uart_event, NULL);
    cyhal_uart_enable_event(&uart, CYHAL_UART_IRQ_TX_DONE, 4, true);
    cyhal_timer_cfg_t timer_config = { .compare_value = 0, .period = 0xffffffffu,
        .direction = CYHAL_TIMER_DIR_UP, .is_compare = false,
        .is_continuous = true, .value = 0 };
    if (cyhal_timer_init(&timer, NC, NULL) != CY_RSLT_SUCCESS) return 4;
    if (cyhal_timer_configure(&timer, &timer_config) != CY_RSLT_SUCCESS) return 4;
    if (cyhal_timer_set_frequency(&timer, 1000000u) != CY_RSLT_SUCCESS) return 4;
    if (cyhal_timer_start(&timer) != CY_RSLT_SUCCESS) return 4;
    if (cyhal_gpio_init(CYBSP_GPIO5, CYHAL_GPIO_DIR_OUTPUT, CYHAL_GPIO_DRIVE_STRONG, 1) ||
        cyhal_gpio_init(CYBSP_GPIO13, CYHAL_GPIO_DIR_OUTPUT, CYHAL_GPIO_DRIVE_STRONG, 1) ||
        cyhal_gpio_init(CYBSP_GPIO11, CYHAL_GPIO_DIR_OUTPUT, CYHAL_GPIO_DRIVE_STRONG, 1) ||
        cyhal_gpio_init(CYBSP_GPIOA2, CYHAL_GPIO_DIR_OUTPUT, CYHAL_GPIO_DRIVE_STRONG, 1)) return 5;
    if (xensiv_bgt60cutrxx_platform_open(&sensor.iface, &interface) != 0) return 6;
    if (xensiv_bgt60cutrxx_platform_init(&sensor, &interface, register_list,
        ARRAY_SIZE(register_list), ACTIVE_MODE, false) != 0) return 7;
    if (qualification_set_hpf() != 0) return 10;
#if RADAR_SCOPE_OUTPUT
    if (qualification_scope_output() != 0) return 11;
#endif
    if (stop_capture() != 0) return 8;
    if (xensiv_bgt60cutrxx_set_reg(&sensor.dev, BGT60CUTR13B_REG_AVG_CTRL_SEQ0, 0) != 0) return 8;
    if (xensiv_bgt60cutrxx_set_reg(&sensor.dev, BGT60CUTR13B_REG_FIFO_CTRL, (191u << 16)) != 0) return 8;
    for (uint16_t address = BGT60CUTR13B_REG_CS_IDX0_RX1;
         address <= BGT60CUTR13B_REG_CS_IDX0_RX3; address += 4u) {
        uint32_t value = 0;
        if (xensiv_bgt60cutrxx_get_reg(&sensor.dev, address, &value) != 0 || !(value & 1u)) return 9;
    }
    uint32_t next_capture = cyhal_timer_read(&timer);
    uint32_t slot = 0;
    for (;;) {
        uint8_t command;
        while (cyhal_uart_readable(&uart)) {
            if (cyhal_uart_getc(&uart, &command, 0) == CY_RSLT_SUCCESS) {
                if (command == 0x42) enabled = true;
                if (command == 0x63) enabled = false;
            }
        }
        uint32_t now = cyhal_timer_read(&timer);
        if (!enabled || (int32_t)(now - next_capture) < 0) continue;
        next_capture = now + 100000u;
        ++sequence;
        if (transmitting) { ++dropped; continue; }
        if (capture(packets[slot]) != 0) { ++errors; ++dropped; continue; }
        transmitting = true;
        if (cyhal_uart_write_async(&uart, packets[slot], PACKET_BYTES) != CY_RSLT_SUCCESS) {
            transmitting = false;
            ++errors;
            ++dropped;
        }
        slot ^= 1u;
    }
}
