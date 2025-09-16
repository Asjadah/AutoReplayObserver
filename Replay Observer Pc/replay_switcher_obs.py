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
    0: '1',
    1: '2',
    2: '3',
    3: '4',
    4: '5',
    5: '6',
    6: '7',
    7: '8',
    8: '9',
    9: '0',
    10: '-',
    11: '='
}


REPLAY_DELAY = 5.5  # seconds delay for replay observer

# =====================
# TRACK KILLS
# =====================
previous_kills = {}
delayed_events = []   # queue of delayed kill events
player_alive = {}     # track who is alive


async def handle_event(event):
    try:
        data = json.loads(event)

        # Multiple players
        if "allplayers" in data:
            for steamid, pdata in data["allplayers"].items():
                # Track alive state
                alive = pdata.get("state", {}).get("health", 0) > 0
                player_alive[steamid] = alive

                await check_kill(steamid, pdata)

        # Single player
        elif "player" in data:
            steamid = data["player"].get("steamid")
            if steamid:
                alive = data["player"].get("state", {}).get("health", 0) > 0
                player_alive[steamid] = alive

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

            # Queue event with steamid for alive check
            delayed_events.append({
                "time": trigger_time,
                "slot": slot,
                "key": key,
                "name": name,
                "kills": kills,
                "steamid": steamid
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
                steamid = event.get("steamid")
                # Skip if the killer is dead
                if steamid and not player_alive.get(steamid, True):
                    print(f"Skipping replay for {event['name']} (Slot {event['slot']}) – player died before replay")
                else:
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
