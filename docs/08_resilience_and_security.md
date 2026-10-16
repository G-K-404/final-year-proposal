# 08 · Resilience to adversity, and security

The brief asks for a system that survives mine disasters well enough to locate people for rescue. Its
baseline also says "adversary-resilient". This document covers both: **physical adversity** (roof falls,
explosions, fire, water, gas, power loss) and **cyber adversaries** (spoofing, jamming, tampering).

---

## 1. Adversity scenarios

| Scenario | What breaks | How the system detects it | How it keeps working | What the twin shows for rescue |
|---|---|---|---|---|
| **Roof fall** (local) | Cables, nodes, sometimes the wearer | Helmet high-g strike (> ~50 g) then no motion → man-down after a 30 s cancel window; node silence pattern | Mesh routes around dead nodes; wearable logs locally and beacons; LF/UWB rescue beacon | Last known position + strike time; fall location from node failures; reachable set |
| **Methane / coal-dust explosion** | Wide damage, power loss, fibre cuts, CO | **Overpressure step on several barometers** (nodes + wearables) within milliseconds; CO rise; mass node loss | All wearables → EMERGENCY; ULF evacuation page (needs no in-mine infrastructure); refuge TTE uplink; wearable backup cells | Explosion source estimate from pressure-wave arrival times; blocked segments; refuge occupancy over TTE |
| **Mine fire** | Visibility (smoke), cameras, ventilation | CO at nodes and wearables; thermal saturation; temperature | Radar and UWB unaffected by smoke; evacuation routes from the twin avoid smoke-logged segments (ventilation model) | Smoke spread estimate; light/air remaining per person |
| **Inundation / water inrush** | Low-lying nodes; RF blocked by water | Water-level switches at sump/low-point nodes; sudden node losses; barometer | Wearables IP68; nodes in low areas mounted high; twin marks flooded segments | Persons trapped up-dip; refuge status |
| **Gas inrush (CH4 / CO2)** | Machines trip at the gas limit | Gas sensors at nodes and supervisor units | **Wearables and nodes are Ex ia (Ma) and keep running** in an explosive atmosphere; machines (Ex d/ib) are de-energised as required | Gassy segments as no-go zones |
| **Mine power failure / fan stoppage** | Line power to nodes | Node "on standby power" status; barometric step across the mine (ventilation change) | Nodes on batteries ≥ 24 h (MSHA [E1]), target 96 h; state of charge reported | Remaining standby hours per node |
| **Highwall / slope failure (OC)** | Machines and people near the toe | Slope-radar alerts (SCCL already tenders slope-stability radar) fed to the twin as a dynamic geofence | Evacuate the geofence through wearables and VPB | Who was inside the failure polygon |
| **Heat stress** | Workers (Indian summers; deep hot workings) | Temperature + humidity at the wearable → heat index | Wearable and supervisor warnings, work-rest prompts | Exposure log |
| **Lightning (OC)** | Pole nodes, antennas | Surge counters | Surge arresters, grounding, fused PoE | Node faults |

## 2. Survivability specifications

| Unit | Ingress / mechanical | Temperature | Explosion protection | Power autonomy |
|---|---|---|---|---|
| MSU (UG wearable) | IP68 (1.5 m, 30 min); 2 m drop onto concrete; crush-resistant belt-pack shell; potted crown pod | −20…+60 °C | **Ex ia I Ma** (stays safe with two faults, so it can keep running after a methane inrush) | Lamp battery + **backup cell ≥ 96 h** beaconing (design ≈ 638 h†) |
| SPU (surface wearable) | IP67; 2 m drop; UV-stable | −10…+70 °C (sun-exposed) | — | ≥ 1 week of shifts per charge |
| VSU (machine) | Exterior sensors **IP69K** (pressure washing); IP67 enclosures; vibration-isolated mounts; ISO 16750-class electrical environment | −20…+85 °C components | UG: Ex d enclosure for the computer, Ex ia/ib sensors | Hold-up supply for cranking and key-off |
| Infrastructure node | IP67; recessed niche or behind a steel guard; cables routed to avoid blast forces perpendicular to them [E1] | −10…+60 °C | Ex ia / Ex d as certified | Standby ≥ 24 h, target 96 h; LiFePO4 in a certified enclosure |
| Refuge Comms Node + TTE | Inside the refuge chamber | — | Certified | ≥ 96 h (refuge-alternative duration [E26]) |

† [tools/generated_tables.md](tools/generated_tables.md)

## 3. Redundancy and standby

| MSHA guidance [E1] | This design |
|---|---|
| Redundant signal pathways to the surface; a single disruption must not break communication | Fibre ring through **two separate roadways** + 865 MHz mesh + optional MF + TTE |
| Display pathway disruptions and malfunctions | Twin shows every link and node state live |
| Standby power, show line vs standby power, state of charge accounting for ageing | Every node reports power source and ageing-corrected state of charge |
| Tracking keeps working after a power loss (24 h typical) | Nodes on battery, wearables on their own power |
| Last known location shown when a tag isn't communicating; location stored ≥ 2 weeks; storage unaffected by link interruptions | Twin + node-local storage + wearable black box |
| Daily check of worn devices; weekly infrastructure examination; manual tracking procedure during failures | Dock self-test at every check-out; weekly node report; paper check-in/out fallback in the SOP |

## 4. Black box and Rescue Locator

**Wearable black box (≥ 72 h rolling, non-volatile):**

* position estimates with uncertainty and source;
* every event (alarms, lamp state, mode changes, impacts, SOS);
* minute summaries of motion, barometer, CO and temperature;
* last contact time on each link.

It can be read through the dock contacts, or through NFC/BLE at close range even if the long-range radios
are dead.

**Rescue Locator (handheld for rescue teams):**

| Function | How |
|---|---|
| Coarse search (tens of metres) | Listens for 865 MHz BACKUP beacons (RSSI + direction from a small antenna array) and UWB blinks (range) |
| **Final approach through rubble** | The wearable's 3-axis LF coils switch to **transmit** (10 ms pulses every 2 s at 125 kHz, or on command). The locator's 3-axis receiver follows field strength and field-line direction, as avalanche transceivers do with 457 kHz beacons under snow. Skin depth at 125 kHz in 100 Ω·m rock is about 14 m, so a few metres of broken rock attenuate the field only modestly (to be validated in a test pile) |
| Read the black box | NFC/BLE once within reach |
| Talk to the buried person | Wearable vibration/lamp patterns as yes/no answers to the locator's queries |

## 5. Functional safety

| Safety function | Hazard addressed | Target | Architecture |
|---|---|---|---|
| SF1 Start-inhibit | Machine starts with a person in or under its first-motion path | ISO 13849-1 **PL d**, Category 3 | Two input channels (UWB + LF), monitored relay, energised-to-permit |
| SF2 UG stop / function inhibit | Machine trams or moves a function into a person | PL d | Two-layer confirmation, machine controller interface, cross-monitoring |
| SF3 Danger alarm | Operator unaware of a person in the path | PL c | Two independent alarm channels (cab + wearable) |
| SF4 Emergency notification | Miners unaware of a disaster | Best effort, multiple paths | 865 MHz + VPB rebroadcast + ULF paging |

Process: HAZOP over the machine-person scenarios → FMEA (below) → verification by test (NIOSH Appendix B,
ISO 21815-1 test procedures [E8]) → proof tests: pre-shift bump test, weekly infrastructure check.

## 6. FMEA (top items)

| Item | Failure mode | Effect | Detection | Mitigation |
|---|---|---|---|---|
| Wearable UWB radio | Dead or antenna broken | Person invisible to UWB | Dock self-test; no blink seen by infrastructure → "silent tag" | LF shell still works; radar/thermal; supervisor alert; worker returns |
| Wearable battery | Lamp battery flat | Lamp and unit lose main power | State-of-charge events | Backup cell, MAIN_POWER_LOST event |
| Machine UWB anchor | Failed / blocked | Coverage hole | Inter-anchor self-ranging | PDS FAULT; remaining anchors + LF |
| LF generator | Coil open / driver fault | No near-field shell | Loop-current monitor | PDS FAULT |
| Radar | Mud-covered / failed | No untagged detection on that side | Reference-reflector check, no-return check | PDS FAULT, cleaning SOP |
| Safety controller | Hang | No alarms | External watchdog | Fail-safe relays (start blocked), cab fault lamp |
| Perception computer | Crash | No untagged layer | Heartbeat to the controller | Cooperative layers continue; fault shown |
| Infrastructure node | Destroyed / no power | Zone coverage loss | Twin link status | Mesh reroute; machines as moving anchors |
| Fibre | Cut | Backbone segment loss | Ring protection alarm | Second route, mesh |
| Twin server | Down | No awareness / roll-call | Watchdog from the control room | Hot standby; nodes buffer data |
| Map | Out of date (new heading) | Wrong geofences / constraints | Map age and survey reconciliation | Relative safety does not depend on the map; survey SOP |
| GNSS | Multipath / spoofing | Wrong OC pose | Integrity checks, UWB cross-check | Widen zones, fall back to UWB |

## 7. Cyber adversaries

| Threat | Possible harm | Mitigation |
|---|---|---|
| **Distance-enlargement / relay attack on UWB** | A person appears farther away than they are → missed alarm | IEEE 802.15.4z **STS** secure ranging [E20]; plausibility checks (range rate vs IMU and LF); LF shell is an independent physical check |
| Spoofed tags / fake machine beacons | Nuisance alarms; false roll-call | Per-device keys, AES-CCM MIC, frame counters (replay), group keys per shift |
| Jamming (UWB or 865 MHz) | Loss of detection | Noise-floor and exchange-loss monitoring → **fault alarm**, slow-down advice; LF and radar layers continue |
| GNSS spoofing / jamming (OC) | Wrong poses | Multi-constellation integrity, UWB V2V cross-check, IMU/odometry consistency |
| Firmware tampering | Arbitrary behaviour | Secure boot, signed firmware, updates only through the dock or a signed backhaul channel, A/B partitions |
| Compromised node or server | Data manipulation, outage | OT network segmented from IT; mutual TLS for MQTT; role-based access; audit logs; IEC 62443-style zones and conduits; offline backups |
| Insider misuse of location data | Privacy harm | Purpose limitation, access logging, retention limits ([07 §9](07_digital_twin.md)) |
| Physical theft of keys | Impersonation | Keys provisioned at the dock, rotated per shift, revocable; no long-term secrets in field radios beyond device keys |

**Principle:** the cyber design never trades away the fail-safe behaviour. Any security check that
fails is treated as a fault (alarm and conservative mode), never as "all clear".
