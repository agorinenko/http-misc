import logging

_logger = logging.getLogger(__name__)


def get_logger(name: str | None = None) -> logging.Logger:
    """ Получить logger """
    if name:
        return _logger.getChild(name)

    return _logger
