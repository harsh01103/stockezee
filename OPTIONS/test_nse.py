import asyncio
from market.nse_client import NSEClient
async def test():
    c = NSEClient()
    d = await c.get_option_chain('NIFTY')
    print('success' if d else 'fail')
asyncio.run(test())