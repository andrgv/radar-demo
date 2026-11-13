import logging
import unittest

from grpclib.exceptions import StreamTerminatedError
from viam_module.rpc_logging import CallerCancellationFilter


class RpcLoggingTests(unittest.TestCase):
    def record(self, error, message='Server error'):
        return logging.LogRecord('grpclib.server', logging.ERROR, '', 1,
                                 message, (), (type(error), error, None))

    def test_expected_cancel_is_informational_without_traceback(self):
        record = self.record(StreamTerminatedError(
            'Stream reset by remote party, error_code: 8'))
        self.assertTrue(CallerCancellationFilter().filter(record))
        self.assertEqual(record.levelno, logging.INFO)
        self.assertIsNone(record.exc_info)

    def test_other_errors_and_failed_cancellation_remain_visible(self):
        for error, message in [
            (StreamTerminatedError('Stream reset by remote party, error_code: 2'), 'Server error'),
            (RuntimeError('Radar disconnected'), 'Server error'),
            (StreamTerminatedError('Stream reset by remote party, error_code: 8'),
             'Failed to handle cancellation'),
        ]:
            record = self.record(error, message)
            self.assertTrue(CallerCancellationFilter().filter(record))
            self.assertEqual(record.levelno, logging.ERROR)
            self.assertIsNotNone(record.exc_info)
