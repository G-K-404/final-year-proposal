# Mine Proximity Safety System: system design (Team A07)

A collision-avoidance, tracking and emergency-communication system for **opencast (SCCL RG-1 pilot) and
underground coal mines**. It covers machine–person and machine–machine collisions, low-power
event-driven communication, a path from underground to the surface, a digital twin, and survival of mine
disasters.

## The design in one paragraph

Every person wears a unit built into the **cap lamp** (underground) or **helmet** (surface). It is detected
three independent ways:

* a **UWB time-of-flight radio** (6.5/8 GHz, ~0.1 m ranging: who and where);
* a **125 kHz magnetic near-field receiver** (works through the body and in any posture, listens at µA);
* an **865 MHz radio** for event-driven messages.

Every machine carries UWB anchors and LF coils on its hull. It measures each person's position **relative
to itself directly**, with no GNSS and no mine infrastructure, so collision avoidance works underground,
in new headings, and after a disaster. Radar and thermal cameras catch people who aren't wearing a unit.
Zones grow with speed, load and grade. Machines block start-up when anyone is in or under their path, and
underground they block only the dangerous functions. A surface **digital twin** shares the mine map with
every device. That lets messages be tiny and rare: the wearable transmits only when it differs from what
the twin already predicts. The twin also keeps everyone's last known location for rescue. When everything
underground is destroyed, a **through-the-earth** link (0.3–4 kHz) from refuge chambers and a **ULF
paging** downlink into every cap lamp still reach the surface.

## Key numbers

| Quantity | Value | Where |
|---|---|---|
| Relative position error, person 5–15 m from a 100 t truck | 100% of positions solvable, 90% with redundancy; p95 0.68 m (single fix) | [03 §3.5](03_positioning_and_sensing.md) |
| Near-field shell | 2–8 m, body-transparent; ±3 dB field error → ±12% distance | [03 §4](03_positioning_and_sensing.md) |
| Danger alarm latency | ≈ 85 ms machine side, ≈ 135 ms wearable side (target ≤ 200 ms) | [06 §11](06_collision_avoidance_logic.md) |
| Stop / warning zone, 100 t truck at 30 km/h loaded, 1:16 downgrade | 53 m / 73 m (reversing at 10 km/h: 15 / 24 m) | [06 §1](06_collision_avoidance_logic.md) |
| Wearable radio + sensing energy | 6.2 mAh per 12 h shift event-driven vs 25.1 mAh polling (4× less) | [05 §6](05_communication.md) |
| Wearable emergency beacon life (600 mAh backup, 50% derated) | ≈ 638 h (requirement 96 h) | [05 §6](05_communication.md) |
| Event-triggered traffic at threshold 2σ | 8.9% of steps transmit (Wu et al.) | [05 §4.2](05_communication.md) |
| TTE carrier, 300 m cover, 100 Ω·m | ≈ 1.1 kHz → 1,125 Hz between mains harmonics | [05 §8.2](05_communication.md) |
| Twin-referenced delta roll-call vs raw coordinates | 556 vs 24,076 bits (43× smaller): 56 s instead of 40 min at 10 b/s | [05 §8.4](05_communication.md) |
| Infrastructure standby | 1.18 W with fibre / 0.18 W mesh-only → 113 Wh for 96 h | [05 §6.2](05_communication.md) |
| Pilot machine unit / personal unit cost | ≈ ₹1.05 lakh / ≈ ₹6,000–8,000 at the lower half of part prices (budget ₹1.05 lakh / ₹8,000) | [11](11_bill_of_materials.md) |

All computed values come from [tools/design_calcs.py](tools/design_calcs.py) and can be regenerated with
the real SCCL fleet data.

---

## Answers to the brief's questions

**Q3. Are LMV and HEMM vehicles possible in CARLA?**
LMVs, yes: they are in the blueprint library. HEMM, not natively. Import them as custom vehicle assets
(Unreal editor build). CARLA's physics assumes **four wheels**, so dump-truck duals are modelled as single
wide wheels. **Tracked and articulated machines** (dozers, excavators, loaders, LHDs) are moved
kinematically each tick. CARLA has **no UWB, magnetic or thermal sensors**; they are added as Python
virtual sensors using `world.cast_ray` for line of sight. Use CARLA for opencast scenarios, and Gazebo with
the DARPA SubT worlds for underground. → [10 §1–3](10_simulation_and_data.md)

**Q4. How should sensors be placed on a vehicle to cover all directions?**
* UWB anchors on the **hull extremities**: four corners, plus **mid-sides** on long machines, plus **one high anchor** on the canopy.
* Radars **at or below chest height**, rear pair **toed in 15°**.
* Cameras and thermal **high, looking down**; the **blind side** (opposite the cab) first.
* Nothing on moving tools; every joint (articulation, swing, body-up) measured.

The coverage study proves it. Rear-only sensing can position *nothing*. Four corners leave the sides at a
p95 of 4.7 m. Adding mid-sides and a canopy anchor gives 100% coverage and p95 0.68 m at 5–15 m. Exact
coordinates per machine are in → [04](04_sensor_placement.md), [03 §3.5](03_positioning_and_sensing.md)

**Q5. Low-power communication underground to the surface using the digital twin: which frequencies and
modulations?**

| Hop | Choice |
|---|---|
| Person ↔ machine ranging | UWB 802.15.4z HRP (BPM-BPSK) on Ch 5/9 |
| Near field | 125 kHz OOK |
| Telemetry | 865–867 MHz LoRa CSS / GFSK, adaptive (900 MHz is NIOSH's best band for coal entries) |
| Backbone | Fibre ring through two roadways → 865 MHz mesh → optional MF ~500 kHz |
| Emergency uplink | TTE at 0.3–4 kHz, carrier from f ≈ 1.01×10⁶·ρ/d², placed between 50 Hz harmonics; BPSK downlink, orthogonal 16-FSK uplink with FEC |
| Emergency downlink | ULF paging at ~1 kHz into every cap lamp |

Power comes down through **event-driven, risk-adaptive rates** and **twin-referenced messages** (the
device sends only what the twin cannot predict). → [05](05_communication.md)

**Q6. Which devices and sensors are needed, and why?**
UWB transceivers, LF generators and 3-D wake-up receivers, 865 MHz radios, 77/60 GHz radars, thermal and
RGB cameras, RTK GNSS (OC), IMUs with high-g accelerometers, barometers, CO cells, ULF receivers, safety
MCUs with interlock relays, NPU/GPU computers, joint encoders, and fibre/mesh/TTE infrastructure. Each
comes with its evidence and the rejected alternative, counts per object, and costs. →
[11](11_bill_of_materials.md)

**Q7. Examples: lanterns, helmets, JCBs, humans.**
* Cap lamp + helmet + person: [04 §3](04_sensor_placement.md). UWB in a helmet crown pod; LF, IMU, radio, gas and ULF in a belt pack powered by the lamp battery with its own backup cell.
* JCB-type backhoe loader: [04 §4.5](04_sensor_placement.md).
* Every other machine class (trucks, shovels, dozers, loaders, graders, drills, LMVs, LHDs, SDLs, continuous miners, shuttle cars, locos): [04 §4–5](04_sensor_placement.md).
* Junctions, conveyors, refuges and the lamp room: [04 §6](04_sensor_placement.md).

**Q8. When the lantern is off, the twin should update.**
Yes. Every lamp state change is an **event** (ON, OFF, LOW BATTERY, FAULT, CORD FAULT, MAIN POWER LOST,
DOCKED), sent within 2 s. The twin then interprets it:

* Lamp off underground + no motion for 10 min → acknowledgement request, then supervisor.
* During an emergency → expected (miners save light); the twin tracks the light-hours remaining.
* Lamp fault → the person is in darkness and invisible to drivers, so nearby machines automatically get **larger zones**.

→ [05 §9](05_communication.md)

**Q9. Should alerts go to the server, and is it viable to send them to surrounding objects of interest?**
Yes, in tiers:

| Tier | Recipients | Path | Latency |
|---|---|---|---|
| Local | Person and operator | UWB/LF/HMI | ≤ 200 ms |
| Neighbourhood | Others whose predicted path crosses the hazard | Machine beacon, Junction Guardians | ≤ 1 s |
| Server | Twin and control room | Backbone | ≤ 2 s |
| Mine-wide | Everyone | Downlink + ULF | Emergencies only |

It is viable because machines and nodes carry the broadcast cost, wearables listen in windows they
already have, and a **relevance filter** prevents alarm flooding. → [05 §7](05_communication.md)

**Q10. Underground, GNSS/GPS don't work and LiDAR/radar aren't sufficient. What prevents collisions?**
* **Cooperative radio ranging between the person and the machine:** UWB time of flight from machine-mounted anchors, so relative position is measured directly.
* A **125 kHz magnetic shell** that can't be fooled by posture or bodies.
* **IMU dead reckoning constrained to the tunnel map**.
* **Anchors at junctions**, and machines acting as **moving anchors**, for absolute position.

Radar and thermal remain as the **untagged-person** layer; LiDAR only localises the machines themselves.
→ [03 §2](03_positioning_and_sensing.md)

**Q11. Each vehicle should have its own sensor/processing system optimised for its parameters.**
Every machine runs the same safety platform, configured by its own **Machine Safety Profile**:

* geometry and joints, speeds, braking, grades;
* sensor kit and exact coordinates;
* zones and interventions;
* compute tier (MCU / NPU / GPU);
* radar clutter models trained on that machine.

The profile drives the code that generates coordinates and zones. → [04 §2](04_sensor_placement.md), [tools/](tools/README.md)

**Q12. Is it possible to simulate, or is there real mine data?**
Both.

* **Simulation:** CARLA (opencast) and Gazebo SubT (underground, with comms loss and rock falls) for scenarios; Sionna RT for UWB and 865 MHz channels in tunnel meshes; ns-3 for network scale.
* **Real data:** AutoMine (open-pit perception), SubSurfaceGeoRobo and MIN3D (underground radar/LiDAR/thermal), the eWINE UWB NLOS dataset, Glasgow radar micro-Doppler, KAIST/FLIR thermal, MSHA accident data, DGMS statistics.
* **Plus our own SCCL measurement campaign** and 7 × 24 h shadow mode.

→ [10](10_simulation_and_data.md)

---

## Traceability to the brief

| Baseline / main objective | Satisfied by |
|---|---|
| Prevent equipment–equipment and equipment–human collisions | [06](06_collision_avoidance_logic.md) zones, path risk, V2V, interventions; [03](03_positioning_and_sensing.md) layers |
| Communication for underground machinery and humans | [05 §1, §8](05_communication.md) |
| Minimise communication power | [05 §4, §6](05_communication.md): 4× vs polling; backup ≈ 638 h |
| Adversity-resilient (roof falls, explosions…) and **adversary**-resilient | [08](08_resilience_and_security.md) scenarios, survivability, redundancy, black box, Rescue Locator, cyber |
| Digital twin + efficient schemes, modulations, timings | [07](07_digital_twin.md); [05 §2, §5, §8.4](05_communication.md) |
| Event-based comms instead of polling | [05 §4](05_communication.md) |
| Accurate positioning of equipment and humans | [03](03_positioning_and_sensing.md) |
| Each vehicle gets its own design | [04 §2](04_sensor_placement.md) |
| Communication between "crust" and "atmosphere" | [05 §8](05_communication.md) |
| Last recorded location for timely rescue | [07 §6](07_digital_twin.md), [08 §4](08_resilience_and_security.md) |
| Transmit only during main events | [05 §4](05_communication.md) |
| Edge cases | [09](09_edge_cases.md): 100 cases |

## What changes from the original proposal, and why

| Proposal (RFID tag + machine reader) | This design | Reason |
|---|---|---|
| RFID presence ("tag in range") | UWB position + LF shell (still a tag–reader architecture; UWB RTLS is an active RFID technology) | Ruff's open problems: orientation, nulls, no position [P1] |
| Fixed detection range | Speed-, load- and grade-adaptive zones | NIOSH: wanted, never built [P3] |
| Fixed update rate | Risk-adaptive, event-driven | Wu et al. used a fixed threshold [P4] |
| Radar as an alternative | Radar gated by a person classifier, fused | 18% false, 42% nuisance alone [P8] |
| No-start lock | Start-inhibit with two-layer checks + function-specific inhibit (UG) | [P3], [P12], [E2] |
| Opencast only | Opencast pilot + underground profile, twin, TTE/ULF emergency chain | The brief |

## Document map

| # | Document | Contents |
|---|---|---|
| 01 | [Requirements](01_requirements.md) | Objects of interest, numeric requirements, Indian regulations, budget, environment |
| 02 | [Architecture](02_architecture.md) | Principles, trade study, subsystems, data flows, modes, safety architecture |
| 03 | [Positioning and sensing](03_positioning_and_sensing.md) | UWB, NLOS ML, LF shell, dead reckoning, absolute positioning, untagged detection, coverage study |
| 04 | [Sensor placement](04_sensor_placement.md) | Exact coordinates for every object of interest; per-machine design process |
| 05 | [Communication and power](05_communication.md) | Links, frequencies, modulations, event protocol, messages, power, alerts, TTE, lamp state |
| 06 | [Collision-avoidance logic](06_collision_avoidance_logic.md) | Zones, path risk, alarm levels, interventions, nuisance control, V2V, geofences, latency |
| 07 | [Digital twin](07_digital_twin.md) | Data model, estimation, synchronisation, roll-call, rescue mode, analytics, stack |
| 08 | [Resilience and security](08_resilience_and_security.md) | Disaster scenarios, survivability, black box, functional safety, FMEA, cyber |
| 09 | [Edge cases](09_edge_cases.md) | 100 edge cases with handling |
| 10 | [Simulation and data](10_simulation_and_data.md) | CARLA, Gazebo, RF simulation, datasets, test plan, pilot |
| 11 | [Bill of materials](11_bill_of_materials.md) | Devices per object, evidence, costs, budget fit |
| 12 | [References](12_references.md) | Papers and external sources, with verification status |

## Open decisions for the team

1. **Fleet data:** replace the representative values in [tools/machine_profiles.toml](tools/machine_profiles.toml) with SCCL machine data and re-run.
2. **DGMS (Tech.) Circular 06/2020 and IS 17055 Part 6:** get the primary text and map our KPIs to it (only vendor citations were found).
3. **WPC:** confirm whether machine-mounted UWB anchors fall under the vehicle limits of the 2018 UWB rules; plan type approval for every radio.
4. **Budget:** infrastructure (RTK base, gateways, Guardians, server, dock, VTUs) is about ₹3–5 lakh and is not itemised in the proposal. The pilot machine kit leaves out thermal cameras to fit ₹1.05 lakh.
5. **Permissions:** measurement campaigns and shadow mode at RG-1; a location-data privacy policy agreed with worker representatives.
6. **Underground phase:** certification route (CSIR-CIMFR, DGMS), a non-gassy training gallery for the demonstrator, and rock resistivity and cover depth at refuge sites for TTE carrier selection.
