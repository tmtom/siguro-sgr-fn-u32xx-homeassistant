import json, os, sys, time
import paho.mqtt.client as mqtt

# usage: mqtt_listen.py <secs> <out.json> [topic_filter] [broker] [port]
# credentials via MQTT_USER / MQTT_PASSWORD environment variables (kept out of argv/files)
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
OUT = sys.argv[2] if len(sys.argv) > 2 else "mqtt_capture.json"
FILTER = sys.argv[3] if len(sys.argv) > 3 else "#"
BROKER = sys.argv[4] if len(sys.argv) > 4 else "mqtt.example.local"
PORT = int(sys.argv[5]) if len(sys.argv) > 5 else 1883

messages = []
connected = []

def on_connect(client, userdata, flags, rc, properties=None):
    # subscribe only once the broker acknowledged the session (canonical pattern)
    client.subscribe(FILTER)
    connected.append(time.strftime("%H:%M:%S"))

def on_message(client, userdata, msg):
    messages.append({
        "t": time.strftime("%H:%M:%S"),
        "topic": msg.topic,
        "payload": msg.payload.decode("utf-8", "replace"),
    })

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="test-listener")
if os.environ.get("MQTT_USER"):
    client.username_pw_set(os.environ["MQTT_USER"], os.environ.get("MQTT_PASSWORD"))
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()
time.sleep(DURATION)
client.loop_stop()
client.disconnect()

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(messages, f, indent=1)
print(f"connected at {connected}, captured {len(messages)} messages from {BROKER} -> {OUT}")
