"""
Интеграционные тесты полного жизненного цикла запроса с OAuth трансформерами
на локальном HTTP сервере: получение токена, кеширование, отправка запроса.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from http_misc import cache, retry_policy, services, transformers
from http_misc.http_utils import join_str, send_and_validate
from http_misc.requests.transports import RequestsTransport

TOKEN_RESPONSE = {
    'access_token': 'LOCAL_ACCESS_TOKEN',
    'expires_in': 36000,
    'token_type': 'Bearer'
}


class LocalApiHandler(BaseHTTPRequestHandler):
    """ Эмуляция OAuth провайдера и внешнего сервиса """

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)

        path = self.path.rstrip('/')
        if path.endswith('/token'):
            response_data = TOKEN_RESPONSE
        elif path.endswith('/api/v1/start'):
            response_data = {'stateId': 'local-state-id'}
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def log_message(self, format, *args):
        pass


@pytest.fixture()
def local_api():
    server = HTTPServer(('127.0.0.1', 0), LocalApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _workflow_request(local_api: str) -> dict:
    request_json = {
        'workflow_path': 'yaml/std.task.100.yaml',
        'inputs': {
            'a': 1,
            'b': 2
        }
    }
    return {
        'method': 'POST',
        'url': join_str(local_api, 'api/v1/start/'),
        'cfg': {
            'json': request_json
        }
    }


async def test_start_workflow__async(local_api):
    """ Аналог test_start_workflow: асинхронный сервис с OAuth трансформером """
    policy = retry_policy.AsyncRetryPolicy()
    transformer = transformers.SetSystemOAuthToken(
        client_id='client_id',
        client_secret='client_secret',
        scope='openid',
        token_url=join_str(local_api, 'token'),
        token_cache=cache.MemoryCache())
    service = services.HttpService(request_preproc=[transformer])

    json_response = await send_and_validate(service, _workflow_request(local_api), expected_status=200, policy=policy)
    assert 'stateId' in json_response


def test_start_workflow__sync(local_api):
    """ Аналог test_start_workflow_sync: синхронный сервис с синхронным OAuth трансформером """
    policy = retry_policy.SyncRetryPolicy()
    transformer = transformers.SyncSetSystemOAuthToken(
        client_id='client_id',
        client_secret='client_secret',
        scope='openid',
        token_url=join_str(local_api, 'token'),
        token_cache=cache.MemorySyncCache())
    service = services.SyncHttpService(request_preproc=[transformer], transport=RequestsTransport())

    json_response = send_and_validate(service, _workflow_request(local_api), expected_status=200, policy=policy)
    assert 'stateId' in json_response
