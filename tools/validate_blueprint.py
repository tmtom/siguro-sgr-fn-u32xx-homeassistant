"""Validate the Siguro discovery blueprint: YAML parses, payload templates
render to valid JSON, and command templates emit the expected MQTT payloads.

Dev tool - requires pyyaml + jinja2 (jinja2 emulates HA's to_json filter).
Test values are fake placeholders; no real device data lives here.
"""
import json
import sys

import yaml


class Loader(yaml.SafeLoader):
    pass


def _input(loader, node):
    return f"!input {loader.construct_scalar(node)}"


Loader.add_constructor("!input", _input)

with open("blueprints/siguro-sgr-fn-u32xx-fan-discovery.yaml", encoding="utf-8") as f:
    doc = yaml.load(f, Loader)

bp = doc["blueprint"]
assert bp["domain"] == "automation"
assert set(bp["input"]) == {"fan_name", "topic", "mac_address"}
assert doc["variables"]["macaddr"]
assert [t["platform"] for t in doc["trigger"]] == ["homeassistant", "mqtt"]
print("YAML structure OK")

import jinja2

env = jinja2.Environment()
env.filters["to_json"] = json.dumps  # HA's to_json filter
ctx = {
    "fan_name": "Siguro SGR-FN-U32xx Fan",
    "topic": "Siguro",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "macaddr": "aabbccddeeff",
}

payloads = {}
for name in ("payload_fan", "payload_ionizer", "payload_display",
             "payload_timer_off", "payload_timer_on", "payload_timer_left"):
    rendered = env.from_string(doc["variables"][name]).render(ctx)
    payloads[name] = json.loads(rendered)  # raises if not valid JSON
    assert payloads[name]["device"]["manufacturer"] == "Siguro"
    assert isinstance(payloads[name]["device"], dict), f"{name}: device not an object"
print("All 6 discovery payloads render to valid JSON with object device blocks")

fan = payloads["payload_fan"]
assert fan["speed_range_min"] == 1 and fan["speed_range_max"] == 12
assert fan["command_topic"] == "cmnd/Siguro/POWER1"
assert fan["state_topic"] == "stat/Siguro/POWER1"
assert fan["percentage_command_topic"] == "cmnd/Siguro/TuyaSend2"
assert fan["percentage_state_topic"] == "stat/Siguro/speed"
assert fan["preset_mode_command_topic"] == "cmnd/Siguro/TuyaSend4"
assert fan["preset_mode_state_topic"] == "stat/Siguro/mode"
assert fan["oscillation_command_topic"] == "cmnd/Siguro/POWER2"
assert fan["availability_topic"] == "tele/Siguro/LWT"

# render inner command templates exactly as HA would, with only `value` in scope
def render_cmd(template, value):
    return env.from_string(template).render(value=value)

checks = [
    (fan["percentage_command_template"], 3, "2,3"),
    (fan["percentage_command_template"], 12, "2,12"),
    (fan["preset_mode_command_template"], "Normal", "3,0"),
    (fan["preset_mode_command_template"], "Natural", "3,1"),
    (fan["preset_mode_command_template"], "Night", "3,2"),
    (payloads["payload_timer_off"]["command_template"], 4, "103,4"),
    (payloads["payload_timer_on"]["command_template"], 12, "102,12"),
]
for tpl, value, expect in checks:
    got = render_cmd(tpl, value)
    assert got == expect, f"command template {tpl!r} with value={value!r}: got {got!r}, want {expect!r}"
print("Command templates OK (2,n speed / 3,n mode / 103,n off / 102,n on)")

for tpl, value, expect in [
    (fan["percentage_value_template"], "7", "7"),
    (fan["preset_mode_value_template"], "0", "Normal"),
    (fan["preset_mode_value_template"], "1", "Natural"),
    (fan["preset_mode_value_template"], "2", "Night"),
]:
    got = render_cmd(tpl, value)
    assert got == expect, f"state template {tpl!r} with value={value!r}: got {got!r}, want {expect!r}"
print("State templates OK")

assert payloads["payload_timer_off"]["command_topic"] == "cmnd/Siguro/TuyaSend2"
assert payloads["payload_timer_on"]["command_topic"] == "cmnd/Siguro/TuyaSend2"
assert payloads["payload_timer_left"]["state_topic"] == "stat/Siguro/timer_left"
print("Timer entities OK")
print("ALL CHECKS PASSED")
