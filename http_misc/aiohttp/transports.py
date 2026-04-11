from contextlib import asynccontextmanager

from http_misc import http_utils
from http_misc.logger import get_logger
from http_misc.transports import ServiceResponse, BaseTransport

logger = get_logger('aiohttp_transformers')
try:
    import aiohttp
except ImportError as ex:
    logger.info('Ошибка импорта aiohttp.')


class AioHttpTransport(BaseTransport):
    """Транспорт на основе aiohttp"""

    async def close(self, *args, **kwargs):
        if self.client_session:
            await self.client_session.close()

    def __init__(self, *args, client_session: aiohttp.ClientSession | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_session = client_session

    async def request(self, method: str, url: str, **kwargs) -> ServiceResponse:
        if url.lower().startswith('https://') and 'ssl' not in kwargs:
            kwargs['ssl'] = False

        async with self._use_client_session() as session:
            async with session.request(method, url, **kwargs) as response:
                response_data = await self._get_response_content(response)
                return ServiceResponse(status=response.status, response_data=response_data, raw_response=response)

    @asynccontextmanager
    async def _use_client_session(self):
        if self.client_session is not None:
            yield self.client_session
        else:
            async with aiohttp.ClientSession(json_serialize=http_utils.json_dumps) as session:
                yield session

    @classmethod
    async def _get_response_content(cls, response):
        try:
            return await response.json()
        except aiohttp.ContentTypeError:
            return await response.text()
