# Siguro SGR-FN-U32xx (tower fan) — Tasmota technical reference

Everything about the fan's internals and its Tasmota configuration, verified
empirically on a Siguro **SGR-FN-U32xx** tower fan (Tasmota 16.0.0, ESP8266).
The Home Assistant side lives in `README.md`; contributor/agent context and the
testing methodology in `AGENTS.md`.

> Device-identifying values (IP/MAC/hostname, WiFi SSID, broker host names) are
> placeholders in this document — real values are intentionally not stored in
> the repository.

---

## 1. The fan

- Siguro **SGR-FN-U320W / SGR-FN-U321Y** tower fan.
- Internally the fan is **Tuya-based**: a Tuya MCU drives the motor, speed,
  modes, oscillation, ionizer, display and the timers, and talks Tuya's serial
  protocol to a small Wi-Fi daughterboard.
- **Conversion to Tasmota:** the original Tuya Wi-Fi module is replaced by a
  generic **ESP8266** board flashed with **Tasmota** (Tasmota 16.0.0 in our case). Tasmota's `TuyaMCU` driver speaks Tuya protocol to the fan's
  MCU over UART, so every fan function becomes a Tasmota component — and
  therefore an MQTT topic. Everything works 100% locally; no Siguro/Tuya cloud.
- Functions: power, speed 1–12, modes (Normal / Natural Breeze / Night),
  oscillation, ionizer, display on/off, and **two independent timers** (auto
  power-off while running, auto power-on while in standby), 0–12 h each.
- Tuya product id (from `TuyaSend8`): `ocajaux7xez7bpft`, firmware `1.0.0`
  (`{"p":"ocajaux7xez7bpft","v":"1.0.0","m":1}`).

### Manual behaviours worth knowing (from the user manual + confirmed live)

- **Two separate timers.** While running: timer = auto power-*down*. While in
  standby: timer = auto power-*up*. Set with the TIMER button + Fan+/Fan−
  (0–12 h), the value is saved after a short pause and the countdown starts.
  Setting the value back to `0` disables the timer.
- **Natural Breeze** varies the speed around the set speed: within the band
  1–4 (low), 5–8 (medium) or 9–12 (high) — the set speed selects the band.
- **Night** dims the noise/backlight and forces the speed down to **3** (set to
  3 immediately if it was 1–3; stepped down 1 step / 5 min if it was 4–12).
- The display blinks the remaining timer hours while a timer counts down.

## 2. Tuya data points (dpIds)

Mapping established empirically (see `AGENTS.md` for the methodology) with
`TuyaSend0`/`TuyaSend8` state dumps and button-press captures:

| dpId | Type      | Function                        | Values                        | Write command                      | Tasmota handle              |
| ---- | --------- | ------------------------------- | ----------------------------- | ---------------------------------- | --------------------------- |
| 1    | bool (1)  | Power                           | 0/1                           | `TuyaSend1 1,<0/1>` (or `POWER1`)  | `POWER1` (fnId 11)          |
| 2    | value (2) | Fan speed                       | **1..12** (= display numbers) | `TuyaSend2 2,<n>`                  | Rule3 → `stat/…/speed`      |
| 3    | enum (4)  | Operating mode                  | 0=Normal, 1=Natural, 2=Night  | `TuyaSend4 3,<n>`                  | Rule3 → `stat/…/mode`       |
| 5    | bool (1)  | Oscillation/swivel              | 0/1                           | `TuyaSend1 5,<0/1>` (or `POWER2`)  | `POWER2` (fnId 12)          |
| 8    | bool (1)  | Ionizer                         | 0/1                           | `TuyaSend1 8,<0/1>` (or `POWER3`)  | `POWER3` (fnId 13)          |
| 12   | bool (1)  | Display                         | 0/1                           | `TuyaSend1 12,<0/1>` (or `POWER4`) | `POWER4` (fnId 14)          |
| 14   | value (2) | Timer countdown, minutes        | 0…720, ticks down 1/min       | *(writes ignored)*                 | Rule3 → `stat/…/timer_left` |
| 102  | value (2) | **Auto power-ON** timer, hours  | 0…12                          | `TuyaSend2 102,<h>`                | Rule3 → `stat/…/timer_on`   |
| 103  | value (2) | **Auto power-OFF** timer, hours | 0…12                          | `TuyaSend2 103,<h>`                | Rule3 → `stat/…/timer_off`  |

Notes:

- The **timer** is one countdown (dpId 14, minutes) plus two set-points
  (dpId 102/103, hours). Whichever timer matches the power state is the active
  one: dpId 14 mirrors its value in minutes (`103,3` → `14=180`) and ticks down
  every minute. `TuyaSend2 102,…` written while the fan is **running** is
  acknowledged but not stored (reports back 0); the same for `103,…` written in
  standby (assumed by symmetry, not verified).
- Speed/mode/timer writes made while the fan is **off** are acknowledged but
  **discarded** — the MCU re-reports its stored values (see §5).
- dpIds 1/5/8/12 are plain booleans and map cleanly to Tasmota relays, so
  `POWER1..4` work natively (`cmnd/<topic>/POWER<n>` `ON`/`OFF`) and the state
  is published to `stat/<topic>/POWER<n>` automatically.
- Raw `TuyaReceived` frame keys double as rule triggers: `DpType1Id1`,
  `DpType2Id2`, `DpType4Id3`, `DpType1Id5`, `DpType1Id8`, `DpType1Id12`,
  `DpType2Id14`, `DpType2Id102`, `DpType2Id103` → rule syntax
  `tuyareceived#dptype<type>id<dpId>`.

## 3. Tasmota configuration (as built)

Assumes a fresh Tasmota on the replacement ESP8266. All commands go into the
Tasmota web UI **Console** (or via MQTT — see `AGENTS.md`; the HTTP `/cm` API is
disabled in this build: `StatusNET.HTTP_API = 0`). The recipe is
topic-independent (the rules use `%topic%`), so it works for any MQTT topic.

**1. Module**

```
Module 54
```

Module 54 = `TuyaMCU`. No template is required; the module uses UART0
(GPIO01 = Tuya Tx, GPIO03 = Tuya Rx) at **9600 8N1** (confirmed in
`StatusPRM`). Use a template instead of `Module 54` only if your board wires
the Tuya serial to other pins.

**2. Map the Tuya data points** (bools → relays; speed/mode/timer are handled
via `TuyaSend<x>` commands + rules):

```
Backlog TuyaMCU 11,1; TuyaMCU 12,5; TuyaMCU 13,8; TuyaMCU 14,12
```

| fnId | Component | dpId | Function    |
| ---- | --------- | ---- | ----------- |
| 11   | `POWER1`  | 1    | power       |
| 12   | `POWER2`  | 5    | oscillation |
| 13   | `POWER3`  | 8    | ionizer     |
| 14   | `POWER4`  | 12   | display     |

(The device restarts once after the mapping is applied — expect a brief
`LWT Offline`/`Online`.)

**3. State-republish rules** — republish every MCU-reported change (including
those made with the fan's own buttons) to dedicated topics. `publish2` marks
the messages retained, so state survives Home Assistant restarts:

```
Rule3 on tuyareceived#dptype2id2 do publish2 stat/%topic%/speed %value% endon on tuyareceived#dptype4id3 do publish2 stat/%topic%/mode %value% endon on tuyareceived#dptype2id103 do publish2 stat/%topic%/timer_off %value% endon on tuyareceived#dptype2id102 do publish2 stat/%topic%/timer_on %value% endon on tuyareceived#dptype2id14 do publish2 stat/%topic%/timer_left %value% endon
Rule3 1
```

Rule3 is 375 of 511 bytes on this firmware — 136 bytes free.

**4. Retain the native power states** as well (so `POWER1..4` also survive
restarts):

```
Backlog StateRetain 1; PowerRetain 1
```

**5. Keep MQTT clean** — don't publish raw `TuyaReceived` frames (that's the
debugging switch, `SetOption66 1`, see `AGENTS.md`):

```
SetOption66 0
```

**6. Recommended: readable topic and name** — nicer in MQTT explorers; you also
need the topic and the MAC address (web UI → *Information*) for the HA setup:

```
Backlog Topic Siguro; FriendlyName1 Siguro
```

**7. MQTT connection** — the fan must connect to the **same broker Home
Assistant uses**: discovery and state travel over one broker, and a mismatch
makes the entities appear but stay "unavailable". Configure with `MqttHost`,
`MqttPort`, and `MqttUser`/`MqttPassword` if the broker requires authentication.

**8. Optional: web-UI speed slider** (**not used on this installation
anymore** — applied earlier, removed 2026-11-05; see §6) — maps the speed to
Tasmota's dimmer so the web UI shows a slider. Apply *after* step 2 (the
device restarts once, and `DimmerRange` only works after that restart). Full
details, quirks and the reason for removal in §6:

```
Backlog TuyaMCU 21,2; DimmerRange 1,12
```

## 4. MQTT topics & state

| Item      | Value                                             |
| --------- | ------------------------------------------------- |
| FullTopic | `%prefix%/%topic%/` (default)                     |
| Prefixes  | `cmnd` / `stat` / `tele` (defaults)               |
| Topic     | configurable (example: `Siguro`)                  |
| LWT       | `tele/<topic>/LWT` — `Online`/`Offline`, retained |

State topics consumed by HA — **all retained**, replayed instantly to any new
subscriber (verified: a fresh subscriber receives all 9 states with zero device
activity). That is what makes state survive HA restarts without queries:

| Topic                     | Payload    | Source                                 |
| ------------------------- | ---------- | -------------------------------------- |
| `stat/<topic>/POWER1`     | `ON`/`OFF` | Tasmota native (PowerRetain) — power   |
| `stat/<topic>/POWER2`     | `ON`/`OFF` | Tasmota native (PowerRetain) — osc.    |
| `stat/<topic>/POWER3`     | `ON`/`OFF` | Tasmota native (PowerRetain) — ionizer |
| `stat/<topic>/POWER4`     | `ON`/`OFF` | Tasmota native (PowerRetain) — display |
| `stat/<topic>/speed`      | `1..12`    | Rule3 (dpId 2)                         |
| `stat/<topic>/mode`       | `0..2`     | Rule3 (dpId 3)                         |
| `stat/<topic>/timer_off`  | `0..12`    | Rule3 (dpId 103) — auto power-off, h   |
| `stat/<topic>/timer_on`   | `0..12`    | Rule3 (dpId 102) — auto power-on, h    |
| `stat/<topic>/timer_left` | `0..720`   | Rule3 (dpId 14) — countdown, minutes   |

Command topics:

| Topic                    | Payload    | Effect                                           |
| ------------------------ | ---------- | ------------------------------------------------ |
| `cmnd/<topic>/POWER1`    | `ON`/`OFF` | power                                            |
| `cmnd/<topic>/POWER2`    | `ON`/`OFF` | oscillation                                      |
| `cmnd/<topic>/POWER3`    | `ON`/`OFF` | ionizer                                          |
| `cmnd/<topic>/POWER4`    | `ON`/`OFF` | display                                          |
| `cmnd/<topic>/TuyaSend2` | `2,<n>`    | speed 1..12                                      |
| `cmnd/<topic>/TuyaSend4` | `3,<n>`    | mode 0..2                                        |
| `cmnd/<topic>/TuyaSend2` | `103,<h>`  | auto-off timer 0..12 h (while running)           |
| `cmnd/<topic>/TuyaSend2` | `102,<h>`  | auto-on timer 0..12 h (while standby)            |
| `cmnd/<topic>/TuyaSend0` | *(empty)*  | full state dump → rules re-seed all state topics |

## 5. Verified behaviours (empirically, via MQTT capture — don't re-litigate)

1. **Speed dpId 2 runs 1..12 raw = the numbers on the fan display.** (Raw 0
   untested.)
2. **Enum/value writes (speed, mode) are ignored by the MCU while the fan is
   OFF.** The write is acknowledged (`TuyaReceived` echo) but not stored; the
   MCU re-reports its stored values on the next query. HA state snaps back.
   Set speed/mode while the fan is running — writes made while it is off are
   lost.
3. **Timer writes are context-dependent**: `103,<h>` sticks only while the fan
   is running (auto-off), `102,<h>` only while in standby (auto-on). The
   non-matching one is acknowledged but reports back 0.
4. **dpId 14 is the live countdown** in minutes of the active timer; it mirrors
   the set-point immediately (`103,3` → `14=180`) and ticks down 1/minute
   (`180` → `179`…). Writes to dpId 14 are silently ignored.
5. **`TuyaSend0` and `TuyaSend8` both elicit a full state dump** of all dpIds
   on this MCU (unlike the Duux DXCF12 MCU, where they don't). `TuyaSend8`
   additionally returns the product info frame. Great for state refresh.
6. **Night mode forces the speed to 3** (dpId 2 jumps to 3 when Night is
   activated with speed 1–3; the manual confirms the step-down from 4–12).
   Changing the speed does **not** reset the mode (verified).
7. **Retained publishes solve HA-restart sync**: a fresh MQTT subscriber
   receives all 9 states instantly with no device activity. Seeding happens
   automatically because the rules fire on every MCU report — a `TuyaSend0`
   dump re-seeds everything on demand.
8. Power toggles cause the MCU to report dpId 1 (and the Tasmota relay
   publishes `stat/<topic>/POWER1`).
9. **Tasmota queries the MCU fully at every boot** (product-info handshake +
   complete dpId dump). The MCU's stored state wins, and the rules re-seed all
   state topics automatically at every Tasmota restart — great for recovery.
10. Heartbeats (`TuyaReceived` `Cmnd:0`, ~10 s) and the raw frame publishing
    (`SetOption66 1` → `tele/<topic>/RESULT`) are debugging aids only — the
    packaged config runs with `SetOption66 0`.
11. Quirk: some MCU interactions re-light the display shortly after it was
    switched off (observed once when the ionizer was switched on right after
    `display off`). A plain `POWER4 OFF` keeps the display dark.

## 6. Web-UI speed slider (dimmer mapping) — optional, removed here

The "dimmer trick" (used e.g. by *newadventuresinwi-fi* for ceiling fans) maps
the speed data point to Tasmota's dimmer component so the **Tasmota web UI
shows a slider** for the speed:

```
Backlog TuyaMCU 21,2; DimmerRange 1,12
```

> **Status on this installation: removed (2026-11-05)** — `TuyaMCU 21,0` was
> applied (device restarts), because of downside 4 below. `DimmerRange 1,12`
> is left set but inert. Verified after the removal: `TuyaMCU` reports only
> the four relay mappings, `STATE` no longer contains `Dimmer`, and the Tasmota
> discovery payload advertises `rl:[1,1,1,1]`, `lk:0`, `lt_st:0` (all channels
> = switch, no light).

- `TuyaMCU 21,2` maps fnId 21 (Dimmer1) to speed dpId 2. **The device restarts
  once** (the light driver activates), and only after that restart is
  `DimmerRange` accepted (before it: `Command Unknown`).
- `DimmerRange 1,12` makes `Dimmer <0..100>` scale onto the raw 1..12 range:
  `Dimmer 100` → raw 12, `Dimmer 50` → raw 7, `Dimmer 3` → raw 1 (verified).
  Conversely the MCU report (raw 3) shows up as `Dimmer: 18`.
- The HA package is **not affected** — the fan entity drives speed with raw
  `TuyaSend2 2,<n>` and never uses `Dimmer`.

**Downsides (all verified live — decide before keeping this):**

1. Tasmota's light subsystem binds its "power" to the **highest mapped
   relay** (verified: with display unmapped it commandeered POWER3/ionizer
   instead). With the standard map that is **POWER4 = the display**: every
   `Dimmer` change **turns the display ON**, and `Dimmer 0` (slider bottom)
   **turns the display OFF without touching the speed**. So the slider bottom
   blanks the display instead of stopping the fan. The display relay is the
   least-bad victim (power/oscillation/ionizer stay clean).
2. The web slider is a percentage, not the speed number: 12 steps quantize
   across 0–100 % (50 % = speed 7), and the shown % never equals the display
   number.
3. **Boot is safe** (verified with raw frames on): Tasmota does *not* push its
   stored dimmer at boot. It queries the MCU at startup (product-info
   handshake + full state dump), the MCU's stored speed wins, and the light
   syncs from the report (stored `Dimmer` 70 % snapped back to 55 % = raw 7).
4. **The light leaks into Home Assistant** when the device is also added to
   the native **Tasmota integration** (the case on this installation): the
   discovery payload `tasmota/discovery/<mac>/config` advertises POWER4 as a
   light channel (`rl:[1,1,1,2]`, `lk:1`, `lt_st:1`), so HA creates a
   `light.<device>` entity whose on/off **is the display switch** — and it
   lands in the room's "Lights" sections, where it reads as a light switch for
   the display. (The blueprint's own Display switch is a plain `switch` and
   unaffected; the duplicate light entity is what confuses the UI. Verified
   2026-11-05; after removing the mapping the same payload reads
   `rl:[1,1,1,1]`, `lk:0`, `lt_st:0`.) If you keep the mapping, disable that
   `light.…` entity in HA. Do **not** try `SetOption30 1` here — that
   announces *all* relays as lights and only makes it worse.

To remove the mapping again (back to §3 behaviour): `TuyaMCU 21,0` (device
restarts). `DimmerRange` then becomes inert.

## 7. Troubleshooting

**Commands seem to do nothing while the fan is off**
Expected — speed/mode writes are discarded in standby (§5.2) and timer writes
only work in their own power context (§5.3). This is a limitation of the MCU,
not of Tasmota or HA.

**Entities show "unknown" after HA restart**
State publishes are retained, so the broker replays the last state instantly.
If state is missing, the retained messages were cleared — send
`cmnd/<topic>/TuyaSend0` (empty payload) to re-seed all of them.

**Entities appear but stay "unavailable"**
The fan and Home Assistant are not using the same MQTT broker (§3.7), or the
LWT topic `tele/<topic>/LWT` is not `Online` — check the device is connected.

**Speed is off by one against the fan display**
Not expected on this unit (dpId 2 runs 1..12 raw = display). If a different
unit behaves differently, check what the MCU reports when the display shows
"1" (`TuyaSend0`) and adjust the templates accordingly.

**Display appears as a *light* in Home Assistant**
The optional dimmer mapping (§6) makes Tasmota's light component bind to
POWER4 = display, and the native Tasmota integration then creates a
`light.<device>` entity for it (it ends up in the room's lights). Fix: remove
the mapping (`TuyaMCU 21,0`, device restarts) or disable that entity in HA.
The blueprint's own Display switch is always a plain `switch` and needs no
fix.

**Removing / re-adding**
Delete the automation, then clear the retained discovery messages from the
broker — the ready-made `mosquitto_pub` commands are in `README.md`
(*Removing / re-adding*).
