import abc
import pprint

from http_misc import errors, transformers, transports
from http_misc.logger import get_logger

DEFAULT_RETRY_ON_STATUSES = frozenset([408, 429, 502, 503, 504])

logger = get_logger('services')


class BaseService(abc.ABC):
    """
    Базовый сервис
    """

    def __init__(self, retry_on_statuses: set[int] | None = DEFAULT_RETRY_ON_STATUSES,
                 request_preproc: list[transformers.Transformer] | None = None,
                 response_preproc: list[transformers.Transformer] | None = None,
                 transport: transports.BaseTransport | None = None):
        """ Сервис """
        self.retry_on_statuses = retry_on_statuses
        self.request_preproc = request_preproc
        self.response_preproc = response_preproc
        self.transport = transport

        if not self.transport:
            from http_misc.aiohttp.transports import AioHttpTransport
            self.transport = AioHttpTransport()

    async def _send(self, **kwargs) -> transports.ServiceResponse:
        raise NotImplementedError('_send')

    async def send_request(self, *args, **kwargs) -> transports.ServiceResponse:
        """
        Вызов внешнего сервиса
        """
        try:
            args, kwargs = await self._before_send(*args, **kwargs)
            logger.debug('Send request %s; %s', args, kwargs)
            service_response = await self._send(**kwargs)
            service_response = await self._transform_response(service_response)
            logger.debug('Response: %s, %s', service_response.status, service_response.response_data)

            if self.retry_on_statuses and service_response.status in self.retry_on_statuses:
                raise errors.RetryError()

            return service_response
        except Exception as ex:  # pylint: disable=broad-except
            if isinstance(ex, errors.RetryError):
                raise ex

            return await self._on_error(ex, *args, **kwargs)

    async def _transform_response(self, response: transports.ServiceResponse) -> transports.ServiceResponse:
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

    async def _on_error(self, ex: Exception, *args, **kwargs) -> transports.ServiceResponse:
        """
        Действие на возникновение ошибки.
        """
        logger.error('Error.\nargs: %s\nkwargs: %s', pprint.pformat(args), pprint.pformat(kwargs))
        logger.exception(ex)

        raise ex


class HttpService(BaseService):
    """
    Вызов сервиса по протоколу http. Реализация жизненного цикла запроса
    """

    async def _send(self, **kwargs) -> transports.ServiceResponse:
        method = kwargs.get('method', 'get')
        url = kwargs.get('url', None)
        if url is None:
            raise ValueError('Url is none')
        url = str(url)

        cfg = kwargs.get('cfg', {})
        if not isinstance(cfg, dict):
            raise ValueError('Invalid cfg type. Must be dict.')

        return await self.transport.request(method, url, **cfg)
