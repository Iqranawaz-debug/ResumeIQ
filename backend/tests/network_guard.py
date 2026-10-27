"""Offline test boundaries; install after IsolatedAsyncioTestCase creates its loop."""
import asyncio
import importlib.util
import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import patch


class NetworkForbidden(AssertionError):
    pass


@contextmanager
def network_guard(loop=None):
    """Block application networking without intercepting existing wakeup writes.

    No localhost exception. Async loop methods cover Windows IOCP operations
    that can bypass socket.connect. HTTP guards stop provider requests before
    transport, including accidentally reused connected clients.
    """
    with ExitStack() as stack:
        targets = ['socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.socket.sendto', 'socket.create_connection',
                       'socket.getaddrinfo', 'socket.gethostbyname',
                       'socket.gethostbyname_ex', 'socket.gethostbyaddr',
                       'socket.getnameinfo', 'http.client.HTTPConnection.connect']
        if importlib.util.find_spec('httpx') is not None:
            targets += ['httpx.Client.send', 'httpx.AsyncClient.send']
        for target in targets:
            stack.enter_context(patch(target, side_effect=NetworkForbidden('Network forbidden in tests')))
        if loop is not None:
            for name in ('create_connection', 'create_datagram_endpoint', 'sock_connect', 'sock_sendto'):
                stack.enter_context(patch.object(loop, name, side_effect=NetworkForbidden('Network forbidden in tests')))
        yield


class OfflineTestCase(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(network_guard())


class OfflineAsyncTestCase(unittest.IsolatedAsyncioTestCase):
    def run(self, result=None):
        # Keep protection through runner shutdown, including task cancellation
        # and async-generator finalizers, not only TestCase cleanups.
        with ExitStack() as self._network_contexts:
            return super().run(result)

    def setUp(self):
        super().setUp()
        # unittest initializes and sets the loop before synchronous setUp.
        self._network_contexts.enter_context(network_guard(asyncio.get_event_loop()))
