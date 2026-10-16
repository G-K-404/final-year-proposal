# 01 · Requirements and constraints

This document fixes **what the system must achieve, in numbers**, before any design choice. Later
documents trace back to the requirement IDs here (`R-POS-*`, `R-CA-*` and so on). Citations in square
brackets point to [12_references.md](12_references.md).

---

## 1. Problem statement

Mobile machines in mines kill people in two ways: they **run over or crush people on foot**, and they
**collide with other machines, especially light vehicles hidden in a large machine's blind area**. NIOSH
counted 21 US surface-mine deaths caused partly by blind areas between January 2000 and mid-2006. 67% of
them happened behind a reversing machine, 38% involved dump trucks and 33% front-end loaders, and 8 of the
21 were machines going over a dump edge or highwall [P3, P18]. Underground, the hazard concentrates at
crosscut corners, at the articulation pinch point of loaders, and around remote-controlled continuous
miners. That is why MSHA now requires proximity detection on continuous mining machines [E2].

The proposal (Team A07) targets **SCCL's RG-1 opencast** for the pilot [P17]. The project brief also asks
for **underground operation**: no GNSS, communication from underground up to the surface, roof falls and
explosions. The design therefore covers both, with one architecture and two deployment profiles:

| Profile | Where | What changes |
|---|---|---|
| **OC** (opencast) | SCCL RG-1 pilot: benches, haul roads, dump yards, shovel faces | GNSS-RTK available, large high-speed HEMM, dust/heat/monsoon, trespassers and cattle |
| **UG** (underground) | Bord-and-pillar and longwall coal workings (SCCL underground mines) | No GNSS, methane (intrinsic safety), narrow galleries, roof falls, explosions, fire, need for a path from underground to the surface |

## 2. Objects of interest (OOI)

The system tracks and protects these classes. Each machine class gets its own **Machine Safety Profile
(MSP)** (see [04_sensor_placement.md](04_sensor_placement.md)).

| Group | Objects |
|---|---|
| Persons | Pedestrian miner, machine operator, surface worker, visitor/contractor, supervisor/shot-firer, rescue team, **trespasser (untagged)** |
| Personal equipment | Cap lamp (the "lantern") + battery, helmet, belt pack, self-rescuer, personal gas detector |
| Surface HEMM | Rear dump truck (RDT), hydraulic excavator/shovel, rope shovel, dragline, crawler dozer, wheel dozer, wheel loader (FEL), motor grader, blast-hole drill, water sprinkler, surface miner, backhoe loader (JCB-type), crane, fuel bowser, explosive van |
| Light vehicles | Jeep/pickup/bus (LMV), two-wheelers used by staff, visiting vehicles |
| UG machines | Side discharge loader (SDL), LHD, continuous miner (CM), shuttle car, roof bolter, battery locomotive + tubs, personnel/utility carrier, longwall shearer and face equipment |
| Fixed hazards / infrastructure | Belt conveyor drives and transfer points, rope haulage, junctions/crosscuts, ventilation doors, refuge chambers and SCSR caches, power centres, magazines, dump edges, highwalls, overhead lines, lamp room |

## 3. Functional requirements

### 3.1 Positioning (R-POS)

| ID | Requirement | Target | Basis |
|---|---|---|---|
| R-POS-1 | Relative position of a tagged person w.r.t. a machine hull | ≤ 0.5 m 2DRMS within 15 m (filtered); single-epoch p95 ≤ 0.7 m at 5–15 m; ≤ 1.5 m within 40 m | Coverage study (§3 of [generated tables](tools/generated_tables.md)); CMM injuries fall 40% at 3 ft vs 2 ft clearance [P12] |
| R-POS-2 | Presence detection in the near zone (≤ 5 m), any posture or orientation, through the body | P(detect) ≥ 99.9% per approach | Ruff: tags missed when worker bends over, and in field nulls [P1] |
| R-POS-3 | UG absolute position for tracking and rescue | ≤ 3 m p95 near anchors or in a vehicle session; ≤ 10 m p95 elsewhere; segment-level always | MSHA guidance: within 200 ft (61 m) on sections [E1]; MINER Act 60.96 m [P16] |
| R-POS-4 | OC absolute position | Vehicles ≤ 0.1 m (RTK fixed), ≤ 1 m (float); persons ≤ 2 m when near any vehicle/anchor | NIOSH saw 2–3 m DGPS and a 15 m multipath jump [P3, P18] |
| R-POS-5 | Update rate | ≥ 10 Hz in WARNING/DANGER; twin refresh ≤ 60 s for every active tag | MSHA: refresh at least every 60 s [E1] |
| R-POS-6 | Direction of travel at key junctions | Required | MSHA [E1] |
| R-POS-7 | Detection of **untagged** persons (rear and blind side) | ≥ 90% within 15 m, day/night/dust; person-vs-object classification ≥ 95% | Tags miss untagged people [P3]; micro-Doppler CNN 97.6% [P11] |

### 3.2 Collision avoidance (R-CA)

| ID | Requirement | Target | Basis |
|---|---|---|---|
| R-CA-1 | Alarm latency from entry into the danger zone | ≤ 200 ms p99 | NIOSH test course: alarm delay < 200 ms [P3, P18]; Ruff ≤ 0.5 s [P1] |
| R-CA-2 | Missed detections of tagged persons in the reliable zone | 0 in acceptance tests (NIOSH "reliable" = 100%) | [P3] |
| R-CA-3 | Zone size grows with speed, grade, load and direction | Per MSP formula ([06](06_collision_avoidance_logic.md)) | NIOSH: "ideally detection range would automatically adjust with equipment speed" [P3] |
| R-CA-4 | False and nuisance alarms | False ≤ 5% of alarms; nuisance ≤ 15% | Radar baseline: 18% false, 42% nuisance [P8] |
| R-CA-5 | Two-way alarm | Person **and** operator are alerted | Tags give two-way alarming [P3, P7] |
| R-CA-6 | Start-inhibit | Engine/tram start blocked while any tag is in the start-inhibit zone, under or on the machine; decision ≤ 1 s after key-on | Most accidents follow a stationary machine moving unexpectedly [P3] |
| R-CA-7 | Function-specific inhibit (UG CM and similar) | Only the hazardous motions are blocked, zone by zone | Jobes et al. [P12]; MSHA 75.1732 stop-before-contact [E2] |
| R-CA-8 | Machine-to-machine and machine-to-LMV conflicts | Warning ≥ 4 s before a predicted conflict | NIOSH GPS trial zones: 30 m warning / 60 m detection for a 797 [P3] |
| R-CA-9 | Fixed hazards | Dump edges, highwalls, overhead lines, unsupported roof, sealed areas, conveyors | 8/21 deaths were edge-related [P18]; Jobes "beyond supported top" [P12] |
| R-CA-10 | Blast clearance | List of every tag inside the blast danger zone before firing | Proposal extension |

### 3.3 Communication (R-COM)

| ID | Requirement | Target |
|---|---|---|
| R-COM-1 | The safety loop (detect → decide → alarm/inhibit) must not depend on the backbone or the server | Local-first |
| R-COM-2 | Alert propagation | Local ≤ 200 ms; neighbouring objects of interest ≤ 1 s; server/twin ≤ 2 s p95 when backbone is up |
| R-COM-3 | Event-driven reporting | No fixed-rate polling of wearables; heartbeat ≤ 60 s only to satisfy the refresh rule |
| R-COM-4 | Underground-to-surface pathways | ≥ 2 independent pathways + 1 emergency path (TTE) that needs no in-mine infrastructure [E1] |
| R-COM-5 | Emergency downlink to every miner | Even with all in-mine infrastructure destroyed (ULF paging, PED precedent [E11]) |
| R-COM-6 | Message integrity | Authenticated, replay-protected; secure ranging against distance manipulation |

### 3.4 Power (R-PWR)

| ID | Requirement | Target |
|---|---|---|
| R-PWR-1 | Wearable (cap-lamp integrated, UG) | Full function ≥ 16 h on the lamp battery, adding < 2% to lamp drain; **backup cell ≥ 96 h** of emergency beaconing |
| R-PWR-2 | Wearable (surface, standalone) | ≥ 1 week of shifts per charge; low-battery warning |
| R-PWR-3 | Tag minimum duration | ≥ 12 h total (shift + 4 h) and low-power warning [E1] |
| R-PWR-4 | Infrastructure standby | ≥ 24 h at 5/5/90 duty (MSHA) [E1]; design target **96 h** (refuge-alternative duration [E26]) |
| R-PWR-5 | Vehicle unit | Runs from 12/24 V machine supply with load-dump protection; instant-on safety controller for start-inhibit |

### 3.5 Resilience (R-RES)

| ID | Requirement | Target |
|---|---|---|
| R-RES-1 | Wearable ruggedness | IP68, 2 m drop, −20 to +60 °C, 100% RH; Ex ia I Ma for UG coal |
| R-RES-2 | Black box | ≥ 72 h on the wearable; ≥ 2 weeks on the twin, unaffected by link interruptions [E1] |
| R-RES-3 | Event detection on the body | Man-down, impact (roof fall), explosion overpressure, CO rise, SOS: surface alert ≤ 60 s when any path exists |
| R-RES-4 | Last known location | Shown for every miner whose tag is not communicating, with timestamp and uncertainty [E1] |
| R-RES-5 | Rescue localisation | Final-approach locator, ≤ 0.5 m through ≥ 5 m of rubble (to be validated) |
| R-RES-6 | Infrastructure survivability | Recessed mounting, cables protected against blast forces, pathway-fault display [E1] |

### 3.6 Digital twin (R-DT)

| ID | Requirement |
|---|---|
| R-DT-1 | Unique identity for every person, machine and node; every location time-stamped [E1] |
| R-DT-2 | Live roll-call: lamp-room check-out list reconciled with live tags within 60 s |
| R-DT-3 | Rescue view: last known positions, uncertainty, reachable set, blocked segments, refuge occupancy, printable list [E1] |
| R-DT-4 | Shared, versioned mine map pushed to vehicles, nodes and wearables (enables compact messages) |
| R-DT-5 | Near-miss analytics: every WARNING/DANGER event logged with context |

## 4. Non-functional constraints

### 4.1 Regulatory (India first, US as reference practice)

| Area | Constraint | Design consequence |
|---|---|---|
| UWB spectrum | India *Very Low Power UWB Devices (Exemption) Rules, 2018*: 6–8.5 GHz at −41.3 dBm/MHz mean e.i.r.p., 0 dBm peak/50 MHz. Vehicle-mounted devices: −53.3 dBm/MHz exterior limit unless low-duty-cycle (LDC) or transmit-power-control (TPC) mitigation is used [E4] | Use UWB channels 5 (6.5 GHz) and 9 (8.0 GHz). Vehicle anchors mostly **listen**, transmit at low duty and implement TPC. Confirm the classification with WPC during equipment type approval |
| Sub-GHz | 865–867 MHz license-exempt: ≤ 1 W transmitter, ≤ 4 W ERP, ≤ 200 kHz carrier bandwidth (DoT clarification of G.S.R. 564(E)); the 2021 rules extend the SRD band to 868 MHz (G.S.R. 853(E)) [E5] | LoRa BW125/GFSK channels inside 865–867 MHz; power ≤ +14 dBm in practice (blasting and IS margins) |
| Radar | 77–81 GHz short-range vehicular radar exempted (DoT, Nov 2025, ≤ 50 dBm mean EIRP) [E6] | 77 GHz radars on HEMM; 60/24 GHz short-range units only after checking current WPC status |
| Proximity warning (India) | DGMS (Tech.) Circular 06/2020 and IS 17055 Part 6 are cited by Indian PWS vendors; BIS working group MED 07/WG05 is drafting a standard [E9] | Obtain the circular text and current IS 17055-6 before the pilot; map our KPIs to it |
| Intrinsic safety (UG coal) | IEC/IS 60079 series; CSIR-CIMFR testing, DGMS approval. RF threshold power for Group I: 6 W, 1500 µJ for pulses [E7] | Wearables and infrastructure: Ex ia I Ma (must keep working after a methane inrush). Vehicle units: Ex d/Ex ib (machines are de-energised at the gas limit anyway) |
| Collision warning standard | ISO 21815-1:2022 (detection, operator warning, automatic intervention, tests; operator stays responsible) [E8] | Alarm levels and test procedures aligned to it |
| Blasting | RF energy must not fire electric detonators [P1] | "Blast mode": transmit-power cap and LF generators off near charged holes; UWB is far below any threshold |
| Exposure | Human RF exposure limits (Ruff cites 47 CFR 2.1091/2.1093) [P1] | All radiated powers in mW range |

### 4.2 Budget (from the proposal's evidence note [P18])

| Item | Budget | Implication |
|---|---|---|
| Vehicle unit | ≈ ₹1.05 lakh each (₹8.40 lakh ÷ 8 vehicles) | Pilot kit is trimmed to fit (see [11_bill_of_materials.md](11_bill_of_materials.md)); the full kit is a production target |
| Personal tag | ≈ ₹8,000 each (₹6.40 lakh ÷ 80 tags) | Single helmet UWB radio in the pilot, second radio optional; CO sensor on a subset |

### 4.3 Environment

| Parameter | OC (Ramagundam) | UG coal |
|---|---|---|
| Temperature | Up to ~47 °C ambient in summer, machine skins hotter | 30–40 °C in deep workings, high humidity |
| Particulates | Haul-road dust, blasting fumes | Coal dust, stone dust |
| Water | Monsoon rain, pit water, high-pressure washing | Dripping water, inundation risk |
| Mechanical | Continuous vibration, mud throw, rock impact | Roof falls, rib spalls, low headroom |
| Light | Night shifts, glare | Darkness except cap lamps and machine lights |
| Gas | Blasting fumes, diesel exhaust | Methane, CO, CO2, low O2 |

## 5. Assumptions (to be confirmed on site)

1. Every person entering a controlled area is issued a wearable at the lamp room or gate. Untagged persons are still possible, so the non-cooperative sensing layer is mandatory.
2. Machine dimensions, speeds and braking values in [tools/machine_profiles.toml](tools/machine_profiles.toml) are representative. They must be replaced with SCCL fleet data.
3. UG cap lamps are corded with a belt-worn Li-ion battery. The wearable draws power from that battery and carries its own backup cell.
4. UG infrastructure power is available along main roadways (mine supply through IS power units). Standby batteries carry the nodes through outages.
5. Automatic braking of moving surface HEMM is **not** part of the pilot, following NIOSH advice on nuisance alarms [P3]. Interventions are start-inhibit (surface) and function-inhibit/stop (UG, where regulation expects it [E2]).
