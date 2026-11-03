import json, os, sys, time
import paho.mqtt.client as mqtt

# usage: mqtt_cmd.py <topic> <command> [secs] [broker] [port]
# Publishes cmnd/<topic>/<command> and captures stat/+/tele/ replies.
# Credentials via MQTT_USER / MQTT_PASSWORD environment variables (kept out of argv/files).
TOPIC = sys.argv[1]
COMMAND = sys.argv[2]
DURATION = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
BROKER = sys.argv[4] if len(sys.argv) > 4 else "mqtt.example.local"
PORT = int(sys.argv[5]) if len(sys.argv) > 5 else 1883

messages = []

def on_connect(client, userdata, flags, rc, properties=None):
    client.subscribe(f"stat/{TOPIC}/#")
    client.subscribe(f"tele/{TOPIC}/#")
    time.sleep(0.3)
    # command word goes in the topic, parameters in the message body (Tasmota convention)
    cmd, _, payload = COMMAND.partition(" ")
    client.publish(f"cmnd/{TOPIC}/{cmd}", payload)

def on_message(client, userdata, msg):
    messages.append({
        "t": time.strftime("%H:%M:%S"),
        "topic": msg.topic,
        "payload": msg.payload.decode("utf-8", "replace"),
    })

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mqtt-cmd")
if os.environ.get("MQTT_USER"):
    client.username_pw_set(os.environ["MQTT_USER"], os.environ.get("MQTT_PASSWORD"))
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()
time.sleep(DURATION)
client.loop_stop()
client.disconnect()

for m in messages:
    print(f"[{m['t']}] {m['topic']}: {m['payload'][:2000]}")
print(f"--- {len(messages)} messages")
