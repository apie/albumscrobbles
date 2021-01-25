# Simple file cache for functions that return a string
# By Apie
# 2020-12-05
import os
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

try:
    # Local cache used for testing. To use it, create this subdir.
    SUBDIR = Path('cache')
    assert SUBDIR.exists()
except AssertionError:
    # Default cache location
    SUBDIR = Path('/tmp/albumscrobbles')

def get_filename(*args):
    # Truncate filename to a max length
    filename = '-'.join(arg.replace('/','-') for arg in args if arg)[:200]
    return filename or 'empty'

def get_from_cache(*args, func_name, keep_days=None) -> str:
    filename = SUBDIR / Path(f"{func_name}/{get_filename(*args)}")
    # print(f"Getting {func_name} from file cache: {args} {keep_days}")
    if keep_days and datetime.fromtimestamp(filename.stat().st_mtime)+timedelta(days=keep_days) < datetime.now():
        print(f'Cache expired. Removing file. {func_name} {args}')
        os.remove(filename)
    with open(filename) as f:
        # print(f'Found in cache {func_name} {args}')
        return f.read()

def update_cache(*args, func_name, result: str):
    assert isinstance(result, str), f'Cache can only be used for string results! Not for {type(result)}'
    # print(f"Updating {func_name} in file cache: {args} {result}")
    path = SUBDIR / Path(func_name)
    path.mkdir(parents=True, exist_ok=True)
    with open(path / Path(get_filename(*args)), "w") as f:
        f.write(result)

def file_cache_decorator(keep_days=None):
    def inner(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return get_from_cache(*args, **kwargs, func_name=func.__name__, keep_days=keep_days)
            except (FileNotFoundError, IsADirectoryError):
                result = func(*args, **kwargs)
                update_cache(*args, **kwargs, func_name=func.__name__, result=result)
                return result
        return wrapper
    return inner