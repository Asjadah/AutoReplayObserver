import telnetlib
import time

# --- Config ---
HOST = "10.0.0.32"          # Replay Observer PC IP
PORT = 2121                  # NetCon port
PASSWORD = "observerpwd"     # Must match exactly what you set in CS2 launch options

try:
    # Connect to NetCon
    tn = telnetlib.Telnet(HOST, PORT, timeout=5)
    time.sleep(0.1)

    # Send password
    tn.write(f"PASS {PASSWORD}\n".encode("ascii"))
    time.sleep(0.2)

    # Test command
    tn.write(b"echo NETCON_OK\n")
    time.sleep(0.2)

    # Read response
    output = tn.read_very_eager().decode("utf-8", errors="ignore")
    print("Received from CS2 NetCon:\n", output.strip())

    tn.close()

except Exception as e:
    print("Error connecting to NetCon:", e)
