"""Custom decorators for timing execution and retrying transient operations.

Used across extractors, database queries, and external API requests.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, TypeVar

from config.settings import logger

F = TypeVar("F", bound=Callable[..., Any])


def timed(func: F) -> F:
    """Measure and log the execution time of a callable.

    Args:
        func: The function or method to be timed.

    Returns:
        Callable: The wrapped function that logs elapsed runtime.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        func_name = getattr(func, "__qualname__", func.__name__)
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed = time.perf_counter() - start_time
            logger.info("Executed %s in %.3f seconds", func_name, elapsed)

    return wrapper  # type: ignore[return-value]


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator to retry a function upon catching specified exceptions.

    Args:
        max_attempts: Maximum number of execution tries before re-raising.
        delay_seconds: Initial wait time in seconds before first retry.
        backoff_factor: Multiplier applied to delay after each retry attempt.
        exceptions: Tuple of exception classes that trigger a retry.

    Returns:
        Callable decorator wrapping the target function.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay_seconds
            func_name = getattr(func, "__qualname__", func.__name__)

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        logger.error(
                            "Failed %s after %d attempts. Error: %s",
                            func_name,
                            attempt,
                            exc,
                        )
                        raise
                    logger.warning(
                        "Attempt %d/%d for %s failed with %s: %s. Retrying in %.1fs...",
                        attempt,
                        max_attempts,
                        func_name,
                        exc.__class__.__name__,
                        exc,
                        current_delay,
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff_factor

        return wrapper  # type: ignore[return-value]

    return decorator
