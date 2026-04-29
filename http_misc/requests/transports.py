from contextlib import contextmanager

from http_misc.logger import get_logger
from http_misc.transports import ServiceResponse, BaseSyncTransport

logger = get_logger('requests_transformers')
try:
    import requests
except ImportError as ex:
    logger.info('Ошибка импорта requests.')


class RequestsTransport(BaseSyncTransport):
    """ Транспорт на основе requests """

    def __init__(self, *args, client_session: requests.Session = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client_session = client_session

    def close(self, *args, **kwargs):
        if self.client_session:
            self.client_session.close()

    def request(self, method: str, url: str, **kwargs) -> ServiceResponse:
        with self._use_client_session() as session:
            response = session.request(method=method, url=url, **kwargs)
            response_data = self._get_response_content(response)
            return ServiceResponse(status=response.status_code, response_data=response_data, raw_response=response)

    @contextmanager
    def _use_client_session(self):
        if self.client_session is not None:
            yield self.client_session
        else:
            with requests.Session() as session:
                yield session

    @classmethod
    def _get_response_content(cls, response: requests.Response):
        try:
            return response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            return response.text
