import tomllib
from pathlib import Path
import functools
import asyncio
import sys
import time
import logging
import shelve

_logger = logging.getLogger(__name__)


def load_kvdb():
    file_name = Path(sys.argv[0]).stem
    db_path = Path(f"./db/{file_name}.db")
    db_path.parent.mkdir(exist_ok=True)
    db = shelve.open(db_path, writeback=True)

    return db


def load_config() -> dict[str]:
    # 获取入口文件的文件名
    file_name = Path(sys.argv[0]).stem

    toml_file = Path("config.toml")
    with toml_file.open("rb") as f:
        cfg = tomllib.load(f)
    return cfg[file_name]


def retry(retry_time=3, delay=1, catch_exceptions=(Exception,)):
    def decorator(f):
        @functools.wraps(f)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for i in range(retry_time):
                try:
                    return await f(*args, **kwargs)
                except catch_exceptions as e:
                    _logger.warning(f"Attempt {f.__name__} {i+1} failed with error: {e}")
                    last_exception = e
                    await asyncio.sleep(delay)
            if last_exception:
                raise last_exception

        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for i in range(retry_time):
                try:
                    return f(*args, **kwargs)
                except catch_exceptions as e:
                    _logger.warning(f"Attempt {f.__name__} {i+1} failed with error: {e}")
                    last_exception = e
                    time.sleep(delay)  # sleep synchronously
            if last_exception:
                raise last_exception

        if asyncio.iscoroutinefunction(f):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def async_thread(func):
    """
    Decorator to run a function in a separate thread.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

    return wrapper


# Decorator to limit the number of concurrent tasks
def limit_async(num=5):
    semaphore = asyncio.Semaphore(num)

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Acquire semaphore before calling the actual function
            async with semaphore:
                return await func(*args, **kwargs)

        return wrapper

    return decorator
