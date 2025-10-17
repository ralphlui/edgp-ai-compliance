import sys
import types
import asyncio

if "aiomysql" not in sys.modules:
    module = types.ModuleType("aiomysql")

    class _DummyPool:
        async def acquire(self):
            raise RuntimeError("aiomysql stub - no connection")

        def close(self):
            return None

        async def wait_closed(self):
            return None

    async def create_pool(*args, **kwargs):
        return _DummyPool()

    module.create_pool = create_pool
    sys.modules["aiomysql"] = module
