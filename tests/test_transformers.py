import base64
from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from http_misc import transformers, cache

TOKEN_RESPONSES = [
    {
        "access_token": "nb0G0HyVooN5XbSBaN2uYUr6pW75wh",
        "expires_in": 36000,
        "token_type": "Bearer",
        "scope": "read write"
    },
    {
        "access_token": "YYPfV0LG1jdTRl6D1qx9Hq0UxJvBKf",
        "expires_in": 36000,
        "token_type": "Bearer",
        "scope": "read write"
    }
]


@pytest.mark.parametrize('is_user', (
        True,
        False
))
async def test_set_system_oauth_token(mocker, is_user):
    execute_token_request_mocker = mocker.patch('http_misc.aiohttp.utils.execute_token_request')
    execute_token_request_mocker.side_effect = TOKEN_RESPONSES

    if is_user:
        transformer = transformers.SetUserOAuthToken(
            'user1', '123', 'client_id', 'secret', 'read write', 'http://localhost/api/v1/oauth/token/',
            token_cache=cache.MemoryCache()
        )
    else:
        transformer = transformers.SetSystemOAuthToken(
            'client_id', 'secret', 'read write', 'http://localhost/api/v1/oauth/token/', token_cache=cache.MemoryCache()
        )

    request = {
        'method': 'POST',
        'url': 'https://localhost',
        'cfg': {
            'json': {}
        }
    }
    with freeze_time('2025-01-14 12:00:01'):
        await transformer.modify(**request)
        await transformer.modify(**request)

    assert 'headers' in request['cfg']
    assert 'Authorization' in request['cfg']['headers']
    token_1 = request['cfg']['headers']['Authorization']
    assert token_1 == 'Bearer nb0G0HyVooN5XbSBaN2uYUr6pW75wh'
    # Протух
    transformer.force_token_update = True
    with freeze_time('2025-01-16 12:00:01'):
        await transformer.modify(**request)
        token_2 = request['cfg']['headers']['Authorization']
        assert token_2 == 'Bearer YYPfV0LG1jdTRl6D1qx9Hq0UxJvBKf'
        assert token_1 != token_2


@pytest.mark.parametrize('is_user', (
        True,
        False
))
def test_set_system_oauth_token_sync(mocker, is_user):
    """ Синхронные трансформеры SetSystemOAuthToken и SetUserOAuthToken """
    execute_token_request_mocker = mocker.patch('http_misc.requests.utils.execute_token_request')
    execute_token_request_mocker.side_effect = TOKEN_RESPONSES

    if is_user:
        transformer = transformers.SyncSetUserOAuthToken(
            'user1', '123', 'client_id', 'secret', 'read write', 'http://localhost/api/v1/oauth/token/',
            token_cache=cache.MemorySyncCache()
        )
    else:
        transformer = transformers.SyncSetSystemOAuthToken(
            'client_id', 'secret', 'read write', 'http://localhost/api/v1/oauth/token/', token_cache=cache.MemorySyncCache()
        )

    request = {
        'method': 'POST',
        'url': 'https://localhost',
        'cfg': {
            'json': {}
        }
    }
    with freeze_time('2025-01-14 12:00:01'):
        transformer.modify(**request)
        transformer.modify(**request)

    assert 'headers' in request['cfg']
    assert 'Authorization' in request['cfg']['headers']
    token_1 = request['cfg']['headers']['Authorization']
    assert token_1 == 'Bearer nb0G0HyVooN5XbSBaN2uYUr6pW75wh'
    # Протух
    transformer.force_token_update = True
    with freeze_time('2025-01-16 12:00:01'):
        transformer.modify(**request)
        token_2 = request['cfg']['headers']['Authorization']
        assert token_2 == 'Bearer YYPfV0LG1jdTRl6D1qx9Hq0UxJvBKf'
        assert token_1 != token_2


def test_sync_oauth_token__refresh(mocker):
    """ Обновление устаревшего токена через refresh_token в синхронном режиме """
    execute_token_request_mocker = mocker.patch('http_misc.requests.utils.execute_token_request')
    execute_token_request_mocker.side_effect = [
        {
            "access_token": "REFRESHED_TOKEN",
            "expires_in": 36000,
            "token_type": "Bearer"
        }
    ]
    token_cache = cache.MemorySyncCache(expired_timeout=None)
    token_cache.set('client_id', {
        'access_token': 'OLD_TOKEN',
        'expires_in': 36000,
        'expires_at': datetime(2025, 1, 15, tzinfo=timezone.utc),
        'refresh_token': 'REFRESH_TOKEN_VALUE'
    })

    transformer = transformers.SyncSetSystemOAuthToken(
        'client_id', 'secret', 'read write', 'http://localhost/api/v1/oauth/token/', token_cache=token_cache
    )
    request = {
        'method': 'POST',
        'url': 'https://localhost',
        'cfg': {
            'json': {}
        }
    }
    with freeze_time('2025-01-16 12:00:01'):
        transformer.modify(**request)

    assert request['cfg']['headers']['Authorization'] == 'Bearer REFRESHED_TOKEN'
    execute_token_request_mocker.assert_called_once_with(
        'client_id', 'secret', 'read write', 'http://localhost/api/v1/oauth/token/',
        grant_type='refresh_token', extended_token_request={'refresh_token': 'REFRESH_TOKEN_VALUE'}
    )


def test_custom_sync_token_transformer():
    """ Базовый SyncTokenTransformer позволяет реализовывать кастомные синхронные трансформеры """

    class CustomTransformer(transformers.SyncTokenTransformer):
        @property
        def token_name(self):
            return 'Custom'

        def get_token(self, *args, **kwargs):
            return 'custom-token'

    transformer = CustomTransformer()
    request = {
        'method': 'POST',
        'url': 'https://localhost',
        'cfg': {}
    }
    transformer.modify(**request)

    assert request['cfg']['headers']['Authorization'] == 'Custom custom-token'


@pytest.mark.parametrize('transformer, is_sync', (
        (transformers.SetBasicAuthorization('client_id', 'client_secret'), False),
        (transformers.SyncSetBasicAuthorization('client_id', 'client_secret'), True),
))
async def test_set_basic_authorization(transformer, is_sync):
    """ Basic-авторизация в синхронном и асинхронном вариантах """
    request = {
        'method': 'POST',
        'url': 'https://localhost',
        'cfg': {}
    }
    if is_sync:
        transformer.modify(**request)
    else:
        await transformer.modify(**request)

    expected = 'Basic ' + base64.b64encode(b'client_id:client_secret').decode('utf-8')
    assert request['cfg']['headers']['Authorization'] == expected
