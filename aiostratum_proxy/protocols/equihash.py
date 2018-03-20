import logging

from .. import app_version
from ..errors import *
from .stratum import BaseStratumPoolProtocol, BaseStratumWorkerProtocol

logger = logging.getLogger(__name__)


class EquihashWorkerProtocol(BaseStratumWorkerProtocol):
    async def hook_post_subscribe(self, connection):
        # checks around these to ensure the first miner connecting doesn't get
        # sent these notification before the pool sends this proxy the initial
        # values for them! (otherwise, we send junk values)
        if self.pool.target_difficulty is not None:
            await connection.rpc('mining.set_target', [self.pool.target_difficulty], is_notification=True)
        if self.pool.current_job is not None:
            await connection.rpc('mining.notify', self.pool.current_job, is_notification=True)

    async def hook_validate_share_params(self, connection, params):
        if len(params) == 5:
            # account_name, job_id, time, nonce2, equihash_solution
            job_id = params[1]

            # handle the distinct nonce spacing by prepending the nonce1
            # tail to the nonce2 from the worker
            nonce2 = connection.extra['extra_nonce1_tail'] + params[-2]
            params[-2] = nonce2

            if job_id not in self.pool.jobs:
                raise JSONRPCJobNotFound

            check = (job_id, nonce2)
            if check in self.recent_shares:
                raise JSONRPCDuplicateShare

            self.recent_shares.append(check)

            return params

        raise JSONRPCInvalidParams


class EquihashPoolProtocol(BaseStratumPoolProtocol):
    async def hook_subscription_request_params(self):
        return [
            app_version,
            self.subscriptions.get('mining.notify'),
            self.connection_settings.get('host'),
            self.connection_settings.get('port')
        ]

    # async def hook_extra_nonce2_size(self):
    #     return 32 - len(self.extra_nonce1) / 2

    async def hook_validate_job_params(self, params):
        # normally only 8 params, some pools send another bool at the end
        if len(params) in (8, 9):
            # job_id, version, prevhash, merkleroot, reserved, time, bits, clean_jobs
            job_id, job_version = params[:2]

            # 04000000: zcash, other equihash derivatives;
            # 00000020: bitcoin gold, zencash
            if job_version in ["04000000", "00000020"]:
                clean_jobs = params[7]
                return job_id, clean_jobs

        raise JSONRPCInvalidParams

