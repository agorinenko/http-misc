import uuid
from unittest.mock import call

import aiohttp
import httpx
import pytest
from http_misc.transports import ServiceResponse

from http_misc import http_utils, transports
from http_misc.aiohttp.transports import AioHttpTransport
from http_misc.configuration import Configuration

from http_misc.errors import RetryError, MaxRetryError
from http_misc.httpx.transports import HttpxTransport
from http_misc.requests.transports import RequestsTransport
from http_misc.retry_policy import AsyncRetryPolicy, SyncRetryPolicy
from http_misc.services import HttpService, SyncHttpService


async def test_default_configuration(mocker):
    """ Проверка proxy """
    url = 'http://127.0.0.1:8000/api/v1/health/'
    proxy = 'http://user:pass@some.proxy.com:123'
    timeout = 10
    method = 'POST'
    policy = SyncRetryPolicy()
    service = SyncHttpService(transport=RequestsTransport())
    send_request_mock = mocker.patch.object(service.transport, 'request',
                                            return_value=ServiceResponse(status=200, response_data={'status': True}))
    Configuration.default_http_method = 'GET'
    Configuration.default_url = 'https://jsonplaceholder.typicode.com/todos'
    Configuration.default_http_cfg = {
        'proxy': proxy,
        'timeout': timeout
    }

    request = {
        'method': method,
        'url': url
    }
    result = policy.apply(service.send_request, **request)
    assert result.status == 200

    expected_kwargs = {
        'proxy': proxy,
        'timeout': timeout
    }
    send_request_mock.assert_called_once_with(method, url, **expected_kwargs)
    send_request_mock.reset_mock()
    # Переопределяем proxy
    new_proxy = '123'
    request = {
        'method': method,
        'url': url,
        'cfg': {
            'proxy': new_proxy,
        }
    }
    result = policy.apply(service.send_request, **request)
    assert result.status == 200

    expected_kwargs = {
        'proxy': new_proxy,
        'timeout': timeout
    }
    send_request_mock.assert_called_once_with(method, url, **expected_kwargs)

    Configuration.reset_to_default()


@pytest.mark.integration
@pytest.mark.parametrize('transport', (
        None,
        RequestsTransport(),
))
@pytest.mark.parametrize('url', (
        'https://jsonplaceholder.typicode.com/todos',
        'https://gorinenko.ru/'
))
def test_http_service__sync_integration(transport, url):
    policy = SyncRetryPolicy()
    service = SyncHttpService(transport=transport)
    request = {
        'method': 'GET',
        'url': url
    }

    result = policy.apply(service.send_request, **request)
    assert result.status == 200


@pytest.mark.integration
@pytest.mark.parametrize('transport', (
        None,
        AioHttpTransport(),
        HttpxTransport(),
))
@pytest.mark.parametrize('url', (
        'https://jsonplaceholder.typicode.com/todos',
        'https://gorinenko.ru/'
))
async def test_http_service__async_integration(transport, url):
    policy = AsyncRetryPolicy()
    service = HttpService(transport=transport)
    request = {
        'method': 'GET',
        'url': url
    }

    result = await policy.apply(service.send_request, **request)
    assert result.status == 200


@pytest.mark.parametrize('transport', (
        AioHttpTransport(),
        HttpxTransport(),
))
async def test_http_service__dns_error(transport):
    policy = AsyncRetryPolicy(ignore_exceptions=[
        aiohttp.client_exceptions.ClientConnectorDNSError, httpx.ConnectError
    ])
    service = HttpService(transport=transport)
    request = {
        'method': 'GET',
        'url': f'https://{uuid.uuid4()}.ru'
    }

    result = await policy.apply(service.send_request, **request)
    assert result is None


@pytest.mark.parametrize('transport', (
        None,
        AioHttpTransport(),
        HttpxTransport(),
))
async def test_http_service(mocker, transport):
    response_data = {
        'meta': {
            'count': 5
        },
        'list': [
            1, 2, 3, 4, 5
        ]
    }
    send_mocker = mocker.patch('http_misc.services.HttpService._send')
    send_mocker.return_value = transports.ServiceResponse(status=200, response_data=response_data, raw_response=None)

    policy = AsyncRetryPolicy()
    service = HttpService(transport=transport)
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
    send_mocker.return_value = transports.ServiceResponse(status=500, response_data=response_data, raw_response=None)

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
