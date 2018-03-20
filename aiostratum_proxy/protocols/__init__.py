import asyncio
import binascii
from collections import deque, OrderedDict
import logging
import struct

from aiojsonrpc2 import ServerProtocol, ClientProtocol

from ..errors import *

logger = logging.getLogger(__name__)


class BaseWorkerProtocol(ServerProtocol):
    pool = None
    pool_watchdog_fut = None

    registered_extra_nonce1_tails = set()

    # we'll optionally track the most recent n shares/solutions
    # for duplicate detection; this needs to be 'enabled' in
    # hook_validate_share_params by adding 'unique' data to be
    # checked (which likely differs by algo/coin)
    recent_shares = deque(maxlen=500)

    def __init__(self, proxy, connection_settings, *args, **kwargs):
        self.proxy = proxy
        self.settings = kwargs
        self.log_prefix = 'W:{}:'.format(self.proxy.name)

        super().__init__(connection_settings)

        mw = self.settings.get('max_workers')
        if mw is None:
            self.max_workers = 256
            logger.info("{} defaulting to {} max workers".format(self.log_prefix, mw, self.max_workers))
        else:
            try:
                self.max_workers = int(mw)
                if self.max_workers not in [1, 256, 65536]:
                    raise ValueError
            except (ValueError, TypeError):
                self.max_workers = 256
                logger.warning("{} invalid 'max_workers' setting ({}), defaulting to {} instead".format(self.log_prefix, mw, self.max_workers))

        if self.max_workers != 1:
            logger.info("{} up to {} workers supported (distinct nonce spaces)".format(self.log_prefix, self.max_workers))
        else:
            logger.info("{} solo worker mode (single nonce space)".format(self.log_prefix, self.max_workers))

    async def pool_watchdog(self):
        while not self.stopping:
            await asyncio.sleep(1)

            # only try to reconnect to the pool if we have existing client
            # connections
            if len(self.clients) and not self.pool.connected:
                while True:
                    try:
                        await self.pool.connect()
                        break
                    except:
                        if self.stopping:
                            return
                        await self.pool.use_next_pool_config()

                await self.pool.initialize()
                self.pool.set_ready()

    async def initialize(self):
        self.pool = self.proxy.pool
        self.pool_watchdog_fut = asyncio.ensure_future(self.pool_watchdog())

    async def loop(self, connection):
        if not self.pool.connected or not self.pool.is_ready():
            self.recent_shares.clear()

            # wait until the pool is subscribed, authorized, etc
            await self.pool.wait_until_ready()

        try:
            connection.extra['extra_nonce1_tail'] = self.get_extra_nonce1_tail()
        except MaxClientsConnected:
            await self.close_connection(connection)
            # connection.close()
            # self.client_connections.remove(connection)
            # self.cleanup_connection(connection)
            logger.warning("{} maximum number of {} workers reached, disconnecting".format(
                self.log_prefix, len(self.clients)))
            return

        connection.extra['subscriptions'] = {}

        await super().loop(connection)

    def cleanup_connection(self, connection):
        tail = connection.extra.get('extra_nonce1_tail')
        if tail:
            try:
                self.registered_extra_nonce1_tails.remove(tail)
            except:
                pass

    async def close(self):
        await super().close()
        await self.pool_watchdog_fut

    def get_extra_nonce1_tail(self):
        if self.max_workers != 1:
            if self.max_workers == 65536:
                # 2 bytes allows for 65536 (0000 through FFFF)
                _format = '>H'
            else:
                # 1 byte allows for 256 workers (00 through FF)
                _format = '>B'

            for i in range(0, self.max_workers):
                tail = binascii.hexlify(struct.pack(_format, i)).decode('ascii')

                if tail not in self.registered_extra_nonce1_tails:
                    self.registered_extra_nonce1_tails.add(tail)
                    return tail

            raise MaxClientsConnected


class BasePoolProtocol(ClientProtocol):
    workers = None

    pool_configs = []

    ready = asyncio.Event()

    subscriptions = {}
    extra_nonce1 = None
    extra_nonce2_size = None

    target_difficulty = None

    jobs = OrderedDict()
    current_job = None

    authorized_workers = {}
    unauthorized_workers = set()

    def __init__(self, proxy, connection_settings, *args, **kwargs):
        self.proxy = proxy
        self.settings = kwargs

        if isinstance(connection_settings, dict):
            self.pool_configs = [connection_settings]
        else:
            self.pool_configs = connection_settings

        self.log_prefix = 'P:{}:'.format(self.proxy.name)
        # start things up with the first pool configuration in the list!
        super().__init__(self.pool_configs.pop(0))

    async def use_next_pool_config(self):
        # If we get here, there was a pool disconnection and we should
        # try the next pool and/or exponentially back off our reconnection
        # attempts (local internet disconnection, perhaps???)

        # reset the ready indicator
        self.ready.clear()

        try:
            next_config = self.pool_configs.pop(0)
        except IndexError:
            # There wasn't another pool configuration available (no fallback pool!)
            next_config = None

            # No other pool to connect to, so let's wait a few seconds and
            # try to reconnect to the current and only pool settings
            logger.warning("{} waiting 10 seconds before reconnecting to current pool".format(self.log_prefix))
            await asyncio.sleep(10)

        if next_config:
            # Store the current (disconnected) config back in our pool config list
            self.pool_configs.append(self.connection_settings)
            # Switch to the next config!
            self.set_connection_config(next_config)

    async def initialize(self):
        self.workers = self.proxy.workers

    def is_ready(self):
        return self.ready.is_set()

    def set_ready(self):
        if not self.ready.is_set():
            self.ready.set()

    async def wait_until_ready(self):
        await self.ready.wait()

    def set_extra_nonce_data(self, extra_nonce1, extra_nonce2_size=None):
        self.extra_nonce1 = extra_nonce1
        self.extra_nonce2_size = extra_nonce2_size

    async def loop(self, connection):
        await super().loop(connection)

        if not self.stopping:
            # All client connections will need to be closed so they
            # auto-reconnect to resubscribe for the new nonce, etc
            await self.workers.close_all_connections()

            self.jobs.clear()
            self.current_job = None

            self.authorized_workers.clear()
            self.unauthorized_workers.clear()

            await self.use_next_pool_config()

    # async def _DELETE_THIS_test_method(self):
    #     await asyncio.sleep(4)
    #     logger.critical("{} kill connection for testing purposes".format(self.log_prefix))
    #     if self.connected:
    #         await self.connection.close()
    #         self.cleanup_connection(self.connection)
    #         self.connection = None
    #
    # # TODO DELETE this override
    # async def connect(self):
    #     await super().connect()
    #     asyncio.ensure_future(self._DELETE_THIS_test_method())
