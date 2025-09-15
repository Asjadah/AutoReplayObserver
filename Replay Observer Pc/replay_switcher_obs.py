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

REPLAY_DELAY = 5.5  # seconds delay for replay observer

# =====================
# TRACK KILLS
# =====================
previous_kills = {}
delayed_events = []  # queue of delayed kill events


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

        if isinstance(slot, int) and slot in SLOT_KEY_MAP:
            key = SLOT_KEY_MAP[slot]
            trigger_time = time.time() + REPLAY_DELAY

            # Queue event
            delayed_events.append({
                "time": trigger_time,
                "slot": slot,
                "key": key,
                "name": name,
                "kills": kills
            })
            print(f"Queued switch to {name} (Slot {slot}) after {REPLAY_DELAY}s")
        else:
            print(f"Slot {slot} not mapped to a key")

    previous_kills[steamid] = kills


async def delayed_executor():
    """Execute queued kill events after the replay delay."""
    while True:
        now = time.time()
        for event in delayed_events[:]:
            if event["time"] <= now:
                try:
                    print(f"Switching Replay Observer to {event['name']} "
                          f"(Slot {event['slot']}) by pressing {event['key'].upper()}")
                    pyautogui.press(event["key"])
                    time.sleep(0.2)  # small delay to avoid overlapping key presses
                except Exception as e:
                    print(f"Failed to switch observer: {e}")
                delayed_events.remove(event)
        await asyncio.sleep(0.1)


# =====================
# LISTEN TO BROADCASTER
# =====================
async def listen_to_broadcaster():
    while True:
        try:
            async with websockets.connect(BROADCASTER_WS) as websocket:
                print("Connected to broadcaster at", BROADCASTER_WS)

                # run listener + executor together
                consumer_task = asyncio.create_task(delayed_executor())

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
