import logfire, logging
from fastapi import FastAPI
from configs.config import get_settings

settings = get_settings()

logfire.configure(token=settings.api_keys.logfire.get_secret_value(), environment=settings.app_config.logfire_env) # type: ignore
logging.basicConfig(handlers=[logfire.LogfireLoggingHandler(level=logging.DEBUG)]) # type: ignore

def init_logging(app: FastAPI):
    logfire.instrument_fastapi(app, capture_headers=True) # type: ignore


def setup_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    return logger