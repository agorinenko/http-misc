from http_misc.http_utils import SingletonMeta


class Configuration(metaclass=SingletonMeta):
    default_http_method: str | None = 'get'
    default_url: str | None = None
    default_http_cfg: dict | None = {}

    @staticmethod
    def instance():
        """ Получение объекта конфигурации. """
        return Configuration()

    @classmethod
    def reset_to_default(cls):
        cls.default_http_method = 'get'
        cls.default_url = None
        cls.default_http_cfg = {}
