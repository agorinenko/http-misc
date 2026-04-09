import pytest
from freezegun import freeze_time

from http_misc import transformers, cache


@pytest.mark.parametrize('is_user', (
        True,
        False
))
async def test_set_system_oauth_token(mocker, is_user):
    send_and_validate_mocker = mocker.patch('http_misc.http_utils.send_and_validate')
    send_and_validate_mocker.side_effect = [
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
