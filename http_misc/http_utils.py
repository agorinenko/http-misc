import datetime
import decimal
import json
import uuid
from typing import Optional

from http_misc import services, errors, retry_policy


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


async def send_and_validate(service: 'services.BaseService', request, expected_status: int | None = 200,
                            policy: Optional['retry_policy.AsyncRetryPolicy'] = None):
    """ Вызов внешнего сервиса и проверка его статуса"""
    if policy:
        response = await policy.apply(service.send_request, **request)
    else:
        response = await service.send_request(**request)

    if response.status != expected_status:
        raise errors.InteractionError('Произошла ошибка при вызове внешнего сервиса',
                                      status_code=response.status, response=response.response_data)

    return response.response_data


def filter_list_by_key(filter_data: list, id_key: str, key_value,
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
