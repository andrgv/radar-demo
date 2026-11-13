"""Keep expected HTTP/2 caller cancellations out of server-error tracebacks."""
import logging

from grpclib.exceptions import StreamTerminatedError


class CallerCancellationFilter(logging.Filter):
    def filter(self, record):
        error = record.exc_info[1] if record.exc_info else None
        if (record.name == 'grpclib.server'
                and record.getMessage() == 'Server error'
                and isinstance(error, StreamTerminatedError)
                and str(error) == 'Stream reset by remote party, error_code: 8'):
            record.levelno = logging.INFO
            record.levelname = 'INFO'
            record.msg = 'RPC caller cancelled the stream (HTTP/2 CANCEL)'
            record.args = ()
            record.exc_info = None
            record.exc_text = None
        return True


def configure_rpc_logging():
    logger = logging.getLogger('grpclib.server')
    if not any(isinstance(f, CallerCancellationFilter) for f in logger.filters):
        logger.addFilter(CallerCancellationFilter())
