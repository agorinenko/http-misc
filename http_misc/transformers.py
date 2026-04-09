import base64
from abc import ABC, abstractmethod

import aiohttp

from http_misc import services, http_utils, retry_policy, cache
from http_misc.services import Transformer


class TokenTransformer(Transformer, ABC):
    def __init__(self, force_token_update: bool | None = False):
        self.force_token_update = force_token_update

    @abstractmethod
    async def get_token(self, *args, **kwargs):
        """ Получение токена """
        raise NotImplementedError('get_token')

    @property
    @abstractmethod
    def token_name(self):
        """ Наименование токена """
        raise NotImplementedError('token_name')

    async def modify(self, *args, **kwargs):
        """ Применение токена в заголовке Authorization """
        headers = kwargs.setdefault('cfg', {}).setdefault('headers', {})
        if not self.force_token_update and 'Authorization' in headers and headers['Authorization']:
            return args, kwargs
        token = await self.get_token(*args, **kwargs)
        headers['Authorization'] = f'{self.token_name} {token}'

        return args, kwargs


class SetBasicAuthorization(TokenTransformer):
    """ Указывает Basic token """

    @property
    def token_name(self):
        return 'Basic'

    async def get_token(self, *args, **kwargs):
        return base64.b64encode(self.client_id + b':' + self.client_secret).decode('utf-8')

    def __init__(self, client_id: str, client_secret: str, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.client_id = client_id.encode('utf-8')
        self.client_secret = client_secret.encode('utf-8')


class OAuthTokenTransformer(TokenTransformer, ABC):
    """ Базовый класс, отвечающий за получение и обновление токена у OAuth провайдера """

    @property
    def token_name(self):
        return 'Bearer'

    @property
    @abstractmethod
    def grant_type(self):
        raise NotImplementedError('grant_type')

    @property
    def extended_token_request(self) -> dict:
        return {}

    def __init__(self, client_id: str, client_secret: str, scope: str, token_url: str, *args,
                 token_cache: cache.BaseCache | None = None,
                 access_token_field: str | None = 'access_token',
                 refresh_token_field: str | None = 'refresh_token',
                 expires_in_field: str | None = 'expires_in',
                 **kwargs):
        """
        Базовый класс, отвечающий за получение и обновление токена у OAuth провайдера
        :param client_id: идентификатор клиента
        :param client_secret: секретный ключ клиента
        :param scope: разделенный пробелами список областей для приложений OAuth
        :param token_url: конечная точка получения токенов
        :param arg: прочие аргументы
        :param token_cache: реализация кеширования
        :param access_token_field: поле ответа, в котором содержится access_token
        :param expires_in_field: поле ответа, в котором содержится дата устаревания
        :param kwargs: прочие именованные параметры
        """
        super().__init__(*args, **kwargs)
        self.token_cache = token_cache
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.scope = scope

        self.access_token_field = access_token_field
        self.refresh_token_field = refresh_token_field
        self.expires_in_field = expires_in_field

        self._service = services.HttpService()
        self._policy = retry_policy.AsyncRetryPolicy()

    def _init_token_request(self):
        form = aiohttp.FormData(quote_fields=True)
        form.add_field('grant_type', self.grant_type)
        form.add_field('client_id', self.client_id)
        form.add_field('client_secret', self.client_secret)
        form.add_field('scope', self.scope)

        for key, value in self.extended_token_request.items():
            form.add_field(key, value)

        request = {
            'method': 'POST',
            'url': self.token_url,
            'cfg': {
                'data': form
            }
        }

        return request

    def _parse_token_response(self, response: dict) -> tuple[dict, float]:
        access_token = response.get(self.access_token_field)
        expires_in = response.get(self.expires_in_field)
        refresh_token = response.get(self.refresh_token_field)

        if not access_token or not expires_in:
            raise ValueError('Invalid response - access_token or expires_in is none.')

        return {
            'access_token': access_token,
            'expires_in': expires_in,
            'refresh_token': refresh_token
        }, float(expires_in) - 60  # делаем срок устаревания на 60 секунд меньше

    async def _init_token(self) -> dict:
        request = self._init_token_request()
        response_data = await http_utils.send_and_validate(self._service, request, policy=self._policy)
        data, expires_in = self._parse_token_response(response_data)
        if self.token_cache:
            await self.token_cache.set(self.client_id, data, expired_timeout=expires_in)

        return data

    async def _get_token_cache(self) -> dict | None:
        """ Получение закешированного токена """
        if self.token_cache:
            return await self.token_cache.get(self.client_id)

        return None

    async def get_token(self, *args, **kwargs):
        """ Получение access_token """
        data = await self._get_token_cache()
        if data:
            # если токен найден
            # TODO: Не используется refresh token
            return data['access_token']

        # если токен не найден, то инициализируем токены
        data = await self._init_token()
        return data['access_token']


class SetSystemOAuthToken(OAuthTokenTransformer):
    """ Указывает Bearer token учетных записей для автоматизации """

    @property
    def grant_type(self):
        return 'client_credentials'


class SetUserOAuthToken(OAuthTokenTransformer):
    """ Указывает Bearer token для пользовательских учетных записей """

    def __init__(self, username: str, password: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username = username
        self.password = password

    @property
    def grant_type(self):
        return 'password'

    @property
    def extended_token_request(self) -> dict:
        return {
            'username': self.username,
            'password': self.password
        }
