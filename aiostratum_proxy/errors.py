from aiojsonrpc2.errors import *


class AIOStratumError(Exception):
    pass


class ConfigurationError(AIOStratumError):
    pass


class NetworkError(AIOStratumError):
    pass


class ServerAddressInUse(NetworkError):
    pass


class MaxClientsConnected(AIOStratumError):
    pass


class JSONRPCOtherUnknownError(JSONRPCError):
    def __init__(self, msg=''):
        super().__init__(20, msg or "Other/Unknown")


class JSONRPCJobNotFound(JSONRPCError):
    def __init__(self, msg=''):
        super().__init__(21, msg or "Job not found (=stale)")


class JSONRPCDuplicateShare(JSONRPCError):
    def __init__(self, msg=''):
        super().__init__(22, msg or "Duplicate share")


class JSONRPCLowDifficultyShare(JSONRPCError):
    def __init__(self, msg=''):
        super().__init__(23, msg or "Low difficulty share")


class JSONRPCUnauthorizedWorker(JSONRPCError):
    def __init__(self, msg=''):
        super().__init__(24, msg or "Unauthorized worker")


class JSONRPCNotSubscribed(JSONRPCError):
    def __init__(self, msg=''):
        super().__init__(25, msg or "Not subscribed")
