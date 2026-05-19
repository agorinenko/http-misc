import uuid
from unittest.mock import MagicMock, AsyncMock

import pytest
from aiohttp import client_exceptions

from http_misc import services, http_utils
from http_misc.errors import RetryError, MaxRetryError
from http_misc.retry_policy import AsyncRetryPolicy, SyncRetryPolicy


@pytest.mark.parametrize('clazz', [SyncRetryPolicy, AsyncRetryPolicy])
async def test_async_apply(clazz):
    """ Выполнение асинхронного действия. Успех """
    policy = clazz()
    is_async_policy = isinstance(policy, AsyncRetryPolicy)

    def __some_action():
        request_context = http_utils.get_request_context()
        assert 'request_id' in request_context
        return '123'

    async def __asome_action():
        request_context = http_utils.get_request_context()
        assert 'request_id' in request_context
        return '123'

    some_action = __asome_action if is_async_policy else __some_action

    if is_async_policy:
        result = await policy.apply(some_action)
    else:
        result = policy.apply(some_action)

    requests = await policy.request_count_manager.get_requests() if is_async_policy else policy.request_count_manager.get_requests()
    assert result == '123'
    assert len(requests.keys()) == 0


@pytest.mark.parametrize('clazz', [SyncRetryPolicy, AsyncRetryPolicy])
async def test_async_apply__retry_error(clazz):
    """ Выполнение асинхронного действия. RetryError """
    max_retry = 5
    policy = clazz(max_retry=max_retry, backoff_factor=0.001, jitter=0.001)
    is_async_policy = isinstance(policy, AsyncRetryPolicy)

    some_action = AsyncMock() if is_async_policy else MagicMock()
    some_action.side_effect = RetryError()

    with pytest.raises(MaxRetryError, match=f'Exceeded the maximum number of attempts {max_retry}.'):
        if is_async_policy:
            await policy.apply(some_action)
        else:
            policy.apply(some_action)

    requests = await policy.request_count_manager.get_requests() if is_async_policy else policy.request_count_manager.get_requests()
    assert some_action.call_count == max_retry + 1
    assert len(requests.keys()) == 0


@pytest.mark.parametrize('clazz', [SyncRetryPolicy, AsyncRetryPolicy])
async def test_async_apply__error(clazz):
    """ Выполнение асинхронного действия. Exception """
    policy = clazz()
    is_async_policy = isinstance(policy, AsyncRetryPolicy)

    some_action = AsyncMock() if is_async_policy else MagicMock()
    some_action.side_effect = Exception('Test')
    with pytest.raises(Exception, match=f'Test'):
        if is_async_policy:
            await policy.apply(some_action)
        else:
            policy.apply(some_action)

    requests = await policy.request_count_manager.get_requests() if is_async_policy else policy.request_count_manager.get_requests()
    assert some_action.call_count == 1
    assert len(requests.keys()) == 0


async def test_retry_on_exceptions():
    """ Проверка того, что DNS недоступен """
    service = services.HttpService()
    request = {
        'method': 'GET',
        'url': f'http://{uuid.uuid4()}.abc/notfound',
        'cfg': {
            'timeout': 10
        }
    }
    max_retry = 5
    retry_on_exceptions = [
        client_exceptions.ClientConnectorError
    ]

    policy = AsyncRetryPolicy(max_retry=max_retry, backoff_factor=0.001, jitter=0.001,
                              retry_on_exceptions=retry_on_exceptions)

    with pytest.raises(MaxRetryError, match=f'Exceeded the maximum number of attempts {max_retry}.'):
        await policy.apply(service.send_request, **request)


async def test_retry_on_exceptions__sync():
    """ Проверка того, что DNS недоступен """
    service = services.HttpService()
    request = {
        'method': 'GET',
        'url': f'http://{uuid.uuid4()}/notfound',
        'cfg': {
            'timeout': 10
        }
    }
    max_retry = 5
    retry_on_exceptions = [
        client_exceptions.ClientConnectorError
    ]
    policy = AsyncRetryPolicy(max_retry=max_retry, backoff_factor=0.001, jitter=0.001,
                              retry_on_exceptions=retry_on_exceptions)
    with pytest.raises(MaxRetryError, match=f'Exceeded the maximum number of attempts {max_retry}.'):
        await policy.apply(service.send_request, **request)
