from freezegun import freeze_time

from http_misc import transformers, cache


async def test_set_system_oauth_token(mocker):
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
    transformer = transformers.SetSystemOAuthToken(
        client_id='6x7ujMdws6tDLbpePzQZvkYd0yFADYNJ11putMRw',
        client_secret='RgCUfgtFHxqZ2amnqS4eTFL6cRsdfc3YYN0lTBrAIarLrt0Icewv6QzC1nFZXusEjqpG0aFmC14f8Jme4z3Q4TpxI9UQM5aU5LQkvuKpOoZ3oF2wDlyC7J41zPGTYuhO',
        scope='read write',
        token_url='http://localhost/api/v1/oauth/token/',
        token_cache=cache.MemoryTokenCache())

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
    with freeze_time('2025-01-16 12:00:01'):
        await transformer.modify(**request)
        token_2 = request['cfg']['headers']['Authorization']
        assert token_2 == 'Bearer YYPfV0LG1jdTRl6D1qx9Hq0UxJvBKf'
        assert token_1 != token_2
