import asyncio
from market.nse_client import NSEClient
from market.strike_selector import StrikeSelector

async def test():
    c = NSEClient()
    s = StrikeSelector(c)
    await s.update_universe()
    nifty = s.get_selected_strikes("NIFTY")
    print(nifty[:1] if nifty else "NIFTY empty")
    await c.close()

if __name__ == "__main__":
    asyncio.run(test())
