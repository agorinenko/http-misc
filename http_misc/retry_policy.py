"""
Политика повторов
"""
import asyncio
import random
import uuid
from abc import ABC
from collections.abc import Callable, Iterable
from time import sleep, time

from http_misc.errors import RetryError, MaxRetryError
from http_misc.logger import get_logger

logger = get_logger('retry_policy')


class BaseRetryPolicy(ABC):
    """
    Базовая политика действий
    """

    def __init__(self, max_retry: int | None = 9,
                 backoff_factor: float | None = 0.3,
                 jitter: float | None = 0.1,
                 retry_on_exceptions: Iterable[type[Exception]] | None = None,
                 ignore_exceptions: Iterable[type[Exception]] | None = None):
        """ Базовая политика действий
        :param max_retry: максимальное количество повторений(без учета основного вызова)
        :param backoff_factor: коэффициент задержки попыток повторных вызовов
        :param jitter: коэффициент "дрожания" повторных вызовов
        """
        if max_retry is None or max_retry < 0:
            raise ValueError('max_retry должен быть больше или равен нулю.')

        if backoff_factor is None or backoff_factor < 0:
            raise ValueError('backoff_factor должен быть больше или равен нулю.')

        if jitter is None or jitter < 0:
            raise ValueError('jitter должен быть больше или равен нулю.')

        self.max_retry = max_retry
        self.backoff_factor = backoff_factor
        self.jitter = jitter

        _retry_on_exceptions: list[type[Exception]] = [RetryError]
        if retry_on_exceptions:
            _retry_on_exceptions.extend(retry_on_exceptions)
        self.retry_on_exceptions = tuple(_retry_on_exceptions)
        self.ignore_exceptions = ignore_exceptions

        self.request_count_manager = RequestCountManager()

    def _on_retry_error(self, current_step: int, request_id: uuid.UUID) -> None:
        if self.max_retry <= 0:
            return None

        if current_step >= self.max_retry:
            raise MaxRetryError(f'Exceeded the maximum number of attempts {self.max_retry}.')

        sleep_seconds = self.backoff_factor * (2 ** (current_step - 1))
        if self.jitter:
            sleep_seconds += random.normalvariate(0, sleep_seconds * self.jitter)
            # sleep_seconds += random.uniform(sleep_seconds * (1 - self.jitter), sleep_seconds * (1 + self.jitter))

        self.request_count_manager.inc(request_id)
        sleep_seconds = max(0.001, sleep_seconds)

        sleep(sleep_seconds)
        return None


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
                    logger.debug('Step %s. Repeat action #%s.', current_step, request_id)
                try:
                    return await action(*args, **kwargs)
                except self.retry_on_exceptions as ex:
                    if self.ignore_exceptions and type(ex) in self.ignore_exceptions:
                        break

                    self._on_retry_error(current_step, request_id)
                except Exception as ex:
                    if self.ignore_exceptions and type(ex) in self.ignore_exceptions:
                        break

                    raise ex

            return None
        finally:
            self.request_count_manager.pop(request_id)


class SyncRetryPolicy(BaseRetryPolicy):
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
                    logger.debug('Step %s. Repeat action #%s.', current_step, request_id)
                try:
                    return action(*args, **kwargs)
                except self.retry_on_exceptions as ex:
                    if self.ignore_exceptions and type(ex) in self.ignore_exceptions:
                        break
                    self._on_retry_error(current_step, request_id)
        finally:
            self.request_count_manager.pop(request_id)


class RequestCountManager:
    def __init__(self, expired_timeout: float = 3600):  # 1h
        self._requests: dict[uuid.UUID, tuple[int, float]] = {}
        self.expired_timeout = expired_timeout

    def get_requests(self):
        return self._requests

    def add(self) -> uuid.UUID:
        """ Инициализация запроса """
        request_id = uuid.uuid4()
        self._requests[request_id] = (0, time())

        self._cleanup_old_requests()

        return request_id

    def exist(self, request_id: uuid.UUID) -> bool:
        """ Проверка наличия запроса """
        if request_id not in self._requests:
            raise KeyError(f'Request {request_id} not in registry.')

        return True

    def pop(self, request_id: uuid.UUID) -> int | None:
        """ Удаление запроса """
        self.exist(request_id)
        result = self._requests.pop(request_id)

        self._cleanup_old_requests()

        if result:
            return result[0]

        return None

    def get(self, request_id: uuid.UUID) -> int:
        """ Получение количества попыток запроса """
        self.exist(request_id)
        result = self._requests[request_id]

        return result[0]

    def inc(self, request_id: uuid.UUID) -> int:
        """ Увеличение количества попыток на 1 """
        request_count = self.get(request_id)
        request_count += 1
        self._requests[request_id] = (request_count, time())

        return request_count

    def _cleanup_old_requests(self):
        """ Очистка запросов старше определенного времени, по умолчанию 1 часа """
        now = time()
        expired_request_ids = [
            rid for rid, (_, ts) in self._requests.items() if now - ts > self.expired_timeout
        ]
        for request_id in expired_request_ids:
            self._requests.pop(request_id, None)
