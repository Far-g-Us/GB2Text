import logging


class GBLogger:
    """Конфигурируемый логгер для отладки"""

    def __init__(self, level=logging.INFO):
        self.logger = logging.getLogger("GBTextExtractor")
        self.logger.setLevel(level)

        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)