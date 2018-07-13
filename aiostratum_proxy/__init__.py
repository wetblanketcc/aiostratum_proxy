import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__appname__ = __package__.replace('_', '-')
__version__ = "1.0.2"

app_version = "{}/{}".format(__appname__, __version__)
