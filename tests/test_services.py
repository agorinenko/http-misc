from unittest.mock import call

import pytest
from http_misc import http_utils

from http_misc.errors import RetryError, MaxRetryError
from http_misc.retry_policy import AsyncRetryPolicy
from http_misc.services import HttpService, ServiceResponse


async def test_http_service(mocker):
    response_data = {
        'meta': {
            'count': 5
        },
        'list': [
            1, 2, 3, 4, 5
        ]
    }
    send_mocker = mocker.patch('http_misc.services.HttpService._send')
    send_mocker.return_value = ServiceResponse(status=200, response_data=response_data, raw_response=None)

    policy = AsyncRetryPolicy()
    service = HttpService()
    request = {
        'method': 'GET',
        'url': 'https://localhost:8000',
        'cfg': {
            'params': {
                'q1': 1,
                'q2': '2'
            }
        }
    }
    result = await policy.apply(service.send_request, **request)
    assert result.status == 200
    assert result.response_data == response_data

    assert send_mocker.call_args_list == [
        call(method='GET', url='https://localhost:8000', cfg={'params': {'q1': 1, 'q2': '2'}})
    ]


async def test_http_service__500(mocker):
    response_data = {
        'error': 'Error1'
    }
    send_mocker = mocker.patch('http_misc.services.HttpService._send')
    send_mocker.return_value = ServiceResponse(status=500, response_data=response_data, raw_response=None)

    policy = AsyncRetryPolicy()
    service = HttpService()
    request = {
        'method': 'GET',
        'url': 'https://localhost:8000',
        'cfg': {
            'params': {
                'q1': 1,
                'q2': '2'
            }
        }
    }
    result = await http_utils.send_and_validate(service, request, expected_status=500, policy=policy)
    assert result == response_data

    assert send_mocker.call_args_list == [
        call(method='GET', url='https://localhost:8000', cfg={'params': {'q1': 1, 'q2': '2'}})
    ]


async def test_http_service__retry_error(mocker):
    send_mocker = mocker.patch('http_misc.services.HttpService._send')
    send_mocker.side_effect = RetryError()

    max_retry = 5
    policy = AsyncRetryPolicy(max_retry=max_retry, backoff_factor=0.001, jitter=0.001)
    service = HttpService()
    request = {
        'method': 'GET',
        'url': 'https://localhost:8000',
        'cfg': {
            'params': {
                'q1': 1,
                'q2': '2'
            }
        }
    }
    with pytest.raises(MaxRetryError, match=f'Exceeded the maximum number of attempts {max_retry}.'):
        await policy.apply(service.send_request, **request)

    assert send_mocker.call_args_list == [
        call(method='GET', url='https://localhost:8000', cfg={'params': {'q1': 1, 'q2': '2'}})
    ] * (max_retry + 1)


async def test_http_service__error(mocker):
    send_mocker = mocker.patch('http_misc.services.HttpService._send')
    send_mocker.side_effect = Exception('Test')

    max_retry = 5
    policy = AsyncRetryPolicy(max_retry=max_retry, backoff_factor=0.001, jitter=0.001)
    service = HttpService()
    request = {
        'method': 'GET',
        'url': 'https://localhost:8000',
        'cfg': {
            'params': {
                'q1': 1,
                'q2': '2'
            }
        }
    }
    with pytest.raises(Exception, match=f'Test'):
        await policy.apply(service.send_request, **request)

    assert send_mocker.call_args_list == [
        call(method='GET', url='https://localhost:8000', cfg={'params': {'q1': 1, 'q2': '2'}})
    ]
