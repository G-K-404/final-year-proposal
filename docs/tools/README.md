# Design tools

`design_calcs.py` regenerates every computed number and figure in the design documents. Edit the inputs,
not the outputs.

| File | Role |
|---|---|
| `machine_profiles.toml` | Machine Safety Profiles: dimensions, speeds, braking, grades, cab side, joints, kit. **Replace the representative values with SCCL fleet data.** |
| `design_calcs.py` | Zones, sensor coordinates, UWB coverage study, event-rate table, power budgets, node standby energy, TTE carrier and message sizes |
| `generated_tables.md` | Output tables (do not edit by hand) |
| `../figures/*.png` | Output figures |

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows; use .venv/bin/pip on Linux/macOS
.venv/Scripts/python design_calcs.py               # writes generated_tables.md and ../figures/
.venv/Scripts/python design_calcs.py --profiles my_fleet.toml --out my_tables.md --figdir my_figs
```

Requires Python ≥ 3.11 (uses the built-in `tomllib`).

**To add a machine**, append a `[[machine]]` block with an existing `kit` (`haul`, `swing`, `tracked`,
`artic`, `bhl`, `drill`, `lmv`, `rigid_ug`, `cm`, `bidir`, `rail`). If none fits, add a kit to
`placement()`.

**To change assumptions**: the zone parameters are in `[defaults]` in the TOML. Device currents, the duty
mix and the shift length are the `DEV`, `MIX` and `SHIFT_H` constants in the script. Replace the currents
with measured values from the prototype.
