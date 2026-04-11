import asyncio

from http_misc.cache import MemoryCache


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