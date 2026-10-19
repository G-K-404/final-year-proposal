# Market-component simulation

Simulates the exact parts in [docs/13](../docs/13_component_simulation.md) against the scenario library of
[docs/10 §6](../docs/10_simulation_and_data.md): V2P and V2V collision warning on the RDT100 truck and an
LMV, and gate attendance with biometric + helmet checks.

| File | Role |
|---|---|
| `components.toml` | Datasheet values for every part (with the document and table they came from) and, separately, every assumption that is not on a datasheet. **Edit this, not the outputs.** |
| `sensors.py` | One model per part: DWM3000 UWB ranging, AS3932 LF shell, AWR1843AOP/IWR6843AOP radar equation, ARS 408-21 envelope, R700 + M730 RFID link, SX1262 radio, ZED-F9P error process, R503/GT-521F52 fingerprint, FDC1004 worn sensor |
| `v2p.py` | Vehicle-to-person Monte Carlo: S01, S02, S06, S08, SF, S00 and key-on start-inhibit (S03); Kalman tracking, swept-path TTC, alarm levels L1–L4 |
| `v2v.py` | Vehicle-to-vehicle: blind bench corner (S05) with an OC Guardian relay, passing trucks by GNSS grade, channel load |
| `attendance.py` | Gate attendance: four configurations, shift-change queue, PPE checks, UHF reader-power sweep, outsider acceptance, roll-call |
| `run_all.py` | Runs everything in parallel; writes `results.md`, `results.json` and `../docs/figures/fig_sim_*.png` |
| `common.py` | Shared helpers; imports `docs/tools/design_calcs.py` for zones, sensor coordinates, LoRa airtime and the chart style |

```bash
python -m venv .venv
.venv/Scripts/pip install -r sim/requirements.txt   # Windows; use .venv/bin/pip on Linux/macOS
.venv/Scripts/python sim/run_all.py                 # full run, about 2 min on 16 processes
.venv/Scripts/python sim/run_all.py --quick         # one fifth of the runs
.venv/Scripts/python sim/run_all.py --runs 1000     # more V2P runs per scenario
```

Requires Python ≥ 3.11. Seeds are fixed, so a re-run reproduces every number.

**To try another part**, overwrite its table in `components.toml` with that part's datasheet values (for
example a different radar's EIRP and EINF) and re-run. **To use a measurement**, replace the matching value
in `[assumptions]`. The machine geometry, speeds and braking come from
`docs/tools/machine_profiles.toml`.
