"""Shared helpers for the market-sensor simulation.

Reuses docs/tools/design_calcs.py (zones, sensor placement, line-of-sight test, LoRa time on air,
chart palette) so the simulation and the design documents can never disagree on those numbers.
"""
from __future__ import annotations

import math
import pathlib
import sys
import tomllib

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
TOOLS = ROOT / "docs" / "tools"
sys.path.insert(0, str(TOOLS))

import design_calcs as dc  # noqa: E402  (sets the matplotlib Agg backend and the chart style)

C_LIGHT = 299_792_458.0
K_T0 = 1.380649e-23 * 290.0  # W/Hz


def load_components(path: pathlib.Path = HERE / "components.toml") -> dict:
    return tomllib.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def load_profiles(path: pathlib.Path = TOOLS / "machine_profiles.toml") -> tuple[dict, dict]:
    cfg = tomllib.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    return cfg["defaults"], {m["id"]: m for m in cfg["machine"]}


def db2lin(x):
    return 10.0 ** (np.asarray(x, dtype=float) / 10.0)


def lin2db(x):
    return 10.0 * np.log10(np.asarray(x, dtype=float))


def fspl_db(d_m, f_hz):
    """Free-space path loss, dB (distance clipped at 0.1 m)."""
    d = np.maximum(np.asarray(d_m, dtype=float), 0.1)
    return 20.0 * np.log10(4.0 * math.pi * d * f_hz / C_LIGHT)


def p_link(prx_dbm, sens_dbm, slope_db=0.5):
    """Frame success probability: 1 % PER at the datasheet sensitivity, logistic around it.

    Datasheet sensitivities (D2, D8) are quoted at 1 % PER, so PER(sens) = 0.01 fixes the curve's
    position: the 50 % point sits ln(99) * slope = 2.3 dB below the sensitivity.
    """
    p50 = sens_dbm - math.log(99.0) * slope_db
    return 1.0 / (1.0 + np.exp(-(np.asarray(prx_dbm, dtype=float) - p50) / slope_db))


def knife_edge_db(v):
    """ITU-R P.526 single knife-edge diffraction loss J(v), dB (0 for v <= -0.78)."""
    v = np.asarray(v, dtype=float)
    j = 6.9 + 20.0 * np.log10(np.sqrt((v - 0.1) ** 2 + 1.0) + v - 0.1)
    return np.where(v > -0.78, j, 0.0)


def lognormal(rng, median, sigma_ln, size=None):
    return median * np.exp(sigma_ln * rng.standard_normal(size))


def pct(x, q):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return float(np.percentile(x, q)) if x.size else float("nan")


def fmt_pct(num, den, digits=1):
    if den == 0:
        return "-"
    return f"{100.0 * num / den:.{digits}f}%"


def fmt(x, digits=1, unit=""):
    if x is None or not np.isfinite(x):
        return "-"
    return f"{x:.{digits}f}{unit}"


md_table = dc.md_table
SERIES, INK, INK2, MUTED, GRID, AXIS, SURFACE = (dc.SERIES, dc.INK, dc.INK2, dc.MUTED, dc.GRID,
                                                 dc.AXIS, dc.SURFACE)
despine = dc._despine
