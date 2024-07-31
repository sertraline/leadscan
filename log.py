import logging
from logging.handlers import RotatingFileHandler


class DebugLogging:

    def __init__(self, enabled):
        self.logger = logging.getLogger("italiabot")
        _formatter = logging.Formatter(
            (
                "[%(asctime)s] [%(module)8s: %(funcName)-20s()] "
                "%(lineno)4s    %(message)s"
            )
        )
        _stream_handler = logging.StreamHandler()
        _stream_handler.setLevel(logging.DEBUG)
        _stream_handler.setFormatter(_formatter)
        _file_handler = RotatingFileHandler(
            filename="debug.log",
            mode="a",
            maxBytes=10 * 1024 * 1024,
            backupCount=0,
            encoding="utf-8",
            delay=False,
        )
        _file_handler.setFormatter(_formatter)
        _file_handler.setLevel(logging.INFO)
        if enabled:
            _file_handler.setLevel(logging.DEBUG)
        else:
            _file_handler.setLevel(logging.INFO)
        self.logger.addHandler(_file_handler)
        self.logger.addHandler(_stream_handler)
        if enabled:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)
