"""
Утилитарные функции
"""
import datetime
import decimal
import json
import threading
import uuid
from collections.abc import Sequence, Collection
from typing import Any

import jwt

from http_misc import errors


def default_encoder(obj):
    """ Default JSON encoder """
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()

    if isinstance(obj, (uuid.UUID, decimal.Decimal)):
        return str(obj)

    return obj


def json_dumps(*args, **kwargs):
    """ Сериализация в json """
    return json.dumps(*args, **kwargs, default=default_encoder)


def join_str(*args, sep: str | None = '/', append_last_sep: bool | None = False) -> str:
    """ Объединение строк """
    args_str = [str(a) for a in args]
    url = sep.join([arg.strip(sep) for arg in args_str])
    if append_last_sep:
        url = url + sep
    return url


async def send_and_validate(service,  # services.BaseService
                            request,
                            expected_status: int | None = 200,
                            ignore_status: int | Collection[int] = None,
                            policy=None):  # retry_policy.AsyncRetryPolicy | None
    """ Вызов внешнего сервиса и проверка его статуса"""
    if policy:
        response = await policy.apply(service.send_request, **request)
    else:
        response = await service.send_request(**request)

    if response is None:
        return None

    if not _is_legal_status(response.status, expected_status=expected_status, ignore_status=ignore_status):
        raise errors.InteractionError('Произошла ошибка при вызове внешнего сервиса',
                                      status_code=response.status, response=response.response_data)

    return response.response_data


def _is_legal_status(status: int, expected_status: int | None = 200,
                     ignore_status: int | Collection[int] = None) -> bool:
    if ignore_status and status in ignore_status:
        return True

    if status == expected_status:
        return True

    return False


def filter_list_by_key(filter_data: list, id_key: str, key_value: Any,
                       find_first: bool | None = True,
                       raise_if_not_found: bool | None = False) -> list | dict:
    """ Фильтрация списка словарей по ключевому полю """
    if not isinstance(filter_data, list):
        raise KeyError('Invalid filter data - expected list.')

    if not isinstance(key_value, str):
        key_value = str(key_value)

    data_filter = filter(lambda x: str(x[id_key]) == key_value, filter_data)
    if find_first:
        data = next(data_filter, None)
        if data is None and raise_if_not_found:
            raise KeyError(f'Item with field {id_key} not found for key value {key_value}')
        return data

    return list(data_filter)


def parse_authorization_header(authorization_header: str) -> tuple[str, str]:
    """
    Парсинг значения заголовка Authorization
    Authorization: Bearer 401f7ac837da42b97f613d789819ff93537bee6a
    """
    if not authorization_header:
        raise errors.TokenParseError('Заголовок AUTHORIZATION не указан или его значение отсутствует.')

    auth = authorization_header.split()

    len_auth = len(auth)

    if len_auth == 0:
        raise errors.TokenParseError('Не верный заголовок AUTHORIZATION: значение должно содержать пробелы.')

    if len_auth == 1:
        raise errors.TokenParseError(
            'Не верный заголовок AUTHORIZATION: не указан один из реквизитов для входа.')

    if len_auth > 2:
        raise errors.TokenParseError('Не верный заголовок AUTHORIZATION: реквизитов для входа больше чем 2.')

    return auth[0], auth[1]


def token_is_valid(authorization_header: str, use_utc: bool | None = True, secret_key: str | bytes = '',
                   algorithms: Sequence[str] | None = None) -> bool:
    """
    Проверка времени жизни токена.

    True - токен еще действителен.
    """
    token_name, token = parse_authorization_header(authorization_header)

    if token_name.lower() == 'bearer':
        try:
            options = {'verify_signature': bool(secret_key)}

            decoded = jwt.decode(token, key=secret_key, algorithms=algorithms, options=options)
            exp = decoded.get('exp')
            if exp:
                now = datetime.datetime.now(tz=datetime.timezone.utc if use_utc else None)
                current_time = now.timestamp()
                return current_time < exp
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, jwt.InvalidSignatureError, jwt.DecodeError):
            return False

    return True

class SingletonMeta(type):
    """ Потокобезопасный мета класс для Singleton """

    _instances: dict[type, Any] = {}
    _lock: threading.Lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]