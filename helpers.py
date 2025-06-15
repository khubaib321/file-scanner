import time as _time
import functools as _ft
from typing import Callable

def time_it() -> Callable:
    """
    Decorator that measures and prints execution time of a function.
    """

    def decorator(func):
        @_ft.wraps(func)
        def wrapper(*args, **kwargs):
            _args = ", ".join(f"'{str(a)}'" for a in args)
            print(f"⏱️ {func.__name__}({_args}): ", end="", flush=True)

            start_time = _time.time()
            result = func(*args, **kwargs)
            end_time = _time.time()
            
            execution_time = end_time - start_time
            print(f"{execution_time:.3f} seconds")
            
            return result

        return wrapper

    return decorator
