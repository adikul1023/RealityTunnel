import asyncio
from unittest.mock import AsyncMock

async def test():
    am = AsyncMock()
    result = await am.execute()
    try:
        scalars = result.scalars()
        scalars.all()
    except Exception as e:
        print('Exception:', type(e), e)

asyncio.run(test())
