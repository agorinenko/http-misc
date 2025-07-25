import asyncio
import logging
import random
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

from aiohttp import ContentTypeError, ClientSession

from http_misc import http_utils, errors

DEFAULT_RETRY_ON_STATUSES = frozenset([413, 429, 503, 504])
logger = logging.getLogger(__name__)


@dataclass
class ServiceResponse:
    """ Ответ сервиса """
    status: int
    response_data: any = None
    raw_response: any = None


class OnErrorResult(Enum):
    """
    SILENT - проигнорировать ошибку
    THROW - возбудить ошибку
    REFRESH - при ошибке выполнить действие повторно
    """
    SILENT = 1
    THROW = 2
    REFRESH = 3


@dataclass
class RetryPolicy:
    max_retry: int | None = 10
    retry_on_statuses: set[int] | None = DEFAULT_RETRY_ON_STATUSES
    backoff_factor: int | None = 0.3
    jitter: int | None = 0.1


class Transformer(ABC):
    @abstractmethod
    async def modify(self, request_id, *args, **kwargs):
        """ Изменение параметров запроса или ответа """
        return args, kwargs


class BaseService(ABC):
    """
    Abstract service
    """

    def __init__(self, retry_policy: RetryPolicy | None = None,
                 request_preproc: list[Transformer] | None = None,
                 response_preproc: list[Transformer] | None = None):
        """ Сервис """
        self.retry_policy = retry_policy or RetryPolicy()
        self.request_preproc = request_preproc
        self.response_preproc = response_preproc
        self._request_count_manager = _RequestCountManager()

    @abstractmethod
    async def _send(self, request_id: uuid.UUID, *args, **kwargs) -> ServiceResponse:
        """
        Abstract _send
        """
        raise NotImplementedError('Not implemented _send method')

    async def send_request(self, *args, **kwargs):
        """  Вызов внешнего сервиса """
        request_id = self._request_count_manager.add()
        try:
            return await self._send_request(request_id, *args, **kwargs)
        finally:
            # обнуляем current_step для запроса, он выполнен успешно
            self._request_count_manager.pop(request_id)

    def get_current_step(self, request_id: uuid.UUID):
        """ Получение количества попыток запроса """
        return self._request_count_manager.get(request_id)

    async def _send_request(self, request_id: uuid.UUID, *args, **kwargs) -> ServiceResponse:
        """
        Вызов внешнего сервиса
        """
        try:
            args, kwargs = await self._before_send(request_id, *args, **kwargs)
            logger.debug('Send request %s: %s; %s', self.get_current_step(request_id), args, kwargs)
            service_response = await self._send(request_id, *args, **kwargs)
            service_response = await self._transform_response(request_id, service_response)
            logger.debug('Response %s: %s, %s', self.get_current_step(request_id),
                         service_response.status, service_response.response_data)

            if self.retry_policy.retry_on_statuses and service_response.status in self.retry_policy.retry_on_statuses:
                raise errors.RetryError()

            return service_response
        except Exception as ex:
            if isinstance(ex, errors.RetryError):
                on_error_result = OnErrorResult.REFRESH
            else:
                on_error_result = await self._on_error(ex, *args, **kwargs)

            if on_error_result == OnErrorResult.THROW:
                logger.exception(ex)
                raise ex

            if on_error_result == OnErrorResult.SILENT:
                logger.exception(ex)
                return ServiceResponse(status=-1)

            if on_error_result == OnErrorResult.REFRESH:
                return await self._resend_request(request_id, ex, *args, **kwargs)

            raise NotImplementedError(f'on_error_result "{on_error_result}" not implemented') from ex

    async def _transform_response(self, request_id: uuid.UUID, response: ServiceResponse) -> ServiceResponse:
        """ Преобразование ответа для возврата пользователю """
        if self.response_preproc:
            for response_preproc in self.response_preproc:
                response = await response_preproc.modify(request_id, response)
        return response

    async def _before_send(self, request_id: uuid.UUID, *args, **kwargs):
        """ Действие перед вызовом """
        if self.request_preproc:
            for request_preproc in self.request_preproc:
                args, kwargs = await request_preproc.modify(request_id, *args, **kwargs)
        return args, kwargs

    async def _on_error(self, ex: Exception, *args, **kwargs) -> OnErrorResult:  # pylint: disable=unused-argument
        """
        Действие на возникновение ошибки.
        SILENT - продолжить работу без возникновения ошибки
        THROW - выкинуть исключение дальше
        REFRESH - сделать повторный вызов сервиса
        """
        return OnErrorResult.THROW

    async def _resend_request(self, request_id: uuid.UUID, ex: Exception, *args, **kwargs):
        """ Повторная отправка запроса """
        self._request_count_manager.inc(request_id)

        current_step = self.get_current_step(request_id)
        logger.debug('Repeat request #%s.', current_step)

        if current_step >= self.retry_policy.max_retry:
            raise errors.MaxRetryError(f'Exceeded the maximum number of attempts {self.retry_policy.max_retry}') from ex

        sleep_seconds = self.retry_policy.backoff_factor * (2 ** (current_step - 1))
        sleep_seconds += random.normalvariate(0, sleep_seconds * self.retry_policy.jitter)
        await asyncio.sleep(sleep_seconds)

        return await self._send_request(request_id, *args, **kwargs)


class HttpService(BaseService):
    """
    Вызов по протоколу http
    """

    def __init__(self, *args, client_session: ClientSession | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_session = client_session

    async def _send(self, request_id: uuid.UUID, *args, **kwargs) -> ServiceResponse:
        method = kwargs.get('method', 'get')
        url = kwargs.get('url', None)
        if url is None:
            raise ValueError('Url is none')
        url = str(url)

        cfg = kwargs.get('cfg', {})
        if not isinstance(cfg, dict):
            raise ValueError('Invalid cfg type. Must be dict.')

        if url.lower().startswith('https://') and 'ssl' not in cfg:
            cfg['ssl'] = False

        async with self._use_client_session() as session:
            async with session.request(method, url, **cfg) as response:
                response_data = await _get_response_content(response)
                return ServiceResponse(status=response.status, response_data=response_data, raw_response=response)

    @asynccontextmanager
    async def _use_client_session(self):
        if self.client_session is not None:
            yield self.client_session
        else:
            async with ClientSession(json_serialize=http_utils.json_dumps) as session:
                yield session


class _RequestCountManager:
    def __init__(self):
        self._requests: dict[uuid.UUID, int] = {}

    def add(self) -> uuid.UUID:
        """ Инициализация запроса """
        request_id = uuid.uuid4()
        self._requests[request_id] = 0
        return request_id

    def exist(self, request_id: uuid.UUID) -> bool:
        """ Проверка наличия запроса """
        if request_id not in self._requests:
            raise KeyError(f'Request {str(request_id)} not in registry')

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


async def _get_response_content(response):
    try:
        return await response.json()
    except ContentTypeError:
        return await response.text()
