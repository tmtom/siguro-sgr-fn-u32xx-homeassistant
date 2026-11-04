# AGENTS.md — Siguro SGR-FN-U32xx fan for Home Assistant (Tasmota)

Working context for agents on this repo. Read this first; device details live
in `tasmota-config.md`, user-facing docs in `README.md`.

## Goal

Package a Siguro SGR-FN-U32xx tower fan (SGR-FN-U320W / SGR-FN-U321Y) running
Tasmota firmware so HAOS users can install it **without editing
`configuration.yaml`**. Chosen approach (same as the Duux DXCF12 project):
an **HA blueprint** publishing MQTT discovery.

## Physical / network setup

| Item              | Value                                                                                                                                                   |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fan               | Siguro **SGR-FN-U32xx** tower fan (Tuya MCU + ESP8266 replacement module)                                                                               |
| Tasmota           | 16.0.0(release-tasmota), ESP8266EX                                                                                                                      |
| Device web API    | `http://<device-ip>/` web UI only — **`HTTP_API: 0`** in `StatusNET`, so the `/cm?cmnd=` HTTP API returns empty replies. Drive the device over **MQTT** |
| MQTT broker (fan) | broker host name is a placeholder here; port 1883, no password on the fan side                                                                          |
| Device topic      | **`Siguro`** (configurable — package takes it as input)                                                                                                 |
| FullTopic         | `%prefix%/%topic%/` (default; prefixes cmnd/stat/tele)                                                                                                  |
| MAC               | placeholder — real device values are intentionally not stored in this repo                                                                              |

## How to test Tasmota / Tuya (methodology used here — reuse it)

Everything is done over MQTT with the two helpers in `tools/`
(python3 + `paho-mqtt`; credentials via `MQTT_USER`/`MQTT_PASSWORD` env vars,
never in argv/files):

```
python tools/mqtt_cmd.py <topic> "<command> [params]" [secs] [broker] [port]
python tools/mqtt_listen.py <secs> <out.json> [topic_filter] [broker] [port]
```

`mqtt_cmd.py` puts the command word in the topic and parameters in the message
body (Tasmota convention), captures the replies and prints them. `mqtt_listen.py`
records a capture to JSON for later analysis. Keep raw captures in `work/`
(local scratch, git-ignored — see "Sanitization").

### Discovery procedure (dpId mapping)

1. **State dump first.** `TuyaSend0` and `TuyaSend8` both make this MCU report
   *every* dpId with type and value (`tele/<topic>/RESULT` → `TuyaReceived`
   JSON). `TuyaSend8` adds the product info frame (`{"p":…,"v":…,"m":…}`). This
   gives the full dpId/type inventory in one shot.
2. **Raw frames for debugging:** `SetOption66 1` publishes every `TuyaReceived`
   frame to `tele/<topic>/RESULT` (incl. heartbeats every ~10 s). Turn it off
   (`SetOption66 0`) for the final config. Rule triggers use the JSON keys:
   `tuyareceived#dptype<1|2|4>id<dpId>` (e.g. `DpType2Id2` → `dptype2id2`).
3. **Button-press capture to assign functions:** run `mqtt_listen.py` on
   `tele/<topic>/#`, then press **one function at a time** on the device panel
   (≥5–10 s between presses, note the order!), and correlate the `DpType…`
   reports. One press may produce no report at all — that means the button
   adjusts something only when its value actually changes (e.g. the Siguro
   timer button enters a setting mode; nothing is reported until Fan+/Fan−
   move the value).
4. **Write-probes to confirm control:** `TuyaSend1 <dp>,<0/1>` (bool),
   `TuyaSend2 <dp>,<n>` (value), `TuyaSend4 <dp>,<n>` (enum). Observe (a) the
   echo in `TuyaReceived`, (b) whether the value **sticks** (follow with
   `TuyaSend0` — MCUs can acknowledge a write and still discard it), (c) the
   physical effect — ask the user to look at the device. Mind the **power
   context**: this MCU discards speed/mode writes while off, and timer writes
   only stick in their own context (running ↔ auto-off, standby ↔ auto-on).
5. **Restore every probed state** afterwards (mode/speed/timers/power).

### Testing the finished config

- Rules + retains: `TuyaSend0` → all state topics must republish; then a fresh
  subscriber (`mqtt_listen.py` on `stat/<topic>/#`) must receive all states
  instantly (retained replay). This proves HA-restart sync.
- Native relays: `cmnd/<topic>/POWER2..4` `ON`/`OFF` must echo on
  `stat/<topic>/POWER2..4`.
- Remote controls vs panel buttons must land on the same topics.

## Tasmota configuration (as built — full detail in `tasmota-config.md`)

- `Module 54` (TuyaMCU), UART0 GPIO01/03, 9600 8N1.
- dpId map (`TuyaMCU`): 11→1 power (`POWER1`), 12→5 oscillation (`POWER2`),
  13→8 ionizer (`POWER3`), 14→12 display (`POWER4`). Speed (dpId 2, 1..12),
  mode (dpId 3, 0..2) and the timers (dpId 103/102 set-points + dpId 14
  countdown) are driven with `TuyaSend2`/`TuyaSend4` and republished by Rule3.
- Rule3 (ON, 375/511 bytes) publishes `stat/%topic%/speed|mode|timer_off|
  timer_on|timer_left` (plain values, `publish2` = retained).
- `StateRetain 1`, `PowerRetain 1` — native `POWER1..4` retained too.
- `SetOption66 0` — no raw `TuyaReceived` noise on MQTT.
- Optional, **removed on this installation (2026-11-05)**: `TuyaMCU 21,2` +
  `DimmerRange 1,12` = speed slider in the Tasmota web UI. Quirks documented
  in `tasmota-config.md` §6 — notably the light hijacks the highest relay
  (= display) and, with the native Tasmota integration in HA, the display
  leaks into HA as a `light.…` entity (shown among the room's lights).
  Removed with `TuyaMCU 21,0` (verified: discovery `rl:[1,1,1,1]`, `lk:0`,
  `lt_st:0`, no `Dimmer` in STATE); `DimmerRange 1,12` remains set but inert.

## Verified behaviours (empirically, via MQTT capture — don't re-litigate)

Full list in `tasmota-config.md` §5. The load-bearing ones for the HA package:

1. Speed dpId 2 runs **1..12 raw = display numbers**.
2. Speed/mode writes are **ignored while the fan is OFF** (acknowledged, then
   discarded); timer writes only stick in their own power context.
3. dpId 14 is a live countdown in minutes shared by both timers; writes ignored.
4. `TuyaSend0`/`TuyaSend8` **do** elicit full state dumps on this MCU (unlike
   the Duux one) — use `TuyaSend0` as the HA-start state refresher.
5. Retained publishes solve HA-restart sync (verified with a fresh subscriber;
   HA-restart state restore also confirmed live in HA on 2026-11-03).
6. Night mode forces speed 3; Natural mode varies speed within a band
   (1–4 / 5–8 / 9–12). Speed changes don't reset the mode.
7. With the dimmer trick active, Tasmota's Tasmota-integration discovery
   (`tasmota/discovery/<mac>/config`) advertises the display relay as a
   **light** channel (`rl:[1,1,1,2]`, `lk:1`, `lt_st:1`) and HA shows a
   display-bound `light.…` entity among the room's lights; without it the
   payload is `rl:[1,1,1,1]`, `lk:0`, `lt_st:0` (verified 2026-11-05,
   before/after `TuyaMCU 21,0`). `SetOption30` is a red herring: `1`
   announces *all* relays as lights.

## HA-side design (what the package contains)

MQTT discovery payload (fan + ionizer/display `switch` + auto-off/auto-on
`number` + countdown `sensor`, one device keyed on MAC, manufacturer `Siguro`,
model `SGR-FN-U32xx (tower fan)`) published by a blueprint automation on HA
start + device LWT Online. State topics are the Rule3/native retained topics;
speed/mode/timer commands are `TuyaSend2`/`TuyaSend4` payloads built with
command templates. **Inner command templates may only use `value`** — the
discovery payload is rendered by the blueprint and only `value` is in scope at
command time (lesson from the Duux project).

## Sanitization

Never commit device-identifying or private values — IP/MAC/hostname, WiFi
SSID/BSSID, broker host names, other LAN devices. Docs use placeholders; keep
test data (e.g. `tools/validate_blueprint.py`) fake. Raw MQTT captures go to
`work/`, which is **git-ignored** (`work/` captures have contained SSIDs, IPs
and MACs of unrelated devices — double-check before ever force-adding).

## Repo layout

| File                                                | Status                                                            |
| --------------------------------------------------- | ----------------------------------------------------------------- |
| `tasmota-config.md`                                 | fan/Tuya/Tasmota technical reference + troubleshooting — done     |
| `AGENTS.md`                                         | this file (context + testing methodology) — done                  |
| `blueprints/siguro-sgr-fn-u32xx-fan-discovery.yaml` | MQTT-discovery blueprint — live-tested in HA 2026-11-03           |
| `README.md`                                         | project overview + install guide — done                           |
| `tools/mqtt_cmd.py`                                 | send one Tasmota command over MQTT and print the replies          |
| `tools/mqtt_listen.py`                              | MQTT capture helper: `<secs> <out.json> [filter] [broker] [port]` |
| `tools/validate_blueprint.py`                       | offline check of the blueprint (dev tool)                         |
| `work/`                                             | local scratch (MQTT captures) — git-ignored, never committed      |
| `LICENSE`                                           | MIT, (c) 2026 tmtom                                               |

## Device change protocol

User requires: **document current config before any change** (`tasmota-config.md`),
then apply, then verify via MQTT capture. The device is fully configured per
`tasmota-config.md` §3 — **don't re-run the setup recipe blindly**. The device
is the user's live fan: keep writes minimal, restore any probed state (mode,
speed, timers, power), and ask the user to confirm physical effects.
