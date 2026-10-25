"""Generate an isolated HPF/timing qualification source; preserve firmware/main.c."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from radar.config import Config
from radar.recording_audit import read_register_profile


HPF_CODE=r'''
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
'''


def prepare(root=ROOT):
    source=(root/'firmware/main.c').read_text(encoding='utf-8')
    digest=hashlib.sha256((root/'firmware/main.c').read_bytes()).hexdigest()
    modified=source
    replacements={
        '#include "vendor/presence_detection_tracking.h"':'#include "../../firmware/vendor/presence_detection_tracking.h"',
        '#define PROFILE_ID 0x33525801u':'#define PROFILE_ID (RADAR_SCOPE_OUTPUT ? 0x33515301u : ((RADAR_HPF_KHZ == 100) ? 0x33514801u : 0x33514802u))',
        'static uint32_t crc32(const uint8_t *bytes, size_t length)':HPF_CODE+'\nstatic uint32_t crc32(const uint8_t *bytes, size_t length)',
        'ARRAY_SIZE(register_list), ACTIVE_MODE, false) != 0) return 7;':
            'ARRAY_SIZE(register_list), ACTIVE_MODE, false) != 0) return 7;\n    if (qualification_set_hpf() != 0) return 10;\n#if RADAR_SCOPE_OUTPUT\n    if (qualification_scope_output() != 0) return 11;\n#endif',
        'packet[7] = RECEIVERS | (16u << 8) | (1u << 16);':
            'packet[7] = RECEIVERS | (16u << 8) | ((3u | ((RADAR_HPF_KHZ == 100) ? 4u : 0u)) << 16);',
        'packet[10] = 0;':'packet[10] = cyhal_timer_read(&timer) - start; /* acquisition path elapsed, NOT chirp spacing */'}
    for old,new in replacements.items():
        if modified.count(old)!=1:
            raise ValueError(f'Baseline changed: expected exactly one occurrence of {old!r}')
        modified=modified.replace(old,new)
    # Preserve a reviewable exact baseline outside default source discovery.
    destination=root/'experiments/qualification'
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'main.c').write_text(f'/* Generated from firmware/main.c SHA256 {digest}. Do not edit; rerun tools/prepare_qualification.py. */\n'+modified,encoding='utf-8')
    config=Config.load(root/'configs/range-vendor-matrix-experimental.json')
    from dataclasses import replace
    for hpf,profile in [(100,0x33514801),(350,0x33514802)]:
        replace(config,profile_id=profile,calibration_id=f'qualification-hpf1-{hpf}kHz; timing-and-angles-unverified',
            chirp_timing_verified=False,carrier_frequency_verified=False).save(root/f'configs/qualification-hpf{hpf}.json')
    replace(config,profile_id=0x33515301,calibration_id='scope-CHIRP_ACTIVE-on-DIO4; HPF350; timing-unverified',
        chirp_timing_verified=False,carrier_frequency_verified=False).save(root/'configs/qualification-scope.json')
    registers,_=read_register_profile(root/'firmware/vendor/presence_detection_tracking.h')
    changes=[]
    for address in [0x1010,0x1014,0x1018]:
        changes.append(dict(address=hex(address),hpf350=hex(registers[address]),hpf100=hex(registers[address]&~0x300),changed_mask='0x00000300'))
    report=dict(baseline_sha256=digest,source=str(destination/'main.c'),register_differences=changes,
        unchanged='Same downloaded register list, sequencer instruction bytes, AVG_CTRL_SEQ0 override, FIFO threshold/drain logic, chirp/sample counts, 100 ms frame scheduling and serial baud.',
        common_instrumentation='Read back all three modified RX registers before streaming. Use header flag bit1 plus word10 for acquisition-path elapsed microseconds; not chirp spacing. Bit2 identifies 100 kHz. Distinct profile IDs prevent accidental host mixing.',
        hpf_mask=0x300)
    (destination/'manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    print(json.dumps(prepare(),indent=2))
