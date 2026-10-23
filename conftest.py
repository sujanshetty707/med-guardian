import asyncio
import pytest

# Ensure event loop exists during pytest collection on Python 3.12+ / 3.14
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
