# Generated design tables

Produced by `docs/tools/design_calcs.py` from `machine_profiles.toml`. Do not edit by hand.

## 1. Speed-adaptive zones (distance from hull, m)

| ID | Machine | v fwd km/h | Stop | Warn | Aware | v rev km/h | Stop (rev) | Warn (rev) | Start-inhibit (v=0) |
|---|---|---|---|---|---|---|---|---|---|
| RDT100 | Rear dump truck, ~100 t class | 30 | 53.2 | 72.9 | 97.9 | 10 | 15.0 | 23.5 | 4.2 |
| RDT60 | Rear dump truck, ~60 t class | 30 | 49.0 | 68.6 | 93.6 | 10 | 14.3 | 22.8 | 4.2 |
| WTR28 | Water sprinkler / tanker, ~28 kL | 25 | 41.6 | 58.5 | 79.3 | 8 | 12.4 | 19.8 | 4.2 |
| GRD | Motor grader | 20 | 26.8 | 40.9 | 57.6 | 15 | 19.6 | 30.9 | 4.2 |
| HEX | Hydraulic excavator / shovel, ~200 t | 2.5 | 6.7 | 11.1 | 13.2 | 2.5 | 6.7 | 11.1 | 4.2 |
| DOZ | Crawler dozer, D375 class | 11 | 15.8 | 24.9 | 34.1 | 14 | 20.0 | 30.8 | 4.2 |
| FEL | Wheel loader (articulated), 5-6 m3 | 20 | 26.8 | 40.9 | 57.6 | 15 | 19.6 | 30.9 | 4.2 |
| BHL | Backhoe loader (JCB 3DX class) | 20 | 24.2 | 38.3 | 54.9 | 10 | 12.6 | 21.1 | 4.2 |
| DRL | Blast-hole drill (crawler) | 2.5 | 6.9 | 11.3 | 13.4 | 2.5 | 6.9 | 11.3 | 4.2 |
| LMV | Light motor vehicle (jeep / pickup) | 40 | 44.4 | 69.6 | 102.9 | 10 | 11.3 | 19.8 | 4.2 |
| LHD | Load-haul-dump (articulated), ~3 m3 | 12 | 17.1 | 26.8 | 36.8 | 12 | 17.1 | 26.8 | 4.2 |
| SDL | Side discharge loader | 6 | 11.0 | 17.3 | 22.3 | 6 | 11.0 | 17.3 | 4.2 |
| CM | Continuous miner (remote controlled) | 1.5 | 6.3 | 10.2 | 11.4 | 1.5 | 6.3 | 10.2 | 4.2 |
| SC | Shuttle car (bidirectional) | 8 | 12.0 | 19.5 | 26.2 | 8 | 12.0 | 19.5 | 4.2 |
| LOCO | Battery locomotive (8 t) hauling tubs | 10 | 21.0 | 29.6 | 37.9 | 10 | 21.0 | 29.6 | 4.2 |
| UPC | Underground personnel / utility carrier | 20 | 23.6 | 37.7 | 54.4 | 8 | 10.5 | 17.9 | 4.2 |

Swing machine HEX: danger radius 7.1 m, warning radius 12.8 m from swing centre; counterweight travels 5.5 m of arc after an alarm before it stops.

Backhoe work mode (BHL): exclusion radius = reach 5.5 m + 1.5 m = 7.0 m from the swing post.

## 2. Sensor coordinates per machine (body frame: x fwd, y left, z up; m, deg)

### RDT100 - Rear dump truck, ~100 t class  (L 10.3 x W 6.1 x H 5.0 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 5.3 | 3.05 | 1.6 | 45 | - | front-left corner |
| UWB anchor | U2 | 5.3 | -3.05 | 1.6 | -45 | - | front-right corner |
| UWB anchor | U3 | 0.0 | 3.2 | 1.8 | 90 | - | mid-left (fills side null) |
| UWB anchor | U4 | 0.0 | -3.2 | 1.8 | -90 | - | mid-right (fills side null) |
| UWB anchor | U5 | -5.3 | 2.75 | 2.0 | 135 | - | rear-left, fender bracket behind duals |
| UWB anchor | U6 | -5.3 | -2.75 | 2.0 | -135 | - | rear-right, fender bracket behind duals |
| UWB anchor | U7 | 3.35 | 1.85 | 5.1 | omni | - | canopy top: over-body LOS, V2V ranging |
| LF coil 125 kHz | F1 | 5.3 | 0.0 | 1.0 | 0 | - | near-field shell, front |
| LF coil 125 kHz | F2 | -5.3 | 0.0 | 1.0 | 180 | - | near-field shell, rear |
| LF coil 125 kHz | F3 | 0.0 | 3.2 | 1.0 | 90 | - | near-field shell, left / tyres |
| LF coil 125 kHz | F4 | 0.0 | -3.2 | 1.0 | -90 | - | near-field shell, right / tyres |
| Radar 77 GHz | R1 | 5.3 | 0.0 | 1.0 | 0 | 0 | front, FOV 120 deg, 0.5-80 m |
| Radar 77 GHz | R2 | -5.3 | 1.52 | 1.0 | -165 | 0 | rear-left, toed-in 15 deg (NIOSH) |
| Radar 77 GHz | R3 | -5.3 | -1.52 | 1.0 | 165 | 0 | rear-right, toed-in 15 deg (NIOSH) |
| Radar 77 GHz | R4 | 0.5 | -3.2 | 1.2 | -90 | 0 | right (blind) side, 0.3-20 m |
| Thermal LWIR | T1 | -5.3 | 0.0 | 2.6 | 180 | -25 | rear, untagged-person detection |
| Thermal LWIR | T2 | 1.0 | -3.2 | 3.0 | -90 | -30 | right side (optional) |
| RGB camera | C1 | 5.3 | 0.0 | 2.5 | 0 | -15 | front view |
| RGB camera | C2 | 3.15 | -3.2 | 3.5 | -100 | -35 | right side, looking down/back |
| RGB camera | C3 | -5.3 | 0.0 | 3.0 | 180 | -30 | rear view (auto on reverse gear) |
| GNSS antenna | G1 | 3.65 | 2.05 | 5.15 | - | - | RTK, moving-baseline primary |
| GNSS antenna | G2 | 3.65 | -2.05 | 5.15 | - | - | RTK heading (baseline = W-2 m) |

### RDT60 - Rear dump truck, ~60 t class  (L 9.0 x W 4.9 x H 4.4 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 4.65 | 2.45 | 1.6 | 45 | - | front-left corner |
| UWB anchor | U2 | 4.65 | -2.45 | 1.6 | -45 | - | front-right corner |
| UWB anchor | U3 | 0.0 | 2.6 | 1.8 | 90 | - | mid-left (fills side null) |
| UWB anchor | U4 | 0.0 | -2.6 | 1.8 | -90 | - | mid-right (fills side null) |
| UWB anchor | U5 | -4.65 | 2.15 | 2.0 | 135 | - | rear-left, fender bracket behind duals |
| UWB anchor | U6 | -4.65 | -2.15 | 2.0 | -135 | - | rear-right, fender bracket behind duals |
| UWB anchor | U7 | 2.7 | 1.25 | 4.5 | omni | - | canopy top: over-body LOS, V2V ranging |
| LF coil 125 kHz | F1 | 4.65 | 0.0 | 1.0 | 0 | - | near-field shell, front |
| LF coil 125 kHz | F2 | -4.65 | 0.0 | 1.0 | 180 | - | near-field shell, rear |
| LF coil 125 kHz | F3 | 0.0 | 2.6 | 1.0 | 90 | - | near-field shell, left / tyres |
| LF coil 125 kHz | F4 | 0.0 | -2.6 | 1.0 | -90 | - | near-field shell, right / tyres |
| Radar 77 GHz | R1 | 4.65 | 0.0 | 1.0 | 0 | 0 | front, FOV 120 deg, 0.5-80 m |
| Radar 77 GHz | R2 | -4.65 | 1.23 | 1.0 | -165 | 0 | rear-left, toed-in 15 deg (NIOSH) |
| Radar 77 GHz | R3 | -4.65 | -1.23 | 1.0 | 165 | 0 | rear-right, toed-in 15 deg (NIOSH) |
| Radar 77 GHz | R4 | 0.5 | -2.6 | 1.2 | -90 | 0 | right (blind) side, 0.3-20 m |
| Thermal LWIR | T1 | -4.65 | 0.0 | 2.6 | 180 | -25 | rear, untagged-person detection |
| Thermal LWIR | T2 | 1.0 | -2.6 | 3.0 | -90 | -30 | right side (optional) |
| RGB camera | C1 | 4.65 | 0.0 | 2.5 | 0 | -15 | front view |
| RGB camera | C2 | 2.5 | -2.6 | 3.5 | -100 | -35 | right side, looking down/back |
| RGB camera | C3 | -4.65 | 0.0 | 3.0 | 180 | -30 | rear view (auto on reverse gear) |
| GNSS antenna | G1 | 3.0 | 1.45 | 4.55 | - | - | RTK, moving-baseline primary |
| GNSS antenna | G2 | 3.0 | -1.45 | 4.55 | - | - | RTK heading (baseline = W-2 m) |

### WTR28 - Water sprinkler / tanker, ~28 kL  (L 9.6 x W 3.6 x H 3.9 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 4.95 | 1.8 | 1.6 | 45 | - | front-left corner |
| UWB anchor | U2 | 4.95 | -1.8 | 1.6 | -45 | - | front-right corner |
| UWB anchor | U3 | 0.0 | 1.95 | 1.8 | 90 | - | mid-left (fills side null) |
| UWB anchor | U4 | 0.0 | -1.95 | 1.8 | -90 | - | mid-right (fills side null) |
| UWB anchor | U5 | -4.95 | 1.5 | 2.0 | 135 | - | rear-left, fender bracket behind duals |
| UWB anchor | U6 | -4.95 | -1.5 | 2.0 | -135 | - | rear-right, fender bracket behind duals |
| UWB anchor | U7 | 3.0 | 0.6 | 4.0 | omni | - | canopy top: over-body LOS, V2V ranging |
| LF coil 125 kHz | F1 | 4.95 | 0.0 | 1.0 | 0 | - | near-field shell, front |
| LF coil 125 kHz | F2 | -4.95 | 0.0 | 1.0 | 180 | - | near-field shell, rear |
| LF coil 125 kHz | F3 | 0.0 | 1.95 | 1.0 | 90 | - | near-field shell, left / tyres |
| LF coil 125 kHz | F4 | 0.0 | -1.95 | 1.0 | -90 | - | near-field shell, right / tyres |
| Radar 77 GHz | R1 | 4.95 | 0.0 | 1.0 | 0 | 0 | front, FOV 120 deg, 0.5-80 m |
| Radar 77 GHz | R2 | -4.95 | 0.9 | 1.0 | -165 | 0 | rear-left, toed-in 15 deg (NIOSH) |
| Radar 77 GHz | R3 | -4.95 | -0.9 | 1.0 | 165 | 0 | rear-right, toed-in 15 deg (NIOSH) |
| Radar 77 GHz | R4 | 0.5 | -1.95 | 1.2 | -90 | 0 | right (blind) side, 0.3-20 m |
| Thermal LWIR | T1 | -4.95 | 0.0 | 2.6 | 180 | -25 | rear, untagged-person detection |
| Thermal LWIR | T2 | 1.0 | -1.95 | 3.0 | -90 | -30 | right side (optional) |
| RGB camera | C1 | 4.95 | 0.0 | 2.5 | 0 | -15 | front view |
| RGB camera | C2 | 2.8 | -1.95 | 3.5 | -100 | -35 | right side, looking down/back |
| RGB camera | C3 | -4.95 | 0.0 | 3.0 | 180 | -30 | rear view (auto on reverse gear) |
| GNSS antenna | G1 | 3.3 | 0.8 | 4.05 | - | - | RTK, moving-baseline primary |
| GNSS antenna | G2 | 3.3 | -0.8 | 4.05 | - | - | RTK heading (baseline = W-2 m) |

### GRD - Motor grader  (L 10.0 x W 3.0 x H 3.4 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 5.15 | 1.5 | 1.6 | 45 | - | front-left corner |
| UWB anchor | U2 | 5.15 | -1.5 | 1.6 | -45 | - | front-right corner |
| UWB anchor | U3 | 0.0 | 1.65 | 1.8 | 90 | - | mid-left (fills side null) |
| UWB anchor | U4 | 0.0 | -1.65 | 1.8 | -90 | - | mid-right (fills side null) |
| UWB anchor | U5 | -5.15 | 1.2 | 2.0 | 135 | - | rear-left, fender bracket behind duals |
| UWB anchor | U6 | -5.15 | -1.2 | 2.0 | -135 | - | rear-right, fender bracket behind duals |
| UWB anchor | U7 | 3.2 | 0.0 | 3.5 | omni | - | canopy top: over-body LOS, V2V ranging |
| LF coil 125 kHz | F1 | 5.15 | 0.0 | 1.0 | 0 | - | near-field shell, front |
| LF coil 125 kHz | F2 | -5.15 | 0.0 | 1.0 | 180 | - | near-field shell, rear |
| LF coil 125 kHz | F3 | 0.0 | 1.65 | 1.0 | 90 | - | near-field shell, left / tyres |
| LF coil 125 kHz | F4 | 0.0 | -1.65 | 1.0 | -90 | - | near-field shell, right / tyres |
| Radar 77 GHz | R1 | 5.15 | 0.0 | 1.0 | 0 | 0 | front, FOV 120 deg, 0.5-80 m |
| Radar 77 GHz | R2 | -5.15 | 0.75 | 1.0 | -165 | 0 | rear-left, toed-in 15 deg (NIOSH) |
| Radar 77 GHz | R3 | -5.15 | -0.75 | 1.0 | 165 | 0 | rear-right, toed-in 15 deg (NIOSH) |
| Radar 77 GHz | R4 | 0.5 | -1.65 | 1.2 | -90 | 0 | right (blind) side, 0.3-20 m |
| Thermal LWIR | T1 | -5.15 | 0.0 | 2.6 | 180 | -25 | rear, untagged-person detection |
| Thermal LWIR | T2 | 1.0 | -1.65 | 3.0 | -90 | -30 | right side (optional) |
| RGB camera | C1 | 5.15 | 0.0 | 2.5 | 0 | -15 | front view |
| RGB camera | C2 | 3.0 | -1.65 | 3.5 | -100 | -35 | right side, looking down/back |
| RGB camera | C3 | -5.15 | 0.0 | 3.0 | 180 | -30 | rear view (auto on reverse gear) |
| GNSS antenna | G1 | 3.5 | 0.5 | 3.55 | - | - | RTK, moving-baseline primary |
| GNSS antenna | G2 | 3.5 | -0.5 | 3.55 | - | - | RTK heading (baseline = W-2 m) |

### HEX - Hydraulic excavator / shovel, ~200 t  (L 7.0 x W 5.5 x H 7.0 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | -5.4 | 2.45 | 2.2 | 135 | - | counterweight rear-left |
| UWB anchor | U2 | -5.4 | -2.45 | 2.2 | -135 | - | counterweight rear-right |
| UWB anchor | U3 | 2.0 | 2.9 | 2.0 | 60 | - | house front-left |
| UWB anchor | U4 | 2.0 | -2.9 | 2.0 | -60 | - | house front-right (boom side) |
| UWB anchor | U5 | 2.0 | 1.75 | 7.1 | omni | - | cab roof |
| UWB anchor | U6 | 3.65 | 0.0 | 1.0 | 0 | - | undercarriage track end (frame U) |
| UWB anchor | U7 | -3.65 | 0.0 | 1.0 | 180 | - | undercarriage track end (frame U) |
| Swing encoder | E1 | 0.0 | 0.0 | 1.5 | - | - | house angle vs undercarriage (or dual IMU) |
| LF coil 125 kHz | F1 | -5.6 | 0.0 | 1.8 | 180 | - | swing annulus shell, counterweight |
| LF coil 125 kHz | F2 | 0.0 | 2.9 | 1.5 | 90 | - | house left |
| LF coil 125 kHz | F3 | 0.0 | -2.9 | 1.5 | -90 | - | house right |
| Radar 77 GHz | R1 | -5.6 | 1.0 | 1.6 | 145 | 0 | counterweight, diverging 35 deg |
| Radar 77 GHz | R2 | -5.6 | -1.0 | 1.6 | -145 | 0 | counterweight, diverging 35 deg |
| Thermal LWIR | T1 | -5.6 | 0.0 | 2.6 | 180 | -20 | counterweight |
| RGB camera | C1 | -5.6 | 0.0 | 3.0 | 180 | -30 | rear (counterweight) |
| RGB camera | C2 | 1.0 | -2.9 | 3.2 | -90 | -30 | right side (opposite cab) |
| GNSS antenna | G1 | -5.0 | 1.5 | 4.2 | - | - | house top, RTK |
| GNSS antenna | G2 | -5.0 | -1.5 | 4.2 | - | - | house top, heading |

### DOZ - Crawler dozer, D375 class  (L 9.5 x W 4.3 x H 4.0 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 3.45 | 1.65 | 2.0 | 45 | - | radiator-guard front-left (not on blade) |
| UWB anchor | U2 | 3.45 | -1.65 | 2.0 | -45 | - | radiator-guard front-right |
| UWB anchor | U3 | 0.0 | 1.95 | 1.9 | 90 | - | left fender |
| UWB anchor | U4 | 0.0 | -1.95 | 1.9 | -90 | - | right fender |
| UWB anchor | U5 | -3.25 | 1.55 | 2.0 | 135 | - | rear-left (frame, not ripper) |
| UWB anchor | U6 | -3.25 | -1.55 | 2.0 | -135 | - | rear-right (frame, not ripper) |
| UWB anchor | U7 | -0.5 | 0.0 | 4.1 | omni | - | ROPS top |
| LF coil 125 kHz | F1 | 3.45 | 0.0 | 1.2 | 0 | - | front (behind blade) |
| LF coil 125 kHz | F2 | -3.75 | 0.0 | 1.2 | 180 | - | rear |
| LF coil 125 kHz | F3 | 0.0 | 2.15 | 1.0 | 90 | - | left |
| LF coil 125 kHz | F4 | 0.0 | -2.15 | 1.0 | -90 | - | right |
| Radar 77 GHz | R1 | -3.75 | 1.0 | 1.2 | -165 | 0 | rear-left, toed-in |
| Radar 77 GHz | R2 | -3.75 | -1.0 | 1.2 | 165 | 0 | rear-right, toed-in |
| Radar 77 GHz | R3 | 0.0 | 2.3 | 1.2 | 90 | 0 | left side (dozers pivot fast) |
| Radar 77 GHz | R4 | 0.0 | -2.3 | 1.2 | -90 | 0 | right side |
| Radar 77 GHz | R5 | 3.25 | 0.0 | 2.3 | 0 | -10 | front, over blade |
| Thermal LWIR | T1 | -3.75 | 0.0 | 2.6 | 180 | -25 | rear |
| RGB camera | C1 | -3.75 | 0.0 | 2.8 | 180 | -30 | rear |
| RGB camera | C2 | 3.45 | 0.0 | 2.6 | 0 | -20 | front (blade raised) |
| GNSS antenna | G1 | -0.5 | 1.0 | 4.15 | - | - | ROPS, RTK |
| GNSS antenna | G2 | -0.5 | -1.0 | 4.15 | - | - | ROPS, heading |

### FEL - Wheel loader (articulated), 5-6 m3  (L 9.2 x W 3.3 x H 3.6 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 3.0 | 1.8 | 1.4 | 45 | - | front frame, at lift-arm pivot (not bucket) |
| UWB anchor | U2 | 3.0 | -1.8 | 1.4 | -45 | - | front frame, at lift-arm pivot |
| UWB anchor | U3 | 0.0 | 1.8 | 1.3 | 90 | - | articulation pinch zone left |
| UWB anchor | U4 | 0.0 | -1.8 | 1.3 | -90 | - | articulation pinch zone right |
| UWB anchor | U5 | -4.75 | 1.45 | 1.4 | 135 | - | rear frame corner |
| UWB anchor | U6 | -4.75 | -1.45 | 1.4 | -135 | - | rear frame corner |
| UWB anchor | U7 | -1.0 | 0.0 | 3.65 | omni | - | canopy top |
| Articulation encoder | E1 | 0.0 | 0.0 | 1.0 | - | - | hull polygon follows steering |
| LF coil 125 kHz | F1 | 3.0 | 0.0 | 1.0 | 0 | - | front |
| LF coil 125 kHz | F2 | -4.75 | 0.0 | 1.0 | 180 | - | rear |
| LF coil 125 kHz | F3 | 0.0 | 1.8 | 1.0 | 90 | - | pinch zone left |
| LF coil 125 kHz | F4 | 0.0 | -1.8 | 1.0 | -90 | - | pinch zone right |
| Radar 60/77 GHz | R1 | 2.8 | 0.0 | 3.4 | 0 | -5 | front, above bucket line |
| Radar 60/77 GHz | R2 | -4.75 | 0.0 | 1.0 | 180 | 0 | rear |
| Thermal LWIR | T1 | -4.75 | 0.0 | 2.4 | 180 | -20 | rear |
| RGB/IR camera | C1 | -4.75 | 0.0 | 2.6 | 180 | -25 | rear |
| RGB/IR camera | C2 | 2.8 | 0.0 | 3.6 | 0 | -15 | front (bucket raised) |
| GNSS antenna | G1 | -1.0 | 0.6 | 3.75 | - | - | RTK |
| GNSS antenna | G2 | -1.0 | -0.6 | 3.75 | - | - | heading (rear frame) |

### BHL - Backhoe loader (JCB 3DX class)  (L 5.9 x W 2.35 x H 3.6 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 2.05 | 1.32 | 1.3 | 45 | - | front-left (behind loader arms) |
| UWB anchor | U2 | 2.05 | -1.32 | 1.3 | -45 | - | front-right |
| UWB anchor | U3 | -2.35 | 1.32 | 1.3 | 135 | - | rear-left (stabiliser leg, outside swing) |
| UWB anchor | U4 | -2.35 | -1.32 | 1.3 | -135 | - | rear-right |
| UWB anchor | U5 | 0.0 | 0.0 | 3.65 | omni | - | cab roof |
| Seat-direction switch | E1 | 0.0 | 0.0 | 1.0 | - | - | loader mode vs backhoe mode |
| LF coil 125 kHz | F1 | 2.05 | 0.0 | 1.0 | 0 | - | front |
| LF coil 125 kHz | F2 | -2.35 | 0.0 | 1.0 | 180 | - | rear / backhoe swing |
| Radar 24/60 GHz | R1 | 2.05 | 0.0 | 1.4 | 0 | 0 | front near-field |
| Radar 24/60 GHz | R2 | -2.35 | 0.0 | 1.4 | 180 | 0 | rear near-field |
| RGB camera | C1 | -2.35 | 0.0 | 2.4 | 180 | -30 | rear |
| GNSS antenna | G1 | 0.0 | 0.0 | 3.75 | - | - | RTK (single, IMU heading) |

### DRL - Blast-hole drill (crawler)  (L 9.0 x W 4.5 x H 4.5 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 4.65 | 2.25 | 1.5 | 45 | - | front-left |
| UWB anchor | U2 | 4.65 | -2.25 | 1.5 | -45 | - | front-right |
| UWB anchor | U3 | -4.65 | 2.25 | 1.5 | 135 | - | rear-left |
| UWB anchor | U4 | -4.65 | -2.25 | 1.5 | -135 | - | rear-right |
| UWB anchor | U5 | 0.0 | 0.0 | 4.6 | omni | - | deck top (mast down) |
| LF coil 125 kHz | F1 | 4.65 | 0.0 | 1.0 | 0 | - | front / drill-string zone |
| LF coil 125 kHz | F2 | -4.65 | 0.0 | 1.0 | 180 | - | rear |
| Radar 24/60 GHz | R1 | -4.65 | 0.0 | 1.2 | 180 | 0 | rear (tramming) |
| RGB camera | C1 | -4.65 | 0.0 | 2.6 | 180 | -30 | rear |
| Mast-angle switch | E1 | 0.0 | 0.0 | 2.0 | - | - | mast up = overhead-line geofence check |
| GNSS antenna | G1 | 0.0 | 1.0 | 4.65 | - | - | RTK (hole positioning reuse) |

### LMV - Light motor vehicle (jeep / pickup)  (L 4.4 x W 1.75 x H 1.9 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| Combo node (UWB+sub-GHz) | N1 | 0.2 | 0.0 | 2.0 | omni | - | magnetic roof mount, beacon + V2X |
| UWB anchor | U1 | 2.35 | 0.0 | 0.9 | 0 | - | front bumper (optional) |
| UWB anchor | U2 | -2.35 | 0.0 | 1.0 | 180 | - | rear bumper (optional) |
| Radar 24/60 GHz | R1 | -2.35 | 0.0 | 0.6 | 180 | 0 | rear (optional) |
| Cab alert unit | H1 | 0.6 | 0.0 | 1.2 | - | - | buzzer + LED + voice |
| GNSS antenna | G1 | 0.2 | 0.3 | 2.02 | - | - | in combo node |
| Whip flag + strobe | V1 | -1.0 | 0.6 | 4.4 | - | - | visibility to HEMM drivers |

### LHD - Load-haul-dump (articulated), ~3 m3  (L 9.0 x W 2.2 x H 2.1 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 2.9 | 1.25 | 1.4 | 45 | - | front frame, at lift-arm pivot (not bucket) |
| UWB anchor | U2 | 2.9 | -1.25 | 1.4 | -45 | - | front frame, at lift-arm pivot |
| UWB anchor | U3 | 0.4 | 1.25 | 1.3 | 90 | - | articulation pinch zone left |
| UWB anchor | U4 | 0.4 | -1.25 | 1.3 | -90 | - | articulation pinch zone right |
| UWB anchor | U5 | -4.65 | 0.9 | 1.4 | 135 | - | rear frame corner |
| UWB anchor | U6 | -4.65 | -0.9 | 1.4 | -135 | - | rear frame corner |
| UWB anchor | U7 | -0.6 | 0.0 | 2.15 | omni | - | canopy top |
| Articulation encoder | E1 | 0.4 | 0.0 | 1.0 | - | - | hull polygon follows steering |
| LF coil 125 kHz | F1 | 2.9 | 0.0 | 1.0 | 0 | - | front |
| LF coil 125 kHz | F2 | -4.65 | 0.0 | 1.0 | 180 | - | rear |
| LF coil 125 kHz | F3 | 0.4 | 1.25 | 1.0 | 90 | - | pinch zone left |
| LF coil 125 kHz | F4 | 0.4 | -1.25 | 1.0 | -90 | - | pinch zone right |
| Radar 60/77 GHz | R1 | 2.7 | 0.0 | 1.9 | 0 | -5 | front, above bucket line |
| Radar 60/77 GHz | R2 | -4.65 | 0.0 | 1.0 | 180 | 0 | rear (FOV 90 deg in tunnels) |
| Thermal LWIR | T1 | -4.65 | 0.0 | 1.8 | 180 | -20 | rear |
| RGB/IR camera | C1 | -4.65 | 0.0 | 1.9 | 180 | -25 | rear |
| RGB/IR camera | C2 | 2.7 | 0.0 | 2.1 | 0 | -15 | front (bucket raised) |
| Thermal LWIR | T2 | 2.7 | 0.0 | 2.0 | 0 | -10 | front |
| 2-D LiDAR (Ex) | L1 | 3.9 | 0.0 | 1.6 | 0 | 0 | front: map-matching localisation |
| 2-D LiDAR (Ex) | L2 | -3.9 | 0.0 | 1.6 | 180 | 0 | rear: map-matching localisation |

### SDL - Side discharge loader  (L 6.5 x W 1.85 x H 1.45 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 3.4 | 0.93 | 1.1 | 45 | - | front-left |
| UWB anchor | U2 | 3.4 | -0.93 | 1.1 | -45 | - | front-right |
| UWB anchor | U3 | -3.4 | 0.93 | 1.1 | 135 | - | rear-left |
| UWB anchor | U4 | -3.4 | -0.93 | 1.1 | -135 | - | rear-right |
| UWB anchor | U5 | 0.0 | 1.07 | 1.2 | 90 | - | operator side |
| LF coil 125 kHz | F1 | 3.4 | 0.0 | 0.8 | 0 | - | front |
| LF coil 125 kHz | F2 | -3.4 | 0.0 | 0.8 | 180 | - | rear |
| LF coil 125 kHz | F3 | 0.0 | 1.07 | 0.8 | 90 | - | left |
| LF coil 125 kHz | F4 | 0.0 | -1.07 | 0.8 | -90 | - | right |
| Radar 60 GHz | R1 | 3.4 | 0.0 | 0.9 | 0 | 0 | front, FOV 90 deg |
| Radar 60 GHz | R2 | -3.4 | 0.0 | 0.9 | 180 | 0 | rear, FOV 90 deg |
| Thermal LWIR | T1 | 3.4 | 0.0 | 1.3 | 0 | -10 | front |
| Thermal LWIR | T2 | -3.4 | 0.0 | 1.3 | 180 | -10 | rear |

### CM - Continuous miner (remote controlled)  (L 11.0 x W 3.3 x H 1.9 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 4.7 | 1.8 | 1.2 | 60 | - | cutter-drum end left |
| UWB anchor | U2 | 4.7 | -1.8 | 1.2 | -60 | - | cutter-drum end right |
| UWB anchor | U3 | 0.0 | 1.8 | 1.2 | 90 | - | mid-left (operator walkway) |
| UWB anchor | U4 | 0.0 | -1.8 | 1.2 | -90 | - | mid-right |
| UWB anchor | U5 | -4.5 | 1.05 | 1.2 | 135 | - | tail-boom left |
| UWB anchor | U6 | -4.5 | -1.05 | 1.2 | -135 | - | tail-boom right |
| LF coil 125 kHz | F1 | 3.5 | 1.65 | 0.9 | 60 | - | front-left (cutter boom pivot) |
| LF coil 125 kHz | F2 | 3.5 | -1.65 | 0.9 | -60 | - | front-right |
| LF coil 125 kHz | F3 | -0.5 | 1.65 | 0.9 | 90 | - | mid-left |
| LF coil 125 kHz | F4 | -0.5 | -1.65 | 0.9 | -90 | - | mid-right |
| LF coil 125 kHz | F5 | -5.0 | 0.0 | 0.9 | 180 | - | tail conveyor |
| Function-inhibit I/O | E1 | 0.0 | 0.0 | 1.0 | - | - | tram/swing/cutter/gathering-arm interlocks |

### SC - Shuttle car (bidirectional)  (L 8.5 x W 3.0 x H 1.5 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 4.4 | 1.5 | 1.0 | 45 | - | end A left |
| UWB anchor | U2 | 4.4 | -1.5 | 1.0 | -45 | - | end A right |
| UWB anchor | U3 | -4.4 | 1.5 | 1.0 | 135 | - | end B left |
| UWB anchor | U4 | -4.4 | -1.5 | 1.0 | -135 | - | end B right |
| UWB anchor | U5 | 0.0 | 1.65 | 1.1 | 90 | - | mid-left |
| UWB anchor | U6 | 0.0 | -1.65 | 1.1 | -90 | - | mid-right |
| LF coil 125 kHz | F1 | 4.4 | 0.0 | 0.8 | 0 | - | end A |
| LF coil 125 kHz | F2 | -4.4 | 0.0 | 0.8 | 180 | - | end B |
| LF coil 125 kHz | F3 | 0.0 | 1.65 | 0.8 | 90 | - | operator-cab side |
| LF coil 125 kHz | F4 | 0.0 | -1.65 | 0.8 | -90 | - | cable-reel side |
| Radar 60 GHz | R1 | 4.4 | 0.0 | 0.9 | 0 | 0 | end A |
| Radar 60 GHz | R2 | -4.4 | 0.0 | 0.9 | 180 | 0 | end B |
| IR camera | C1 | 4.4 | 0.0 | 1.3 | 0 | -10 | end A |
| IR camera | C2 | -4.4 | 0.0 | 1.3 | 180 | -10 | end B |

### LOCO - Battery locomotive (8 t) hauling tubs  (L 4.5 x W 1.1 x H 1.6 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| UWB anchor | U1 | 2.4 | 0.45 | 1.3 | 20 | - | loco front-left |
| UWB anchor | U2 | 2.4 | -0.45 | 1.3 | -20 | - | loco front-right |
| UWB anchor | U3 | -2.4 | 0.45 | 1.3 | 160 | - | loco rear-left |
| UWB anchor | U4 | -2.4 | -0.45 | 1.3 | -160 | - | loco rear-right |
| End-of-train unit | N1 | -47.25 | 0.0 | 1.0 | 180 | - | last tub: UWB+sub-GHz, train length |
| LF coil 125 kHz | F1 | 2.4 | 0.0 | 0.8 | 0 | - | front |
| LF coil 125 kHz | F2 | -2.4 | 0.0 | 0.8 | 180 | - | rear |
| Radar 60 GHz | R1 | 2.4 | 0.0 | 1.0 | 0 | 0 | front, FOV 30-60 deg along track |
| Radar 60 GHz | R2 | -2.4 | 0.0 | 1.0 | 180 | 0 | rear |
| IR camera | C1 | 2.4 | 0.0 | 1.4 | 0 | -5 | front |

### UPC - Underground personnel / utility carrier  (L 5.0 x W 1.9 x H 1.9 m)

| Sensor | ID | x | y | z | yaw | pitch | Purpose |
|---|---|---|---|---|---|---|---|
| Combo node (UWB+sub-GHz) | N1 | 0.2 | 0.0 | 2.0 | omni | - | magnetic roof mount, beacon + V2X |
| UWB anchor | U1 | 2.65 | 0.0 | 0.9 | 0 | - | front bumper (optional) |
| UWB anchor | U2 | -2.65 | 0.0 | 1.0 | 180 | - | rear bumper (optional) |
| Radar 24/60 GHz | R1 | -2.65 | 0.0 | 0.6 | 180 | 0 | rear (optional) |
| Cab alert unit | H1 | 0.6 | 0.0 | 1.2 | - | - | buzzer + LED + voice |
| Radar 60 GHz | R2 | 2.65 | 0.0 | 0.8 | 0 | 0 | front |

## 3. UWB layout study, RDT100 (helmet tag at 1.7 m, sigma_r 0.10 m, LOS only, 60 m max)

| Layout | Ring from hull | >=1 anchor (range) | >=2 (position) | >=3 (redundant) | Median 2DRMS (m) | p95 2DRMS (m) |
|---|---|---|---|---|---|---|
| A - 2 rear anchors | 0-5 m | 35% | 28% | 0% | 0.44 | 3.85 |
| A - 2 rear anchors | 5-15 m | 50% | 40% | 0% | 1.00 | 18.29 |
| A - 2 rear anchors | 15-40 m | 58% | 46% | 0% | 2.40 | 33.48 |
| B - 4 corners | 0-5 m | 100% | 63% | 15% | 0.31 | 1.89 |
| B - 4 corners | 5-15 m | 100% | 90% | 33% | 0.52 | 4.66 |
| B - 4 corners | 15-40 m | 100% | 100% | 47% | 1.10 | 5.33 |
| C - 4 corners + 2 mid-sides | 0-5 m | 100% | 100% | 39% | 0.30 | 1.21 |
| C - 4 corners + 2 mid-sides | 5-15 m | 100% | 100% | 78% | 0.46 | 0.68 |
| C - 4 corners + 2 mid-sides | 15-40 m | 100% | 100% | 95% | 0.95 | 1.51 |
| D - C + canopy-top anchor (recommended) | 0-5 m | 100% | 100% | 46% | 0.30 | 1.21 |
| D - C + canopy-top anchor (recommended) | 5-15 m | 100% | 100% | 90% | 0.45 | 0.68 |
| D - C + canopy-top anchor (recommended) | 15-40 m | 100% | 100% | 99% | 0.92 | 1.48 |

## 4. Event-triggered transmission rate vs threshold

| delta (sigma) | m = 2 (position) | m = 4 (pos + vel) |
|---|---|---|
| 1.0 | 53.39% | 78.28% |
| 1.5 | 24.94% | 43.66% |
| 2.0 | 8.89% | 17.00% |
| 2.5 | 2.47% | 4.88% |
| 3.0 | 0.54% | 1.08% |

## 5. Wearable average current (uA) by subsystem

| Mode | Sensing + MCU baseline | IMU (accel + gyro) | UWB discovery blinks | UWB ranging sessions | Sub-GHz telemetry + listening | LF rescue locator | Total uA | mAh / 12 h |
|---|---|---|---|---|---|---|---|---|
| Event-driven (this design) | 108 | 168 | 28 | 127 | 90 | 0 | 521 | 6.2 |
| Fixed-rate polling (10 Hz UWB, 5 s reports) | 108 | 460 | 0 | 1042 | 478 | 0 | 2088 | 25.1 |
| Backup cell, emergency beacon mode | 78 | 10 | 6 | 0 | 226 | 150 | 470 | 5.6 |

Per UWB discovery blink: 28.8 uC. Per 1-to-4 DS-TWR fix: 104.2 uC. Per 16-byte LoRa SF7 packet incl. RX windows: 2138 uC (time on air 51.5 ms; SF9 164.9 ms; GFSK 50 kb/s 4.3 ms).

Alarm actuators (vibration 70 mA, 10% duty in WARNING, 50% in DANGER) average 1.12 mA = 13.4 mAh per shift in both designs.

Backup cell 600 mAh, derated 50% for temperature and ageing: 638 h of emergency beaconing (requirement >= 96 h).

## 6. Infrastructure node power

| Case | Average W | Wh for 24 h | Wh for 96 h |
|---|---|---|---|
| Normal operation (line power) | 3.10 | 74 | 298 |
| Standby, fibre alive (5/5/90 radio) | 1.18 | 28 | 113 |
| Standby, fibre cut, mesh only | 0.18 | 4.2 | 16.9 |

## 7. Through-the-earth carrier

| Depth (m) | rho 10 ohm.m | rho 100 ohm.m | rho 1000 ohm.m | Inter-harmonic carrier (rho 100) |
|---|---|---|---|---|
| 100 | 1,013 Hz (delta 50 m) | 10,132 Hz (delta 50 m) | 101,321 Hz (delta 50 m) | 10,125 Hz |
| 200 | 253 Hz (delta 100 m) | 2,533 Hz (delta 100 m) | 25,330 Hz (delta 100 m) | 2,525 Hz |
| 300 | 113 Hz (delta 150 m) | 1,126 Hz (delta 150 m) | 11,258 Hz (delta 150 m) | 1,125 Hz |
| 400 | 63 Hz (delta 200 m) | 633 Hz (delta 200 m) | 6,333 Hz (delta 200 m) | 625 Hz |
| 600 | 28 Hz (delta 300 m) | 281 Hz (delta 300 m) | 2,814 Hz (delta 300 m) | 275 Hz |

| Message | Bits | Time @ 10 b/s net | Time @ 50 b/s net | Uplink energy @ 20 W, 10 b/s |
|---|---|---|---|---|
| Full roll-call, 200 persons (twin-referenced) | 6476 | 648 s | 129.5 s | 12952 J |
| Full roll-call, 200 persons (raw float xyz) | 24076 | 2408 s | 481.5 s | 48152 J |
| Delta roll-call: 15 persons changed vs twin | 556 | 56 s | 11.1 s | 1112 J |
| Refuge status: count, injured, O2/CO | 112 | 11 s | 2.2 s | 224 J |
| Downlink: evacuate via route code | 84 | 8 s | 1.7 s | 168 J |

