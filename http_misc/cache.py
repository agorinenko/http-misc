import datetime
from abc import abstractmethod, ABC


class TokenCache(ABC):
    @abstractmethod
    def set_token(self, cache_key: str, access_token: str, expires_in: datetime):
        pass

    @abstractmethod
    def get_token(self, cache_key: str):
        pass

    @abstractmethod
    def remove(self, cache_key: str):
        pass


class MemoryTokenCache(TokenCache):
    """ Класс, реализующий хранение access_token в памяти """

    def set_token(self, cache_key: str, access_token: str, expires_in: datetime):
        """ Установка токенов """
        cache_value = {'access_token': access_token, 'expires_in': expires_in}

        self.memory_cache[cache_key] = cache_value

    def get_token(self, cache_key: str):
        """ Получение access_token """

        result = self.memory_cache.get(cache_key, {})
        return result.get('access_token'), result.get('expires_in')

    def remove(self, cache_key: str):
        if cache_key in self.memory_cache:
            self.memory_cache.pop(cache_key)

    memory_cache = {}
