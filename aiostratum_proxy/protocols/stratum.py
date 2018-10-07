import asyncio
import logging

from .. import app_version
from ..errors import *
from . import BaseWorkerProtocol, BasePoolProtocol

logger = logging.getLogger(__name__)


class BaseStratumWorkerProtocol(BaseWorkerProtocol):
    async def hook_get_subscription_response_params(self, connection):
        extra_nonce1_tail = connection.extra.get('extra_nonce1_tail') or ''

        # `None` here because we don't need to support resuming subscriptions
        params = [None, self.pool.extra_nonce1 + extra_nonce1_tail]

        # if self.pool.extra_nonce2_size is `None`, it's a stratum-like
        # protocol that doesn't pass it around (ie. zcash & derivatives)
        if self.pool.extra_nonce2_size is not None:
            params.append(int(self.pool.extra_nonce2_size - len(extra_nonce1_tail) / 2))

        return params

    async def hook_validate_share_params(self, connection, params):
        logger.warning("{} hook_validate_share_params not implemented".format(self.log_prefix))
        # - Without an implementation in here, it's possible to have stale,
        # duplicate, or unauthorized shares submitted to the pool.
        # - Share submission differs enough between coins, making a default
        # implementation here problematic at best
        return params

    async def hook_post_subscribe(self, connection):
        logger.warning("{} hook_post_subscribe not implemented".format(self.log_prefix))
        # - This hook most likely needs to be implemented for most coin
        # protocol communication; sending mining.notify, etc to clients
        # - Coin protocol implementations differ enough to make this
        # problematic

    async def handle_mining_subscribe(self, connection, params, **kwargs):
        asyncio.ensure_future(self.hook_post_subscribe(connection))
        return await self.hook_get_subscription_response_params(connection)

    async def handle_mining_authorize(self, connection, params, **kwargs):
        if len(params) == 2:
            account_name, account_password = params
        elif len(params) == 1:
            account_name, = params
            account_password = ''
        else:
            raise JSONRPCInvalidParams

        # possible future auth ideas:
        # - proxy settings define the auth user/pass params for the pool connection
        #   - but enforce worker user/pass auth through local proxy settings (so not just anyone can join)
        #   - or allow any auth to proxy from miner/worker
        # - proxy settings allow the miner/worker to pass-thru user/pass to the pool; in this case,
        #   we'd store if the user was already authed
        #   - multiple miners can use the same user/pass OR use separate credentials

        return await self.pool.authorize(account_name, account_password)

    async def handle_mining_submit(self, connection, params, **kwargs):
        params = await self.hook_validate_share_params(connection, params)
        return await self.pool.submit(params)

    # async def handle_mining_extranonce_subscribe(self, connection, params, **kwargs):
    #     connection.extra['subscriptions']['mining.extranonce.subscribe'] = True
    #     return True
    #
    # async def handle_mining_suggest_difficulty(self, connection, params, **kwargs):
    #     pass
    #
    # async def handle_mining_suggest_target(self, connection, params, **kwargs):
    #     pass
    #
    # this one is also shown as unsupported in original stratum-mining-proxy?
    # async def handle_mining_get_transactions(self, connection, params, **kwargs):
    #     pass


class BaseStratumPoolProtocol(BasePoolProtocol):
    async def initialize(self):
        await super().initialize()

        await self.subscribe()
        await self.extranonce_subscribe()

    async def hook_subscription_request_params(self):
        # This is in its own method to allow subclassing for future coins.
        return []

    # async def hook_extra_nonce2_size(self):
    #     # This is in its own method to allow subclassing for future coins.
    #     # `extra_nonce2_size` isn't supported by some coins' mining.subscribe
    #     # (zcash, zclassic, etc), so calculate it differently by overriding
    #     # this method in a derived class
    #     return self.extra_nonce2_size

    async def hook_validate_job_params(self, params):
        logger.warning("{} hook_validate_job_params not implemented".format(self.log_prefix))

        # a good default is to return the job id and whether to clean old jobs
        # most stratum-based protocols seem to have job id first and clean_jobs last
        return params[0], params[-1]

    async def hook_set_target(self, params):
        try:
            self.target_difficulty = params[0]
        except IndexError:
            raise JSONRPCInvalidParams

    async def subscribe(self):
        response = await self.connection.rpc('mining.subscribe', await self.hook_subscription_request_params())
        if not response.success:
            logger.warning('{} mining.subscribe response error code {}, message "{}"'.format(
                self.log_prefix, response.data.get('code'), response.data.get('msg')))
            return False

        extra_nonce2_size = None
        subscriptions, extra_nonce1 = response.data[:2]
        if len(response.data) > 2:
            extra_nonce2_size = response.data[2]

        # if subscriptions is empty/None, then the pool doesn't support subscriptions
        if subscriptions:
            if isinstance(subscriptions, list):
                if isinstance(subscriptions[0], list):
                    # Some coins pass back a list of two-item subscription methods/ids
                    # pairs ie. [[m1, id1], [m2, id2]] includes mining.notify
                    for _method, _id in subscriptions:
                        self.subscriptions[_method] = _id
                else:
                    # Some coins pass back a list containing a single method/id
                    # pairs ie. [m1, id1] - it should be just mining.notify
                    self.subscriptions[subscriptions[0]] = subscriptions[1]
            else:
                # Some coins pass back just the subscription id for mining.notify
                # ie. id1 (like zcash, zclassic)
                self.subscriptions['mining.notify'] = subscriptions

        if extra_nonce1 != self.extra_nonce1:
            self.set_extra_nonce_data(extra_nonce1, extra_nonce2_size)
            # TODO: ensure all clients get updated nonces, etc - reset 'jobs'

        return True

    async def extranonce_subscribe(self):
        if self.settings.get('extranonce_subscribe', False):
            try:
                # use a timeout here because some pools (eg. MPOS??) don't reply to this
                # JSONRPC request (even though it's NOT a JSONRPC notification); 3 seconds
                # ought to be enough
                response = await self.connection.rpc('mining.extranonce.subscribe', timeout=5)
                return response.success and response.data
            except:
                logger.info("{} pool doesn't support 'mining.extranonce.subscribe'".format(self.log_prefix))
        return False

    def is_authorized(self, account_name, account_password):
        if account_name in self.authorized_workers:
            return self.authorized_workers.get(account_name) == account_password
        return False

    def get_auth_params(self, miner_account_name, miner_account_password):
        paccount_name = self.connection_settings.get('account_name', '')
        paccount_password = self.connection_settings.get('account_password', '')
        if not paccount_name:
            logger.error("{} no pool credentials (account name/password) are set".format(self.log_prefix))

        # If the pool's auth account doesn't specify a worker name, then
        # try to get and append one from the miner's params
        if '.' not in paccount_name:
            try:
                worker_name = miner_account_name.rsplit('.', 1)[1]
            except IndexError:
                worker_name = ''

            # concatenate the worker name to the pool's
            paccount_name = ".".join([s for s in [paccount_name, worker_name] if len(s)])

        return paccount_name, paccount_password

    async def authorize(self, account_name, account_password):
        paccount_name, paccount_password = self.get_auth_params(account_name, account_password)

        if self.is_authorized(paccount_name, paccount_password):
            return True

        result = False
        if paccount_name and paccount_name not in self.unauthorized_workers:
            response = await self.connection.rpc('mining.authorize', [paccount_name, paccount_password])
            if response.success:
                result = response.data
                if result:
                    self.authorized_workers[paccount_name] = paccount_password
                else:
                    logger.warning("{} pool authorization denied".format(self.log_prefix))
                    self.unauthorized_workers.add(paccount_name)

        return result

    async def submit(self, params):
        # params[0] is the account_name from the miner, 'translate'
        # it as necessary to the account name we need for the pool
        paccount_name, paccount_password = self.get_auth_params(params[0], '')

        if not self.is_authorized(paccount_name, paccount_password):
            raise JSONRPCUnauthorizedWorker

        params[0] = paccount_name

        logger.debug('{} mining.submit params sent to pool {}'.format(self.log_prefix, params))
        response = await self.connection.rpc('mining.submit', params)
        return response.success and response.data

    async def handle_mining_notify(self, connection, params, **kwargs):
        job_id, clean_jobs = await self.hook_validate_job_params(params)
        if job_id:
            if clean_jobs:
                # TODO: abandon/clean all current jobs
                self.jobs.clear()

            self.current_job = params
            self.jobs[job_id] = params

            # only keep the last 3 jobs around for handling older job share submits
            while len(self.jobs) > 3:
                # get the first job key-value pair and remove it from the jobs
                # as it will be an old job that shouldn't be worked on anymore
                k, v = next(iter(self.jobs.items()))
                self.jobs.pop(k)

            await self.workers.broadcast('mining.notify', params, is_notification=True)

    async def handle_mining_set_target(self, connection, params, **kwargs):
        await self.hook_set_target(params)
        await self.workers.broadcast('mining.set_target', params, is_notification=True)

    async def handle_mining_set_difficulty(self, connection, params, **kwargs):
        # TODO: add another hook for hook_set_difficulty if it
        # needs to be treated differently at the proxy level
        await self.hook_set_target(params)
        await self.workers.broadcast('mining.set_difficulty', params, is_notification=True)

    async def handle_client_get_version(self, connection, params, **kwargs):
        return app_version

    async def handle_client_show_message(self, connection, params, **kwargs):
        if len(params) != 1:
            raise JSONRPCInvalidParams
        await self.workers.broadcast('client.show_message', params)

    async def handle_mining_set_extranonce(self, connection, params, **kwargs):
        if len(params) != 2:
            raise JSONRPCInvalidParams

        self.set_extra_nonce_data(*params[:2])

        for conn in self.workers.clients.keys():
            # has the user subscribed to receive new extranonce notifications?
            if conn.extra.get('subscriptions', {}).get('mining.extranonce.subscribe'):
                tail = conn.extra.get('extra_nonce1_tail')
                if tail:
                    # copy the params...
                    _p = params[:]

                    # ... so we can add the connection's nonce 'tail' on (maintains
                    # distinct nonce spaces between multiple workers)
                    _p[0] = _p[0] + tail

                    # extra_nonce2_size is only set if the coin/algo supports it
                    # (eg. zcash/zclassic do not)
                    if self.extra_nonce2_size is not None:
                        _p[1] = int(self.extra_nonce2_size - len(tail) / 2)

                    await conn.rpc('mining.set_extranonce', _p, True)
            else:
                # Need to drop worker connections that aren't able (haven't subscribed!)
                # to receive new extranonce values? So they'll reconnect...
                self.workers.close_connection(conn)

    # async def handle_client_reconnect(self, connection, params, **kwargs):
    #     pass
    #
    # async def handle_client_add_peers(self, connection, params, **kwargs):
    #     pass
    #
    # async def handle_mining_get_hashrate(self, connection, params, **kwargs):
    #     pass
    #
    # async def handle_mining_get_temperature(self, connection, params, **kwargs):
    #     pass


class StratumWorkerProtocol(BaseStratumWorkerProtocol):
    # TODO: need to implement hooks; these are for bitcoin, litecoin, etc,  I believe?
    pass


class StratumPoolProtocol(BaseStratumPoolProtocol):
    # TODO: need to implement hooks; these are for bitcoin, litecoin, etc,  I believe?
    pass
