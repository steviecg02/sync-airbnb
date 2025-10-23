import logging
import os

from sync_airbnb.config import LOG_LEVEL

try:
    import coloredlogs
except ImportError:
    coloredlogs = None

LOG_FORMAT = "[%(asctime)s] %(levelname)s in %(name)s:%(lineno)d: %(message)s"


def setup_logging(level: str = LOG_LEVEL):
    """
    Set up root logger and optionally install coloredlogs if in dev.
    """
    logging.basicConfig(level=level.upper(), format=LOG_FORMAT)

    # Optional: Use colored logs locally
    if coloredlogs and os.path.exists(".env"):
        coloredlogs.install(level=level.upper(), fmt=LOG_FORMAT)

    # Suppress noisy third-party libraries
    for noisy in ["urllib3", "requests", "sqlalchemy.engine", "botocore"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
