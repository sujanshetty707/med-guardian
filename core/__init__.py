import asyncio

# Ensure an active event loop exists in MainThread for Python 3.12+ / 3.14 compatibility with uagents
try:
    asyncio.get_event_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
