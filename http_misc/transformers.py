import base64
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone

import aiohttp

from http_misc import services, http_utils, retry_policy
from http_misc.cache import TokenCache
from http_misc.services import Transformer


class TokenTransformer(Transformer, ABC):

    @abstractmethod
    async def get_token(self, *args, **kwargs):
        pass

    @abstractmethod
    async def get_token_name(self, *args, **kwargs):
        pass

    async def modify(self, *args, **kwargs):
        headers = kwargs.setdefault('cfg', {}).setdefault('headers', {})
        token = await self.get_token(*args, **kwargs)
        token_name = await self.get_token_name(*args, **kwargs)
        headers['Authorization'] = f'{token_name} {token}'

        return args, kwargs


class SetBasicAuthorization(TokenTransformer):
    """ Указывает Basic token """

    async def get_token_name(self, *args, **kwargs):
        return 'Basic'

    async def get_token(self, *args, **kwargs):
        return base64.b64encode(self.client_id + b':' + self.client_secret).decode('utf-8')

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id.encode('utf-8')
        self.client_secret = client_secret.encode('utf-8')


class SetSystemOAuthToken(TokenTransformer):
    """ Указывает Bearer token учетных записей для автоматизации """

    async def get_token_name(self, *args, **kwargs):
        return 'Bearer'

    def __init__(self, client_id: str, client_secret: str, scope: str,
                 token_url: str, token_cache: TokenCache | None = None, use_utc: bool | None = True):
        self.token_cache = token_cache
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.scope = scope
        self._service = services.HttpService()
        self._policy = retry_policy.AsyncRetryPolicy()
        self.use_utc = use_utc

    def _init_token_request(self):
        form = aiohttp.FormData(quote_fields=True)
        form.add_field('grant_type', 'client_credentials')
        form.add_field('client_id', self.client_id)
        form.add_field('client_secret', self.client_secret)
        form.add_field('scope', self.scope)
        request = {
            'method': 'POST',
            'url': self.token_url,
            'cfg': {
                'data': form
            }
        }
        return request

    def _parse_token_response(self, response: dict):
        access_token = response.get('access_token')
        expires_in = response.get('expires_in')
        if not access_token or not expires_in:
            raise ValueError('Invalid response - access_token or expires_in is none.')

        return access_token, expires_in

    def _now(self):
        return datetime.now(tz=timezone.utc if self.use_utc else None)

    async def _init_token(self) -> str:
        request = self._init_token_request()
        response_data = await http_utils.send_and_validate(self._service, request, policy=self._policy)
        access_token, expires_in = self._parse_token_response(response_data)
        if self.token_cache:
            expires_in = self._now() + timedelta(seconds=expires_in)
            self.token_cache.set_token(self.client_id, access_token, expires_in)
        return access_token

    async def _get_token(self) -> tuple[str | None, datetime | None]:
        if self.token_cache:
            return self.token_cache.get_token(self.client_id)

        return None, None

    async def get_token(self, *args, **kwargs):
        access_token, expires_in = await self._get_token()
        # если токен найден
        if access_token:
            # проверяем срок жизни токена и если он истек получаем новый.
            if self._now() < expires_in:
                return access_token

            # время жизни истекло, инициализируем токен
            return await self._init_token()
        else:
            # если токен не найден, то инициализируем токены
            return await self._init_token()
