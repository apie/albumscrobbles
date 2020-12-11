# Simple file cache for functions that return a string
# By Apie
# 2020-12-05
from pathlib import Path

SUBDIR = 'albumscrobbles'

def get_filename(*args):
    return '-'.join(arg.replace('/','-') for arg in args)

def get_from_cache(*args, func, keep_days=None) -> str:
    #TODO implement keep_days
    # print(f"getting {func} from cache: {args} {keep_days}")
    with open(f"/tmp/{SUBDIR}/{func}/{get_filename(*args)}") as f:
        return f.read()

def update_cache(*args, func, result: str):
    assert isinstance(result, str), f'Cache can only be used for string results! Not for {type(result)}'
    print(f"updating {func} in cache: {args} {result}")
    path = Path(f"/tmp/{SUBDIR}/{func}")
    path.mkdir(parents=True, exist_ok=True)
    with open(path / Path(get_filename(*args)), "w") as f:
        f.write(result)

def file_cache_decorator(keep_days=None):
    def inner(func):
        def wrapper(*args, **kwargs):
            try:
                return get_from_cache(*args, **kwargs, func=func.__name__, keep_days=keep_days)
            except FileNotFoundError:
                result = func(*args, **kwargs)
                update_cache(*args, **kwargs, func=func.__name__, result=result)
                return result
        return wrapper
    return inner