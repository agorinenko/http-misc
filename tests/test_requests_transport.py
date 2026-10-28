import pytest

from http_misc.requests.transports import RequestsTransport


@pytest.fixture()
def transport_with_mock_session(mocker):
    session = mocker.MagicMock()
    return RequestsTransport(client_session=session), session


def test_requests_transport__ssl_disabled_for_https_by_default(transport_with_mock_session):
    """ Для https проверка SSL отключена по умолчанию, как в асинхронных транспортах """
    transport, session = transport_with_mock_session
    url = 'https://localhost:8000/token'

    transport.request('POST', url, data={'a': 1})

    session.request.assert_called_once_with(method='POST', url=url, data={'a': 1}, verify=False)


def test_requests_transport__verify_explicitly_provided(transport_with_mock_session):
    """ Явно переданный verify не переопределяется """
    transport, session = transport_with_mock_session
    url = 'https://localhost:8000/token'

    transport.request('POST', url, verify='/path/to/ca.pem')

    session.request.assert_called_once_with(method='POST', url=url, verify='/path/to/ca.pem')


def test_requests_transport__verify_not_added_for_http(transport_with_mock_session):
    """ Для http verify не подставляется """
    transport, session = transport_with_mock_session
    url = 'http://localhost:8000/token'

    transport.request('POST', url, data={'a': 1})

    session.request.assert_called_once_with(method='POST', url=url, data={'a': 1})
