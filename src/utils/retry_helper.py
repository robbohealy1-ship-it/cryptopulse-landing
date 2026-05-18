import asyncio
import functools
from typing import Callable, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for async functions to retry on failure with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        exceptions: Tuple of exceptions to catch and retry
    
    Example:
        @async_retry(max_attempts=3, base_delay=1.0)
        async def fetch_data():
            # Your code here
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        # Calculate delay with exponential backoff
                        delay = min(
                            base_delay * (exponential_base ** attempt),
                            max_delay
                        )
                        
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
            
            # If we get here, all attempts failed
            raise last_exception
        
        return wrapper
    return decorator


class RetryHelper:
    """
    Helper class for retry logic with various strategies.
    """
    
    @staticmethod
    async def retry_with_backoff(
        func: Callable,
        *args,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        **kwargs
    ) -> Any:
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Async function to retry
            *args: Positional arguments for func
            max_attempts: Maximum retry attempts
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            **kwargs: Keyword arguments for func
        
        Returns:
            Result from successful function call
        
        Raises:
            Last exception if all attempts fail
        """
        last_exception = None
        
        for attempt in range(max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < max_attempts - 1:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Waiting {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
        
        raise last_exception
    
    @staticmethod
    async def retry_on_condition(
        func: Callable,
        condition: Callable[[Any], bool],
        *args,
        max_attempts: int = 3,
        delay: float = 1.0,
        **kwargs
    ) -> Any:
        """
        Retry a function until a condition is met.
        
        Args:
            func: Async function to retry
            condition: Function that returns True if result is acceptable
            *args: Positional arguments for func
            max_attempts: Maximum retry attempts
            delay: Delay between attempts in seconds
            **kwargs: Keyword arguments for func
        
        Returns:
            First result that meets the condition
        
        Raises:
            Exception if max attempts reached without meeting condition
        """
        for attempt in range(max_attempts):
            try:
                result = await func(*args, **kwargs)
                
                if condition(result):
                    return result
                
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Result did not meet condition (attempt {attempt + 1}/{max_attempts}). "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        
        raise Exception(f"Failed to meet condition after {max_attempts} attempts")
