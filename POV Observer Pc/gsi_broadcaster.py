# gsi_broadcaster.py
import asyncio
from aiohttp import web
import websockets
import json

connected_clients = set()

# Handle POST requests from CS2
async def handle_gsi(request):
    try:
        data = await request.json()
        print("Received from CS2:", json.dumps(data, indent=2))
        # Broadcast to all connected replay clients
        if connected_clients:
            msg = json.dumps(data)
            await asyncio.gather(*[ws.send(msg) for ws in connected_clients])
        return web.Response(text="ok")
    except Exception as e:
        print(f"GSI error: {e}")
        return web.Response(status=500, text=str(e))

# WebSocket server for Replay machine
async def ws_handler(websocket):
    print("Replay client connected")
    connected_clients.add(websocket)
    try:
        async for _ in websocket:
            pass
    finally:
        connected_clients.remove(websocket)
        print("Replay client disconnected")

async def main():
    # HTTP server (for CS2 GSI)
    app = web.Application()
    app.router.add_post('/', handle_gsi)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 3000)
    await site.start()
    print("Listening for CS2 GSI on http://0.0.0.0:3000")

    # WebSocket server (for Replay)
    await websockets.serve(ws_handler, "0.0.0.0", 6789)
    print("WebSocket server started on ws://0.0.0.0:6789")

    await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())