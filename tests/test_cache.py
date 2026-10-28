import asyncio
import inspect
import time

from http_misc.cache import MemoryCache, MemorySyncCache


async def test_expired_timeout():
    """ Проверка устаревания
    - expired_timeout в None(кэш никогда не устареет)
    - 0 (все ключи будут сразу устаревать)
    """
    cache = MemoryCache(expired_timeout=None)
    await cache.set('key1', 'value')

    has_key = await cache.has_key('key1')
    assert not cache.use_expire_info
    assert has_key

    cache = MemoryCache(expired_timeout=0)
    await cache.set('key2', 'value')

    has_key = await cache.has_key('key2')
    assert not cache.use_expire_info
    assert not has_key

    # Устаревание 1 сек

    cache = MemoryCache(expired_timeout=1.0)
    await cache.set('key3', 'value')

    has_key = await cache.has_key('key3')
    assert cache.use_expire_info
    assert has_key

    await asyncio.sleep(1)

    has_key = await cache.has_key('key3')
    assert cache.use_expire_info
    assert not has_key


def test_expired_timeout_sync():
    """ Проверка устаревания синхронного кеша MemorySyncCache
    - expired_timeout в None(кэш никогда не устареет)
    - 0 (все ключи будут сразу устаревать)
    """
    cache = MemorySyncCache(expired_timeout=None)
    cache.set('key1', 'value')

    has_key = cache.has_key('key1')
    assert not cache.use_expire_info
    assert has_key
    assert cache.get('key1') == 'value'

    cache = MemorySyncCache(expired_timeout=0)
    cache.set('key2', 'value')

    has_key = cache.has_key('key2')
    assert not cache.use_expire_info
    assert not has_key

    # Устаревание 1 сек

    cache = MemorySyncCache(expired_timeout=1.0)
    cache.set('key3', 'value')

    has_key = cache.has_key('key3')
    assert cache.use_expire_info
    assert has_key

    time.sleep(1)

    has_key = cache.has_key('key3')
    assert cache.use_expire_info
    assert not has_key


def test_memory_cache__signatures_parity():
    """ Сигнатуры методов синхронного и асинхронного кеша совпадают """
    method_names = ('set', 'get', 'remove', 'has_key')

    for method_name in method_names:
        async_method = getattr(MemoryCache, method_name)
        sync_method = getattr(MemorySyncCache, method_name)
        assert inspect.signature(async_method) == inspect.signature(sync_method)
        assert inspect.iscoroutinefunction(async_method)
        assert not inspect.iscoroutinefunction(sync_method)
