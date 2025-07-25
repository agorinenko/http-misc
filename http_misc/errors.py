class RetryError(Exception):
    """
    Ошибка, которая вызывает повторный вызов запроса
    """


class MaxRetryError(Exception):
    """
    Превышено максимальное число повторов
    """


class InteractionError(Exception):
    """ Ошибки взаимодействия с внешним сервисом """

    def __init__(self, message, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)

        self.status_code = status_code
        self.response = response
