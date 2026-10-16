#!/usr/bin/env python3
"""
Design calculations for the Mine Proximity Safety System (Team A07).

Reproduces every number quoted in docs/0*.md that is computed rather than cited:

  1. Speed-adaptive stop / warning / awareness zones per machine profile
  2. Exact sensor coordinates per machine, generated from placement rules ("kits")
  3. UWB anchor-layout coverage + position-error study (rear dump truck)
  4. Event-triggered communication rate vs threshold (Wu et al., IEEE TAC 2013)
  5. Wearable power budget: event-driven design vs fixed-rate polling
  6. Infrastructure-node standby energy (MSHA P14-V-01 5/5/90 duty cycle)
  7. Through-the-earth (TTE) carrier choice and digital-twin message sizes
  8. LoRa time-on-air helper (Semtech AN1200.13 formula)

Usage:
    python design_calcs.py                # writes figures/ and generated_tables.md
    python design_calcs.py --profiles my_fleet.toml

Requires: Python >= 3.11 (tomllib), numpy, matplotlib  (see requirements.txt)

All device currents below are INDICATIVE datasheet-class values for budgeting.
Measure the real prototype (e.g. with a Nordic PPK2 / Joulescope) and update.
"""
from __future__ import annotations

import argparse
import math
import pathlib
import tomllib

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

HERE = pathlib.Path(__file__).resolve().parent
DOCS = HERE.parent

# ---------------------------------------------------------------------------
# Chart style - validated reference palette (light surface)
# ---------------------------------------------------------------------------
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]  # fixed order
ORDINAL = ["#86b6ef", "#3987e5", "#256abf", "#184f95", "#0d366b"]  # blue 250..700
NEUTRAL_LIGHT, NEUTRAL_DARK = "#ecebe6", "#c3c2b7"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
    "font.size": 10,
    "axes.facecolor": SURFACE,
    "figure.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "grid.linestyle": "-",
    "axes.axisbelow": True,
    "legend.frameon": False,
    "legend.labelcolor": INK2,
    "lines.linewidth": 2,
    "lines.solid_capstyle": "round",
    "lines.solid_joinstyle": "round",
    "hatch.color": "#898781",
    "hatch.linewidth": 0.6,
})


def _despine(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


# ---------------------------------------------------------------------------
# 1. Zones
# ---------------------------------------------------------------------------
def zones(m: dict, d: dict, v_kmh: float) -> tuple[float, float, float]:
    """Return (stop, warning, awareness) distances from the machine hull, metres.

    stop    = v(t_sys+t_react) + v^2/(2 a_eff) + v_ped*T_total + k*sigma + buffer
    warning = stop + (v + v_ped) * t_warn_extra
    aware   = warning + v * t_aware_extra
    a_eff   = a_brake - g*grade  (downgrade worst case)
    With v = 0 the stop distance is the start-inhibit radius (a person can walk
    into the first-motion path during the operator's reaction time).
    """
    v = v_kmh / 3.6
    a_eff = m["a_brake_mps2"] - d["g"] * m.get("design_grade", 0.0)
    if a_eff <= 0.2:
        raise ValueError(f"{m['id']}: effective deceleration {a_eff:.2f} m/s2 is unsafe")
    t1 = d["t_sys_s"] + d["t_react_s"]
    t_total = t1 + v / a_eff
    stop = (v * t1 + v * v / (2 * a_eff) + d["v_ped_mps"] * t_total
            + d["k_sigma"] * d["sigma_pos_m"] + d["buffer_m"])
    warn = stop + (v + d["v_ped_mps"]) * d["t_warn_extra_s"]
    aware = warn + v * d["t_aware_extra_s"]
    return stop, warn, aware


def swing_zones(m: dict, d: dict) -> tuple[float, float, float]:
    """Radial zones (from swing centre) for a rotating superstructure."""
    r = m["tail_swing_radius_m"]
    omega = m["swing_rpm"] * 2 * math.pi / 60
    v_tip = r * omega
    a_tip = r * m["swing_decel_rad_s2"]
    t1 = d["t_sys_s"] + d["t_react_s"]
    danger = r + d["k_sigma"] * d["sigma_pos_m"] + d["buffer_m"]
    warn = danger + d["v_ped_mps"] * (t1 + d["t_warn_extra_s"])
    arc_stop = v_tip * t1 + v_tip ** 2 / (2 * a_tip)  # arc travelled after alarm
    return danger, warn, arc_stop


# ---------------------------------------------------------------------------
# 2. Placement rules -> exact coordinates
# ---------------------------------------------------------------------------
O = 0.15  # outboard offset so a sensor clears paint, guards and its own bracket


def _s(sensor, sid, x, y, z, yaw="-", pitch="-", purpose=""):
    return dict(sensor=sensor, id=sid, x=x, y=y, z=z, yaw=yaw, pitch=pitch, purpose=purpose)


def placement(m: dict) -> list[dict]:
    """Rule-based sensor coordinates in the machine body frame (see TOML header)."""
    L2, W2, H = m["length_m"] / 2, m["width_m"] / 2, m["height_m"]
    kit = m["kit"]
    cab = m.get("cab_side", "centre")
    blind = -1 if cab == "left" else (1 if cab == "right" else -1)  # sign of blind side
    bs = "right" if blind < 0 else "left"
    S = []
    if kit == "haul":
        S += [
            _s("UWB anchor", "U1", L2 + O, W2, 1.6, 45, purpose="front-left corner"),
            _s("UWB anchor", "U2", L2 + O, -W2, 1.6, -45, purpose="front-right corner"),
        ]
        if m["length_m"] >= 8.0:
            S += [
                _s("UWB anchor", "U3", 0.0, W2 + O, 1.8, 90, purpose="mid-left (fills side null)"),
                _s("UWB anchor", "U4", 0.0, -(W2 + O), 1.8, -90, purpose="mid-right (fills side null)"),
            ]
        S += [
            _s("UWB anchor", "U5", -(L2 + O), W2 - 0.3, 2.0, 135, purpose="rear-left, fender bracket behind duals"),
            _s("UWB anchor", "U6", -(L2 + O), -(W2 - 0.3), 2.0, -135, purpose="rear-right, fender bracket behind duals"),
        ]
        roof_y = (W2 - 1.2) if cab == "left" else (-(W2 - 1.2) if cab == "right" else 0.0)
        S += [
            _s("UWB anchor", "U7", L2 - 1.8, roof_y, H + 0.1, "omni", purpose="canopy top: over-body LOS, V2V ranging"),
            _s("LF coil 125 kHz", "F1", L2 + O, 0.0, 1.0, 0, purpose="near-field shell, front"),
            _s("LF coil 125 kHz", "F2", -(L2 + O), 0.0, 1.0, 180, purpose="near-field shell, rear"),
            _s("LF coil 125 kHz", "F3", 0.0, W2 + O, 1.0, 90, purpose="near-field shell, left / tyres"),
            _s("LF coil 125 kHz", "F4", 0.0, -(W2 + O), 1.0, -90, purpose="near-field shell, right / tyres"),
            _s("Radar 77 GHz", "R1", L2 + O, 0.0, 1.0, 0, 0, "front, FOV 120 deg, 0.5-80 m"),
            _s("Radar 77 GHz", "R2", -(L2 + O), W2 / 2, 1.0, -165, 0, "rear-left, toed-in 15 deg (NIOSH)"),
            _s("Radar 77 GHz", "R3", -(L2 + O), -W2 / 2, 1.0, 165, 0, "rear-right, toed-in 15 deg (NIOSH)"),
            _s("Radar 77 GHz", "R4", 0.5, blind * (W2 + O), 1.2, blind * 90, 0, f"{bs} (blind) side, 0.3-20 m"),
            _s("Thermal LWIR", "T1", -(L2 + O), 0.0, 2.6, 180, -25, "rear, untagged-person detection"),
            _s("Thermal LWIR", "T2", 1.0, blind * (W2 + O), 3.0, blind * 90, -30, f"{bs} side (optional)"),
            _s("RGB camera", "C1", L2 + O, 0.0, 2.5, 0, -15, "front view"),
            _s("RGB camera", "C2", L2 - 2.0, blind * (W2 + O), 3.5, blind * 100, -35, f"{bs} side, looking down/back"),
            _s("RGB camera", "C3", -(L2 + O), 0.0, 3.0, 180, -30, "rear view (auto on reverse gear)"),
        ]
        if m["domain"] == "surface":
            S += [
                _s("GNSS antenna", "G1", L2 - 1.5, W2 - 1.0, H + 0.15, purpose="RTK, moving-baseline primary"),
                _s("GNSS antenna", "G2", L2 - 1.5, -(W2 - 1.0), H + 0.15, purpose="RTK heading (baseline = W-2 m)"),
            ]
    elif kit == "swing":  # rotating house frame, origin = swing centre
        R = m["tail_swing_radius_m"]
        S += [
            _s("UWB anchor", "U1", -R + 0.2, W2 - 0.3, 2.2, 135, purpose="counterweight rear-left"),
            _s("UWB anchor", "U2", -R + 0.2, -(W2 - 0.3), 2.2, -135, purpose="counterweight rear-right"),
            _s("UWB anchor", "U3", 2.0, W2 + O, 2.0, 60, purpose="house front-left"),
            _s("UWB anchor", "U4", 2.0, -(W2 + O), 2.0, -60, purpose="house front-right (boom side)"),
            _s("UWB anchor", "U5", 2.0, (W2 - 1.0) if cab == "left" else -(W2 - 1.0), H + 0.1, "omni", purpose="cab roof"),
            _s("UWB anchor", "U6", m["length_m"] / 2 + O, 0.0, 1.0, 0, purpose="undercarriage track end (frame U)"),
            _s("UWB anchor", "U7", -(m["length_m"] / 2 + O), 0.0, 1.0, 180, purpose="undercarriage track end (frame U)"),
            _s("Swing encoder", "E1", 0.0, 0.0, 1.5, purpose="house angle vs undercarriage (or dual IMU)"),
            _s("LF coil 125 kHz", "F1", -R, 0.0, 1.8, 180, purpose="swing annulus shell, counterweight"),
            _s("LF coil 125 kHz", "F2", 0.0, W2 + O, 1.5, 90, purpose="house left"),
            _s("LF coil 125 kHz", "F3", 0.0, -(W2 + O), 1.5, -90, purpose="house right"),
            _s("Radar 77 GHz", "R1", -R, 1.0, 1.6, 145, 0, "counterweight, diverging 35 deg"),
            _s("Radar 77 GHz", "R2", -R, -1.0, 1.6, -145, 0, "counterweight, diverging 35 deg"),
            _s("Thermal LWIR", "T1", -R, 0.0, 2.6, 180, -20, "counterweight"),
            _s("RGB camera", "C1", -R, 0.0, 3.0, 180, -30, "rear (counterweight)"),
            _s("RGB camera", "C2", 1.0, blind * (W2 + O), 3.2, blind * 90, -30, f"{bs} side (opposite cab)"),
            _s("GNSS antenna", "G1", -R + 0.6, 1.5, 4.2, purpose="house top, RTK"),
            _s("GNSS antenna", "G2", -R + 0.6, -1.5, 4.2, purpose="house top, heading"),
        ]
    elif kit == "tracked":
        S += [
            _s("UWB anchor", "U1", L2 - 1.3, W2 - 0.5, 2.0, 45, purpose="radiator-guard front-left (not on blade)"),
            _s("UWB anchor", "U2", L2 - 1.3, -(W2 - 0.5), 2.0, -45, purpose="radiator-guard front-right"),
            _s("UWB anchor", "U3", 0.0, W2 - 0.2, 1.9, 90, purpose="left fender"),
            _s("UWB anchor", "U4", 0.0, -(W2 - 0.2), 1.9, -90, purpose="right fender"),
            _s("UWB anchor", "U5", -(L2 - 1.5), W2 - 0.6, 2.0, 135, purpose="rear-left (frame, not ripper)"),
            _s("UWB anchor", "U6", -(L2 - 1.5), -(W2 - 0.6), 2.0, -135, purpose="rear-right (frame, not ripper)"),
            _s("UWB anchor", "U7", -0.5, 0.0, H + 0.1, "omni", purpose="ROPS top"),
            _s("LF coil 125 kHz", "F1", L2 - 1.3, 0.0, 1.2, 0, purpose="front (behind blade)"),
            _s("LF coil 125 kHz", "F2", -(L2 - 1.0), 0.0, 1.2, 180, purpose="rear"),
            _s("LF coil 125 kHz", "F3", 0.0, W2, 1.0, 90, purpose="left"),
            _s("LF coil 125 kHz", "F4", 0.0, -W2, 1.0, -90, purpose="right"),
            _s("Radar 77 GHz", "R1", -(L2 - 1.0), 1.0, 1.2, -165, 0, "rear-left, toed-in"),
            _s("Radar 77 GHz", "R2", -(L2 - 1.0), -1.0, 1.2, 165, 0, "rear-right, toed-in"),
            _s("Radar 77 GHz", "R3", 0.0, W2 + O, 1.2, 90, 0, "left side (dozers pivot fast)"),
            _s("Radar 77 GHz", "R4", 0.0, -(W2 + O), 1.2, -90, 0, "right side"),
            _s("Radar 77 GHz", "R5", L2 - 1.5, 0.0, 2.3, 0, -10, "front, over blade"),
            _s("Thermal LWIR", "T1", -(L2 - 1.0), 0.0, 2.6, 180, -25, "rear"),
            _s("RGB camera", "C1", -(L2 - 1.0), 0.0, 2.8, 180, -30, "rear"),
            _s("RGB camera", "C2", L2 - 1.3, 0.0, 2.6, 0, -20, "front (blade raised)"),
            _s("GNSS antenna", "G1", -0.5, 1.0, H + 0.15, purpose="ROPS, RTK"),
            _s("GNSS antenna", "G2", -0.5, -1.0, H + 0.15, purpose="ROPS, heading"),
        ]
    elif kit == "artic":  # wheel loader / LHD; joint at x = joint_x_m
        j = m.get("joint_x_m", 0.0)
        ug = m["domain"] == "underground"
        S += [
            _s("UWB anchor", "U1", L2 - 1.6, W2 + O, 1.4, 45, purpose="front frame, at lift-arm pivot (not bucket)"),
            _s("UWB anchor", "U2", L2 - 1.6, -(W2 + O), 1.4, -45, purpose="front frame, at lift-arm pivot"),
            _s("UWB anchor", "U3", j, W2 + O, 1.3, 90, purpose="articulation pinch zone left"),
            _s("UWB anchor", "U4", j, -(W2 + O), 1.3, -90, purpose="articulation pinch zone right"),
            _s("UWB anchor", "U5", -(L2 + O), W2 - 0.2, 1.4, 135, purpose="rear frame corner"),
            _s("UWB anchor", "U6", -(L2 + O), -(W2 - 0.2), 1.4, -135, purpose="rear frame corner"),
            _s("UWB anchor", "U7", j - 1.0, 0.0, H + 0.05, "omni", purpose="canopy top"),
            _s("Articulation encoder", "E1", j, 0.0, 1.0, purpose="hull polygon follows steering"),
            _s("LF coil 125 kHz", "F1", L2 - 1.6, 0.0, 1.0, 0, purpose="front"),
            _s("LF coil 125 kHz", "F2", -(L2 + O), 0.0, 1.0, 180, purpose="rear"),
            _s("LF coil 125 kHz", "F3", j, W2 + O, 1.0, 90, purpose="pinch zone left"),
            _s("LF coil 125 kHz", "F4", j, -(W2 + O), 1.0, -90, purpose="pinch zone right"),
            _s("Radar 60/77 GHz", "R1", L2 - 1.8, 0.0, H - 0.2, 0, -5, "front, above bucket line"),
            _s("Radar 60/77 GHz", "R2", -(L2 + O), 0.0, 1.0, 180, 0, "rear" + (" (FOV 90 deg in tunnels)" if ug else "")),
            _s("Thermal LWIR", "T1", -(L2 + O), 0.0, 1.8 if ug else 2.4, 180, -20, "rear"),
            _s("RGB/IR camera", "C1", -(L2 + O), 0.0, 1.9 if ug else 2.6, 180, -25, "rear"),
            _s("RGB/IR camera", "C2", L2 - 1.8, 0.0, H, 0, -15, "front (bucket raised)"),
        ]
        if ug:
            S += [
                _s("Thermal LWIR", "T2", L2 - 1.8, 0.0, H - 0.1, 0, -10, "front"),
                _s("2-D LiDAR (Ex)", "L1", L2 - 0.6, 0.0, 1.6, 0, 0, "front: map-matching localisation"),
                _s("2-D LiDAR (Ex)", "L2", -(L2 - 0.6), 0.0, 1.6, 180, 0, "rear: map-matching localisation"),
            ]
        else:
            S += [_s("GNSS antenna", "G1", j - 1.0, 0.6, H + 0.15, purpose="RTK"),
                  _s("GNSS antenna", "G2", j - 1.0, -0.6, H + 0.15, purpose="heading (rear frame)")]
    elif kit == "bhl":
        S += [
            _s("UWB anchor", "U1", L2 - 0.9, W2 + O, 1.3, 45, purpose="front-left (behind loader arms)"),
            _s("UWB anchor", "U2", L2 - 0.9, -(W2 + O), 1.3, -45, purpose="front-right"),
            _s("UWB anchor", "U3", -(L2 - 0.6), W2 + O, 1.3, 135, purpose="rear-left (stabiliser leg, outside swing)"),
            _s("UWB anchor", "U4", -(L2 - 0.6), -(W2 + O), 1.3, -135, purpose="rear-right"),
            _s("UWB anchor", "U5", 0.0, 0.0, H + 0.05, "omni", purpose="cab roof"),
            _s("Seat-direction switch", "E1", 0.0, 0.0, 1.0, purpose="loader mode vs backhoe mode"),
            _s("LF coil 125 kHz", "F1", L2 - 0.9, 0.0, 1.0, 0, purpose="front"),
            _s("LF coil 125 kHz", "F2", -(L2 - 0.6), 0.0, 1.0, 180, purpose="rear / backhoe swing"),
            _s("Radar 24/60 GHz", "R1", L2 - 0.9, 0.0, 1.4, 0, 0, "front near-field"),
            _s("Radar 24/60 GHz", "R2", -(L2 - 0.6), 0.0, 1.4, 180, 0, "rear near-field"),
            _s("RGB camera", "C1", -(L2 - 0.6), 0.0, 2.4, 180, -30, "rear"),
            _s("GNSS antenna", "G1", 0.0, 0.0, H + 0.15, purpose="RTK (single, IMU heading)"),
        ]
    elif kit == "drill":
        S += [
            _s("UWB anchor", "U1", L2 + O, W2, 1.5, 45, purpose="front-left"),
            _s("UWB anchor", "U2", L2 + O, -W2, 1.5, -45, purpose="front-right"),
            _s("UWB anchor", "U3", -(L2 + O), W2, 1.5, 135, purpose="rear-left"),
            _s("UWB anchor", "U4", -(L2 + O), -W2, 1.5, -135, purpose="rear-right"),
            _s("UWB anchor", "U5", 0.0, 0.0, H + 0.1, "omni", purpose="deck top (mast down)"),
            _s("LF coil 125 kHz", "F1", L2 + O, 0.0, 1.0, 0, purpose="front / drill-string zone"),
            _s("LF coil 125 kHz", "F2", -(L2 + O), 0.0, 1.0, 180, purpose="rear"),
            _s("Radar 24/60 GHz", "R1", -(L2 + O), 0.0, 1.2, 180, 0, "rear (tramming)"),
            _s("RGB camera", "C1", -(L2 + O), 0.0, 2.6, 180, -30, "rear"),
            _s("Mast-angle switch", "E1", 0.0, 0.0, 2.0, purpose="mast up = overhead-line geofence check"),
            _s("GNSS antenna", "G1", 0.0, 1.0, H + 0.15, purpose="RTK (hole positioning reuse)"),
        ]
    elif kit == "lmv":
        S += [
            _s("Combo node (UWB+sub-GHz)", "N1", 0.2, 0.0, H + 0.1, "omni", purpose="magnetic roof mount, beacon + V2X"),
            _s("UWB anchor", "U1", L2 + O, 0.0, 0.9, 0, purpose="front bumper (optional)"),
            _s("UWB anchor", "U2", -(L2 + O), 0.0, 1.0, 180, purpose="rear bumper (optional)"),
            _s("Radar 24/60 GHz", "R1", -(L2 + O), 0.0, 0.6, 180, 0, "rear (optional)"),
            _s("Cab alert unit", "H1", 0.6, 0.0, 1.2, purpose="buzzer + LED + voice"),
        ]
        if m["domain"] == "surface":
            S += [_s("GNSS antenna", "G1", 0.2, 0.3, H + 0.12, purpose="in combo node"),
                  _s("Whip flag + strobe", "V1", -1.0, 0.6, H + 2.5, purpose="visibility to HEMM drivers")]
        else:
            S += [_s("Radar 60 GHz", "R2", L2 + O, 0.0, 0.8, 0, 0, "front")]
    elif kit == "rigid_ug":
        side = 1 if cab == "left" else -1
        S += [
            _s("UWB anchor", "U1", L2 + O, W2, 1.1, 45, purpose="front-left"),
            _s("UWB anchor", "U2", L2 + O, -W2, 1.1, -45, purpose="front-right"),
            _s("UWB anchor", "U3", -(L2 + O), W2, 1.1, 135, purpose="rear-left"),
            _s("UWB anchor", "U4", -(L2 + O), -W2, 1.1, -135, purpose="rear-right"),
            _s("UWB anchor", "U5", 0.0, side * (W2 + O), 1.2, side * 90, purpose="operator side"),
            _s("LF coil 125 kHz", "F1", L2 + O, 0.0, 0.8, 0, purpose="front"),
            _s("LF coil 125 kHz", "F2", -(L2 + O), 0.0, 0.8, 180, purpose="rear"),
            _s("LF coil 125 kHz", "F3", 0.0, W2 + O, 0.8, 90, purpose="left"),
            _s("LF coil 125 kHz", "F4", 0.0, -(W2 + O), 0.8, -90, purpose="right"),
            _s("Radar 60 GHz", "R1", L2 + O, 0.0, 0.9, 0, 0, "front, FOV 90 deg"),
            _s("Radar 60 GHz", "R2", -(L2 + O), 0.0, 0.9, 180, 0, "rear, FOV 90 deg"),
            _s("Thermal LWIR", "T1", L2 + O, 0.0, 1.3, 0, -10, "front"),
            _s("Thermal LWIR", "T2", -(L2 + O), 0.0, 1.3, 180, -10, "rear"),
        ]
    elif kit == "cm":
        S += [
            _s("UWB anchor", "U1", L2 - 0.8, W2 + O, 1.2, 60, purpose="cutter-drum end left"),
            _s("UWB anchor", "U2", L2 - 0.8, -(W2 + O), 1.2, -60, purpose="cutter-drum end right"),
            _s("UWB anchor", "U3", 0.0, W2 + O, 1.2, 90, purpose="mid-left (operator walkway)"),
            _s("UWB anchor", "U4", 0.0, -(W2 + O), 1.2, -90, purpose="mid-right"),
            _s("UWB anchor", "U5", -(L2 - 1.0), W2 - 0.6, 1.2, 135, purpose="tail-boom left"),
            _s("UWB anchor", "U6", -(L2 - 1.0), -(W2 - 0.6), 1.2, -135, purpose="tail-boom right"),
            _s("LF coil 125 kHz", "F1", L2 - 2.0, W2, 0.9, 60, purpose="front-left (cutter boom pivot)"),
            _s("LF coil 125 kHz", "F2", L2 - 2.0, -W2, 0.9, -60, purpose="front-right"),
            _s("LF coil 125 kHz", "F3", -0.5, W2, 0.9, 90, purpose="mid-left"),
            _s("LF coil 125 kHz", "F4", -0.5, -W2, 0.9, -90, purpose="mid-right"),
            _s("LF coil 125 kHz", "F5", -(L2 - 0.5), 0.0, 0.9, 180, purpose="tail conveyor"),
            _s("Function-inhibit I/O", "E1", 0.0, 0.0, 1.0, purpose="tram/swing/cutter/gathering-arm interlocks"),
        ]
    elif kit == "bidir":
        side = 1 if cab == "left" else -1
        S += [
            _s("UWB anchor", "U1", L2 + O, W2, 1.0, 45, purpose="end A left"),
            _s("UWB anchor", "U2", L2 + O, -W2, 1.0, -45, purpose="end A right"),
            _s("UWB anchor", "U3", -(L2 + O), W2, 1.0, 135, purpose="end B left"),
            _s("UWB anchor", "U4", -(L2 + O), -W2, 1.0, -135, purpose="end B right"),
            _s("UWB anchor", "U5", 0.0, W2 + O, 1.1, 90, purpose="mid-left"),
            _s("UWB anchor", "U6", 0.0, -(W2 + O), 1.1, -90, purpose="mid-right"),
            _s("LF coil 125 kHz", "F1", L2 + O, 0.0, 0.8, 0, purpose="end A"),
            _s("LF coil 125 kHz", "F2", -(L2 + O), 0.0, 0.8, 180, purpose="end B"),
            _s("LF coil 125 kHz", "F3", 0.0, side * (W2 + O), 0.8, side * 90, purpose="operator-cab side"),
            _s("LF coil 125 kHz", "F4", 0.0, -side * (W2 + O), 0.8, -side * 90, purpose="cable-reel side"),
            _s("Radar 60 GHz", "R1", L2 + O, 0.0, 0.9, 0, 0, "end A"),
            _s("Radar 60 GHz", "R2", -(L2 + O), 0.0, 0.9, 180, 0, "end B"),
            _s("IR camera", "C1", L2 + O, 0.0, 1.3, 0, -10, "end A"),
            _s("IR camera", "C2", -(L2 + O), 0.0, 1.3, 180, -10, "end B"),
        ]
    elif kit == "rail":
        T = m.get("train_length_m", 0.0)
        S += [
            _s("UWB anchor", "U1", L2 + O, 0.45, 1.3, 20, purpose="loco front-left"),
            _s("UWB anchor", "U2", L2 + O, -0.45, 1.3, -20, purpose="loco front-right"),
            _s("UWB anchor", "U3", -(L2 + O), 0.45, 1.3, 160, purpose="loco rear-left"),
            _s("UWB anchor", "U4", -(L2 + O), -0.45, 1.3, -160, purpose="loco rear-right"),
            _s("End-of-train unit", "N1", -(L2 + T), 0.0, 1.0, 180, purpose="last tub: UWB+sub-GHz, train length"),
            _s("LF coil 125 kHz", "F1", L2 + O, 0.0, 0.8, 0, purpose="front"),
            _s("LF coil 125 kHz", "F2", -(L2 + O), 0.0, 0.8, 180, purpose="rear"),
            _s("Radar 60 GHz", "R1", L2 + O, 0.0, 1.0, 0, 0, "front, FOV 30-60 deg along track"),
            _s("Radar 60 GHz", "R2", -(L2 + O), 0.0, 1.0, 180, 0, "rear"),
            _s("IR camera", "C1", L2 + O, 0.0, 1.4, 0, -5, "front"),
        ]
    else:
        raise ValueError(f"unknown kit {kit}")
    for row in S:
        for k in ("x", "y", "z"):
            row[k] = round(float(row[k]), 2)
    return S


# ---------------------------------------------------------------------------
# 3. UWB coverage / accuracy study
# ---------------------------------------------------------------------------
def los_mask(anchor: np.ndarray, P: np.ndarray, bmin: np.ndarray, bmax: np.ndarray) -> np.ndarray:
    """True where the segment anchor->P does NOT pass through the body box (slab test)."""
    D = P - anchor
    tmin = np.zeros(len(P))
    tmax = np.ones(len(P))
    for i in range(3):
        di = D[:, i]
        par = np.abs(di) < 1e-12
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (bmin[i] - anchor[i]) / di
            t2 = (bmax[i] - anchor[i]) / di
        lo, hi = np.minimum(t1, t2), np.maximum(t1, t2)
        inside = bmin[i] <= anchor[i] <= bmax[i]
        lo = np.where(par, -np.inf if inside else np.inf, lo)
        hi = np.where(par, np.inf if inside else -np.inf, hi)
        tmin = np.maximum(tmin, lo)
        tmax = np.minimum(tmax, hi)
    return ~(tmin <= tmax)


def coverage_study(m: dict, layouts: dict, sigma_r=0.10, r_max=60.0, extent=45.0, step=0.5):
    """2DRMS horizontal error (tag height known) for each anchor layout."""
    L2, W2 = m["length_m"] / 2, m["width_m"] / 2
    zt = m["tag_height_m"]
    xs = np.arange(-extent, extent + step / 2, step)
    X, Y = np.meshgrid(xs, xs)
    P = np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, zt)])
    outside = (np.abs(P[:, 0]) > L2) | (np.abs(P[:, 1]) > W2)
    dx = np.maximum(np.abs(P[:, 0]) - L2, 0)
    dy = np.maximum(np.abs(P[:, 1]) - W2, 0)
    dist_hull = np.hypot(dx, dy)
    bmin = np.array([-L2, -W2, 0.0])
    bmax = np.array([L2, W2, m["body_height_m"]])
    results = {}
    for name, anchors in layouts.items():
        A = np.array(anchors, dtype=float)
        vis = np.zeros((len(P), len(A)), bool)
        for k, a in enumerate(A):
            rng = np.linalg.norm(P - a, axis=1)
            vis[:, k] = los_mask(a, P, bmin, bmax) & (rng <= r_max)
        n = vis.sum(1)
        drms = np.full(len(P), np.nan)
        # n >= 2: with two anchors the mirror solution lies on the far side of the
        # anchor baseline, where the body blocks line of sight, so the fix is unique.
        for idx in np.where((n >= 2) & outside)[0]:
            a = A[vis[idx]]
            d3 = P[idx] - a
            r = np.linalg.norm(d3, axis=1)
            Hm = np.column_stack([d3[:, 0] / r, d3[:, 1] / r])
            try:
                cov = sigma_r ** 2 * np.linalg.inv(Hm.T @ Hm)
                drms[idx] = 2 * math.sqrt(max(np.trace(cov), 0.0))
            except np.linalg.LinAlgError:
                pass
        results[name] = dict(n=n, drms=drms)
    return dict(X=X, Y=Y, outside=outside, dist=dist_hull, results=results, L2=L2, W2=W2)


def coverage_table(cov, rings=((0, 5), (5, 15), (15, 40))):
    rows = []
    for name, r in cov["results"].items():
        for lo, hi in rings:
            sel = cov["outside"] & (cov["dist"] > lo) & (cov["dist"] <= hi)
            n = r["n"][sel]
            dr = r["drms"][sel]
            ok = np.isfinite(dr)
            rows.append([name, f"{lo}-{hi} m", f"{100 * np.mean(n >= 1):.0f}%",
                         f"{100 * np.mean(n >= 2):.0f}%", f"{100 * np.mean(n >= 3):.0f}%",
                         f"{np.median(dr[ok]):.2f}" if ok.any() else "-",
                         f"{np.percentile(dr[ok], 95):.2f}" if ok.any() else "-"])
    return rows


def plot_coverage(cov, layouts, path):
    bounds = [0, 0.2, 0.3, 0.5, 1.0, 50]
    cmap = ListedColormap(ORDINAL)
    norm = BoundaryNorm(bounds, cmap.N)
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 10.2), constrained_layout=True)
    X, Y = cov["X"], cov["Y"]
    for ax, (name, res) in zip(axes.ravel(), cov["results"].items()):
        n = res["n"].reshape(X.shape)
        dr = res["drms"].reshape(X.shape)
        inside = ~cov["outside"].reshape(X.shape)
        base = np.where(n == 0, 2, 1).astype(float)  # 1 = one anchor, 2 = none
        base[inside] = np.nan
        base[np.isfinite(dr)] = np.nan
        ax.pcolormesh(X, Y, np.ma.masked_invalid(base), cmap=ListedColormap([NEUTRAL_LIGHT, NEUTRAL_DARK]),
                      vmin=0.5, vmax=2.5, shading="nearest")
        ax.pcolormesh(X, Y, np.ma.masked_invalid(dr), cmap=cmap, norm=norm, shading="nearest")
        two = ((n == 2) & np.isfinite(dr)).astype(float)
        if two.any():
            ax.contourf(X, Y, two, levels=[0.5, 1.5], colors="none", hatches=["////"])
        ax.add_patch(Rectangle((-cov["L2"], -cov["W2"]), 2 * cov["L2"], 2 * cov["W2"],
                               facecolor=SURFACE, edgecolor=INK, linewidth=1.2, zorder=3))
        ax.annotate("", xy=(cov["L2"] - 0.6, 0), xytext=(-cov["L2"] + 1.2, 0),
                    arrowprops=dict(arrowstyle="->", color=INK2, lw=1.2), zorder=4)
        A = np.array(layouts[name])
        ax.plot(A[:, 0], A[:, 1], "o", ms=7, color=INK, mec=SURFACE, mew=2, zorder=5)
        ax.set_title(name, loc="left")
        ax.set_aspect("equal")
        ax.set_xlim(X.min(), X.max())
        ax.set_ylim(Y.min(), Y.max())
        ax.set_xlabel("x, forward (m)")
        ax.set_ylabel("y, left (m)")
        ax.grid(False)
        _despine(ax)
    handles = [Patch(facecolor=c, label=l) for c, l in zip(
        ORDINAL, ["<= 0.2 m", "0.2-0.3 m", "0.3-0.5 m", "0.5-1.0 m", "> 1.0 m"])]
    handles += [Patch(facecolor="none", edgecolor=MUTED, hatch="////", label="2-anchor fix (no redundancy)"),
                Patch(facecolor=NEUTRAL_LIGHT, label="1 anchor in LOS (range only)"),
                Patch(facecolor=NEUTRAL_DARK, label="no UWB LOS (LF / radar layer only)"),
                Line2D([], [], marker="o", ls="", color=INK, mec=SURFACE, mew=2, ms=7, label="UWB anchor")]
    fig.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.5, -0.01),
               title="Horizontal position error, 2DRMS (sigma_range = 0.10 m, tag at 1.7 m)",
               title_fontsize=10)
    fig.suptitle("UWB anchor layouts on a 100 t rear dump truck: where a helmet tag can be positioned",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 4. Event-triggered communication rate (Wu, Jia, Johansson, Shi 2013)
# ---------------------------------------------------------------------------
def q_func(x):
    return 0.5 * math.erfc(x / math.sqrt(2))


def event_rate(delta, m_dims):
    """Average transmission probability per step: 1 - (1 - 2Q(delta))^m."""
    return 1 - (1 - 2 * q_func(delta)) ** m_dims


# ---------------------------------------------------------------------------
# 8. LoRa time on air (Semtech AN1200.13)
# ---------------------------------------------------------------------------
def lora_toa_ms(payload_bytes, sf, bw_hz=125e3, cr=1, preamble=8, explicit_header=True, crc=True):
    tsym = (2 ** sf) / bw_hz * 1000
    de = 1 if tsym > 16 else 0
    ih = 0 if explicit_header else 1
    num = 8 * payload_bytes - 4 * sf + 28 + 16 * int(crc) - 20 * ih
    n_payload = 8 + max(math.ceil(num / (4 * (sf - 2 * de))) * (cr + 4), 0)
    return (preamble + 4.25) * tsym + n_payload * tsym


def fsk_toa_ms(payload_bytes, bitrate=50e3, overhead_bytes=11):
    return (payload_bytes + overhead_bytes) * 8 / bitrate * 1000


# ---------------------------------------------------------------------------
# 5. Wearable power budget
# ---------------------------------------------------------------------------
DEV = dict(  # indicative currents, mA, at 3.3 V
    uwb_tx=35.0, uwb_rx=65.0, uwb_wake=8.0,
    lora_tx=40.0, lora_rx=5.0,
    gyro=0.45, accel_lp=0.01,
    baseline_always=0.058,  # MCU sleep 2uA + AS3933 6uA + high-g 2uA + baro 3uA + CO AFE 15uA + ULF RX 30uA
    mcu_active_avg=0.05,
    vib=70.0,
)
UWB_BLINK_UC = DEV["uwb_tx"] * 0.15 + DEV["uwb_rx"] * 0.30 + DEV["uwb_wake"] * 0.5      # uC per blink
UWB_FIX_UC = DEV["uwb_tx"] * 0.45 + DEV["uwb_rx"] * (4 * 0.25 + 0.3) + DEV["uwb_wake"] * 0.5  # 1-to-4 DS-TWR


def packet_uc(payload=16, sf=7):
    toa = lora_toa_ms(payload, sf)
    return DEV["lora_tx"] * toa + 2 * 8.0 * DEV["lora_rx"]  # + two short RX windows


SHIFT_H = 12.0
MIX = dict(far=0.70, aware=0.22, warning=0.06, danger=0.02, walking=0.35, traffic=0.60)
RATE = dict(aware=1.0, warning=10.0, danger=20.0)  # ranging fixes per second


def tag_budget_event():
    blink_hz = MIX["traffic"] * 2.0 + (1 - MIX["traffic"]) * 0.5
    hb = packet_uc() / 60.0 / 1000
    ev = event_rate(2.0, 2) * MIX["far"] * MIX["walking"] * packet_uc() / 1000
    cad = 1.5 * DEV["lora_rx"] / 1000
    return {
        "Sensing + MCU baseline": DEV["baseline_always"] + DEV["mcu_active_avg"],
        "IMU (accel + gyro)": DEV["accel_lp"] + DEV["gyro"] * MIX["walking"],
        "UWB discovery blinks": UWB_BLINK_UC * blink_hz * MIX["far"] / 1000,
        "UWB ranging sessions": UWB_FIX_UC * sum(MIX[k] * RATE[k] for k in RATE) / 1000,
        "Sub-GHz telemetry + listening": hb + ev + cad,
        "LF rescue locator": 0.0,
    }


def tag_budget_polling():
    return {
        "Sensing + MCU baseline": DEV["baseline_always"] + DEV["mcu_active_avg"],
        "IMU (accel + gyro)": DEV["accel_lp"] + DEV["gyro"],
        "UWB discovery blinks": 0.0,
        "UWB ranging sessions": UWB_FIX_UC * 10.0 / 1000,
        "Sub-GHz telemetry + listening": packet_uc() / 5.0 / 1000 + 10 * DEV["lora_rx"] / 1000,
        "LF rescue locator": 0.0,
    }


def tag_budget_backup():
    beacon = (DEV["lora_tx"] * lora_toa_ms(16, 9) + 2 * 20 * DEV["lora_rx"]) / 30.0 / 1000
    return {
        "Sensing + MCU baseline": DEV["baseline_always"] + 0.02,
        "IMU (accel + gyro)": DEV["accel_lp"],
        "UWB discovery blinks": UWB_BLINK_UC * 0.2 / 1000,
        "UWB ranging sessions": 0.0,
        "Sub-GHz telemetry + listening": beacon,
        "LF rescue locator": 30.0 * 10 / 2000,  # 10 ms pulse @ 30 mA every 2 s
    }


def alerts_ma():
    return DEV["vib"] * (MIX["warning"] * 0.10 + MIX["danger"] * 0.50)


def plot_power(budgets: dict, path):
    comps = list(next(iter(budgets.values())).keys())
    names = list(budgets.keys())
    fig, ax = plt.subplots(figsize=(10, 3.4), constrained_layout=True)
    y = np.arange(len(names))[::-1]
    left = np.zeros(len(names))
    for ci, comp in enumerate(comps):
        vals = np.array([budgets[n][comp] * SHIFT_H for n in names])
        ax.barh(y, vals, left=left, height=0.42, color=SERIES[ci], edgecolor=SURFACE, linewidth=2,
                label=comp)
        left += vals
    for yi, tot in zip(y, left):
        ax.text(tot + 0.4, yi, f"{tot:.1f} mAh", va="center", color=INK2, fontsize=10)
    ax.set_yticks(y, names)
    ax.tick_params(axis="y", colors=INK2, length=0)
    ax.set_xlabel("Charge per 12 h shift (mAh), alarm actuators excluded")
    ax.set_xlim(0, left.max() * 1.18)
    ax.grid(axis="y", visible=False)
    _despine(ax)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, fontsize=9)
    ax.set_title("Wearable radio/sensing energy: event-driven design vs fixed-rate polling", loc="left")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 6. Infrastructure node standby
# ---------------------------------------------------------------------------
def node_standby():
    mesh_radio_w = 0.05 * 0.5 + 0.05 * 0.05 + 0.90 * 0.01  # MSHA 5/5/90, 0.5 W TX
    with_fibre = 1.0 + 0.06 + mesh_radio_w + 0.05 + 0.03    # SFP+switch, UWB RX 25%, radio, MCU, sensors
    mesh_only = 0.06 + mesh_radio_w + 0.05 + 0.03
    normal = 0.25 + 0.6 + 1.5 + 0.5 + 0.05 + 0.2
    return normal, with_fibre, mesh_only


# ---------------------------------------------------------------------------
# 7. Through-the-earth
# ---------------------------------------------------------------------------
MU0 = 4e-7 * math.pi


def tte_fopt(rho, depth):
    """Frequency maximising  f * exp(-d/delta)  (Faraday pickup x skin attenuation): d = 2 delta."""
    return 4 * rho / (math.pi * MU0 * depth ** 2)


def skin_depth(rho, f):
    return math.sqrt(2 * rho / (2 * math.pi * f * MU0))


def nearest_interharmonic(f, mains=50.0):
    return (math.floor(f / mains) + 0.5) * mains


TWIN_BITS = dict(person=9 + 13 + 8 + 2, header=4 + 8 + 16 + 16, mic=32)
NAIVE_PERSON_BITS = 16 + 3 * 32 + 8  # id + float32 xyz + status


def tte_messages():
    h = TWIN_BITS["header"] + TWIN_BITS["mic"]
    return [
        ("Full roll-call, 200 persons (twin-referenced)", 200 * TWIN_BITS["person"] + h),
        ("Full roll-call, 200 persons (raw float xyz)", 200 * NAIVE_PERSON_BITS + h),
        ("Delta roll-call: 15 persons changed vs twin", 15 * TWIN_BITS["person"] + h),
        ("Refuge status: count, injured, O2/CO", 8 + 8 + 4 + 16 + h),
        ("Downlink: evacuate via route code", 8 + h),
    ]


def plot_tte(path):
    d = np.linspace(50, 800, 300)
    fig, ax = plt.subplots(figsize=(8.5, 4.6), constrained_layout=True)
    ax.axhspan(72, 4000, color=GRID, alpha=0.6, lw=0)
    ax.text(450, 82, "band used by fielded TTE systems: 72 Hz - 4 kHz (NIOSH)", color=MUTED, fontsize=9)
    for i, rho in enumerate((10, 100, 1000)):
        f = [tte_fopt(rho, x) for x in d]
        ax.plot(d, f, color=SERIES[i], label=f"rho = {rho} ohm.m")
        ax.text(d[-1] + 8, f[-1], f"{rho} ohm.m", color=INK2, va="center", fontsize=9)
    ax.set_yscale("log")
    ax.set_xlim(50, 900)
    ax.set_xlabel("Depth of cover d (m)")
    ax.set_ylabel("Best carrier frequency (Hz)")
    ax.set_title("Through-the-earth carrier that maximises received voltage (d = 2 x skin depth)", loc="left")
    ax.legend(loc="upper right")
    _despine(ax)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_zones(ms, d, path):
    sel = [("RDT100", "100 t dump truck, loaded, 1:16 downgrade"),
           ("LMV", "Light motor vehicle, gravel"),
           ("LHD", "Underground LHD, 1:10 grade")]
    v = np.linspace(0, 40, 161)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True, constrained_layout=True)
    for ax, (k, title) in zip(axes, ((0, "Stop zone (must be clear)"), (1, "Warning zone (alert issued)"))):
        for i, (mid, label) in enumerate(sel):
            m = ms[mid]
            vmax = 40 if mid != "LHD" else 20
            vv = v[v <= vmax]
            yy = [zones(m, d, x)[k] for x in vv]
            ax.plot(vv, yy, color=SERIES[i], label=label)
            ax.text(vv[-1] + 0.5, yy[-1], f"{yy[-1]:.0f} m", color=INK2, va="center", fontsize=9)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Machine speed (km/h)")
        ax.set_xlim(0, 45)
        _despine(ax)
    axes[0].set_ylabel("Distance from machine hull (m)")
    axes[1].legend(loc="upper left", fontsize=9)
    fig.suptitle("Speed-adaptive zones: t_sys 0.3 s + reaction 1.5 s + braking + walking pedestrian + 2-sigma",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_event_rate(path):
    deltas = np.linspace(0, 4, 161)
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    for i, (mdim, lab) in enumerate(((2, "2-D position innovation"), (4, "position + velocity (4-D)"))):
        g = [100 * event_rate(x, mdim) for x in deltas]
        ax.plot(deltas, g, color=SERIES[i], label=lab)
    for x, off in ((1.5, (-120, -10)), (2.0, (-120, -2)), (3.0, (4, 30))):
        g = 100 * event_rate(x, 2)
        ax.plot([x], [g], "o", ms=8, color=SERIES[0], mec=SURFACE, mew=2, zorder=5)
        ax.annotate(f"delta={x}: {g:.1f}%", (x, g), xytext=off, textcoords="offset points",
                    color=INK2, fontsize=9,
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, shrinkA=2, shrinkB=5))
    ax.set_xlabel("Event threshold delta (normalised innovation, in sigma)")
    ax.set_ylabel("Steps that trigger a transmission (%)")
    ax.set_title("Send-on-innovation: gamma = 1 - (1 - 2Q(delta))^m   (Wu et al., IEEE TAC 2013)", loc="left")
    ax.legend(loc="upper right")
    ax.set_ylim(0, 102)
    _despine(ax)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profiles", default=str(HERE / "machine_profiles.toml"))
    ap.add_argument("--figdir", default=str(DOCS / "figures"))
    ap.add_argument("--out", default=str(HERE / "generated_tables.md"))
    args = ap.parse_args()
    figdir = pathlib.Path(args.figdir)
    figdir.mkdir(parents=True, exist_ok=True)
    cfg = tomllib.loads(pathlib.Path(args.profiles).read_text(encoding="utf-8"))
    d = cfg["defaults"]
    ms = {m["id"]: m for m in cfg["machine"]}
    out = ["# Generated design tables", "",
           "Produced by `docs/tools/design_calcs.py` from `machine_profiles.toml`. Do not edit by hand.", ""]

    # 1. zones
    rows = []
    for m in ms.values():
        s0 = zones(m, d, 0.0)[0]
        sf, wf, af = zones(m, d, m["v_fwd_kmh"])
        sr, wr, ar = zones(m, d, m["v_rev_kmh"])
        rows.append([m["id"], m["name"], m["v_fwd_kmh"], f"{sf:.1f}", f"{wf:.1f}", f"{af:.1f}",
                     m["v_rev_kmh"], f"{sr:.1f}", f"{wr:.1f}", f"{s0:.1f}"])
    out += ["## 1. Speed-adaptive zones (distance from hull, m)", "",
            md_table(["ID", "Machine", "v fwd km/h", "Stop", "Warn", "Aware", "v rev km/h",
                      "Stop (rev)", "Warn (rev)", "Start-inhibit (v=0)"], rows), ""]
    hx = ms["HEX"]
    dz, wz, arc = swing_zones(hx, d)
    out += [f"Swing machine HEX: danger radius {dz:.1f} m, warning radius {wz:.1f} m from swing centre; "
            f"counterweight travels {arc:.1f} m of arc after an alarm before it stops.", ""]
    bh = ms["BHL"]
    out += [f"Backhoe work mode (BHL): exclusion radius = reach {bh['backhoe_reach_m']} m + "
            f"{d['k_sigma'] * d['sigma_pos_m'] + d['buffer_m']:.1f} m = "
            f"{bh['backhoe_reach_m'] + d['k_sigma'] * d['sigma_pos_m'] + d['buffer_m']:.1f} m from the swing post.", ""]

    # 2. placement
    out += ["## 2. Sensor coordinates per machine (body frame: x fwd, y left, z up; m, deg)", ""]
    for m in ms.values():
        S = placement(m)
        out += [f"### {m['id']} - {m['name']}  (L {m['length_m']} x W {m['width_m']} x H {m['height_m']} m)", "",
                md_table(["Sensor", "ID", "x", "y", "z", "yaw", "pitch", "Purpose"],
                         [[s["sensor"], s["id"], s["x"], s["y"], s["z"], s["yaw"], s["pitch"], s["purpose"]]
                          for s in S]), ""]

    # 3. coverage
    rdt = ms["RDT100"]
    P = {s["id"]: (s["x"], s["y"], s["z"]) for s in placement(rdt) if s["sensor"] == "UWB anchor"}
    layouts = {
        "A - 2 rear anchors": [P["U5"], P["U6"]],
        "B - 4 corners": [P["U1"], P["U2"], P["U5"], P["U6"]],
        "C - 4 corners + 2 mid-sides": [P["U1"], P["U2"], P["U3"], P["U4"], P["U5"], P["U6"]],
        "D - C + canopy-top anchor (recommended)": [P[k] for k in ("U1", "U2", "U3", "U4", "U5", "U6", "U7")],
    }
    cov = coverage_study(rdt, layouts)
    plot_coverage(cov, layouts, figdir / "fig_uwb_coverage_rdt100.png")
    hdr = ["Layout", "Ring from hull", ">=1 anchor (range)", ">=2 (position)", ">=3 (redundant)",
           "Median 2DRMS (m)", "p95 2DRMS (m)"]
    out += ["## 3. UWB layout study, RDT100 (helmet tag at 1.7 m, sigma_r 0.10 m, LOS only, 60 m max)", "",
            md_table(hdr, coverage_table(cov)), ""]

    # 4. event rate
    rows = [[x, f"{100 * event_rate(x, 2):.2f}%", f"{100 * event_rate(x, 4):.2f}%"]
            for x in (1.0, 1.5, 2.0, 2.5, 3.0)]
    out += ["## 4. Event-triggered transmission rate vs threshold", "",
            md_table(["delta (sigma)", "m = 2 (position)", "m = 4 (pos + vel)"], rows), ""]
    plot_event_rate(figdir / "fig_event_rate.png")

    # 5. power
    budgets = {"Event-driven (this design)": tag_budget_event(),
               "Fixed-rate polling (10 Hz UWB, 5 s reports)": tag_budget_polling(),
               "Backup cell, emergency beacon mode": tag_budget_backup()}
    plot_power(budgets, figdir / "fig_tag_power_budget.png")
    rows = []
    for name, b in budgets.items():
        tot = sum(b.values())
        rows.append([name] + [f"{v * 1000:.0f}" for v in b.values()] + [f"{tot * 1000:.0f}",
                                                                          f"{tot * SHIFT_H:.1f}"])
    out += ["## 5. Wearable average current (uA) by subsystem", "",
            md_table(["Mode"] + list(next(iter(budgets.values())).keys()) + ["Total uA", "mAh / 12 h"], rows), "",
            f"Per UWB discovery blink: {UWB_BLINK_UC:.1f} uC. Per 1-to-4 DS-TWR fix: {UWB_FIX_UC:.1f} uC. "
            f"Per 16-byte LoRa SF7 packet incl. RX windows: {packet_uc():.0f} uC "
            f"(time on air {lora_toa_ms(16, 7):.1f} ms; SF9 {lora_toa_ms(16, 9):.1f} ms; "
            f"GFSK 50 kb/s {fsk_toa_ms(16):.1f} ms).", "",
            f"Alarm actuators (vibration 70 mA, 10% duty in WARNING, 50% in DANGER) average "
            f"{alerts_ma():.2f} mA = {alerts_ma() * SHIFT_H:.1f} mAh per shift in both designs.", ""]
    bk = sum(budgets["Backup cell, emergency beacon mode"].values())
    out += [f"Backup cell 600 mAh, derated 50% for temperature and ageing: {0.5 * 600 / bk:.0f} h "
            f"of emergency beaconing (requirement >= 96 h).", ""]

    # 6. node standby
    normal, wf, mo = node_standby()
    out += ["## 6. Infrastructure node power", "",
            md_table(["Case", "Average W", "Wh for 24 h", "Wh for 96 h"],
                     [["Normal operation (line power)", f"{normal:.2f}", f"{normal * 24:.0f}", f"{normal * 96:.0f}"],
                      ["Standby, fibre alive (5/5/90 radio)", f"{wf:.2f}", f"{wf * 24:.0f}", f"{wf * 96:.0f}"],
                      ["Standby, fibre cut, mesh only", f"{mo:.2f}", f"{mo * 24:.1f}", f"{mo * 96:.1f}"]]), ""]

    # 7. TTE
    rows = []
    for depth in (100, 200, 300, 400, 600):
        r = [depth]
        for rho in (10, 100, 1000):
            f = tte_fopt(rho, depth)
            r.append(f"{f:,.0f} Hz (delta {skin_depth(rho, f):.0f} m)")
        r.append(f"{nearest_interharmonic(tte_fopt(100, depth)):,.0f} Hz")
        rows.append(r)
    out += ["## 7. Through-the-earth carrier", "",
            md_table(["Depth (m)", "rho 10 ohm.m", "rho 100 ohm.m", "rho 1000 ohm.m",
                      "Inter-harmonic carrier (rho 100)"], rows), ""]
    rows = []
    for name, bits in tte_messages():
        rows.append([name, bits, f"{bits / 10:.0f} s", f"{bits / 50:.1f} s", f"{20 * bits / 10:.0f} J"])
    out += [md_table(["Message", "Bits", "Time @ 10 b/s net", "Time @ 50 b/s net", "Uplink energy @ 20 W, 10 b/s"],
                     rows), ""]
    plot_tte(figdir / "fig_tte_frequency.png")

    plot_zones(ms, d, figdir / "fig_zones_vs_speed.png")
    pathlib.Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
