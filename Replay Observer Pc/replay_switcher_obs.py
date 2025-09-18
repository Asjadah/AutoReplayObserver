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
match_kills = {}      # total kills reported by GSI
round_kills = {}      # per-round kills (reset each round)
delayed_events = []   # queue of delayed kill events
player_alive = {}     # track who is alive


def get_priority(kills, alive):
    """Return priority score based on kills and alive state."""
    if kills > 1 and alive:
        return 1
    elif kills > 1 and not alive:
        return 2
    elif kills == 1 and alive:
        return 3
    else:
        return 4


async def check_kill(steamid, pdata):
    if not steamid or steamid == "?":
        return

    name = pdata.get("name", "Unknown")
    slot = pdata.get("observer_slot", "?")
    kills = pdata.get("match_stats", {}).get("kills", 0)  # match kills
    alive = pdata.get("state", {}).get("health", 0) > 0

    prev_match = match_kills.get(steamid, 0)
    if kills > prev_match:
        new_kills = kills - prev_match  # kills scored since last update
        round_kills[steamid] = round_kills.get(steamid, 0) + new_kills

        print(f"[Slot {slot}] {name} → +{new_kills} this round "
              f"(Round total: {round_kills[steamid]}, Alive={alive})")

        if isinstance(slot, int) and slot in SLOT_KEY_MAP:
            key = SLOT_KEY_MAP[slot]
            trigger_time = time.time() + REPLAY_DELAY
            priority = get_priority(new_kills, alive)

            delayed_events.append({
                "time": trigger_time,
                "slot": slot,
                "key": key,
                "name": name,
                "kills": new_kills,
                "steamid": steamid,
                "alive": alive,
                "priority": priority
            })
            print(f"Queued switch to {name} (Slot {slot}) after {REPLAY_DELAY}s "
                  f"with priority {priority}")
        else:
            print(f"Slot {slot} not mapped to a key")

    # update match total
    match_kills[steamid] = kills


async def delayed_executor():
    """Execute queued kill events after the replay delay, respecting priority."""
    while True:
        now = time.time()
        ready_events = [e for e in delayed_events if e["time"] <= now]

        if ready_events:
            # sort by priority first, then by time
            ready_events.sort(key=lambda e: (e["priority"], e["time"]))

            # take the highest priority event
            event = ready_events[0]
            steamid = event.get("steamid")

            # Skip if player died (and rule requires alive)
            if steamid and not player_alive.get(steamid, True) and event["priority"] in [1, 3]:
                print(f"Skipping replay for {event['name']} (Slot {event['slot']}) – player died before replay")
            else:
                try:
                    print(f"Switching Replay Observer to {event['name']} "
                          f"(Slot {event['slot']}) by pressing {event['key'].upper()} "
                          f"[Priority {event['priority']}]")
                    pyautogui.press(event["key"])
                    time.sleep(0.2)
                except Exception as e:
                    print(f"Failed to switch observer: {e}")

            # remove executed event
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
# HANDLE EVENTS
# =====================
async def handle_event(message: str):
    """Parse incoming websocket messages and update players/kills."""
    try:
        data = json.loads(message)

        # Detect round phase changes
        if "phase_countdowns" in data:
            phase = data["phase_countdowns"].get("phase")
            if phase == "over":
                print("\n========== ROUND ENDED ==========")
                delayed_events.clear()
            elif phase == "live":
                print("\n========== ROUND STARTED ==========")
                round_kills.clear()   # reset only per-round kills

        # Multiple players update
        if "allplayers" in data:
            for steamid, pdata in data["allplayers"].items():
                alive = pdata.get("state", {}).get("health", 0) > 0
                player_alive[steamid] = alive
                await check_kill(steamid, pdata)

        # Single player update
        elif "player" in data:
            steamid = data["player"].get("steamid")
            if steamid:
                alive = data["player"].get("state", {}).get("health", 0) > 0
                player_alive[steamid] = alive
                await check_kill(steamid, data["player"])

    except Exception as e:
        print("Error in handle_event:", e)

# =====================
# MAIN
# =====================
if __name__ == "__main__":
    print("Make sure CS2 Replay Observer window is focused!")
    try:
        asyncio.run(listen_to_broadcaster())
    except KeyboardInterrupt:
        print("Exiting...")
