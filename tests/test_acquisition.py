import unittest
from unittest.mock import patch
from radar.acquisition import Source
from radar.config import Config
from radar.protocol import encode
from radar.synthetic import generate


class FakeSerial:
    def __init__(self, *arguments, **keywords):
        self.data = bytearray()
        self.commands = []
        self.closed = False

    @property
    def in_waiting(self):
        return len(self.data)

    def read(self, count):
        count = min(count, 127)
        result = bytes(self.data[:count])
        del self.data[:count]
        return result

    def write(self, data):
        self.commands.append(data)

    def reset_input_buffer(self):
        self.data.clear()

    def flush(self):
        pass

    def close(self):
        self.closed = True


class AcquisitionTests(unittest.TestCase):
    @patch("radar.acquisition.serial.Serial", FakeSerial)
    def test_start_read_stop_with_fragmented_transport(self):
        config = Config()
        source = Source(config, port="FAKE")
        self.assertEqual(source.serial.commands, [b"B"])
        frame = generate(config, seed=2)
        source.serial.data.extend(encode(frame))
        received = None
        for iteration in range(100):
            received = source.read()
            if received is not None:
                break
        self.assertIsNotNone(received)
        self.assertEqual(received.sequence, frame.sequence)
        source.close()
        self.assertEqual(source.serial.commands, [b"B", b"c"])
        self.assertTrue(source.serial.closed)

    @patch("radar.acquisition.serial.Serial", FakeSerial)
    def test_silent_device_returns_control(self):
        source = Source(Config(), port="FAKE")
        self.assertIsNone(source.read())
        source.close()

    @patch('radar.acquisition.time.sleep')
    @patch('radar.acquisition.serial.Serial', FakeSerial)
    def test_synchronized_start_stops_then_starts_and_closes(self, sleep):
        source = Source(Config(), port='FAKE', synchronize=True)
        self.assertEqual(source.serial.commands, [b'c', b'B'])
        sleep.assert_called_once_with(.5)
        source.close()
        self.assertTrue(source.serial.closed)

    def test_failed_start_closes_port(self):
        serial = FakeSerial()
        with patch('radar.acquisition.serial.Serial', return_value=serial), \
                patch.object(serial, 'write', side_effect=OSError('disconnected')):
            with self.assertRaises(OSError):
                Source(Config(), port='FAKE', synchronize=True)
        self.assertTrue(serial.closed)


if __name__ == "__main__":
    unittest.main()
