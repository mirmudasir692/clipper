import functools
import uuid
import time


def redis_store_process(store, ttl=None):
    """
    Decorator factory to track function execution lifecycle and persist data in Redis.

    This decorator wraps a function and automatically stores its execution details
    in Redis, including input arguments, execution status, result, and errors.

    A unique execution ID is generated for each function call, and all related
    data is stored under keys prefixed with:
        "<function_name>:<execution_id>"

    Stored keys:
        - "<base_key>:input"   → function arguments (args, kwargs)
        - "<base_key>:meta"    → execution metadata (status, start timestamp)
        - "<base_key>:result"  → result and completion timestamp (on success)
        - "<base_key>:error"   → error message and failure timestamp (on exception)

    Args:
        store (RedisStore):
            An instance of RedisStore used for persisting execution data.

        ttl (int | None, optional):
            Time-to-live (in seconds) for stored keys. If None, keys persist
            indefinitely unless a default TTL is configured in RedisStore.

    Returns:
        Callable:
            A decorator that can be applied to any function.

    Usage:
        >>> redis = configure_redis("redis://127.0.0.1:6379/0")
        >>> @redis_store_process(redis, ttl=3600)
        ... def add(a, b):
        ...     return a + b
        >>> add(2, 3)

    Notes:
        - The original function signature remains unchanged.
        - This decorator does not modify function execution behavior; it only logs
          execution details to Redis.
        - Suitable for debugging, monitoring, and lightweight job tracking.
        - Not a replacement for full background job queues like Celery or RQ.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate a unique tracking ID for this specific invocation
            execution_id = str(uuid.uuid4())
            # Define a common prefix for all Redis keys related to this run
            base_key = f"{func.__name__}:{execution_id}"
            
            # Persist original input arguments for debugging or audit trails
            store.set(f"{base_key}:input", {
                "args": args,
                "kwargs": kwargs
            }, ttl=ttl)
            
            # Mark the process as 'started' in the metadata store
            store.set(f"{base_key}:meta", {
                "status": "started",
                "timestamp": time.time()
            }, ttl=ttl)
            
            try:
                # Execute the actual function
                result = func(*args, **kwargs)
                
                # On success, log the result and completion time
                store.set(f"{base_key}:result", {
                    "status": "completed",
                    "result": result,
                    "completed_at": time.time()
                }, ttl=ttl)
                return result
                
            except Exception as e:
                # On failure, log the error message and failure time before re-raising
                store.set(f"{base_key}:error", {
                    "status": "failed",
                    "error": str(e),
                    "failed_at": time.time()
                }, ttl=ttl)
                raise
        return wrapper
    return decorator