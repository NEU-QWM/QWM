import logging


class JavaLoggingHandler(logging.Handler):
    def __init__(self, service):
        super(JavaLoggingHandler, self).__init__()
        self.log = service

    def emit(self, record):
        self.log(record.levelname, self.format(record))
