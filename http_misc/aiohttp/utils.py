from http_misc import retry_policy, services, http_utils

try:
    import aiohttp
except ImportError as ex:
    pass

DEFAULT_POLICY = retry_policy.AsyncRetryPolicy()


async def execute_token_request(client_id: str, client_secret: str, scope: str, token_url: str,
                                grant_type: str | None = 'client_credentials',
                                extended_token_request: dict | None = None) -> dict:
    """ Получение токена """
    form = aiohttp.FormData(quote_fields=True)
    form.add_field('grant_type', grant_type)
    form.add_field('client_id', client_id)
    form.add_field('client_secret', client_secret)
    form.add_field('scope', scope)

    if extended_token_request:
        for key, value in extended_token_request.items():
            form.add_field(key, value)

    request = {
        'method': 'POST',
        'url': token_url,
        'cfg': {
            'data': form
        }
    }

    return await http_utils.send_and_validate(services.HttpService(), request, policy=DEFAULT_POLICY)
