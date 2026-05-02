"""Shared rate-limiter instance.

Single Limiter, imported by both main.py (for app.state + exception handler)
and any router that decorates endpoints with `@limiter.limit(...)`. Sharing
the instance is required — separate instances have separate in-memory
counters and would silently disagree.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# `get_remote_address` reads `X-Forwarded-For` when present, so it works
# correctly behind Render's proxy. In-memory storage is fine for a single
# uvicorn worker; with multiple workers each gets its own counter.
limiter = Limiter(key_func=get_remote_address)
