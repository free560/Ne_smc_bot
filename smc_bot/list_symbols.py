import asyncio
import json
import websockets

async def main():
    ws = await websockets.connect(
        "wss://api.derivws.com/trading/v1/options/ws/public"
    )

    await ws.send(json.dumps({
        "ticks_history": "BOOM1000",
        "end": "latest",
        "style": "candles",
        "granularity": 60,
        "subscribe": 1
    }))

    while True:
        print(await ws.recv())

asyncio.run(main())