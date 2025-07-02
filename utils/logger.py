import logging

def setup_logging(level=logging.INFO):
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
    )

    # Suppress noisy lower-level logs from libraries we use
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    # If using httpx or boto3 or other chatty libs in the future, you can add:
    # logging.getLogger("httpx").setLevel(logging.WARNING)
    # logging.getLogger("botocore").setLevel(logging.WARNING)
