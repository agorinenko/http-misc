# HTTP Misc Library

Асинхронная библиотека для HTTP взаимодействия с поддержкой retry policy, кэширования токенов OAuth 2.0 и множества
транспортов.

## Особенности

- 🚀 **Полностью асинхронная** - построена на asyncio
- 🔄 **Умные повторные попытки** - экспоненциальная задержка с jitter
- 🔐 **OAuth 2.0 из коробки** - автоматическое получение и обновление токенов
- 💾 **Кэширование с TTL** - встроенный MemoryCache
- 🔌 **Несколько транспортов** - aiohttp, httpx, gRPC
- 🔧 **Трансформеры** - гибкая модификация запросов/ответов
- 🛡️ **Безопасность** - проверка подписи JWT токенов
- 📊 **Мониторинг** - встроенное логирование и метрики

## Установка

```bash
pip install http-misc[aiohttp]   # для AioHttpTransport
pip install http-misc[httpx]     # для HttpxTransport
pip install http-misc[all]       # все транспорты
```

## Быстрый старт

### Простой HTTP запрос

```python
import asyncio
from http_misc.services import HttpService
from http_misc.aiohttp.transports import AioHttpTransport


async def main():
    # Создание сервиса с транспортом по умолчанию
    service = HttpService()

    # Выполнение запроса
    response = await service.send_request(
        method="GET",
        url="https://api.example.com/users",
        cfg={
            "headers": {"Accept": "application/json"},
            "params": {"limit": 10}
        }
    )

    print(f"Status: {response.status}")
    print(f"Data: {response.response_data}")


asyncio.run(main())
```

### Basic Authentication

```python
from http_misc.transformers import SetBasicAuthorization

auth = SetBasicAuthorization(
    client_id="username",
    client_secret="password"
)

service = HttpService(
    request_preproc=[auth]  # Автоматически добавляет заголовок Authorization
)
```

### OAuth 2.0 Client Credentials (для сервисных аккаунтов)

```python
from http_misc.transformers import SetSystemOAuthToken
from http_misc.cache import MemoryCache

# Кэш токенов (опционально)
token_cache = MemoryCache(expired_timeout=3600)  # 1 час

# Настройка OAuth
oauth = SetSystemOAuthToken(
    client_id="your_client_id",
    client_secret="your_secret",
    scope="read write",
    token_url="https://auth.example.com/oauth/token",
    token_cache=token_cache
)

service = HttpService(request_preproc=[oauth])

# Токен автоматически добавляется в каждый запрос
response = await service.send_request(
    method="GET",
    url="https://api.example.com/protected"
)
```

### OAuth 2.0 Password Grant (для пользователей)

```python
from http_misc.transformers import SetUserOAuthToken

oauth = SetUserOAuthToken(
    client_id="your_client_id",
    client_secret="your_secret",
    scope="read write",
    token_url="https://auth.example.com/oauth/token",
    username="user@example.com",
    password="user_password",
    token_cache=token_cache
)

service = HttpService(request_preproc=[oauth])
```

### Автоматические повторы при ошибках

```python
from http_misc.retry_policy import AsyncRetryPolicy
from http_misc.services import HttpService

# Настройка политики повторов
retry_policy = AsyncRetryPolicy(
    max_retry=5,  # Максимум 5 повторов
    backoff_factor=0.5,  # Начальная задержка 0.5 сек
    jitter=0.2,  # Случайное отклонение ±20%
    retry_on_exceptions=[ConnectionError, TimeoutError],
    ignore_exceptions=[ValueError]  # Не повторять для ValueError
)

# Применение политики
response = await retry_policy.apply(
    service.send_request,
    method="GET",
    url="https://api.example.com/unstable"
)
```

### Встроенные статусы для повтора

По умолчанию повторяются статусы: 408, 429, 502, 503, 504

```python
# Кастомизация статусов для повтора
service = HttpService(
    retry_on_statuses={408, 429, 500, 502, 503, 504}
)
```

### In-Memory кэш 

```python
from http_misc.cache import MemoryCache

# Кэш на 5 минут (по умолчанию)
cache = MemoryCache(expired_timeout=300)

# Бессрочный кэш
cache_forever = MemoryCache(expired_timeout=None)

# Кэш с UTC временем
cache_utc = MemoryCache(use_utc=True)

# Использование
await cache.set("user:123", {"name": "John"}, expired_timeout=60)
data = await cache.get("user:123")
await cache.remove("user:123")

if await cache.has_key("user:123"):
    print("Key exists and not expired")
```

###  Создание кастомного трансформера

```python
from http_misc.transformers import Transformer

class LoggingTransformer(Transformer):
    async def modify(self, *args, **kwargs):
        print(f"Request: {args}, {kwargs}")
        # Модификация запроса
        if 'cfg' not in kwargs:
            kwargs['cfg'] = {}
        kwargs['cfg']['headers'] = kwargs['cfg'].get('headers', {})
        kwargs['cfg']['headers']['X-Request-ID'] = str(uuid.uuid4())
        return args, kwargs

service = HttpService(
    request_preproc=[LoggingTransformer()],
    response_preproc=[ResponseLogger()]
)
```

###  Цепочка трансформеров

```python
service = HttpService(
    request_preproc=[
        AddDefaultHeaders(),    # Добавляет стандартные заголовки
        LoggingTransformer(),   # Логирует запрос
        oauth_transformer       # Добавляет Bearer токен
    ]
)
```

### AioHttpTransport
Используется пакетом по умолчанию
```python
from http_misc.aiohttp.transports import AioHttpTransport

# С автоматическим управлением сессией
transport = AioHttpTransport()

# С переиспользованием существующей сессии
import aiohttp
session = aiohttp.ClientSession()
transport = AioHttpTransport(client_session=session)

service = HttpService(transport=transport)
```

###  HttpxTransport

```python
from http_misc.httpx.transports import HttpxTransport

transport = HttpxTransport()
service = HttpService(transport=transport)
```

###  Кастомная функция получения токена

```python
async def custom_token_request(
    client_id: str,
    client_secret: str,
    scope: str,
    token_url: str,
    grant_type: str = 'client_credentials',
    extended_token_request: dict = None
) -> dict:
    """Кастомная логика получения токена"""
    # Ваша реализация
    pass

oauth = SetSystemOAuthToken(
    client_id="id",
    client_secret="secret",
    scope="read",
    token_url="https://auth.example.com/token",
    execute_token_request_func=custom_token_request
)
```

###  Игнорирование определенных статусов

```python
from http_misc.http_utils import send_and_validate

response_data = await send_and_validate(
    service,
    request,
    expected_status=200,
    ignore_status={404, 409}  # Не вызывать ошибку для этих статусов
)
```

###  Тестирование

Библиотека включает утилиты для тестирования:

```python
from http_misc.testing_utils import validate_dict_fields, IS_NOT_NONE

# Проверка полей ответа
response = {"id": 123, "name": "John", "email": None}

validate_dict_fields(response, [
    ("id", IS_NOT_NONE),
    ("name", "John"),
    ("email", None)
])

# Проверка списков
from http_misc.testing_utils import validate_list_response

response_json = {
    "count": 2,
    "results": [{"id": 1}, {"id": 2}]
}
validate_list_response(response_json, [1, 2], id_field_name="id")
```

## pylint

pylint --output-format=parseable http_misc --disable=C0114

## Генерация ключей для JWT при использовании django-oauth-toolkit

Для django-oauth-toolkit, настоятельно рекомендуется использовать асимметричное шифрование (RS256), а не общий секрет (
HS256).

**Шаг 1.** Генерация RSA-ключей
Нужно сгенерировать пару: приватный (подписывает токены в django-oauth-toolkit) и публичный (проверяет подпись).

```bash
# Генерация приватного ключа (2048 bit)
ssh-keygen -t rsa -b 2048 -m PEM -f private.pem -N ""
# Генерация публичного ключа из приватного
openssl rsa -in private.pem -outform PEM -pubout -out public.pem
```

**Шаг 2.** Настройка django-oauth-toolkit
Нужно переопределить генератор токенов, чтобы он создавал JWT, а не случайную строку. Библиотека django-oauth-toolkit
поддерживает это из коробки.

settings.py:

```python
OAUTH2_PROVIDER = {
    # Генератор, создающий JWT
    "ACCESS_TOKEN_GENERATOR": "oauthlib.oauth2.rfc6749.tokens.JWTToken",
    # Алгоритм подписи
    "JWT_ALG": "RS256",
    # Путь к ПРИВАТНОМУ ключу 
    "JWT_PRIVATE_KEY": open("/etc/secrets/private.pem").read(),
    # Время жизни токена (5 минут - хороший стандарт)
    "ACCESS_TOKEN_EXPIRE_SECONDS": 300,
    # Включаем защиту от повторного использования refresh-токена (важно для безопасности)
    "REFRESH_TOKEN_REUSE_PROTECTION": True,
}
```

**Шаг 3.** Проверка токена
Клиент должен проверять токены, используя публичный ключ.

```python
with open("public.pem", "r") as f:
    secret_key = f.read()
```