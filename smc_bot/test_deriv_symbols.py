import asyncio
import json
import websockets

async def main():
    ws = await websockets.connect(
        "wss://ws.derivws.com/websockets/v3?app_id=1089"
    )


    payload = {
        "ticks": "BOOM1000",
        "subscribe": 1
    }

    await ws.send(json.dumps(payload))

    while True:
        msg = await ws.recv()
        print(msg)

asyncio.run(main())