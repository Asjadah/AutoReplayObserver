import asyncio
import websockets
import json
import pyautogui
import time

# =====================
# CONFIGURATION
# =====================
BROADCASTER_WS = "ws://10.0.0.34:6789"  # POV Observer PC broadcasting kills

SLOT_KEY_MAP = {
    0: 'f1',
    1: 'f2',
    2: 'f3',
    3: 'f4',
    4: 'f5',
    5: 'f6',
    6: 'f7',
    7: 'f8',
    8: 'f9',
    9: 'f10',
    10: 'f11',
    11: 'f12'
}

# =====================
# TRACK KILLS
# =====================
previous_kills = {}

async def handle_event(event):
    try:
        data = json.loads(event)

        # Multiple players
        if "allplayers" in data:
            for steamid, pdata in data["allplayers"].items():
                await check_kill(steamid, pdata)

        # Single player
        elif "player" in data:
            steamid = data["player"].get("steamid")
            await check_kill(steamid, data["player"])

    except Exception as e:
        print("Error handling event:", e)

async def check_kill(steamid, pdata):
    if not steamid or steamid == "?":
        return

    name = pdata.get("name", "Unknown")
    slot = pdata.get("observer_slot", "?")
    kills = pdata.get("match_stats", {}).get("kills", 0)

    prev = previous_kills.get(steamid, 0)
    if kills > prev:
        print(f"[Slot {slot}] {name} → {kills} kills")

        # Press F-key for the slot
        try:
            if isinstance(slot, int) and slot in SLOT_KEY_MAP:
                key = SLOT_KEY_MAP[slot]
                print(f"Switching Replay Observer to {name} (Slot {slot}) by pressing {key.upper()}")
                pyautogui.press(key)
                time.sleep(0.2)
            else:
                print(f"Slot {slot} not mapped to a key")
        except Exception as e:
            print(f"Failed to switch observer: {e}")

    previous_kills[steamid] = kills

# =====================
# LISTEN TO BROADCASTER
# =====================
async def listen_to_broadcaster():
    while True:
        try:
            async with websockets.connect(BROADCASTER_WS) as websocket:
                print("Connected to broadcaster at", BROADCASTER_WS)
                async for message in websocket:
                    await handle_event(message)
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            print("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)

# =====================
# MAIN
# =====================
if __name__ == "__main__":
    print("Make sure CS2 Replay Observer window is focused!")
    try:
        asyncio.run(listen_to_broadcaster())
    except KeyboardInterrupt:
        print("Exiting...")
