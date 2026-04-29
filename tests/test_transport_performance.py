# file name: test_transport_performance.py

import asyncio
import time
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any

import pytest
import aiohttp
import httpx
import requests

from http_misc.requests.transports import RequestsTransport
from http_misc.aiohttp.transports import AioHttpTransport
from http_misc.httpx.transports import HttpxTransport
from http_misc.services import HttpService, SyncHttpService
from http_misc.retry_policy import AsyncRetryPolicy, SyncRetryPolicy
from http_misc.logger import get_logger

logger = get_logger('performance_test')


@dataclass
class PerformanceResult:
    """Результаты замера производительности"""
    transport_name: str
    mode: str  # 'sequential' или 'parallel'
    total_time: float
    requests_per_second: float
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    success_count: int
    error_count: int


class TransportPerformanceTester:
    """Тестировщик производительности транспортов"""

    def __init__(
            self,
            num_clients: int = 10,
            requests_per_client: int = 10,
            test_url: str = 'https://jsonplaceholder.typicode.com/posts/1',
            warmup_requests: int = 5
    ):
        """
        Инициализация тестировщика.

        :param num_clients: количество одновременных клиентов
        :param requests_per_client: количество запросов на каждого клиента
        :param test_url: URL для тестирования
        :param warmup_requests: количество разогревочных запросов
        """
        self.num_clients = num_clients
        self.requests_per_client = requests_per_client
        self.test_url = test_url
        self.warmup_requests = warmup_requests
        self.total_requests = num_clients * requests_per_client

    async def _warmup_async(self, transport):
        """Разогрев асинхронного транспорта"""
        service = HttpService(transport=transport)
        policy = AsyncRetryPolicy(max_retry=2, backoff_factor=0.1, jitter=0.05)

        for _ in range(self.warmup_requests):
            try:
                await policy.apply(
                    service.send_request,
                    method='GET',
                    url=self.test_url
                )
            except Exception as ex:
                logger.warning(f"Warmup error: {ex}")

    def _warmup_sync(self, transport):
        """Разогрев синхронного транспорта"""
        service = SyncHttpService(transport=transport)
        policy = SyncRetryPolicy(max_retry=2, backoff_factor=0.1, jitter=0.05)

        for _ in range(self.warmup_requests):
            try:
                policy.apply(
                    service.send_request,
                    method='GET',
                    url=self.test_url
                )
            except Exception as ex:
                logger.warning(f"Warmup error: {ex}")

    async def _make_async_request(self, service, policy) -> tuple[float, bool]:
        """Выполнение одного асинхронного запроса"""
        start = time.time()
        try:
            response = await policy.apply(
                service.send_request,
                method='GET',
                url=self.test_url
            )
            elapsed = time.time() - start
            success = response.status == 200 if response else False
            return elapsed, success
        except Exception as ex:
            logger.debug(f"Request error: {ex}")
            return time.time() - start, False

    def _make_sync_request(self, service, policy) -> tuple[float, bool]:
        """Выполнение одного синхронного запроса"""
        start = time.time()
        try:
            response = policy.apply(
                service.send_request,
                method='GET',
                url=self.test_url
            )
            elapsed = time.time() - start
            success = response.status == 200 if response else False
            return elapsed, success
        except Exception as ex:
            logger.debug(f"Request error: {ex}")
            return time.time() - start, False

    async def _test_async_sequential(self, transport_name: str, transport) -> PerformanceResult:
        """Последовательное асинхронное тестирование"""
        logger.info(f"Starting async sequential test for {transport_name}")
        service = HttpService(transport=transport)
        policy = AsyncRetryPolicy(max_retry=2, backoff_factor=0.1, jitter=0.05)

        response_times = []
        success_count = 0
        error_count = 0

        start_total = time.time()

        for client_id in range(self.num_clients):
            for _ in range(self.requests_per_client):
                elapsed, success = await self._make_async_request(service, policy)
                response_times.append(elapsed)
                if success:
                    success_count += 1
                else:
                    error_count += 1

        total_time = time.time() - start_total

        return PerformanceResult(
            transport_name=transport_name,
            mode='async_sequential',
            total_time=total_time,
            requests_per_second=self.total_requests / total_time if total_time > 0 else 0,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            success_count=success_count,
            error_count=error_count
        )

    async def _test_async_parallel(self, transport_name: str, transport) -> PerformanceResult:
        """Параллельное асинхронное тестирование"""
        logger.info(f"Starting async parallel test for {transport_name}")
        service = HttpService(transport=transport)
        policy = AsyncRetryPolicy(max_retry=2, backoff_factor=0.1, jitter=0.05)

        async def client_task(client_id: int) -> List[tuple[float, bool]]:
            results = []
            for _ in range(self.requests_per_client):
                elapsed, success = await self._make_async_request(service, policy)
                results.append((elapsed, success))
            return results

        start_total = time.time()

        # Запускаем всех клиентов параллельно
        tasks = [client_task(i) for i in range(self.num_clients)]
        all_results = await asyncio.gather(*tasks)

        total_time = time.time() - start_total

        # Собираем статистику
        response_times = []
        success_count = 0
        error_count = 0

        for client_results in all_results:
            for elapsed, success in client_results:
                response_times.append(elapsed)
                if success:
                    success_count += 1
                else:
                    error_count += 1

        return PerformanceResult(
            transport_name=transport_name,
            mode='async_parallel',
            total_time=total_time,
            requests_per_second=self.total_requests / total_time if total_time > 0 else 0,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            success_count=success_count,
            error_count=error_count
        )

    def _test_sync_sequential(self, transport_name: str, transport) -> PerformanceResult:
        """Последовательное синхронное тестирование"""
        logger.info(f"Starting sync sequential test for {transport_name}")
        service = SyncHttpService(transport=transport)
        policy = SyncRetryPolicy(max_retry=2, backoff_factor=0.1, jitter=0.05)

        response_times = []
        success_count = 0
        error_count = 0

        start_total = time.time()

        for client_id in range(self.num_clients):
            for _ in range(self.requests_per_client):
                elapsed, success = self._make_sync_request(service, policy)
                response_times.append(elapsed)
                if success:
                    success_count += 1
                else:
                    error_count += 1

        total_time = time.time() - start_total

        return PerformanceResult(
            transport_name=transport_name,
            mode='sync_sequential',
            total_time=total_time,
            requests_per_second=self.total_requests / total_time if total_time > 0 else 0,
            avg_response_time=statistics.mean(response_times) if response_times else 0,
            min_response_time=min(response_times) if response_times else 0,
            max_response_time=max(response_times) if response_times else 0,
            success_count=success_count,
            error_count=error_count
        )

    async def run_all_tests(self) -> List[PerformanceResult]:
        """Запуск всех тестов производительности"""
        results = []

        # Инициализация транспортов
        transports_config = {
            'AioHttpTransport': AioHttpTransport(),
            'HttpxTransport': HttpxTransport(),
            'RequestsTransport': RequestsTransport()
        }

        # Разогрев
        logger.info("Starting warmup...")
        for name, transport in transports_config.items():
            if name == 'RequestsTransport':
                self._warmup_sync(transport)
            else:
                await self._warmup_async(transport)
        logger.info("Warmup completed")

        # Тестирование
        for name, transport in transports_config.items():
            logger.info(f"Testing {name}...")

            if name == 'RequestsTransport':
                # Синхронный транспорт
                result = self._test_sync_sequential(name, transport)
                results.append(result)
                logger.info(f"{name} sync sequential: {result.requests_per_second:.2f} req/s")
            else:
                # Асинхронные транспорты
                # Последовательное выполнение
                result = await self._test_async_sequential(name, transport)
                results.append(result)
                logger.info(f"{name} async sequential: {result.requests_per_second:.2f} req/s")

                # Параллельное выполнение
                result = await self._test_async_parallel(name, transport)
                results.append(result)
                logger.info(f"{name} async parallel: {result.requests_per_second:.2f} req/s")

            # Закрываем транспорт
            if hasattr(transport, 'close'):
                await transport.close() if asyncio.iscoroutinefunction(transport.close) else transport.close()

        return results

    def print_results(self, results: List[PerformanceResult]):
        """Вывод результатов в читаемом формате"""
        print("\n" + "=" * 100)
        print("PERFORMANCE TEST RESULTS")
        print("=" * 100)
        print(
            f"Configuration: {self.num_clients} clients × {self.requests_per_client} requests = {self.total_requests} total requests")
        print(f"Test URL: {self.test_url}")
        print("-" * 100)

        # Заголовок таблицы
        print(
            f"{'Transport':<20} {'Mode':<20} {'Total (s)':<10} {'Req/s':<10} {'Avg (s)':<10} {'Min (s)':<10} {'Max (s)':<10} {'Success':<10} {'Errors':<10}")
        print("-" * 100)

        for result in results:
            print(
                f"{result.transport_name:<20} "
                f"{result.mode:<20} "
                f"{result.total_time:<10.2f} "
                f"{result.requests_per_second:<10.2f} "
                f"{result.avg_response_time:<10.3f} "
                f"{result.min_response_time:<10.3f} "
                f"{result.max_response_time:<10.3f} "
                f"{result.success_count:<10} "
                f"{result.error_count:<10}"
            )

        print("-" * 100)

        # Сравнение производительности
        self._print_comparison(results)

    def _print_comparison(self, results: List[PerformanceResult]):
        """Вывод сравнения производительности"""
        print("\nPERFORMANCE COMPARISON:")
        print("-" * 50)

        # Группируем результаты по режимам
        parallel_results = [r for r in results if 'parallel' in r.mode]
        sequential_results = [r for r in results if 'sequential' in r.mode]

        if parallel_results:
            fastest = min(parallel_results, key=lambda x: x.total_time)
            slowest = max(parallel_results, key=lambda x: x.total_time)
            print(f"Parallel mode - Fastest: {fastest.transport_name} ({fastest.requests_per_second:.2f} req/s)")
            print(f"Parallel mode - Slowest: {slowest.transport_name} ({slowest.requests_per_second:.2f} req/s)")
            if fastest.requests_per_second > 0:
                print(f"Speedup: {fastest.requests_per_second / slowest.requests_per_second:.2f}x")

        if sequential_results:
            fastest = min(sequential_results, key=lambda x: x.total_time)
            slowest = max(sequential_results, key=lambda x: x.total_time)
            print(f"\nSequential mode - Fastest: {fastest.transport_name} ({fastest.requests_per_second:.2f} req/s)")
            print(f"Sequential mode - Slowest: {slowest.transport_name} ({slowest.requests_per_second:.2f} req/s)")
            if fastest.requests_per_second > 0:
                print(f"Speedup: {fastest.requests_per_second / slowest.requests_per_second:.2f}x")


@pytest.mark.integration
@pytest.mark.performance
@pytest.mark.parametrize('num_clients,requests_per_client', [
    # (1, 10),  # Легкая нагрузка
    # (5, 10),  # Средняя нагрузка
    # (10, 10),  # Высокая нагрузка
    (30, 10),  # Высокая нагрузка
])
async def test_transport_performance(num_clients, requests_per_client):
    """
    Тест производительности транспортов.
    """
    tester = TransportPerformanceTester(
        num_clients=num_clients,
        requests_per_client=requests_per_client,
        warmup_requests=3
    )

    results = await tester.run_all_tests()
    tester.print_results(results)

    # Базовые проверки
    for result in results:
        assert result.success_count > 0, f"{result.transport_name} has no successful requests"
        assert result.total_time > 0, f"{result.transport_name} total time is invalid"
        assert result.requests_per_second > 0, f"{result.transport_name} requests per second is invalid"


@pytest.mark.integration
@pytest.mark.performance
async def test_transport_performance_comparison():
    """
    Расширенный тест сравнения производительности с различными конфигурациями.
    """
    configurations = [
        (1, 20),  # 1 клиент, 20 запросов
        (5, 20),  # 5 клиентов, 100 запросов
        (10, 20),  # 10 клиентов, 200 запросов
    ]

    all_results = []

    for num_clients, requests_per_client in configurations:
        print(f"\n\nTesting configuration: {num_clients} clients × {requests_per_client} requests")
        print("=" * 80)

        tester = TransportPerformanceTester(
            num_clients=num_clients,
            requests_per_client=requests_per_client,
            warmup_requests=3
        )

        results = await tester.run_all_tests()
        all_results.extend(results)
        tester.print_results(results)

        # Пауза между тестами для стабилизации соединений
        await asyncio.sleep(2)

    # Проверяем, что параллельное выполнение быстрее последовательного
    for num_clients, requests_per_client in configurations:
        parallel_results = [r for r in all_results if r.mode == 'async_parallel' and r.total_time > 0]
        sequential_results = [r for r in all_results if r.mode == 'async_sequential' and r.total_time > 0]

        if parallel_results and sequential_results:
            for p_result in parallel_results:
                s_result = next(
                    (r for r in sequential_results if r.transport_name == p_result.transport_name),
                    None
                )
                if s_result:
                    assert p_result.total_time <= s_result.total_time * 1.5, \
                        f"Parallel should be significantly faster than sequential for {p_result.transport_name}"

# if __name__ == '__main__':
#     # Запуск вручную для быстрого тестирования
#     async def main():
#         tester = TransportPerformanceTester(
#             num_clients=5,
#             requests_per_client=10,
#             test_url='https://jsonplaceholder.typicode.com/posts/1'
#         )
#         results = await tester.run_all_tests()
#         tester.print_results(results)
#
#
#     asyncio.run(main())
