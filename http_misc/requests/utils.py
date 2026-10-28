from http_misc import http_utils, retry_policy, services

DEFAULT_POLICY = retry_policy.SyncRetryPolicy()


def execute_token_request(client_id: str, client_secret: str, scope: str, token_url: str,
                          grant_type: str | None = 'client_credentials',
                          extended_token_request: dict | None = None) -> dict:
    """ Получение токена """
    form = {
        'grant_type': grant_type,
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': scope
    }

    if extended_token_request:
        form.update(extended_token_request)

    request = {
        'method': 'POST',
        'url': token_url,
        'cfg': {
            'data': form
        }
    }

    return http_utils.send_and_validate(services.SyncHttpService(), request, policy=DEFAULT_POLICY)
