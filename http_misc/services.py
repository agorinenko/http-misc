import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass

from aiohttp import ContentTypeError, ClientSession

from http_misc import http_utils, errors
from http_misc.logger import get_logger

DEFAULT_RETRY_ON_STATUSES = frozenset([413, 429, 503, 504])
logger = get_logger('services')


@dataclass
class ServiceResponse:
    """ Ответ сервиса """
    status: int
    response_data: any = None
    raw_response: any = None


class Transformer(ABC):
    @abstractmethod
    async def modify(self, *args, **kwargs):
        """ Изменение параметров запроса или ответа """
        return args, kwargs


class BaseService(ABC):
    """
    Abstract service
    """

    def __init__(self, retry_on_statuses: set[int] | None = DEFAULT_RETRY_ON_STATUSES,
                 request_preproc: list[Transformer] | None = None,
                 response_preproc: list[Transformer] | None = None):
        """ Сервис """
        self.retry_on_statuses = retry_on_statuses
        self.request_preproc = request_preproc
        self.response_preproc = response_preproc

    @abstractmethod
    async def _send(self, *args, **kwargs) -> ServiceResponse:
        """
        Abstract _send
        """
        raise NotImplementedError('Not implemented _send method')

    async def send_request(self, *args, **kwargs) -> ServiceResponse:
        """
        Вызов внешнего сервиса
        """
        try:
            args, kwargs = await self._before_send(*args, **kwargs)
            logger.debug('Send request %s; %s', args, kwargs)
            service_response = await self._send(*args, **kwargs)
            service_response = await self._transform_response(service_response)
            logger.debug('Response: %s, %s', service_response.status, service_response.response_data)

            if self.retry_on_statuses and service_response.status in self.retry_on_statuses:
                raise errors.RetryError()

            return service_response
        except Exception as ex:
            if isinstance(ex, errors.RetryError):
                raise ex
            else:
                return await self._on_error(ex, *args, **kwargs)

    async def _transform_response(self, response: ServiceResponse) -> ServiceResponse:
        """ Преобразование ответа для возврата пользователю """
        if self.response_preproc:
            for response_preproc in self.response_preproc:
                response = await response_preproc.modify(response)
        return response

    async def _before_send(self, *args, **kwargs):
        """ Действие перед вызовом """
        if self.request_preproc:
            for request_preproc in self.request_preproc:
                args, kwargs = await request_preproc.modify(*args, **kwargs)
        return args, kwargs

    async def _on_error(self, ex: Exception, *args, **kwargs) -> ServiceResponse:
        """
        Действие на возникновение ошибки.
        """
        logger.exception(ex)
        raise ex


class HttpService(BaseService):
    """
    Вызов сервиса по протоколу http
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


async def _get_response_content(response):
    try:
        return await response.json()
    except ContentTypeError:
        return await response.text()
