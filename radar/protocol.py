from dataclasses import dataclass
import struct
import zlib
import numpy as np

MAGIC = b"GRD3"
HEADER = struct.Struct("<4sHHIIIIHHBBHIIII")
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


def encode(frame):
    chirps, samples, receivers = frame.adc.shape
    payload = np.asarray(frame.adc, dtype="<u2").tobytes()
    header = HEADER.pack(MAGIC, 1, HEADER.size, len(payload), frame.sequence,
                         frame.timestamp_us, frame.profile_id, chirps, samples,
                         receivers, 16, frame.flags | (2 if frame.capture_elapsed_us is not None else 0),
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
            valid = (version == 1 and header_bytes == HEADER.size and receivers == 3 and bits == 16
                     and 0 < chirps <= 1024 and 0 < samples <= 2048
                     and length == chirps * samples * receivers * 2 and length <= MAX_PAYLOAD
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
            adc = np.frombuffer(bytes(self.buffer[HEADER.size:packet_bytes - 4]), dtype="<u2").reshape(chirps, samples, receivers)
            del self.buffer[:packet_bytes]
            if self.last_sequence is not None:
                delta = (sequence - self.last_sequence) & 0xffffffff
                if 1 < delta < 0x80000000:
                    self.gaps += delta - 1
                elif delta == 0 or delta >= 0x80000000:
                    self.restarts += 1
            self.last_sequence = sequence
            frames.append(Frame(sequence, timestamp, profile, adc, dropped, errors, flags,
                                reserved0 if flags & 2 else None))
        return frames
