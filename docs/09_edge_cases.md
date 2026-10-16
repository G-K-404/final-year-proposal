# 09 · Edge-case catalogue

One hundred situations that break naive designs. Each row says how this design handles it and where it is
specified. Use it as a review checklist and as a test-scenario list for the simulator and the pilot
([10](10_simulation_and_data.md)).

---

## A. How the person is standing or wearing the unit

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-01 | Worker bends over or crouches: the body blocks the UWB path (the base paper's tag failed here [P1]) | LF shell is body-transparent; antenna on the helmet crown; track continuity; optional second UWB radio on the belt pack | [03 §4](03_positioning_and_sensing.md), [04 §3](04_sensor_placement.md) |
| EC-02 | Crawling in a low seam: helmet faces forward, rear is blocked | Belt-pack UWB (production); LF; posture flag sets the tag height for the solver | [03 §3.3](03_positioning_and_sensing.md) |
| EC-03 | Worker lying down near or under a machine (resting, injured) | Under-body LF + start-inhibit; 60 GHz presence radar at key-on; man-down detection | [06 §12](06_collision_avoidance_logic.md) |
| EC-04 | Helmet taken off (heat) | Belt pack keeps LF, IMU and radio; helmet-off detected (crown pod still, belt moving) → reminder, then supervisor | [04 §3](04_sensor_placement.md) |
| EC-05 | Unit left behind on a hook, machine or bench | "Stationary unit during shift in a work area > 30 min" → acknowledgement request → supervisor | [07 §5](07_digital_twin.md) |
| EC-06 | Units swapped between people, or two units on one person | Dock binds unit to ID card per shift; swap detected at dock | [04 §6.5](04_sensor_placement.md) |
| EC-07 | Person against steel or carrying steel (LF distortion) | Per-machine field map; shell thresholds with margin; UWB as second layer | [03 §4.2](03_positioning_and_sensing.md) |
| EC-08 | Very tall or short persons | Tag height from the person's dock profile | [03 §3.3](03_positioning_and_sensing.md) |

## B. Operators and occupants

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-09 | Operator steps out with the engine running | Exclusion ends at the cab boundary; becomes a pedestrian | [06 §5](06_collision_avoidance_logic.md) |
| EC-10 | Operator of machine A walks near machine B | Ordinary pedestrian for B | [06 §5](06_collision_avoidance_logic.md) |
| EC-11 | Trainee or second person in the cab | Passenger rule, logged | [06 §5](06_collision_avoidance_logic.md) |
| EC-12 | Person riding outside a machine (ladder, dump body, **LHD bucket**) | "Person on machine": start-inhibit; L4 if moving; twin event | [06 §5](06_collision_avoidance_logic.md) |
| EC-13 | Remote-control CM operator steps into a red zone | Function-specific inhibit | [06 §4.2](06_collision_avoidance_logic.md) |
| EC-14 | Operator's own unit has failed | Operator login by NFC; "operator unit fault" shown; repair before shift | [08 §6](08_resilience_and_security.md) |

## C. Machine shape and state

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-15 | Articulated machine steering: the pinch zone grows | Articulation encoder bends the hull polygon; anchors and coils at the joint | [04 §4.4](04_sensor_placement.md) |
| EC-16 | Excavator house rotating with anchors on it | Swing encoder; zones in the house frame; swing exclusion annulus | [04 §4.2](04_sensor_placement.md) |
| EC-17 | Dump body raised while tipping | No sensors on the body; overhead-line geofence on body-up | [06 §8](06_collision_avoidance_logic.md) |
| EC-18 | Loader bucket raised: front blind | Front sensors above the raised-bucket line | [04 §4.4](04_sensor_placement.md) |
| EC-19 | Bidirectional shuttle car | Leading end from travel direction | [04 §5.4](04_sensor_placement.md) |
| EC-20 | Train length changes | End-of-train unit | [04 §5.5](04_sensor_placement.md) |
| EC-21 | Towing a disabled machine | Tow pairing suppresses alarms only between the pair | [06 §6](06_collision_avoidance_logic.md) |
| EC-22 | **Runaway**: moving with no operator or engine off (brake failure); runaway tubs on haulage | Motion without operator/engine → "RUNAWAY" L4 broadcast to everything in the path; tub/EOT overspeed → junction signals | [06 §7](06_collision_avoidance_logic.md) |
| EC-23 | Loaded on a steep downgrade | a_eff from grade and payload; zones grow automatically | [06 §1](06_collision_avoidance_logic.md) |
| EC-24 | Contractor machine without a unit | Magnetic clip-on VTU issued at the gate; otherwise perception layer; twin flags "uninstrumented machine" | [04 §4.7](04_sensor_placement.md) |
| EC-25 | People gathered around a machine while its unit was off | Key-on LF sweep + presence radar before start is permitted | [06 §12](06_collision_avoidance_logic.md) |
| EC-26 | Machine parked for days | Full self-test at key-on | [06 §12](06_collision_avoidance_logic.md) |

## D. Sensing environment

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-27 | Dust (haul roads, blasting) | Radar and UWB unaffected; cameras degrade (operator aid only) | [03 §8](03_positioning_and_sensing.md) |
| EC-28 | Monsoon rain, water spray | IP67/IP69K; radar and UWB robust | [08 §2](08_resilience_and_security.md) |
| EC-29 | Night / darkness | Thermal, radar, UWB; IR cameras | [03 §8](03_positioning_and_sensing.md) |
| EC-30 | Sun glare; sun-heated rocks look "hot" to thermal | Thermal never decides alone; fused with radar | [03 §8](03_positioning_and_sensing.md) |
| EC-31 | Hot underground workings: low thermal contrast | Radar micro-Doppler is the primary untagged layer underground | [03 §8](03_positioning_and_sensing.md) |
| EC-32 | Mud or coal dust caked on sensors | Self-test (reference reflector, image contrast, inter-anchor ranging); cleaning SOP | [08 §6](08_resilience_and_security.md) |
| EC-33 | Strong multipath near steel (workshops, conveyors) | NLOS classifier; anchor redundancy; LF field maps | [03 §3.4](03_positioning_and_sensing.md) |
| EC-34 | Steel ventilation door between person and machine | Door-mounted node; treated as a blind junction | [04 §6.1](04_sensor_placement.md) |
| EC-35 | LF-band electrical noise (VFDs, cables) | Coded LF patterns with correlation; site noise survey; configurable carrier | [03 §4.3](03_positioning_and_sensing.md) |
| EC-36 | Interference with existing radios (leaky feeder 150/450 MHz, Wi-Fi, CM remote controls) | RF site survey; 865 MHz channel plan; UWB did not interfere with mine WLAN, radio, Bluetooth or GPS in field tests [P9] | [05 §2](05_communication.md) |
| EC-37 | Tag within 0.3 m of an anchor (near-field bias, saturation) | Treated as "contact" → L4 | [06 §3](06_collision_avoidance_logic.md) |

## E. Untagged and unexpected objects

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-38 | Visitor or contractor without a unit | Perception layer → "UNTAGGED PERSON" | [03 §8](03_positioning_and_sensing.md) |
| EC-39 | Trespassers or coal scavengers in the pit at night | Same, plus twin security alert | [07 §7](07_digital_twin.md) |
| EC-40 | Cattle or dogs on haul roads | Radar/thermal "animal/object" → caution | [06 §3](06_collision_avoidance_logic.md) |
| EC-41 | People resting in the shade under parked machines | Presence radar at key-on; SOP rest shelters | [06 §12](06_collision_avoidance_logic.md) |
| EC-42 | Boulder fallen on a haul road | Radar object → L1/L2; road-maintenance report to the twin | [07 §7](07_digital_twin.md) |
| EC-43 | Villagers or children near the lease boundary | Perimeter geofence + untagged detection | [07 §1](07_digital_twin.md) |

## F. Crowds and capacity

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-44 | Shift-change crowd beside a machine | Capacity: ~400 fixes/s per machine with prioritisation; LF shell has no capacity limit | [05 §3.4](05_communication.md) |
| EC-45 | Many machines in a loading area or workshop | UWB channel and preamble-code planning; paired-loading and workshop contexts | [05 §3.3](05_communication.md) |
| EC-46 | Hundreds of tags under one gateway | Event-driven traffic, adaptive PHY, randomised heartbeats | [05 §4](05_communication.md) |

## G. Device failures and logistics

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-47 | Unit faulty at check-out | Dock self-test refuses to issue; spare unit | [04 §6.5](04_sensor_placement.md) |
| EC-48 | Unit fails mid-shift ("silent tag") | Infrastructure and machines expect blinks on vehicle routes; silence → supervisor; worker escorted or given a spare | [08 §6](08_resilience_and_security.md) |
| EC-49 | Backup cell degraded | Measured at the dock; replace | [08 §3](08_resilience_and_security.md) |
| EC-50 | Firmware update fails | A/B partitions; updates only in the dock | [08 §7](08_resilience_and_security.md) |
| EC-51 | Unit not returned at shift end | Missing-person escalation | [07 §5](07_digital_twin.md) |
| EC-52 | Battery overheating in hot conditions | Protected cells, LiFePO4 in nodes, thermal cut-offs, shaded docks | [08 §2](08_resilience_and_security.md) |
| EC-53 | Machine unit fault | PDS FAULT policy | [06 §10](06_collision_avoidance_logic.md) |
| EC-54 | Anchor knocked out of position or re-welded | Inter-anchor self-ranging detects it; recommission after repairs | [03 §3.6](03_positioning_and_sensing.md) |

## H. Communication failures

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-55 | Backbone down | Local safety unaffected; events buffered | [02 §6](02_architecture.md) |
| EC-56 | Twin server down | Hot standby; nodes store data locally | [07 §8](07_digital_twin.md) |
| EC-57 | Person in an area without coverage (bleeders, remote workings) | ISOLATED mode, store-and-forward; MSHA-style check-in/out for such areas [E1] | [05 §4.1](05_communication.md) |
| EC-58 | Radio jamming | Fault alarm + conservative mode; LF and radar continue | [08 §7](08_resilience_and_security.md) |
| EC-59 | Device clock lost | TWR needs no synchronisation; logs re-timed at the dock | [03 §3.2](03_positioning_and_sensing.md) |
| EC-60 | Device holding an old map version | Keeps working; flags "map stale"; twin decodes by version | [07 §4](07_digital_twin.md) |

## I. Positioning failures

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-61 | GNSS degraded in a deep pit or near a highwall | Zones widen; UWB takes over | [03 §7](03_positioning_and_sensing.md) |
| EC-62 | GNSS multipath jump (15 m seen by NIOSH [P3]) | Integrity checks against IMU, odometry and UWB V2V | [03 §7](03_positioning_and_sensing.md) |
| EC-63 | New heading not yet in the map | Relative safety does not use the map; dead reckoning unconstrained there; survey SOP; machine LiDAR can propose map updates | [07 §1](07_digital_twin.md) |
| EC-64 | Multi-level workings, inclines | Barometer + graph levels | [03 §5](03_positioning_and_sensing.md) |
| EC-65 | Person in a cage, skip or man-riding system | Treated as a "conveyance" entity; positions along the shaft; no machine alarms | [07 §2](07_digital_twin.md) |
| EC-66 | Person riding a conveyor belt (prohibited) | Motion at belt speed along a conveyor segment → L3 + twin event | [07 §3](07_digital_twin.md) |

## J. Mine operations

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-67 | Blasting | Blast mode + zero-count clearance | [06 §9](06_collision_avoidance_logic.md) |
| EC-68 | Maintenance / lockout-tagout | Maintenance geofence; start-inhibit latched; lockout-key integration | [06 §4](06_collision_avoidance_logic.md) |
| EC-69 | Shovel–truck loading | Paired-loading suppression between machines only | [06 §6](06_collision_avoidance_logic.md) |
| EC-70 | Dozer working at a dump point | Both machines + edge geofence | [06 §8](06_collision_avoidance_logic.md) |
| EC-71 | Refuelling (bowser + machine + attendant) | Service pairing; start-inhibit while the attendant is in the zone | [06 §4](06_collision_avoidance_logic.md) |
| EC-72 | Tyre change: person beside a wheel for hours | Maintenance mode; start-inhibit | [06 §4](06_collision_avoidance_logic.md) |
| EC-73 | Road crew working on a haul road | Temporary work-zone geofence: speed limit + alerts to approaching trucks | [06 §8](06_collision_avoidance_logic.md) |
| EC-74 | Pedestrian crossing points | Crossing geofence with higher sensitivity | [06 §8](06_collision_avoidance_logic.md) |

## K. Underground-specific

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-75 | Blind crosscut corners | Junction Guardians relay beacons and drive signals | [04 §6.1](04_sensor_placement.md) |
| EC-76 | Person correctly standing in a manhole/refuge hole as a loco passes | Refuge-hole geofence = safe position: driver sees it; no alarm to the person | [06 §6](06_collision_avoidance_logic.md) |
| EC-77 | Runaway tubs on rope haulage | Tub/EOT overspeed detection → alarms along the haulage | [04 §5.5](04_sensor_placement.md) |
| EC-78 | Longwall face: shearer and people along the face | Face anchors every 10th support; drum LF zones | [04 §5.7](04_sensor_placement.md) |
| EC-79 | Low seam; people stooping | Tag height from the posture flag | [03 §3.3](03_positioning_and_sensing.md) |
| EC-80 | Methane above the limit | Machines trip; wearables and nodes (Ex ia Ma) keep running | [08 §1](08_resilience_and_security.md) |
| EC-81 | Ventilation doors opening and closing | Door state at nodes; barometric changes interpreted | [08 §1](08_resilience_and_security.md) |

## L. Opencast-specific

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-82 | LMV in a big truck's front blind area | Start-inhibit, front radar, VTU | [04 §4.7](04_sensor_placement.md) |
| EC-83 | Two-way traffic and overtaking on haul roads | Path-based V2V using the site's lane rule | [06 §7](06_collision_avoidance_logic.md) |
| EC-84 | Staff motorcycles | Clip-on VTU; rules | [04 §4.7](04_sensor_placement.md) |
| EC-85 | Bench-corner intersections without line of sight | OC Guardians on poles | [04 §6.2](04_sensor_placement.md) |
| EC-86 | Extreme heat (45 °C+) | Component ratings, battery derating, shaded docks | [08 §2](08_resilience_and_security.md) |
| EC-87 | Monsoon flooding at the pit bottom | Water geofences; IP67 | [08 §1](08_resilience_and_security.md) |

## M. Emergencies

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-88 | Two emergencies at once (fire + roof fall) | Twin multi-event handling; prioritised rescue planner | [07 §6](07_digital_twin.md) |
| EC-89 | Unconscious person (no acknowledgement) | Man-down escalation | [08 §1](08_resilience_and_security.md) |
| EC-90 | After an explosion, some go to refuges and some try to escape | Reachable sets; TTE delta roll-call | [07 §6](07_digital_twin.md) |
| EC-91 | Rescue team enters | Rescue units are a separate class (not counted missing); Rescue Locator | [08 §4](08_resilience_and_security.md) |

## N. Human factors

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-92 | Alarm fatigue | Nuisance control, graded alarms, volume floor | [06 §3, §6](06_collision_avoidance_logic.md) |
| EC-93 | Operators muting or disconnecting displays (NIOSH saw it [P3]) | Tamper detection → supervisor report | [06 §3](06_collision_avoidance_logic.md) |
| EC-94 | Language and literacy | Voice prompts in Telugu, Hindi and English; icons; zone-diagram training [P3] | [06 §3](06_collision_avoidance_logic.md) |
| EC-95 | Hearing protection | Vibration + lamp flash | [04 §3](04_sensor_placement.md) |
| EC-96 | Over-reliance on the system | SOP: it supplements, never replaces, safe procedures [P3, E8] | [01 §5](01_requirements.md) |

## O. Security and privacy

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-97 | Distance-enlargement attack on UWB | STS secure ranging + LF independent check | [08 §7](08_resilience_and_security.md) |
| EC-98 | Workers' privacy concerns | Governance policy agreed before the pilot | [07 §9](07_digital_twin.md) |

## P. Regulatory and organisational

| ID | Edge case | Handling | Ref |
|---|---|---|---|
| EC-99 | Radio type approval delays; unclear classification of vehicle-mounted UWB | Engage WPC early; implement both TPC and duty-cycle limiting | [01 §4.1](01_requirements.md) |
| EC-100 | Long lead time for IS certification and DGMS approval underground | OC pilot first; UG demonstrator in a non-gassy training gallery | [10 §5](10_simulation_and_data.md) |
