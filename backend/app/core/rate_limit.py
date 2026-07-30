"""Rate limiting (slowapi) — brute-force + abuse protection.

One shared Limiter, keyed by client IP. Behind a proxy in prod, run uvicorn
with --forwarded-allow-ips and a ProxyHeaders middleware so the real client IP
is seen (otherwise every request looks like it comes from the proxy).

Per-route limits are applied with @limiter.limit(...) on endpoints that take a
`request: Request` arg; a generous default guards everything else.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Sensible named limits so call sites read clearly and stay consistent.
AUTH_LIMIT = "10/minute"        # login/signup — stop credential brute-force
EXPENSIVE_LIMIT = "20/hour"     # GPU/AI/scraping — protect cost + upstreams
DEFAULT_LIMITS = ["300/minute"]  # global backstop

limiter = Limiter(key_func=get_remote_address, default_limits=DEFAULT_LIMITS)
