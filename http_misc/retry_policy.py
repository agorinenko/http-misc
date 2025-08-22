import asyncio
import random
import uuid
from abc import ABC
from collections.abc import Callable
from time import sleep

from http_misc.errors import RetryError, MaxRetryError
from http_misc.logger import get_logger

logger = get_logger('retry_policy')


class BaseRetryPolicy(ABC):
    """
    Базовая политика действий
    """

    def __init__(self, max_retry: int | None = 9, backoff_factor: float | None = 0.3, jitter: float | None = 0.1):
        """ Базовая политика действий
        :param max_retry: максимальное количество повторений(без учета основного вызова)
        :param backoff_factor: коэффициент задержки попыток повторных вызовов
        :param jitter: коэффициент "дрожания" повторных вызовов
        """
        self.max_retry = max_retry
        self.backoff_factor = backoff_factor
        self.jitter = jitter

        self.request_count_manager = RequestCountManager()

    def _on_retry_error(self, current_step: int, request_id: uuid.UUID) -> float:
        if current_step >= self.max_retry:
            raise MaxRetryError(f'Exceeded the maximum number of attempts {self.max_retry}.')

        sleep_seconds = self.backoff_factor * (2 ** (current_step - 1))
        sleep_seconds += random.normalvariate(0, sleep_seconds * self.jitter)
        self.request_count_manager.inc(request_id)
        return sleep_seconds


class AsyncRetryPolicy(BaseRetryPolicy):
    """
    Политика повторов асинхронных действий
    """

    async def apply(self, action: Callable, *args, **kwargs):
        """ Выполнение асинхронного действия """
        request_id = self.request_count_manager.add()
        try:
            while True:
                current_step = self.request_count_manager.get(request_id)
                if current_step > 0:
                    logger.debug('Step %s. Repeat action #%s.', request_id)
                try:
                    return await action(*args, **kwargs)
                except RetryError:
                    sleep_seconds = self._on_retry_error(current_step, request_id)
                    await asyncio.sleep(sleep_seconds)
        finally:
            self.request_count_manager.pop(request_id)


class RetryPolicy(BaseRetryPolicy):
    """
    Политика повторов синхронных действий
    """

    def apply(self, action: Callable, *args, **kwargs):
        """ Выполнение синхронного действия """
        request_id = self.request_count_manager.add()
        try:
            while True:
                current_step = self.request_count_manager.get(request_id)
                if current_step > 0:
                    logger.debug('Step %s. Repeat action #%s.', request_id)
                try:
                    return action(*args, **kwargs)
                except RetryError:
                    sleep_seconds = self._on_retry_error(current_step, request_id)
                    sleep(sleep_seconds)
        finally:
            self.request_count_manager.pop(request_id)


class RequestCountManager:
    def __init__(self):
        self._requests: dict[uuid.UUID, int] = {}

    def get_requests(self):
        return self._requests

    def add(self) -> uuid.UUID:
        """ Инициализация запроса """
        request_id = uuid.uuid4()
        self._requests[request_id] = 0
        return request_id

    def exist(self, request_id: uuid.UUID) -> bool:
        """ Проверка наличия запроса """
        if request_id not in self._requests:
            raise KeyError(f'Request {request_id} not in registry.')

        return True

    def pop(self, request_id: uuid.UUID) -> int | None:
        """ Удаление запроса """
        self.exist(request_id)
        return self._requests.pop(request_id)

    def get(self, request_id: uuid.UUID) -> int:
        """ Получение количества попыток запроса """
        self.exist(request_id)
        return self._requests[request_id]

    def inc(self, request_id: uuid.UUID) -> int:
        """ Увеличение количества попыток на 1 """
        self.exist(request_id)
        self._requests[request_id] += 1

        return self._requests[request_id]
