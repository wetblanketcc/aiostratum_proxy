import argparse
import asyncio
import logging

from aiojsonrpc2 import logger as jsonrpc_logger
import yaml

from . import app_version, logger as module_logger
from .errors import *
from .utils import import_from_module


logger = logging.getLogger(__name__)


class Proxy(object):
    def __init__(self, name='', **kwargs):
        self.name = name

        self.settings = kwargs
        self.pool_settings = kwargs.get('pools') or []
        if isinstance(self.pool_settings, dict):
            self.pool_settings = [self.pool_settings]

    async def startup(self):
        try:
            wklass = import_from_module(self.settings.get('worker_class') or '')
            pklass = import_from_module(self.settings.get('pool_class') or '')
        except (ModuleNotFoundError, AttributeError) as e:
            raise ConfigurationError(e)

        logger.info("* {} proxy starting".format(self.name))

        self.workers = wklass(self, self.settings.get('listen'), **self.settings)
        self.pool = pklass(self, self.pool_settings, **self.settings)

        await self.workers.initialize()
        await self.workers.start_listening()

        logger.info("* {} proxy started, waiting for worker connections".format(self.name))

    async def shutdown(self):
        logger.info("* {} proxy stopping".format(self.name))

        await self.workers.close()
        await self.pool.close()

        logger.info("* {} proxy stopped".format(self.name))


class Application(object):
    proxies = {}
    config = {}

    def __init__(self, config_file):
        self.config_file = config_file

    async def startup(self):
        try:
            with open(self.config_file, 'r') as cf:
                self.config = yaml.load(cf.read())
        except Exception:
            raise ConfigurationError("Unable to load configuration file")

        for n, settings in enumerate(self.config.get('proxies', []), 1):
            name = settings.pop('name', '') or 'Proxy {}'.format(n)
            proxy = Proxy(name=name, **settings)
            if proxy.name in self.proxies:
                raise ConfigurationError('A proxy named "{}" already exists; check config file'.format(proxy.name))

            try:
                await proxy.startup()
            except OSError as e:
                await proxy.shutdown()
                raise ServerAddressInUse(e)

            self.proxies[proxy.name] = proxy

    async def shutdown(self):
        await asyncio.gather(*[p.shutdown() for p in self.proxies.values()])
        self.proxies.clear()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", "--generate-config", action="store_true",
                        help="output a starting config file template")
    parser.add_argument("-c", "--config", dest="config_file",
                        help="path to configuration file")
    parser.add_argument("-q", "--quiet", action="store_true",
                        help="minimum output verbosity (>=WARNING)")
    parser.add_argument("-l", "--loud", action="store_true",
                        help="maximum output verbosity (>=DEBUG)")
    parser.add_argument("-v", "--version", action="version", version=app_version)
    args = parser.parse_args()

    if args.generate_config:
        from .utils import output_config
        output_config()
        return

    if args.loud:
        logf = logging.Formatter('%(asctime)s %(levelname)8s - %(message)s (%(name)s:%(lineno)d)')
    else:
        logf = logging.Formatter('%(asctime)s %(levelname)8s - %(message)s')

    logh = logging.StreamHandler()
    logh.setFormatter(logf)

    module_logger.addHandler(logh)
    jsonrpc_logger.addHandler(logh)
    module_logger.setLevel(logging.INFO)
    jsonrpc_logger.setLevel(logging.INFO)

    if args.loud:
        logger.info('* Verbose mode enabled')
        module_logger.setLevel(logging.DEBUG)
        jsonrpc_logger.setLevel(logging.DEBUG)
    elif args.quiet:
        logger.info('* Quiet mode enabled')
        module_logger.setLevel(logging.WARNING)
        jsonrpc_logger.setLevel(logging.WARNING)

    app = Application(args.config_file)

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(app.startup())
        running = True
    except (ServerAddressInUse, ConfigurationError) as e:
        logger.critical(str(e))
        running = False

    if running:
        # Serve requests until Ctrl+C
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass

    loop.run_until_complete(app.shutdown())
    loop.close()
