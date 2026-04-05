import redis
import pickle
from typing import Any, Optional, cast


class RedisStore:
    """
    A persistent key-value store wrapper around Redis for caching and metadata storage.
    Automatically handles object serialization using pickle and supports key prefixing.
    """
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_ttl: Optional[int] = None,
        prefix: str = "video:"
    ) -> None:
        """
        Initializes a connection to the Redis server.
        
        Args:
            redis_url (str): Connection string (e.g., redis://user:password@host:port/db).
            default_ttl (int, optional): Default expiration time for keys in seconds.
            prefix (str): String prepended to all keys to avoid collisions.
        """
        # Initialize the raw redis client
        self.r: redis.Redis = redis.from_url(redis_url, decode_responses=False)
        self.default_ttl = default_ttl
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Internal helper to prepend the prefix to a user-provided key."""
        return f"{self.prefix}{key}"

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Serializes and stores an object in Redis.
        
        Args:
            key (str): The unique identifier for the data.
            value (Any): Any pickleable Python object.
            ttl (int, optional): Time-to-live override for this specific key.
        """
        k = self._key(key)
        # Convert Python object to bytes
        serialized: bytes = pickle.dumps(value)
        # Determine survival time
        effective_ttl = ttl if ttl is not None else self.default_ttl
        
        if effective_ttl is not None:
            # Set with expiration
            self.r.setex(k, int(effective_ttl), serialized)
        else:
            # Set indefinitely
            self.r.set(k, serialized)

    def get(self, key: str) -> Any | None:
        """
        Retrieves and deserializes an object from Redis.
        
        Args:
            key (str): The key to look up.
            
        Returns:
            Any or None: The deserialized object if found, otherwise None.
        """
        k = self._key(key)
        data = self.r.get(k)
        
        if data is None:
            return None
            
        # Ensure we are dealing with a byte stream before unpickling
        if not isinstance(data, (bytes, bytearray)):
            return None
            
        return pickle.loads(cast(bytes, data))

    def exists(self, key: str) -> bool:
        """Checks if a key currently exists in the store."""
        k = self._key(key)
        return bool(self.r.exists(k))

    def delete(self, key: str) -> None:
        """Removes a key and its associated data from the store."""
        k = self._key(key)
        self.r.delete(k)

    def ttl(self, key: str) -> int:
        """
        Returns the remaining time-to-live for a key in seconds.
        
        Returns:
            int: Seconds remaining, -1 for no expiry, or -2 if key doesn't exist.
        """
        k = self._key(key)
        return cast(int, self.r.ttl(k))

    def clear_prefix(self) -> None:
        """
        Wipes all keys from the database that match the current store's prefix.
        EXTREMELY destructive—use only in test environments or migrations.
        """
        pattern = f"{self.prefix}*"
        # Scan for matching keys to avoid blocking the server with KEYS command
        for key in self.r.scan_iter(pattern):
            self.r.delete(key)

def configure_redis(url: str = ""):
    """
    Factory function to initialize a RedisStore instance.
    
    Args:
        url (str): The Redis connection URL.
        
    Returns:
        RedisStore: A configured instance of the store.
        
    Raises:
        ValueError: If a connection URL is not provided.
    """
    if not url:
        raise ValueError("Critical: A valid Redis connection URL must be provided.")
    
    # Return a new store instance with default settings
    return RedisStore(url)
