# 11 · Devices, sensors and bill of materials

This document answers question 6: the devices and sensors needed, with the evidence for each, how many
each object carries, and indicative costs against the proposal budget (₹1.05 lakh per machine unit,
₹8,000 per personal unit [P18]).

> **Prices are indicative 2026 component costs in INR for pilot quantities.** They exclude installation
> labour, certification, margins and GST. Get quotations before committing. Example part numbers are
> illustrations of a class, not endorsements; any part meeting the spec works.

---

## 1. Why each device is needed (evidence)

| Device | Job | Evidence | Rejected alternative |
|---|---|---|---|
| **UWB transceiver** (IEEE 802.15.4z, DW3000/Trimension class) | Who and where: ~0.1 m ranging, secure ranging | UWB works underground, but needs line of sight and redundancy [P9]; NLOS can be classified and corrected with ML [P5, P10]; India permits 6–8.5 GHz [E4] | RSSI RFID: presence only, body shadowing, nulls [P1]; LANDMARC 1.1 m with ~1 min latency [P2] |
| **LF 125 kHz generator + 3-D wake-up receiver** (AS3933 class) | Near-field shell, wake-up, start-inhibit | Magnetic PDS located the personal device to 20–50 cm [P12]; PDS run at 70–500 kHz [E3]; MSHA-compliant CM systems [E2]; µA listening [E19] | Acoustic: line of sight only [P6] |
| **865–867 MHz radio** (LoRa/GFSK, SX126x/STM32WL class) | Event-driven telemetry, machine beacons, alerts, mesh | 900 MHz gives the best range in coal entries [E3]; license-exempt in India [E5]; LPWAN identified as promising for UG [P16] | Wi-Fi on wearables (power); 2.4 GHz (worse round corners, crowded) |
| **mmWave radar** (77 GHz on HEMM, 60/24 GHz short range) | Untagged persons and objects; under-machine presence at key-on | Tags miss untagged people [P3]; micro-Doppler CNN 97.6% [P11]; radar works in dust and dark; 77–81 GHz exempt in India [E6] | Radar alone: 18% false, 42% nuisance [P8], so it is used gated and fused |
| **Thermal LWIR camera** | Confirms untagged persons at night and in smoke | Multimodal fusion keeps the unblinded sensor in charge [P15] | — |
| **RGB / IR cameras** | Operator verification | NIOSH: pair alarms with cameras; front/right/rear standard [P3, P18] | — |
| **GNSS-RTK** (multi-band, NavIC-capable where available) | OC machine pose, geofences, V2V | NIOSH GPS trial and geofence precedent; DGPS 2–3 m, RTK cm [P3, P18] | Plain GNSS: 15 m multipath jumps [P3] |
| **IMU** (6-axis + high-g) | Dead reckoning, man-down, roof-fall strike, ego-motion | INS is the standard hybrid partner underground [P13, P16] | — |
| **Barometer** | Level, explosion overpressure, ventilation change | Physical principle; node + wearable network | — |
| **CO cell** (electrochemical) | Fire / post-explosion gas | µW-class sensing | — |
| **ULF receiver** (ferrite, ~1 kHz) | Evacuation paging with no in-mine infrastructure | PED: > 25 years, 150+ mines, pager on the cap-lamp battery [E11] | — |
| **Safety MCU + relays** | Deterministic zone logic and interlocks | ISO 13849 PL d target for start-inhibit | Doing safety on Linux |
| **NPU / GPU computer** | Radar/thermal/camera ML | CNNs run on low-power hardware [P10] | — |
| **Encoders / state switches** | Hull polygon follows joints | Articulation, swing, body-up, mast-up hazards | — |
| **2-D LiDAR (Ex, optional)** | UG machine self-localisation | Tunnel-profile map matching | Person detection by LiDAR (dust) |
| **Fibre ring + mesh + MF** | Survivable backbone | MSHA redundancy guidance [E1]; MF 3–6 km along conductors [E3] | Single leaky feeder |
| **TTE transceivers** | Emergency link through the strata | MagneLink MSHA-approved to 1,550 ft [E10]; NIOSH: 72 Hz–4 kHz, 10 b/s – 2.5 kb/s [E3] | — |

## 2. What each object carries

| Device | MSU (UG person) | SPU (OC person) | VTU (LMV) | RDT / WTR / GRD | HEX | DOZ | FEL | BHL | DRL | LHD | SDL | CM | SC | LOCO | Junction Guardian |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| UWB radio / anchor | 1 (+1 opt) | 1 | 1 (+2 opt) | 7 | 7 | 7 | 7 | 5 | 5 | 7 | 5 | 6 | 6 | 4 + EOT | 1 |
| LF coils (machine) / LF 3-D Rx (person) | Rx | Rx | – | 4 | 3 | 4 | 4 | 2 | 2 | 4 | 4 | 5 | 4 | 2 | – |
| Radar | – | – | (1) | 4 | 2 | 5 | 2 | 2 | 1 | 2 | 2 | – | 2 | 2 | (opt) |
| Thermal | – | – | – | 2 | 1 | 1 | 1 | – | – | 2 | 2 | – | – | – | – |
| Camera | – | – | – | 3 | 2 | 2 | 2 | 1 | 1 | 2 | – | (opt) | 2 | 1 | – |
| GNSS antenna | – | (opt) | 1 | 2 | 2 | 2 | 2 | 1 | 1 | – | – | – | – | – | – |
| 2-D LiDAR (Ex) | – | – | – | – | – | – | – | – | – | 2 (opt) | – | – | – | – | – |
| 865 MHz radio | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | Gateway |
| IMU | 1 + high-g | 1 + high-g | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | – |
| Joint / state sensor | – | – | – | Body-up | Swing | – | Articulation | Seat direction | Mast | Articulation | – | Function I/O | Direction | Train length | Door state |
| Barometer / CO | 1 / 1 | 1 / – | – | – | – | – | – | – | – | – | – | – | – | – | 1 / opt |
| ULF receiver | 1 | – | – | – | – | – | – | – | – | – | – | – | – | – | – |
| Compute tier ([04 §2](04_sensor_placement.md)) | MCU | MCU | 0 | 2 | 2 | 2 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | MCU/SBC |

## 3. Personal units

| Item | Example class | MSU (UG) ₹ | SPU (OC) ₹ |
|---|---|---|---|
| UWB module | DW3000-family module | 2,000–2,800 | 2,000–2,800 |
| LF 3-D wake-up receiver + 3 ferrite coils | AS3933 class | 500–800 | 500–800 |
| MCU + 865 MHz radio | STM32WL-based module | 800–1,200 | 800–1,200 |
| IMU + high-g accelerometer | ICM-42688 / BMI270 + ADXL372 class | 650–1,000 | 650–1,000 |
| Barometer | BMP390/BMP581 class | 250–400 | 250–400 |
| CO electrochemical cell | Industrial EC cell | 1,500–3,000 (on 1 in 5 units in the pilot) | – |
| ULF receive front-end | Two ferrite rods + LNA + filter | 400–700 | – |
| Power | Lamp-battery DC-DC + 600 mAh backup + 150 mAh crown cell + PMIC (MSU); 2,000 mAh Li-ion + charger (SPU) | 550–850 | 500–800 |
| Haptics ×2, buzzer, LED ring, buttons | — | 250–400 | 250–400 |
| Enclosures (belt pack + crown pod), lamp-cord interface, PCB, assembly | — | 1,200–2,000 | 1,000–1,800 |
| **Total, pilot (module-based)** | | **≈ 6,600–10,150** (without CO); **8,100–13,150** with CO | **≈ 5,950–9,200** |
| Production estimate (chip-down, 1,000+ units) | | ≈ 4,500–6,000 | ≈ 4,000–5,500 |

**Fit to ₹8,000:** both units fit only if bought at the lower half of each range: UWB module
≤ ₹2,200, enclosure and assembly ≤ ₹1,500, MCU module ≤ ₹1,000. The alternative is a small chip-down
board run for the 80 pilot units, which moves the totals toward the production column. In the pilot the CO
cell goes on 1 unit in 5 (supervisors and a few miners per crew), and the second UWB radio is a production
upgrade. Ex ia certification of the MSU design (CSIR-CIMFR testing, DGMS approval) is a one-off cost of
several lakh and takes months; check current fees. It is not a per-unit cost.

## 4. Machine units

### 4.1 Rear dump truck: pilot-fit vs full configuration

| Item | Pilot-fit ₹ | Full (production) ₹ |
|---|---|---|
| Safety controller board (dual CAN, monitored relays, watchdog) | 4,500 | 6,000 |
| Perception computer | Tier 1: Raspberry Pi 5 + Hailo-8L, 16,000 | Tier 2: Jetson Orin class, 35,000 |
| 865 MHz radio + LTE/Wi-Fi modem | 4,000 | 5,000 |
| HMI: rugged 7" display, 105 dB buzzer, voice, external strobe + horn | 8,000 | 15,000 |
| 24 V power conditioning + hold-up | 3,000 | 4,000 |
| Enclosure, IP69K connectors, cabling, brackets | 6,000 | 12,000 |
| UWB anchors (module + IP67 radome + cable) | 6 × 2,800 = 16,800 (canopy anchor in phase 2) | 7 × 3,200 = 22,400 |
| LF generator driver + coils | 4 coils, 8,000 | 4 coils, 10,000 |
| Radar | 1 × 77 GHz rear 15,000 + 2 × 60/24 GHz short range 5,000 | 4 × 77 GHz, 4 × 18,000 = 72,000 |
| Thermal | – (radar micro-Doppler + cameras in the pilot) | 2 × 20,000 = 40,000 |
| RGB cameras (IP67, IR) | 3 × 2,500 = 7,500 | 3 × 4,000 = 12,000 |
| GNSS RTK (dual low-cost dual-band modules + antennas) | 11,000 | 2 × survey-grade, 45,000 |
| **Total** | **≈ 1,04,800** | **≈ 2,78,400** |

The pilot-fit kit meets the ₹1.05 lakh budget and keeps every **cooperative** layer (UWB, LF, 865 MHz,
interlocks). It thins the **non-cooperative** layer to one long-range rear radar plus short-range radars
and cameras, so blind-side untagged detection is weaker in the pilot. For comparison, NIOSH reported a
2007 commercial tag system at about $15,600 per haul truck [P18]; these are component costs, not product
prices.

### 4.2 Other machines (indicative totals)

| Machine | Pilot-fit ₹ | Notes |
|---|---|---|
| Excavator / shovel, dozer, wheel loader, grader, water sprinkler | 0.95–1.10 lakh | Same core as the truck; kit from [04](04_sensor_placement.md) |
| Backhoe loader, drill | 0.70–0.85 lakh | Tier 1, fewer anchors, short-range radars |
| LMV / two-wheeler VTU | 10,000–14,000 | Roof combo node (UWB + 865 MHz + RTK + battery, magnet mount) + cab alert unit |
| Underground machines | × 1.5–3 | Certified Ex d / Ex ia enclosures and barriers, certification; DGMS approval |

## 5. Infrastructure and surface

| Item | ₹ (indicative) | Quantity, OC pilot |
|---|---|---|
| OC Guardian pole (2 UWB anchors, 865 MHz gateway, LED signal, solar + LiFePO4) | 35,000–55,000 | 2–4 |
| 865 MHz gateway (8-channel concentrator class), pole-mounted | 10,000–20,000 | 2–3 |
| RTK base station (dual-band receiver, survey antenna, radio link) | 40,000–80,000 | 1 |
| Twin server (workstation for the pilot; rack pair with hot standby in production) | 1.0–1.5 lakh (pilot) | 1 |
| Lamp-room / gate dock (10 slots with data contacts) | 30,000–50,000 | 1–2 |
| UG Junction Guardian (certified enclosure, fibre, battery) | 0.55–1.10 lakh | Per junction on traffic routes (UG phase) |
| Refuge Comms Node + TTE uplink | Commercial quotation | Per refuge (UG phase) |
| TTE / ULF bench demonstrator (amplifier, wire loop, ferrite coils, preamp, SDR/sound card) | 15,000–30,000 | 1 |
| Rescue Locator prototype | 15,000–25,000 | 1 |

## 6. Budget summary for the RG-1 pilot

| Line | Budget in proposal [P18] | This design |
|---|---|---|
| 8 machine units | ₹8.40 lakh | 8 × ≈ ₹0.95–1.05 lakh = ₹7.6–8.4 lakh |
| 80 personal units (SPU for the OC pilot) | ₹6.40 lakh | 80 × ≈ ₹6,000–8,000 = ₹4.8–6.4 lakh, provided parts are bought at the lower half of the ranges in §3 or a chip-down board is used (CO cells excluded; they are UG-only) |
| Infrastructure, server, dock, RTK, VTUs | Not itemised in the evidence note | ≈ ₹3–5 lakh: **add a line to the proposal budget, or fund from the machine/tag savings** |

## 7. Power at a glance

| Unit | Consumption | Source |
|---|---|---|
| MSU | ≈ 0.52 mA average radio and sensing (6.2 mAh per shift) + alarms ≈ 1.1 mA | Lamp battery; backup cell |
| SPU | Same + optional GNSS snapshots | 2,000 mAh Li-ion |
| Machine unit, Tier 2 full kit | ≈ 40–70 W | 24 V vehicle supply |
| Machine unit, Tier 1 pilot kit | ≈ 20–30 W | 24 V vehicle supply |
| Junction Guardian | 3.1 W normal; 1.18 W standby with fibre; 0.18 W mesh-only | Line + 192 Wh LiFePO4 |
