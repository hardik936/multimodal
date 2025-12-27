import asyncio
import websockets
import sys

async def test_ws(run_id="test_run_id"):
    uri = f"ws://localhost:8000/ws/{run_id}"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected!")
            
            # Expect initial state message
            response = await websocket.recv()
            print(f"Received: {response}")
            
            # Send ping
            # await websocket.send("ping")
            # print("Sent ping")
            
            # Keep open for a bit
            await asyncio.sleep(1)
            print("Closing...")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(test_ws(sys.argv[1]))
    else:
        asyncio.run(test_ws())
