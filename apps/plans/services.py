import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

PLANS_CACHE_VERSION_KEY = "plans_cache_version"
PLANS_CACHE_TIMEOUT = 60 * 15  # 15 minutes

def get_plans_cache_version() -> int:
    """Returns the current cache version for plans, incremented whenever plans change."""
    version = cache.get(PLANS_CACHE_VERSION_KEY)
    if version is None:
        version = 1
        cache.set(PLANS_CACHE_VERSION_KEY, version, timeout=None)
    return version

def get_plans_cache_key(page: int = 1, page_size: int = 10) -> str:
    """Builds a versioned cache key for public plan listings."""
    version = get_plans_cache_version()
    return f"public_plans:v{version}:page_{page}:size_{page_size}"

def invalidate_plans_cache():
    """
    Instantly invalidates all cached plan pages by bumping the cache version
    and attempting to delete matching keys from Redis.
    """
    try:
        # Increment cache version atomically
        try:
            cache.incr(PLANS_CACHE_VERSION_KEY)
        except Exception:
            current = get_plans_cache_version()
            cache.set(PLANS_CACHE_VERSION_KEY, current + 1, timeout=None)

        # In case Redis backend supports pattern deletion:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern("*public_plans:*")

        logger.info("Successfully invalidated public plans cache.")
    except Exception as e:
        logger.warning(f"Error during plans cache invalidation: {e}")
