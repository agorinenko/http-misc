# http-misc 1.0.1 release notes

1. Изменен и доработан подход к политикам повторных вызовов
2. Добавлен retry_policy.py, содержащий новые классы RequestCountManager, RetryPolicy, AsyncRetryPolicy
3. Доработан BaseService, убран код, отвечающий за повторы вызовов
4. Добавлены тесты
5. Добавлен logger.py для получения логгера пакета
6. Доработана функция send_and_validate

# http-misc 0.0.2 release notes

1. Исправлена ошибка циклического импорта

# http-misc 0.0.1 release notes

1. Классы ошибок errors.py
2. Утилитарные функции http_utils.py
3. Классы для реализации межсервисного взаимодействия services.py