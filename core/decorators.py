"""Custom utility decorators for execution performance timing and transient error retries.
"""

from __future__ import annotations

import functools
import time
from typing import Any, Callable, TypeVar
from config.settings import logger

F = TypeVar("F", bound=Callable[..., Any])


def timed(func: F) -> F:
    """Decorator to measure and log execution duration in milliseconds."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info("Executed %s in %d ms", func.__qualname__, elapsed_ms)

    return wrapper  # type: ignore[return-value]


def retry(
    max_attempts: int = 3,
    delay: float = 0.5,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """Decorator to retry a function call with exponential backoff on specified exceptions."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        logger.error(
                            "Failed %s after %d attempts: %s",
                            func.__qualname__,
                            max_attempts,
                            exc,
                        )
                        raise
                    logger.warning(
                        "Attempt %d/%d for %s failed (%s). Retrying in %.2fs...",
                        attempt,
                        max_attempts,
                        func.__qualname__,
                        exc,
                        current_delay,
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper  # type: ignore[return-value]

    return decorator
