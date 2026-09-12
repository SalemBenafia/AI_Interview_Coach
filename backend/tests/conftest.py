"""
tests/conftest.py
====================
pytest-asyncio (asyncio_mode="auto") gives each async test function its own
event loop, but app.db.session.engine's connection pool and
app.core.redis's Redis client are both module-level singletons created
once at import time. Without resetting them between tests, a connection
checked out under one test's event loop gets returned to the pool and then
reused by the next test's *different* event loop, raising "Task ... got
Future ... attached to a different loop" / "Event loop is closed".

Same root cause Celery already works around for forked workers (see
_switch_to_null_pool in app/core/celery_app.py) -- here the fix is just to
tear both down after every test that touched them, so the next test starts
with fresh connections bound to its own loop.
"""
from __future__ import annotations

import pytest

from app.core import redis as redis_module
from app.db import session as db_session


@pytest.fixture(autouse=True)
async def _reset_shared_connections_after_test():
    yield
    await db_session.engine.dispose()
    await redis_module.close_redis()
