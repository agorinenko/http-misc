import base64
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import timezone, datetime, timedelta

from http_misc.logger import get_logger

logger = get_logger('transformers')


class Transformer(ABC):
    """ Базовый асинхронный трансформер """

    @abstractmethod
    async def modify(self, *args, **kwargs):
        """ Изменение параметров запроса или ответа """
        return args, kwargs


class SyncTransformer(ABC):
    """ Базовый синхронный трансформер """

    @abstractmethod
    def modify(self, *args, **kwargs):
        """ Изменение параметров запроса или ответа """
        return args, kwargs


class TokenTransformerBase(ABC):
    """ Общая реализация трансформера, применяющего токен к заголовку Authorization """

    def __init__(self, force_token_update: bool | None = False):
        self.force_token_update = force_token_update

    @property
    @abstractmethod
    def token_name(self):
        """ Наименование токена """
        raise NotImplementedError('token_name')

    def _has_authorization_header(self, kwargs: dict) -> bool:
        """ Признак того, что заголовок Authorization уже указан """
        headers = kwargs.setdefault('cfg', {}).setdefault('headers', {})
        return 'Authorization' in headers and headers['Authorization']

    def _apply_token(self, kwargs: dict, token: str) -> None:
        """ Применение токена в заголовке Authorization """
        headers = kwargs.setdefault('cfg', {}).setdefault('headers', {})
        headers['Authorization'] = f'{self.token_name} {token}'


class TokenTransformer(TokenTransformerBase, Transformer, ABC):
    """ Базовый асинхронный трансформер, применяющий токен к заголовку Authorization """

    @abstractmethod
    async def get_token(self, *args, **kwargs):
        """ Получение токена """
        raise NotImplementedError('get_token')

    async def modify(self, *args, **kwargs):
        """ Применение токена в заголовке Authorization """
        if not self.force_token_update and self._has_authorization_header(kwargs):
            return args, kwargs
        token = await self.get_token(*args, **kwargs)
        self._apply_token(kwargs, token)

        return args, kwargs


class SyncTokenTransformer(TokenTransformerBase, SyncTransformer, ABC):
    """ Базовый синхронный трансформер, применяющий токен к заголовку Authorization """

    @abstractmethod
    def get_token(self, *args, **kwargs):
        """ Получение токена """
        raise NotImplementedError('get_token')

    def modify(self, *args, **kwargs):
        """ Применение токена в заголовке Authorization """
        if not self.force_token_update and self._has_authorization_header(kwargs):
            return args, kwargs
        token = self.get_token(*args, **kwargs)
        self._apply_token(kwargs, token)

        return args, kwargs


class BasicAuthorizationMixin:
    """ Basic-авторизация: логин и пароль, закодированные в base64 """

    @property
    def token_name(self):
        return 'Basic'

    def __init__(self, client_id: str, client_secret: str, *arg, **kwargs):
        super().__init__(*arg, **kwargs)
        self.client_id = client_id.encode('utf-8')
        self.client_secret = client_secret.encode('utf-8')

    def _encode_token(self) -> str:
        return base64.b64encode(self.client_id + b':' + self.client_secret).decode('utf-8')


class SetBasicAuthorization(BasicAuthorizationMixin, TokenTransformer):
    """ Указывает Basic token """

    async def get_token(self, *args, **kwargs):
        return self._encode_token()


class SyncSetBasicAuthorization(BasicAuthorizationMixin, SyncTokenTransformer):
    """ Указывает Basic token (синхронно) """

    def get_token(self, *args, **kwargs):
        return self._encode_token()


EXEC_TOKEN_TYPE = Callable[[str, str, str, str, str | None, dict | None], dict]


class OAuthTokenTransformerMixin(ABC):
    """
    Общая реализация трансформера, отвечающего за получение и обновление токена у OAuth провайдера.
    Используется асинхронной (OAuthTokenTransformer) и синхронной (SyncOAuthTokenTransformer) версиями.
    """

    @property
    def token_cache_key(self):
        return self.client_id

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

    @abstractmethod
    def _get_default_execute_token_request_func(self):
        """ Функция запроса токена по умолчанию (асинхронная или синхронная в зависимости от реализации) """
        raise NotImplementedError('_get_default_execute_token_request_func')

    def __init__(self, client_id: str, client_secret: str, scope: str, token_url: str, *args,
                 token_cache=None,  # cache.BaseCache | cache.BaseSyncCache | None
                 access_token_field: str | None = 'access_token',
                 refresh_token_field: str | None = 'refresh_token',
                 expires_in_field: str | None = 'expires_in',
                 execute_token_request_func: EXEC_TOKEN_TYPE | None = None,
                 use_utc: bool | None = True, **kwargs):
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
        self.use_utc = use_utc
        self.token_cache = token_cache
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.scope = scope
        self.access_token_field = access_token_field
        self.refresh_token_field = refresh_token_field
        self.expires_in_field = expires_in_field

        self.execute_token_request_func = execute_token_request_func
        if not self.execute_token_request_func:
            self.execute_token_request_func = self._get_default_execute_token_request_func()

    def _parse_token_response(self, response: dict) -> tuple[dict, float]:
        access_token = response.get(self.access_token_field)
        expires_in = response.get(self.expires_in_field)
        refresh_token = response.get(self.refresh_token_field)
        expires_buffer = 20.0  # делаем срок устаревания кеша на 20 секунд, а токена на 40 секунд меньше

        if not access_token or not expires_in:
            raise ValueError('Invalid response - access_token or expires_in is none.')

        expires_in = float(expires_in) - expires_buffer
        expires_in = max(0.0, expires_in)

        expires_at_delta = max(0.0, expires_in - expires_buffer)
        expires_at = self._now() + timedelta(seconds=expires_at_delta)
        return {
            'access_token': access_token,
            'expires_in': expires_in,
            'expires_at': expires_at,
            'refresh_token': refresh_token
        }, expires_in

    def _now(self):
        return datetime.now(tz=timezone.utc if self.use_utc else None)

    def _is_expired_data(self, data: dict | None) -> bool:
        """ Считаем токен устаревшим если его нет в кеше или значение текущей жаты больше значения expires_at в кеше """
        if data and (expires_at := data.get('expires_at')):
            return self._now() > expires_at

        return True

    # --- синхронная реализация получения и кеширования токена ---

    def _set_token_cache(self, data: dict, expires_in: float) -> None:
        """ Кеширование токена через синхронный интерфейс кеша """
        if self.token_cache:
            self.token_cache.set(self.token_cache_key, data, expired_timeout=expires_in)

    def _get_token_cache(self) -> dict | None:
        """ Получение закешированного токена через синхронный интерфейс кеша """
        if self.token_cache:
            return self.token_cache.get(self.token_cache_key)

        return None

    def _is_token_expired(self) -> bool:
        return self._is_expired_data(self._get_token_cache())

    def _get_and_cache_token(self, grant_type: str, extended_request: dict | None = None) -> str:
        """ Получение и кеширование токена """
        if extended_request is None:
            extended_request = {}

        extended_request.update(self.extended_token_request)
        response_data = self.execute_token_request_func(
            self.client_id, self.client_secret, self.scope, self.token_url,
            grant_type=grant_type, extended_token_request=extended_request
        )
        data, expires_in = self._parse_token_response(response_data)

        self._set_token_cache(data, expires_in)

        return data['access_token']

    def get_token(self, *args, **kwargs):
        """ Получение access_token """
        data = self._get_token_cache()
        if data:
            # если токен найден
            if self._is_token_expired():
                # Пробуем обновить через refresh_token, если он устарел
                if refresh_token := data.get('refresh_token'):
                    extended_request = {
                        'refresh_token': refresh_token
                    }
                    return self._get_and_cache_token('refresh_token', extended_request=extended_request)

            return data['access_token']

        # если токен не найден, то инициализируем токены
        access_token = self._get_and_cache_token(self.grant_type)
        return access_token


class OAuthTokenTransformer(OAuthTokenTransformerMixin, TokenTransformer, ABC):
    """ Базовый класс, отвечающий за получение и обновление токена у OAuth провайдера (асинхронно) """

    def _get_default_execute_token_request_func(self):
        from http_misc.aiohttp.utils import execute_token_request
        return execute_token_request

    async def _set_token_cache(self, data: dict, expires_in: float) -> None:
        """ Кеширование токена через асинхронный интерфейс кеша """
        if self.token_cache:
            await self.token_cache.set(self.token_cache_key, data, expired_timeout=expires_in)

    async def _get_token_cache(self) -> dict | None:
        """ Получение закешированного токена через асинхронный интерфейс кеша """
        if self.token_cache:
            return await self.token_cache.get(self.token_cache_key)

        return None

    async def _is_token_expired(self) -> bool:
        return self._is_expired_data(await self._get_token_cache())

    async def _get_and_cache_token(self, grant_type: str, extended_request: dict | None = None) -> str:
        """ Получение и кеширование токена """
        if extended_request is None:
            extended_request = {}

        extended_request.update(self.extended_token_request)
        response_data = await self.execute_token_request_func(
            self.client_id, self.client_secret, self.scope, self.token_url,
            grant_type=grant_type, extended_token_request=extended_request
        )
        data, expires_in = self._parse_token_response(response_data)

        await self._set_token_cache(data, expires_in)

        return data['access_token']

    async def get_token(self, *args, **kwargs):
        """ Получение access_token """
        data = await self._get_token_cache()
        if data:
            # если токен найден
            if await self._is_token_expired():
                # Пробуем обновить через refresh_token, если он устарел
                if refresh_token := data.get('refresh_token'):
                    extended_request = {
                        'refresh_token': refresh_token
                    }
                    return await self._get_and_cache_token('refresh_token', extended_request=extended_request)

            return data['access_token']

        # если токен не найден, то инициализируем токены
        access_token = await self._get_and_cache_token(self.grant_type)
        return access_token


class SyncOAuthTokenTransformer(OAuthTokenTransformerMixin, SyncTokenTransformer, ABC):
    """ Базовый класс, отвечающий за получение и обновление токена у OAuth провайдера (синхронно) """

    def _get_default_execute_token_request_func(self):
        from http_misc.requests.utils import execute_token_request
        return execute_token_request


class SystemOAuthTokenMixin:
    """ Токен учетных записей для автоматизации (client_credentials) """

    @property
    def grant_type(self):
        return 'client_credentials'


class SetSystemOAuthToken(SystemOAuthTokenMixin, OAuthTokenTransformer):
    """ Указывает Bearer token учетных записей для автоматизации """


class SyncSetSystemOAuthToken(SystemOAuthTokenMixin, SyncOAuthTokenTransformer):
    """ Указывает Bearer token учетных записей для автоматизации (синхронно) """


class UserOAuthTokenMixin:
    """ Токен пользовательской учетной записи (password) """

    @property
    def token_cache_key(self):
        return f'{self.client_id}-{self.username}'

    @property
    def grant_type(self):
        return 'password'

    def __init__(self, username: str, password: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.username = username
        self.password = password

    @property
    def extended_token_request(self) -> dict:
        return {
            'username': self.username,
            'password': self.password
        }


class SetUserOAuthToken(UserOAuthTokenMixin, OAuthTokenTransformer):
    """ Указывает Bearer token для пользовательских учетных записей """


class SyncSetUserOAuthToken(UserOAuthTokenMixin, SyncOAuthTokenTransformer):
    """ Указывает Bearer token для пользовательских учетных записей (синхронно) """
