import time, threading
from flask import Flask, request, abort
import telnetlib

# --- config ---
NETCON_HOST = "10.0.0.32"   # IP of your Replay Observer PC (delayed GOTV client)
NETCON_PORT = 2121          # must match -netconport
NETCON_PASSWORD = "observerpwd"
DELAY_SECONDS = 7.0         # delay in seconds (same as GOTV delay)

app = Flask(__name__)

live_round_kills = {}  # track kills
tn = None

def steam64_to_accountid(steamid64: int) -> int:
    return int(steamid64) - 76561197960265728

def netcon_connect():
    global tn
    if tn is None:
        tn = telnetlib.Telnet(NETCON_HOST, NETCON_PORT, timeout=5)
        if NETCON_PASSWORD:
            tn.write(f"PASS {NETCON_PASSWORD}\n".encode("ascii"))
            time.sleep(0.05)

def send_console(cmd: str):
    netcon_connect()
    tn.write((cmd + "\n").encode("ascii"))
    print(f"[NetCon] Sent: {cmd}")

def schedule_switch(account_id: int, delay: float):
    def run():
        time.sleep(delay)
        send_console(f"spec_player_by_accountid {account_id}")
        send_console("spec_mode 1")
        send_console("spec_lock_to_current_player 1")
    threading.Thread(target=run, daemon=True).start()

@app.route("/live", methods=["POST"])
def live():
    data = request.get_json(silent=True)
    if not data:
        abort(400)

    round_info = data.get("round", {})
    phase = round_info.get("phase")

    current = {}

    # read all players
    allp = data.get("allplayers", {})
    for sid, info in allp.items():
        kills = None
        if "state" in info and "round_kills" in info["state"]:
            kills = info["state"]["round_kills"]
        elif "match_stats" in info and "kills" in info["match_stats"]:
            kills = info["match_stats"]["kills"]

        if kills is not None:
            current[sid] = kills
            print(f"{info.get('name')} | kills: {kills}")

    # detect new kills
    for sid, rk in current.items():
        prev = live_round_kills.get(sid, 0)
        if rk > prev:
            try:
                account_id = steam64_to_accountid(int(sid))
                schedule_switch(account_id, DELAY_SECONDS)
                print(f"[kill] {sid} -> acc {account_id}, switching in {DELAY_SECONDS}s")
            except Exception as e:
                print("steamid conversion error:", e)
        live_round_kills[sid] = rk

    if phase == "over":
        live_round_kills.clear()

    return "ok"

if __name__ == "__main__":
    print("Replay Auto Observer running on 0.0.0.0:3001")
    app.run(host="0.0.0.0", port=3001, debug=False)
