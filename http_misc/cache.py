import abc
from datetime import timezone, datetime, timedelta
from typing import Any


class BaseCache(abc.ABC):
    """
    Класс, декларирующий общие методы работы с кешем
    """

    def __init__(self, expired_timeout: float | None = 300):
        """
        expired_timeout - время устаревания кэша по умолчанию, в секундах.
        По умолчанию 300 секунд (5 минут). Вы можете установить expired_timeout в None, тогда кэш никогда не устареет.
        Если указать 0, все ключи будут сразу устаревать (таким образом, можно заставить «не кэшировать»).
        """
        self.expired_timeout = expired_timeout

    @abc.abstractmethod
    async def set(self, key: str, value: Any, expired_timeout: float | None = None) -> None:
        """ Установка значения.
        expired_timeout переопределит базовое значение self.expired_timeout только в случае > 0 """
        raise NotImplementedError('set_value')

    @abc.abstractmethod
    async def get(self, key: str) -> Any | None:
        """ Получение значения """
        raise NotImplementedError('get_value')

    @abc.abstractmethod
    async def remove(self, key: str) -> None:
        """ Очистка кеша """
        raise NotImplementedError('remove')

    @abc.abstractmethod
    async def has_key(self, key) -> bool:
        """ Возвращает True если ключ не устарел и есть в хранилище. """
        raise NotImplementedError('has_key')


class MemoryCache(BaseCache):
    """ Класс, реализующий хранение данных в памяти. """

    def __init__(self, *args, use_utc: bool | None = True, **kwargs):
        """
        Крайние случаи в которых не используется кеш:
        - expired_timeout в None(кэш никогда не устареет)
        - 0 (все ключи будут сразу устаревать)
        :param args: прочие аргументы
        :param use_utc: использовать utc зону для определения времени устаревания токена
        :param kwargs: прочие именованные параметры
        """
        super().__init__(*args, **kwargs)
        self.data = {}
        self.expire_info = {}
        self.use_utc = use_utc
        self.use_expire_info = self.expired_timeout is not None and self.expired_timeout > 0

    async def set(self, key: str, value: Any, expired_timeout: float | None = None) -> None:
        self.data[key] = value
        if self.use_expire_info:
            expired_seconds = expired_timeout if expired_timeout is not None and expired_timeout > 0 else self.expired_timeout
            self.expire_info[key] = self._now() + timedelta(seconds=expired_seconds)

    async def get(self, key: str) -> Any | None:
        if await self.has_key(key):
            return self.data[key]

        return None

    async def remove(self, key: str) -> None:
        if key in self.data:
            self.data.pop(key)

        if key in self.expire_info:
            self.expire_info.pop(key)

    async def has_key(self, key) -> bool:
        if key not in self.data:
            await self.remove(key)
            return False

        if not self.use_expire_info:
            return True

        if key not in self.expire_info:
            await self.remove(key)
            return False

        if self.expire_info[key] < self._now():
            await self.remove(key)
            return False

        return True

    def _now(self):
        return datetime.now(tz=timezone.utc if self.use_utc else None)
