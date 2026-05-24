import argparse
import asyncio
import logging
import pprint

from http_misc.configuration import Configuration

from http_misc.aiohttp.transports import AioHttpTransport
from http_misc.retry_policy import AsyncRetryPolicy
from http_misc.services import HttpService

parser = argparse.ArgumentParser(allow_abbrev=False, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-urls', '--urls', required=True, help='Список URL через запятую')
parser.add_argument('-status', '--status', default=200, required=False,
                    help='Ожидаемый статус ответа. Если не указан, то 200')

logger = logging.getLogger('health')


async def async_main(args):
    try:
        urls = str(args.urls).split(',')
        status = int(args.status)
        Configuration.default_http_cfg = {
            'ssl': False,
            'timeout': 5
        }
        for url in urls:
            # logger.info('Проверка "%s"...', url)
            policy = AsyncRetryPolicy(max_retry=2)
            service = HttpService(transport=AioHttpTransport())
            request = {
                'method': 'GET',
                'url': url
            }

            result = await policy.apply(service.send_request, **request)
            is_success = result.status == status
            if is_success:
                logger.info('Сервис "%s" доступен.', url)
            else:
                logger.info('Сервис "%s" не доступен.', url)

        logger.info('Проверка завершена.')
    except Exception as ex:
        logger.exception(ex)


def main():
    logging.basicConfig(level=logging.INFO)

    args = parser.parse_args()

    loop = asyncio.get_event_loop()

    loop.run_until_complete(async_main(args))


if __name__ == '__main__':
    main()
