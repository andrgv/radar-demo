from dataclasses import dataclass
import struct
import zlib
import numpy as np

MAGIC = b"GRD3"
HEADER = struct.Struct("<4sHHIIIIHHBBHIIII")
EDGE_TIMING = struct.Struct("<II64I")  # version 2: count, overflow, 64 offsets (us)
EDGE_TIMING_FULL = struct.Struct("<II128I")  # version 3: same layout, 128 offsets
EDGE_TIMING_AVG16 = struct.Struct("<II320I")  # version 4: AVG16 test, 320 offsets
MAX_PAYLOAD = 1024 * 1024


@dataclass
class Frame:
    sequence: int
    timestamp_us: int
    profile_id: int
    adc: np.ndarray
    dropped: int = 0
    errors: int = 0
    flags: int = 1
    capture_elapsed_us: int | None = None
    edge_times_us: tuple[int, ...] | None = None
    edge_count: int | None = None
    edge_overflow: bool = False
    edge_capacity: int | None = None


def wire_size(frame):
    """Encoded packet size, including the optional edge-timing extension."""
    capacity = (frame.edge_capacity or 64) if frame.edge_times_us is not None else 0
    return HEADER.size+frame.adc.size*2+(8+4*capacity if capacity else 0)+4


def encode(frame):
    chirps, samples, receivers = frame.adc.shape
    payload = np.asarray(frame.adc, dtype="<u2").tobytes()
    version = 2 if frame.edge_times_us is not None else 1
    if version == 2:
        times = tuple(frame.edge_times_us)
        capacity = frame.edge_capacity or 64
        if capacity not in (64, 128, 320):
            raise ValueError("Unsupported edge timing capacity")
        if capacity == 128:
            version = 3
        elif capacity == 320:
            version = 4
        count = len(times) if frame.edge_count is None else frame.edge_count
        if len(times) > capacity or count < len(times) or (count > capacity) != frame.edge_overflow:
            raise ValueError("Invalid edge timing count/overflow")
        layout = EDGE_TIMING_AVG16 if version == 4 else EDGE_TIMING_FULL if version == 3 else EDGE_TIMING
        payload += layout.pack(count, int(frame.edge_overflow), *(times + (0,) * (capacity - len(times))))
    header = HEADER.pack(MAGIC, version, HEADER.size, len(payload), frame.sequence,
                         frame.timestamp_us, frame.profile_id, chirps, samples,
                         receivers, 16, frame.flags | (2 if frame.capture_elapsed_us is not None else 0) | (8 if version in (2, 3, 4) else 0),
                         frame.dropped, frame.errors, frame.capture_elapsed_us or 0, 0)
    header = header[:-4] + struct.pack("<I", zlib.crc32(header[:-4]))
    packet = header + payload
    return packet + struct.pack("<I", zlib.crc32(packet))


class Parser:
    def __init__(self):
        self.buffer = bytearray()
        self.bad_headers = 0
        self.bad_crc = 0
        self.gaps = 0
        self.restarts = 0
        self.last_sequence = None
        self.discarded_bytes = 0

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while len(self.buffer) >= HEADER.size:
            position = self.buffer.find(MAGIC)
            if position < 0:
                self.discarded_bytes += len(self.buffer) - 3
                del self.buffer[:-3]
                break
            if position:
                self.discarded_bytes += position
                del self.buffer[:position]
            if len(self.buffer) < HEADER.size:
                break
            fields = HEADER.unpack_from(self.buffer)
            (_, version, header_bytes, length, sequence, timestamp, profile,
             chirps, samples, receivers, bits, flags, dropped, errors,
             reserved0, header_crc) = fields
            adc_bytes = chirps * samples * receivers * 2
            timing_layout = (EDGE_TIMING if version == 2 else EDGE_TIMING_FULL if version == 3
                             else EDGE_TIMING_AVG16 if version == 4 else None)
            valid = (version in (1, 2, 3, 4) and header_bytes == HEADER.size and receivers == 3 and bits == 16
                     and 0 < chirps <= 1024 and 0 < samples <= 2048
                     and length == adc_bytes + (timing_layout.size if timing_layout else 0) and length <= MAX_PAYLOAD
                     and bool(flags & 8) == (timing_layout is not None)
                     and zlib.crc32(self.buffer[:HEADER.size - 4]) == header_crc)
            if not valid:
                self.bad_headers += 1
                self.discarded_bytes += 1
                del self.buffer[0]
                continue
            packet_bytes = HEADER.size + length + 4
            if len(self.buffer) < packet_bytes:
                break
            expected_crc = struct.unpack_from("<I", self.buffer, packet_bytes - 4)[0]
            if zlib.crc32(self.buffer[:packet_bytes - 4]) != expected_crc:
                self.bad_crc += 1
                self.discarded_bytes += 1
                del self.buffer[0]
                continue
            adc = np.frombuffer(bytes(self.buffer[HEADER.size:HEADER.size + adc_bytes]), dtype="<u2").reshape(chirps, samples, receivers)
            edge_times = None
            edge_count = None
            edge_overflow = False
            edge_capacity = None
            if timing_layout is not None:
                edge_capacity = 320 if version == 4 else 128 if version == 3 else 64
                values = timing_layout.unpack_from(self.buffer, HEADER.size + adc_bytes)
                edge_count, overflow = values[:2]
                if overflow != int(edge_count > edge_capacity):
                    self.bad_headers += 1
                    self.discarded_bytes += 1
                    del self.buffer[0]
                    continue
                edge_times = tuple(values[2:2 + min(edge_count, edge_capacity)])
                edge_overflow = bool(overflow)
            del self.buffer[:packet_bytes]
            if self.last_sequence is not None:
                delta = (sequence - self.last_sequence) & 0xffffffff
                if 1 < delta < 0x80000000:
                    self.gaps += delta - 1
                elif delta == 0 or delta >= 0x80000000:
                    self.restarts += 1
            self.last_sequence = sequence
            frames.append(Frame(sequence, timestamp, profile, adc, dropped, errors, flags,
                                reserved0 if flags & 2 else None, edge_times, edge_count,
                                edge_overflow, edge_capacity))
        return frames
