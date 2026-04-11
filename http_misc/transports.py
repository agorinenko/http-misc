import abc
from dataclasses import dataclass
from typing import Any


@dataclass
class ServiceResponse:
    """ Ответ сервиса """
    status: int
    response_data: Any = None
    raw_response: Any = None


class BaseTransport(abc.ABC):
    """ Абстрактный транспорт  """

    @abc.abstractmethod
    async def close(self, *args, **kwargs):
        """ Закрытие сессии """
        raise NotImplementedError('close')

    @abc.abstractmethod
    async def request(self, *args, **kwargs) -> ServiceResponse:
        """ Выполнение HTTP запроса """
        raise NotImplementedError('request')
