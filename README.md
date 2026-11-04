# Siguro SGR-FN-U32xx fan for Home Assistant (Tasmota)

Local control of the **Siguro SGR-FN-U32xx tower fan (SGR-FN-U320W /
SGR-FN-U321Y)** running **Tasmota** firmware (requires replacing the original
Tuya Wi-Fi module with a generic ESP8266 module) — packaged for Home Assistant
so it installs **without editing `configuration.yaml`**.

- Proper HA **fan** entity: 12 speeds, presets (Normal / Natural / Night),
  oscillation — plus **ionizer** and **display** switches, the fan's two
  **timers** (auto-off 0–12 h and auto-on 0–12 h) and a **countdown** sensor
- **100% local** — no Siguro/Tuya cloud, no account, no phone app
- One-click install via an **MQTT-discovery blueprint** (no YAML on the HA side)
- Live-tested in Home Assistant: all controls, entity states, panel-button
  sync and state restore across HA restarts (retained MQTT messages)

| HA feature            | Fan function                   |
| --------------------- | ------------------------------ |
| Power                 | on / off                       |
| Speed (1–12)          | fan speed                      |
| Preset mode           | Normal / Natural / Night       |
| Oscillation           | swing                          |
| Ionizer switch        | ionizer on / off               |
| Display switch        | display on / off               |
| Auto-off timer 0–12 h | power down after N h (running) |
| Auto-on timer 0–12 h  | power up after N h (standby)   |
| Timer countdown       | minutes remaining              |

The underlying Tuya data points and Tasmota commands are documented once, in
[`tasmota-config.md`](tasmota-config.md#2-tuya-data-points-dpids).

## The fan

The Siguro SGR-FN-U32xx is Tuya-based internally: a Tuya MCU drives the motor,
speed, modes, oscillation, ionizer, display and the timers over a serial
protocol. This project assumes the original Tuya Wi-Fi module has been replaced
by a generic **ESP8266** board running **Tasmota** — its `TuyaMCU` driver turns
every fan function into an MQTT topic.

Full hardware, Tuya-protocol and Tasmota details:
**[`tasmota-config.md`](tasmota-config.md)**.

## How it works

Home Assistant's MQTT integration supports
[MQTT discovery](https://www.home-assistant.io/integrations/mqtt/): a retained
JSON message on `homeassistant/<component>/<id>/config` creates entities
automatically. This repo ships a **blueprint** that publishes those discovery
messages as a tiny automation — on HA start and whenever the fan comes online —
identifying the device as `manufacturer: Siguro`,
`model: SGR-FN-U32xx (tower fan)`, keyed on the Tasmota MAC address (so
multiple fans each become their own device). Tiny **Tasmota rules** on the fan
republish state changes (retained) so HA always shows the current state.

## Requirements

- Home Assistant (OS or Container) ≥ 2022.8 with the **MQTT** integration and a
  broker (tested with Mosquitto). **The fan and HA must use the same broker.**
- Siguro SGR-FN-U32xx with **Tasmota** ≥ 13 (tested on 16.0.0, ESP8266)
- One-time Tasmota setup per device (~5 minutes)

## Installation

**1. Configure the fan** — follow the recipe in
[`tasmota-config.md`](tasmota-config.md#3-tasmota-configuration-as-built)
(module, data-point map, state-republish rules, retains). Note the device's
**MQTT topic** and **MAC address** (web UI → *Information*) — you need both for
step 2.

**2. Add it to Home Assistant — blueprint**

[![Open your Home Assistant instance and show the blueprint import dialog with
a specific blueprint
pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https://github.com/tmtom/siguro-sgr-fn-u32xx-homeassistant/blob/main/blueprints/siguro-sgr-fn-u32xx-fan-discovery.yaml)

Or import it manually:

1. Copy
   [`blueprints/siguro-sgr-fn-u32xx-fan-discovery.yaml`](blueprints/siguro-sgr-fn-u32xx-fan-discovery.yaml)
   into `config/blueprints/automation/` of your HA installation.
2. **Settings → Automations & scenes → Create automation → Import blueprint**,
   pick *Tasmota Discovery: Siguro SGR-FN-U32xx Tower Fan*.
3. Fill in the inputs: **Name**, **Tasmota MQTT topic**, **MAC address**
   (format `AABBCCDDEEFF` or `AA:BB:CC:DD:EE:FF`).
4. Save and enable the automation — the fan appears within seconds. Run the
   automation once manually if you don't want to wait for an HA restart.

Repeat per fan (each fan = its own automation with its own topic + MAC).

### Removing / re-adding

Delete the automation, then clear the retained discovery messages from the
broker:

```
mosquitto_pub -h <broker> -r -t 'homeassistant/fan/<macaddr>/config' -n
mosquitto_pub -h <broker> -r -t 'homeassistant/switch/<macaddr>/ionizer/config' -n
mosquitto_pub -h <broker> -r -t 'homeassistant/switch/<macaddr>/display/config' -n
mosquitto_pub -h <broker> -r -t 'homeassistant/number/<macaddr>/off_timer/config' -n
mosquitto_pub -h <broker> -r -t 'homeassistant/number/<macaddr>/on_timer/config' -n
mosquitto_pub -h <broker> -r -t 'homeassistant/sensor/<macaddr>/timer_left/config' -n
```

## Known behaviours (MCU quirks)

- **Speed and mode changes only take effect while the fan is running** — the
  Tuya MCU acknowledges writes in standby but discards them (HA state snaps
  back). This is a limitation of the fan's MCU, not of this package.
- **The timers are context-dependent**: the auto-*off* timer can only be set
  while the fan is running, the auto-*on* timer while it is in standby — same
  as with the fan's own buttons. The countdown sensor shows the active timer.
- Night mode forces the speed down to 3; Natural mode varies the speed within
  the band of the set speed (1–4 / 5–8 / 9–12). Both are fan behaviours.
- **If you also use the native Tasmota integration in HA**, skip the optional
  web-UI speed slider from [`tasmota-config.md`](tasmota-config.md#6-web-ui-speed-slider-dimmer-mapping--optional-removed-here)
  (or remove it again with `TuyaMCU 21,0`): Tasmota then advertises the
  display as a *light*, and HA shows a second, display-bound light entity in
  the room's lights. The blueprint's Display switch is unaffected.

Full detail on these and other verified behaviours: `tasmota-config.md` §5.

## Repository layout

| File                                                | Purpose                                                       |
| --------------------------------------------------- | ------------------------------------------------------------- |
| `README.md`                                         | this overview and install guide                               |
| `tasmota-config.md`                                 | fan internals, Tuya protocol, Tasmota setup & troubleshooting |
| `blueprints/siguro-sgr-fn-u32xx-fan-discovery.yaml` | MQTT-discovery blueprint                                      |
| `AGENTS.md`                                         | contributor/agent context and verified behaviours             |
| `tools/mqtt_cmd.py`                                 | send one Tasmota command over MQTT                            |
| `tools/mqtt_listen.py`                              | MQTT capture helper used for verification                     |
| `tools/validate_blueprint.py`                       | offline check of the blueprint (dev tool)                     |
| `LICENSE`                                           | MIT                                                           |

## Credits

- [tasmota/blueprints](https://github.com/tasmota/blueprints) — the
  "Tasmota Discovery" blueprint pattern this is based on
- the [Duux DXCF12 project](https://github.com/tmtom/duux-dxcf12-homeassistant)
  by tmtom — the sibling project whose structure this one follows
- [New Adventures in Wi-Fi](https://newadventuresinwi-fi.blogspot.com/2019/12/brilliant-smart-ceiling-fan-remote-in-home-assistant.html)
  — the Tasmota dimmer trick for a web-UI speed slider (optional, see
  `tasmota-config.md` §6)
