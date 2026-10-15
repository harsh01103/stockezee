import asyncio
from market.instrument_resolver import InstrumentResolver

async def test():
    r = InstrumentResolver()
    await r.ensure_loaded()
    print(list(r.lookup_table.keys())[:5])
    print(r.resolve('NIFTY', '14-07-2026', 23550.0, 'CE'))

if __name__ == "__main__":
    asyncio.run(test())
