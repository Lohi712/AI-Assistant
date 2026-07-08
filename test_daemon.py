"""Quick test script for the WhatsApp daemon."""
import socket
import json
import time

t = time.time()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(45)
s.connect(("127.0.0.1", 5824))

request = json.dumps({
    "action": "send",
    "recipient": "Eshwarnath",
    "message": "daemon test from vega",
})
s.sendall(request.encode("utf-8"))
s.shutdown(socket.SHUT_WR)

data = b""
while True:
    chunk = s.recv(4096)
    if not chunk:
        break
    data += chunk
s.close()

resp = json.loads(data.decode("utf-8"))
elapsed = time.time() - t
print(f"Status: {resp.get('status')}")
if resp.get("error"):
    print(f"Error: {resp.get('error')}")
if resp.get("contacts"):
    print(f"Contacts received: {len(resp['contacts'])}")
print(f"Time: {elapsed:.1f}s")
