import json
from typing import Any, Optional, Callable
from functools import wraps
import hashlib
from redis import Redis
from app.core.config import settings

class CacheService:
    def __init__(self):
        self.redis = Redis(
            host='redis', 
            port=6379, 
            db=0, 
            decode_responses=True
        )
        self.default_ttl = 60 * 5  # 5 minutes

    def get(self, key: str) -> Optional[Any]:
        val = self.redis.get(key)
        if val:
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return val
        return None

    def set(self, key: str, value: Any, ttl: int = None):
        if ttl is None:
            ttl = self.default_ttl
        
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
            
        self.redis.setex(key, ttl, value)

    def delete(self, key: str):
        self.redis.delete(key)

    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        # Create a unique key based on arguments
        key_str = f"{prefix}:{args}:{kwargs}"
        return hashlib.md5(key_str.encode()).hexdigest()

# Global check instance
cache = CacheService()

def cache_response(ttl: int = 300, prefix: str = "api"):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            # Note: This simple key gen might need adjustment for complex objects in args
            # For FastAPI endpoints, we might want to use the request path/body
            try:
                # Basic key generation for now
                key = cache.generate_key(f"{prefix}:{func.__name__}", str(args), str(kwargs))
                
                cached_val = cache.get(key)
                if cached_val:
                    return cached_val
                
                result = await func(*args, **kwargs)
                
                # If result is a Pydantic model, dump it
                if hasattr(result, "model_dump"):
                    to_cache = result.model_dump()
                    # Convert datetime objects to str for JSON serialization
                    # simplistic approach: let pydantic handle json via json() but model_dump is dict
                    # We need a serializer that handles datetime. JSON default does not.
                    # Pydantic v2 model_dump_json() returns a string.
                    to_cache = result.model_dump_json() # Store as string
                else:
                    to_cache = result

                cache.set(key, to_cache, ttl)
                
                # If we stored a JSON string from Pydantic, we need to return the object?
                # Actually, the wrapper should return the object.
                # If we return the cached JSON string, FastAPI might re-encode it.
                # For now, let's keep it simple: cache strictly for compute-heavy internal functions
                # OR handle the response object reconstruction.
                
                return result
            except Exception as e:
                # Fallback if cache fails
                print(f"Cache Error: {e}")
                return await func(*args, **kwargs)
        return wrapper
    return decorator
