import asyncio
import logging
import random
import time
from typing import Callable, Any, TypeVar, Dict, Optional
from core.config import settings

logger = logging.getLogger("med-guardian.resilience")

T = TypeVar("T")

class CircuitBreakerOpenException(Exception):
    """Raised when circuit breaker is in OPEN state."""
    pass

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, recovery_time_secs: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_time_secs = recovery_time_secs
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"CircuitBreaker [{self.name}] entered OPEN state.")

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_time_secs:
                self.state = "HALF_OPEN"
                logger.info(f"CircuitBreaker [{self.name}] entered HALF_OPEN state.")
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return True

class SimpleCache:
    def __init__(self, default_ttl_secs: float = 3600.0):
        self._cache: Dict[str, tuple[float, Any]] = {}
        self.default_ttl = default_ttl_secs

    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            ts, val = self._cache[key]
            if time.time() - ts < self.default_ttl:
                return val
            del self._cache[key]
        return None

    def set(self, key: str, val: Any, ttl: Optional[float] = None):
        ttl_to_use = ttl if ttl is not None else self.default_ttl
        self._cache[key] = (time.time(), val)

# Global caches and circuit breakers
drug_cache = SimpleCache(default_ttl_secs=86400)       # 24 hour cache for RxNorm
interaction_cache = SimpleCache(default_ttl_secs=86400) # 24 hour cache for openFDA
pricing_circuit_breaker = CircuitBreaker("pricing", failure_threshold=2, recovery_time_secs=20.0)
openfda_circuit_breaker = CircuitBreaker("openfda", failure_threshold=3, recovery_time_secs=30.0)

async def retry_with_backoff(
    coro_fn: Callable[..., Any],
    *args,
    max_retries: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    **kwargs
) -> Any:
    delay = initial_delay
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt == max_retries:
                logger.error(f"Attempt {attempt}/{max_retries} failed permanently: {e}")
                raise e
            jitter = random.uniform(0.1, 0.3)
            sleep_time = delay + jitter
            logger.warning(f"Attempt {attempt}/{max_retries} failed with {type(e).__name__}: {e}. Retrying in {sleep_time:.2f}s...")
            await asyncio.sleep(sleep_time)
            delay *= backoff_factor

def check_fault_injection(target_name: str):
    """Demo hook: injects simulated timeout or failure if FAULT_INJECT env matches."""
    fault = settings.FAULT_INJECT.strip().lower()
    if not fault:
        return
    if target_name in fault:
        logger.warning(f"[DEMO FAULT INJECTION] Triggering injected failure for '{target_name}' (config: {settings.FAULT_INJECT})")
        if "timeout" in fault:
            raise asyncio.TimeoutError(f"Simulated timeout failure injected on {target_name}")
        else:
            raise ConnectionError(f"Simulated network/500 connection error injected on {target_name}")
