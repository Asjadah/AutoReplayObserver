import asyncio
import websockets
import json
import pyautogui
import time
import keyboard

# =====================
# CONFIGURATION
# =====================
BROADCASTER_WS = "ws://10.0.0.234:6789"
SLOT_KEY_MAP = {
    0: '1', 1: '2', 2: '3', 3: '4',
    4: '5', 5: '6', 6: '7', 7: '8',
    8: '9', 9: '0', 10: '-', 11: '='
}
REPLAY_DELAY = 5.3

# =====================
# STATE
# =====================
match_kills = {}
round_kills = {}
delayed_events = []
player_alive = {}

script_running = False
main_task = None


def get_priority(kills, alive):
    if kills > 1 and alive:
        return 1
    elif kills > 1 and not alive:
        return 2
    elif kills == 1 and alive:
        return 3
    else:
        return 4


async def check_kill(steamid, pdata):
    if not script_running:
        return
    if not steamid or steamid == "?":
        return

    name = pdata.get("name", "Unknown")
    slot = pdata.get("observer_slot", "?")
    kills = pdata.get("match_stats", {}).get("kills", 0)
    alive = pdata.get("state", {}).get("health", 0) > 0

    prev_match = match_kills.get(steamid, 0)
    if kills > prev_match:
        new_kills = kills - prev_match
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

    match_kills[steamid] = kills


async def delayed_executor():
    while True:
        if script_running:
            now = time.time()
            ready_events = [e for e in delayed_events if e["time"] <= now]

            if ready_events:
                # Handle one event at a time
                event = ready_events[0]

                # Pick best player at THIS moment
                best_player = None
                best_priority = 999

                for steamid, kills in round_kills.items():
                    alive = player_alive.get(steamid, True)
                    pdata_priority = get_priority(kills, alive)

                    if pdata_priority < best_priority:
                        best_priority = pdata_priority
                        best_player = {
                            "steamid": steamid,
                            "kills": kills,
                            "alive": alive,
                        }

                if best_player:
                    steamid = best_player["steamid"]
                    slot = None
                    name = "Unknown"

                    # find slot + name (from last match_kills update)
                    for sid, kills in match_kills.items():
                        if sid == steamid:
                            slot = delayed_events[0].get("slot")  # fallback
                            break

                    # safer: just reuse slot from event if unknown
                    slot = slot or event.get("slot", "?")

                    if isinstance(slot, int) and slot in SLOT_KEY_MAP:
                        key = SLOT_KEY_MAP[slot]
                        print(f"👉 Switching to BEST player {steamid} "
                              f"(Kills={best_player['kills']}, Alive={best_player['alive']}) "
                              f"by pressing {key.upper()} [Priority {best_priority}]")
                        pyautogui.press(key)
                    else:
                        print(f"No valid slot for best player {steamid}")

                delayed_events.remove(event)

        await asyncio.sleep(0.1)



async def handle_event(message: str):
    if not script_running:
        return

    try:
        data = json.loads(message)

        if "phase_countdowns" in data:
            phase = data["phase_countdowns"].get("phase")
            if phase == "over":
                print("\n========== ROUND ENDED ==========")
                delayed_events.clear()
            elif phase == "live":
                print("\n========== ROUND STARTED ==========")
                round_kills.clear()

        if "allplayers" in data:
            for steamid, pdata in data["allplayers"].items():
                alive = pdata.get("state", {}).get("health", 0) > 0
                player_alive[steamid] = alive
                await check_kill(steamid, pdata)

        elif "player" in data:
            steamid = data["player"].get("steamid")
            if steamid:
                alive = data["player"].get("state", {}).get("health", 0) > 0
                player_alive[steamid] = alive
                await check_kill(steamid, data["player"])

    except Exception as e:
        print("Error in handle_event:", e)


async def listen_to_broadcaster():
    while script_running:
        try:
            async with websockets.connect(BROADCASTER_WS) as websocket:
                print("Connected to broadcaster at", BROADCASTER_WS)
                consumer_task = asyncio.create_task(delayed_executor())
                async for message in websocket:
                    if not script_running:
                        break
                    await handle_event(message)
        except Exception as e:
            if script_running:
                print(f"WebSocket connection error: {e}")
                print("Reconnecting in 5 seconds...")
                await asyncio.sleep(5)


# =====================
# HOTKEYS
# =====================
def setup_hotkeys(loop):
    keyboard.add_hotkey("s", lambda: loop.call_soon_threadsafe(start_script, loop))
    keyboard.add_hotkey("e", lambda: loop.call_soon_threadsafe(stop_script))


def start_script(loop):
    global script_running, main_task
    if script_running:
        print("Replay Switcher already running.")
        return
    script_running = True
    print("\nReplay Switcher STARTED – Now tracking kills\n")
    main_task = asyncio.run_coroutine_threadsafe(listen_to_broadcaster(), loop)


def stop_script():
    global script_running
    script_running = False
    delayed_events.clear()
    print("\nReplay Switcher STOPPED – Press S to start again\n")


# =====================
# MAIN
# =====================
if __name__ == "__main__":
    print("Press S to START replay switching")
    print("Press E to STOP (can restart later)")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    setup_hotkeys(loop)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Exiting...")