"""Negative controls use mocked underlays: even a broken guard cannot dial out."""
import asyncio
import http.client
import importlib.util
import socket
import unittest
from unittest.mock import patch

from network_guard import NetworkForbidden, OfflineAsyncTestCase, network_guard


class GuardTests(unittest.TestCase):
    def test_tcp_dns_udp_and_localhost_are_blocked(self):
        targets = [('socket.socket.connect', lambda: socket.socket.connect(None, ('192.0.2.1', 443))),
                   ('socket.socket.connect_ex', lambda: socket.socket.connect_ex(None, ('127.0.0.1', 80))),
                   ('socket.create_connection', lambda: socket.create_connection(('example.invalid', 443))),
                   ('socket.getaddrinfo', lambda: socket.getaddrinfo('example.invalid', 443)),
                   ('socket.gethostbyname', lambda: socket.gethostbyname('example.invalid')),
                   ('socket.gethostbyname_ex', lambda: socket.gethostbyname_ex('example.invalid')),
                   ('socket.gethostbyaddr', lambda: socket.gethostbyaddr('192.0.2.1')),
                   ('socket.getnameinfo', lambda: socket.getnameinfo(('192.0.2.1', 443), 0)),
                   ('socket.socket.sendto', lambda: socket.socket.sendto(None, b'x', ('::1', 1234))),
                   ('http.client.HTTPConnection.connect', lambda: http.client.HTTPConnection('example.invalid').connect())]
        for target, attempt in targets:
            with self.subTest(target=target), patch(target, return_value=None) as underlay:
                with network_guard(), self.assertRaises(NetworkForbidden):
                    attempt()
                underlay.assert_not_called()

    def test_restoration_on_exception(self):
        original = socket.socket.connect
        sentinel = RuntimeError('synthetic setup failure')
        with self.assertRaises(RuntimeError):
            with network_guard():
                raise sentinel
        self.assertIs(socket.socket.connect, original)

    def test_repeated_guards_do_not_leak(self):
        originals = (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo)
        for _ in range(3):
            with network_guard():
                self.assertIsNot(socket.socket.connect, originals[0])
            self.assertEqual((socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo), originals)

    def test_disabled_guard_would_fail_negative_control(self):
        # Mutation control: without the guard the synthetic underlay is called,
        # so assertRaises(NetworkForbidden) fails. No actual socket is involved.
        with patch('socket.create_connection', return_value=None) as underlay:
            with self.assertRaises(AssertionError):
                with self.assertRaises(NetworkForbidden):
                    socket.create_connection(('example.invalid', 443))
            underlay.assert_called_once()

    def test_async_lifecycle_and_runner_cleanup_stay_guarded(self):
        phases = []
        loops = []
        originals = socket.socket.connect

        class Probe(OfflineAsyncTestCase):
            async def asyncSetUp(self):
                loops.append(asyncio.get_running_loop())
                phases.append('setup')

            async def test_body(self):
                phases.append('body')
                self.addCleanup(lambda: phases.append('cleanup'))
                async def pending():
                    try:
                        await asyncio.Event().wait()
                    finally:
                        with self.assertRaises(NetworkForbidden):
                            socket.create_connection(('127.0.0.1', 1234))
                        phases.append('cancelled-under-guard')
                asyncio.create_task(pending())
                await asyncio.sleep(0)  # yield to the task, not a timing delay
                with self.assertRaises(NetworkForbidden):
                    socket.create_connection(('example.invalid', 443))

            async def asyncTearDown(self):
                phases.append('teardown')
                with self.assertRaises(NetworkForbidden):
                    socket.create_connection(('example.invalid', 443))

        # Underlay ensures that even a regression cannot open a real connection.
        with patch('socket.create_connection', return_value=None) as underlay:
            result = unittest.TestResult()
            Probe('test_body').run(result)
            self.assertTrue(result.wasSuccessful(), (result.failures, result.errors))
            self.assertEqual(phases, ['setup', 'body', 'teardown', 'cleanup', 'cancelled-under-guard'])
            self.assertTrue(loops[0].is_closed())
            self.assertEqual(asyncio.all_tasks(loops[0]), set())
            underlay.assert_not_called()
        self.assertIs(socket.socket.connect, originals)

    def test_guard_restored_even_when_test_setup_fails(self):
        original = socket.socket.connect
        class Probe(OfflineAsyncTestCase):
            def setUp(self):
                super().setUp()
                raise RuntimeError('synthetic setup failure')

            async def test_body(self):
                self.fail('Body must not run after failed setup')

        result = unittest.TestResult()
        Probe('test_body').run(result)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(len(result.failures), 0)
        self.assertIs(socket.socket.connect, original)


class AsyncGuardTests(OfflineAsyncTestCase):
    async def test_iocp_and_async_http_paths_blocked(self):
        loop = asyncio.get_running_loop()
        for name, args in [('create_connection', (lambda: None, 'example.invalid', 443)),
                           ('create_datagram_endpoint', (lambda: None,)),
                           ('sock_connect', (None, ('192.0.2.1', 443))),
                           ('sock_sendto', (None, b'x', ('127.0.0.1', 1234)))]:
            with self.subTest(name=name):
                # The active method is already a no-network mock. Nest the
                # guard over a mock underlay to prove the guard intercepts it.
                with patch.object(loop, name, return_value=None) as underlay:
                    with network_guard(loop), self.assertRaises(NetworkForbidden):
                        await getattr(loop, name)(*args)
                    underlay.assert_not_called()

    async def test_http_provider_cannot_escape(self):
        if importlib.util.find_spec('httpx') is not None:
            import httpx
            with patch('httpx.Client.send', return_value=None) as sync_underlay, patch('httpx.AsyncClient.send', return_value=None) as async_underlay:
                with network_guard(asyncio.get_running_loop()):
                    with httpx.Client() as client, self.assertRaises(NetworkForbidden):
                        client.get('https://example.invalid')
                    async with httpx.AsyncClient() as client:
                        with self.assertRaises(NetworkForbidden):
                            await client.get('https://example.invalid')
                sync_underlay.assert_not_called()
                async_underlay.assert_not_called()
        # Always exercise the application provider boundary using a synthetic
        # key, even in runners with a lightweight SDK and no HTTPX installation.
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'synthetic-not-a-secret'}):
            from ai.matcher import match_resume_to_job_ai
            with patch('ai.openrouter_client.OpenAI') as factory:
                factory.return_value.chat.completions.create.side_effect = NetworkForbidden('Provider forbidden')
                with self.assertRaises(NetworkForbidden):
                    match_resume_to_job_ai({}, 'Python')
                factory.return_value.chat.completions.create.assert_called_once()

    async def test_framework_wakeup_and_tasks_work(self):
        loop = asyncio.get_running_loop()
        ready = asyncio.Event()
        await asyncio.to_thread(loop.call_soon_threadsafe, ready.set)
        await ready.wait()
        task = asyncio.create_task(asyncio.sleep(0, result='executed'))
        self.assertEqual(await task, 'executed')
        self.assertTrue(task.done())
