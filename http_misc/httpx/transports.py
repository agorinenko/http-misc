import ssl
from contextlib import asynccontextmanager
from json import JSONDecodeError

from http_misc.logger import get_logger
from http_misc.transports import BaseTransport, ServiceResponse

logger = get_logger('httpx_transformers')
try:
    import httpx
except ImportError as ex:
    logger.info('Ошибка импорта httpx.')


class HttpxTransport(BaseTransport):
    """ Транспорт на основе httpx """

    async def close(self, *args, **kwargs):
        if self.client_session:
            await self.client_session.aclose()

    def __init__(self, *args, client_session: httpx.AsyncClient | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_session = client_session

    async def request(self, method: str, url: str, **kwargs) -> ServiceResponse:
        verify = True
        if url.lower().startswith('https://'):
            verify = kwargs.pop('verify', False)

        async with self._use_client_session(verify=verify) as session:
            response = await session.request(method, url, **kwargs)
            response_data = await self._get_response_content(response)
            return ServiceResponse(status=response.status_code, response_data=response_data, raw_response=response)

    @asynccontextmanager
    async def _use_client_session(self, verify: ssl.SSLContext | str | bool = True):
        if self.client_session is not None:
            yield self.client_session
        else:
            async with httpx.AsyncClient(verify=verify) as session:
                yield session

    @classmethod
    async def _get_response_content(cls, response):
        try:
            return response.json()
        except JSONDecodeError:
            return response.text
