import time
import serial
from .protocol import Parser
from .storage import replay
from .synthetic import generate


class Source:
    def __init__(self, config, port=None, recording=None):
        self.config = config
        self.parser = Parser()
        self.serial = None
        self.recording = iter(replay(recording, self.parser)) if recording else None
        self.sequence = 0
        self.pending = []
        self.transport_recorder = None
        if port:
            self.serial = serial.Serial(port, 2000000, timeout=0.1, write_timeout=1)
            self.serial.reset_input_buffer()
            self.serial.write(b"B")

    def read(self):
        if self.serial:
            while not self.pending:
                data = self.serial.read(max(1, min(self.serial.in_waiting, 65536)))
                self.pending.extend(self.parser.feed(data))
                if data and self.transport_recorder is not None:
                    self.transport_recorder.write_transport(data,self.parser)
                if not self.pending:
                    return None
            return self.pending.pop(0)
        if self.recording is not None:
            return next(self.recording)
        self.sequence += 1
        return generate(self.config, self.sequence, seed=self.sequence)

    def close(self):
        if self.serial:
            try:
                self.serial.write(b"c")
                self.serial.flush()
            finally:
                self.serial.close()


def paced_frames(source, stop=None):
    deadline = time.monotonic()
    while stop is None or not stop.is_set():
        try:
            frame = source.read()
        except StopIteration:
            return
        if frame is None:
            continue
        yield frame
        if not source.serial:
            deadline += source.config.frame_interval_s
            delay = max(0, deadline - time.monotonic())
            if stop:
                stop.wait(delay)
            else:
                time.sleep(delay)
