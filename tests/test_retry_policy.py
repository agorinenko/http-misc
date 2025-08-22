from unittest.mock import MagicMock, AsyncMock

import pytest

from http_misc.errors import RetryError, MaxRetryError
from http_misc.retry_policy import RetryPolicy, AsyncRetryPolicy


@pytest.mark.parametrize('clazz', [RetryPolicy, AsyncRetryPolicy])
async def test_async_apply(clazz):
    """ Выполнение асинхронного действия. Успех """
    policy = clazz()
    is_async_policy = isinstance(policy, AsyncRetryPolicy)

    some_action = AsyncMock() if is_async_policy else MagicMock()
    some_action.return_value = '123'

    if is_async_policy:
        result = await policy.apply(some_action)
    else:
        result = policy.apply(some_action)

    requests = policy.request_count_manager.get_requests()
    assert result == '123'
    assert some_action.call_count == 1
    assert len(requests.keys()) == 0


@pytest.mark.parametrize('clazz', [RetryPolicy, AsyncRetryPolicy])
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

    requests = policy.request_count_manager.get_requests()
    assert some_action.call_count == max_retry + 1
    assert len(requests.keys()) == 0


@pytest.mark.parametrize('clazz', [RetryPolicy, AsyncRetryPolicy])
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

    requests = policy.request_count_manager.get_requests()
    assert some_action.call_count == 1
    assert len(requests.keys()) == 0
