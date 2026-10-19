#!/usr/bin/env python3
"""Run every market-sensor simulation and write the results.

    python run_all.py              # full run (a few minutes on a multi-core PC)
    python run_all.py --quick      # one fifth of the runs, for a smoke test
    python run_all.py --runs 600   # V2P Monte Carlo runs per scenario

Writes sim/results.md (tables), sim/results.json (raw aggregates) and docs/figures/fig_sim_*.png.
Every number comes from components.toml (datasheets + named assumptions) and the Machine Safety
Profiles in docs/tools/machine_profiles.toml. Edit those inputs, not the outputs.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from common import (HERE, ROOT, SERIES, INK, INK2, MUTED, AXIS, dc, despine, fmt, fspl_db, load_components,
                    load_profiles, md_table, pct)
import attendance as att
import v2p
import v2v
from sensors import Ars408, FmcwRadar, LfShell, SubGhz, UhfRfid, UwbRanging

import matplotlib.pyplot as plt  # noqa: E402  (backend already set by design_calcs)

FIG = ROOT / "docs" / "figures"
_W = _COMP = _MS = None


# ---------------------------------------------------------------------------------------------
# Worker processes
# ---------------------------------------------------------------------------------------------
def _init():
    global _W, _COMP, _MS
    _COMP = load_components()
    d, _MS = load_profiles()
    _W = v2p.World(_COMP, d, _MS["RDT100"])


def _v2p_job(args):
    key, policy, seeds = args
    return [(key, policy, v2p.simulate_run(_W, key, int(s), policy)) for s in seeds]


def _si_job(args):
    n, seed = args
    return v2p.simulate_start_inhibit(_W, n, seed)


def _corner_job(args):
    key, conflict, seeds = args
    return [(key, conflict, v2v.simulate_corner(_COMP, _MS, v2v.V1_CONFIGS[key], int(s), conflict)) for s in seeds]


def _pass_job(args):
    mode, seeds = args
    return [(mode, v2v.simulate_passing(_COMP, _MS, mode, int(s))) for s in seeds]


def _load_job(args):
    phy, n, rate, seed = args
    return (phy, n, rate, v2v.channel_load(_COMP, phy, n, rate, seed))


def _att_job(args):
    cfg, gates, seed = args
    return att.simulate_shift(_COMP, cfg, gates, seed)


def _chunks(seq, k):
    return [seq[i:i + k] for i in range(0, len(seq), k)]


# ---------------------------------------------------------------------------------------------
# Sensor reach straight from the datasheet models
# ---------------------------------------------------------------------------------------------
def _phi(x):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(x) / math.sqrt(2.0)))


def sensor_reach(comp, w: v2p.World):
    a = comp["assumptions"]
    out = {}
    d = np.linspace(1.0, 160.0, 320)
    out["uwb"] = dict(d=d, los=UwbRanging(comp).p_exchange_vs_distance(d, 0.0),
                      body=UwbRanging(comp).p_exchange_vs_distance(d, 1.0),
                      veh=UwbRanging(comp, vehicle_limit=True).p_exchange_vs_distance(d, 0.0))
    r = np.linspace(0.5, 10.0, 200)
    lf = LfShell(comp, [dict(pos=(0.0, 0.0, 0.0), axis=(1.0, 0.0, 0.0), r_on=a["lf_r_on_m"]["rear"])])
    on = np.array([lf.field_db(np.array([x, 0.0, 0.0]))[0] for x in r])
    side = np.array([lf.field_db(np.array([0.0, x, 0.0]))[0] for x in r])
    out["lf"] = dict(r=r, on=_phi(on / lf.sigma), side=_phi(side / lf.sigma))
    rr = np.linspace(1.0, 90.0, 300)
    awr = FmcwRadar(comp["radar_awr1843aop"], a)
    iwr = FmcwRadar(comp["radar_iwr6843aop"], a)
    ars = Ars408(comp["radar_ars408"], a)
    rcs = a["person_rcs_dbsm"]
    out["radar"] = dict(r=rr, awr_stand=awr.pd(rr, rcs), awr_lying=awr.pd(rr, rcs + a["rcs_posture_db"]["lying"]),
                        iwr_stand=iwr.pd(rr, rcs), ars_stand=ars.pd(rr, rcs),
                        awr_rmax=awr.r_max, awr_res=awr.range_res)
    dd = np.linspace(0.5, 25.0, 200)
    rf = UhfRfid(comp, comp["rfid_reader"]["tx_max_dbm_poe"])
    sig = a["rfid_shadow_db"]
    face = _phi((rf.p_tag(dd, 0.0, 0.0) - rf.sens_tag) / sig)
    away = _phi((rf.p_tag(dd, 0.0, 1.0) - rf.sens_tag) / sig)
    out["rfid"] = dict(d=dd, face=face, away=away, eirp=rf.eirp)

    def reach(x, p, q):
        ok = np.asarray(p) >= q
        if not ok.any():
            return 0.0
        last = np.flatnonzero(ok)[-1]
        return float(x[last])

    rows = [
        ["UWB DS-TWR exchange (DWM3000, CH5 6.8 Mb/s, 89 dB link budget)", "line of sight",
         fmt(reach(d, out["uwb"]["los"], 0.9), 0), fmt(reach(d, out["uwb"]["los"], 0.5), 0)],
        ["", "helmet antenna shadowed by the body (-12 dB)", fmt(reach(d, out["uwb"]["body"], 0.9), 0),
         fmt(reach(d, out["uwb"]["body"], 0.5), 0)],
        ["", "anchors at the vehicle limit -53.3 dBm/MHz", fmt(reach(d, out["uwb"]["veh"], 0.9), 0),
         fmt(reach(d, out["uwb"]["veh"], 0.5), 0)],
        ["LF wake-up (AS3932, 100 uVrms; rear coil set to 6 m)", "on the coil axis",
         fmt(reach(r, out["lf"]["on"], 0.9), 1), fmt(reach(r, out["lf"]["on"], 0.5), 1)],
        ["", "broadside to the coil", fmt(reach(r, out["lf"]["side"], 0.9), 1), fmt(reach(r, out["lf"]["side"], 0.5), 1)],
        ["Radar per-frame detection (AWR1843AOP, EIRP 16 dBm, EINF 10 dB)", "standing person, -8 dBsm",
         fmt(reach(rr, out["radar"]["awr_stand"], 0.9), 0), fmt(reach(rr, out["radar"]["awr_stand"], 0.5), 0)],
        ["", "lying person, -14 dBsm", fmt(reach(rr, out["radar"]["awr_lying"], 0.9), 0),
         fmt(reach(rr, out["radar"]["awr_lying"], 0.5), 0)],
        ["Radar per-frame detection (IWR6843AOP, EIRP 16 dBm, EINF 9 dB)", "standing person, -8 dBsm",
         fmt(reach(rr, out["radar"]["iwr_stand"], 0.9), 0), fmt(reach(rr, out["radar"]["iwr_stand"], 0.5), 0)],
        ["Radar (ARS 408-21 envelope scaled by RCS^1/4)", "standing person, boresight",
         fmt(reach(rr, out["radar"]["ars_stand"], 0.9), 0), fmt(reach(rr, out["radar"]["ars_stand"], 0.5), 0)],
        ["UHF RFID read (R700 30 dBm + 6 dBic, M730 -24 dBm)", "tag facing the reader",
         fmt(reach(dd, face, 0.9), 1), fmt(reach(dd, face, 0.5), 1)],
        ["", "tag behind the head/body (-10 dB)", fmt(reach(dd, away, 0.9), 1), fmt(reach(dd, away, 0.5), 1)],
    ]
    return out, rows


def power_crosscheck(comp):
    """Re-run the docs/05 wearable budget with the datasheet currents instead of the indicative ones."""
    old = dict(dc.DEV)
    blink_old, fix_old = dc.UWB_BLINK_UC, dc.UWB_FIX_UC
    ev_old = sum(dc.tag_budget_event().values()) * dc.SHIFT_H
    po_old = sum(dc.tag_budget_polling().values()) * dc.SHIFT_H
    u, s = comp["uwb"], comp["subghz"]
    dc.DEV.update(uwb_tx=u["i_tx_ma"], uwb_rx=u["i_rx_ma"], uwb_wake=u["i_init_ma"], lora_tx=s["i_tx_14dbm_ma"],
                  lora_rx=s["i_rx_ma"])
    dc.UWB_BLINK_UC = dc.DEV["uwb_tx"] * 0.15 + dc.DEV["uwb_rx"] * 0.30 + dc.DEV["uwb_wake"] * 0.5
    dc.UWB_FIX_UC = dc.DEV["uwb_tx"] * 0.45 + dc.DEV["uwb_rx"] * (4 * 0.25 + 0.3) + dc.DEV["uwb_wake"] * 0.5
    ev_new = sum(dc.tag_budget_event().values()) * dc.SHIFT_H
    po_new = sum(dc.tag_budget_polling().values()) * dc.SHIFT_H
    dc.DEV.clear()
    dc.DEV.update(old)
    dc.UWB_BLINK_UC, dc.UWB_FIX_UC = blink_old, fix_old
    rows = [["UWB TX current", f"{old['uwb_tx']:.0f} mA", f"{u['i_tx_ma']:.0f} mA (D1, CH5)"],
            ["UWB RX current", f"{old['uwb_rx']:.0f} mA", f"{u['i_rx_ma']:.0f} mA (D1, CH5)"],
            ["UWB wake/INIT current", f"{old['uwb_wake']:.0f} mA", f"{u['i_init_ma']:.0f} mA (D1)"],
            ["865 MHz TX current at +14 dBm", f"{old['lora_tx']:.0f} mA", f"{s['i_tx_14dbm_ma']:.0f} mA (D8)"],
            ["865 MHz RX current", f"{old['lora_rx']:.1f} mA", f"{s['i_rx_ma']:.1f} mA (D8)"],
            ["Event-driven budget per 12 h shift", f"{ev_old:.1f} mAh", f"{ev_new:.1f} mAh"],
            ["Fixed-rate polling per 12 h shift", f"{po_old:.1f} mAh", f"{po_new:.1f} mAh"]]
    return rows, dict(event_old=ev_old, event_new=ev_new, poll_old=po_old, poll_new=po_new)


def coexistence(comp):
    """A UHF RFID reader and the 865 MHz V2V radio share India's 865-867 MHz band."""
    a, s, r = comp["assumptions"], comp["subghz"], comp["rfid_reader"]
    eirp = r["tx_max_dbm_poe"] + a["rfid_ant_gain_dbic"] - a["rfid_cable_db"]
    g_rx = a["subghz_ant_gain_dbi"] - a["subghz_cable_db"]
    tolerable = s["sens_lora_sf7_bw125"] + 3.0 + s["blocking_1mhz_db"]  # D8: blocking referred to sens + 3 dB
    rows = []
    for d in (3.0, 10.0, 30.0, 100.0):
        p = eirp + g_rx - float(fspl_db(d, s["f_mhz"] * 1e6))
        rows.append([f"{d:.0f} m", f"{p:.1f} dBm", f"{tolerable:.0f} dBm", "desensitised" if p > tolerable else "ok"])
    need = eirp + g_rx - tolerable
    d_free = 10 ** ((need - float(fspl_db(1.0, s["f_mhz"] * 1e6))) / 20.0)
    return rows, dict(eirp=eirp, tolerable=tolerable, d_free=d_free)


# ---------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------
C_UWB, C_AWR, C_ARS, C_RFID = SERIES[0], SERIES[1], SERIES[2], SERIES[3]


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, loc="left")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    despine(ax)


def _end_label(ax, x, y, text):
    ax.annotate(text, (x[-1], y[-1]), xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5,
                color=INK2)


def fig_reach(R, path):
    fig, axs = plt.subplots(2, 2, figsize=(11, 7.4), constrained_layout=True)
    ax = axs[0, 0]
    u = R["uwb"]
    ax.plot(u["d"], 100 * u["los"], color=SERIES[0], label="line of sight")
    ax.plot(u["d"], 100 * u["body"], color=SERIES[1], label="body shadow or vehicle limit (-12 dB)")
    _style(ax, "UWB DS-TWR exchange - Qorvo DWM3000", "distance (m)", "exchanges completed (%)")
    ax.set_ylim(0, 102)
    ax.legend(loc="lower left", bbox_to_anchor=(0.33, 0.03))
    ax = axs[0, 1]
    lf = R["lf"]
    ax.plot(lf["r"], 100 * lf["on"], color=SERIES[0], label="on the coil axis")
    ax.plot(lf["r"], 100 * lf["side"], color=SERIES[1], label="broadside")
    _style(ax, "LF wake-up - ams AS3932, coil set to 6 m", "distance from coil (m)", "wake-ups (%)")
    ax.set_ylim(0, 102)
    ax.legend(loc="lower left")
    ax = axs[1, 0]
    rd = R["radar"]
    ax.plot(rd["r"], 100 * rd["awr_stand"], color=SERIES[0], label="AWR1843AOP, standing (-8 dBsm)")
    ax.plot(rd["r"], 100 * rd["awr_lying"], color=SERIES[1], label="AWR1843AOP, lying (-14 dBsm)")
    ax.plot(rd["r"], 100 * rd["ars_stand"], color=SERIES[2], label="ARS 408-21, standing")
    _style(ax, "Radar detection per frame - person", "range (m)", "frames with a detection (%)")
    ax.set_ylim(0, 102)
    ax.legend(loc="lower left", bbox_to_anchor=(0.30, 0.24))
    ax = axs[1, 1]
    rf = R["rfid"]
    ax.plot(rf["d"], 100 * rf["face"], color=SERIES[0], label="tag facing the reader")
    ax.plot(rf["d"], 100 * rf["away"], color=SERIES[1], label="tag behind the head")
    _style(ax, "UHF RFID read - Impinj R700 (30 dBm) + M730 tag", "distance (m)", "inventory rounds read (%)")
    ax.set_ylim(0, 102)
    ax.legend(loc="upper right")
    fig.suptitle("Sensor reach computed from the datasheets", x=0.01, ha="left", fontsize=12, fontweight="bold",
                 color=INK)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


SHORT = {"A": "A  RFID R700 + M730", "B": "B  UWB DWM3000", "C": "C  UWB + LF AS3932", "D": "D  C + AWR1843AOP radar",
         "E": "E  C + ARS 408-21 radar", "Bv": "Bv UWB, vehicle PSD limit", "Cv": "Cv UWB + LF, vehicle PSD limit"}


def fig_v2p_outcomes(rows_by_scn, path):
    keys = [k for k in ("S01", "S02", "S08", "SF") if k in rows_by_scn]
    fig, axs = plt.subplots(1, len(keys), figsize=(3.4 * len(keys) + 2.0, 3.6), constrained_layout=True,
                            sharex=True)
    for ax, k in zip(np.atleast_1d(axs), keys):
        items = rows_by_scn[k]
        labels = [SHORT[it[0]] for it in items][::-1]
        vals = [it[1] for it in items][::-1]
        y = np.arange(len(labels))
        ax.barh(y, vals, height=0.34, color=SERIES[0])
        for yi, v in zip(y, vals):
            ax.annotate(f"{v:.0f}%", (v, yi), xytext=(3, 0), textcoords="offset points", va="center",
                        fontsize=8.5, color=INK2)
        ax.set_yticks(y, labels)
        ax.set_xlim(0, 112)
        _style(ax, k + " - " + {"S01": "reversing, upright", "S02": "reversing, low posture",
                                "S08": "reversing, untagged", "SF": "forward 30 km/h"}[k],
               "at-risk runs without a collision (%)", "")
        ax.grid(axis="y", visible=False)
    fig.suptitle("V2P: share of at-risk runs that end without contact (operator brakes on the first L3/L4 alarm)",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_latency(lat, path):
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.0), constrained_layout=True, sharey=True)
    for ax, key, title in ((axs[0], "S01", "S01 upright worker"), (axs[1], "S02", "S02 bending / crouching / lying")):
        for cfg, col, lab in (("B", C_UWB, "UWB (DWM3000 x6)"), ("D", C_AWR, "+ LF + AWR1843AOP radar"),
                              ("E", C_ARS, "+ LF + ARS 408-21 radar")):
            x = np.sort(np.asarray(lat[key][cfg], float))
            if not x.size:
                continue
            x = np.minimum(x, 10.0)
            yv = 100.0 * np.arange(1, len(x) + 1) / len(x)
            ax.step(np.r_[0.0, x * 1000], np.r_[0.0, yv], where="post", color=col, label=lab)
        ax.axvline(200, color=MUTED, lw=1)
        ax.annotate("200 ms requirement", (200, 4), xytext=(4, 0), textcoords="offset points", fontsize=8.5,
                    color=INK2)
        ax.set_xlim(0, 1000)
        ax.set_ylim(0, 101)
        _style(ax, title, "L4 alarm after the person enters the danger zone (ms)", "at-risk runs (%)")
    axs[0].legend(loc="lower right")
    fig.suptitle("Danger-alarm latency (cumulative); runs with no L4 before contact sit at the right edge",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_policy(pts, path):
    fig, ax = plt.subplots(figsize=(6.8, 4.4), constrained_layout=True)
    ax.set_xlim(0, max(60, max(p[1] for p in pts) + 12))
    ymax = max(3.0, max(p[2] for p in pts) * 1.5 + 0.5)
    ax.set_ylim(0, ymax)
    ax.axvline(15, color=MUTED, lw=1)
    ax.annotate("nuisance target 15%", (15, ymax), xytext=(4, -12), textcoords="offset points", fontsize=8.5,
                color=INK2)
    offsets = [(6, 10), (6, 10), (6, -18)]  # worst, tracked 2 sigma, tracked 1 sigma (kept apart)
    for (lab, nuis, coll), col, off in zip(pts, SERIES, offsets):
        ax.plot([nuis], [coll], "o", ms=9, color=col, mec="white", mew=2, label=lab, clip_on=False, zorder=5)
        ax.annotate(lab, (nuis, coll), xytext=off, textcoords="offset points", fontsize=9, color=INK2)
    _style(ax, "Path-prediction policy: nuisance vs safety (UWB + LF)", "S06 workers beside the path with an L3/L4 alarm (%)",
           "S01 + S02 at-risk runs with contact (%)")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_start_inhibit(si, path):
    cats = list(si["rows"])
    series = (("B", "UWB only", SERIES[0]), ("LF", "LF only", SERIES[1]), ("C", "UWB + LF fused", SERIES[2]))
    x = np.arange(len(cats))
    wbar = 0.17
    fig, ax = plt.subplots(figsize=(9.5, 4.2), constrained_layout=True)
    for j, (k, lab, col) in enumerate(series):
        vals = [100.0 * si["rows"][c][k] / max(si["rows"][c]["n"], 1) for c in cats]
        ax.bar(x + (j - 1) * (wbar + 0.03), vals, width=wbar, color=col, label=lab)
    ax.set_xticks(x, [c.replace("grey ", "grey zone ") for c in cats])
    ax.set_ylim(0, 122)
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.legend(loc="upper center", ncol=3)
    _style(ax, "Start-inhibit at key-on: share of people for whom start is blocked (truck at rest)",
           "true distance from the hull", "start blocked (%)")
    ax.grid(axis="x", visible=False)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_v2v_links(comp, path):
    d = np.linspace(5.0, 1500.0, 300)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.0), constrained_layout=True, sharey=True)
    for ax, extra, title in ((axs[0], 0.0, "Line of sight on a haul road"),
                             (axs[1], 35.0, "Round a bench corner (35 dB knife-edge loss)")):
        for phy, col, lab in (("lora7", SERIES[0], "LoRa SF7 / 125 kHz (-124 dBm)"),
                              ("gfsk38", SERIES[1], "GFSK 38.4 kb/s (-109 dBm)")):
            ax.plot(d, 100 * v2v.pdr_vs_distance(comp, phy, d, extra), color=col, label=lab)
        ax.set_ylim(0, 102)
        _style(ax, title, "distance (m)", "packets delivered (%)")
    axs[0].legend(loc="lower left")
    fig.suptitle("865 MHz V2V beacon link - Semtech SX1262 at +14 dBm, path-loss exponent 2.7, 6 dB shadowing",
                 x=0.01, ha="left", fontsize=12, fontweight="bold", color=INK)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_channel(load, path):
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.0), constrained_layout=True, sharex=True)
    for (phy, rate), col, lab in ((("lora7", 2.0), SERIES[0], "LoRa SF7, 2 Hz"), (("lora7", 5.0), SERIES[1], "LoRa SF7, 5 Hz"),
                                  (("gfsk38", 2.0), SERIES[2], "GFSK 38.4, 2 Hz"), (("gfsk38", 5.0), SERIES[3], "GFSK 38.4, 5 Hz")):
        pts = sorted(load[(phy, rate)].items())
        n = [p[0] for p in pts]
        axs[0].plot(n, [100 * p[1]["pdr"] for p in pts], "o-", color=col, ms=5, mec="white", mew=1.5, label=lab)
        axs[1].plot(n, [p[1]["aoi95"] for p in pts], "o-", color=col, ms=5, mec="white", mew=1.5, label=lab)
    axs[0].set_ylim(0, 102)
    _style(axs[0], "Beacons delivered within 300 m", "vehicles sharing one 865 MHz channel", "delivered (%)")
    _style(axs[1], "Age of information, 95th percentile", "vehicles sharing one 865 MHz channel", "seconds")
    axs[1].axhline(1.0, color=MUTED, lw=1)
    axs[1].annotate("1 s", (min(n), 1.0), xytext=(2, 4), textcoords="offset points", fontsize=8.5, color=INK2)
    axs[1].legend(loc="upper left")
    fig.suptitle("Channel load: pure ALOHA with 6 dB capture over a 2 km x 2 km pit", x=0.01, ha="left",
                 fontsize=12, fontweight="bold", color=INK)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_attendance(shift, sweep, chosen, path):
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.0), constrained_layout=True)
    ax = axs[0]
    short = {"A": "A  fingerprint 1:N", "B": "B  fingerprint 1:N + helmet UHF tag",
             "C": "C  UHF claim + 1:k + worn check", "D": "D  SPU UWB claim + 1:1 + worn check"}
    for cfg, col in zip("ABCD", SERIES):
        g = sorted(shift[cfg])
        ax.plot(g, [shift[cfg][k]["wait_p95"] / 60.0 for k in g], "o-", color=col, ms=6, mec="white", mew=1.5,
                label=short[cfg])
    ax.set_xticks(sorted(shift["A"]))
    _style(ax, "Queue at shift change (300 workers)", "gates", "95th-percentile wait (min)")
    ax.legend(loc="upper right")
    ax = axs[1]
    p = sweep["power"]
    ax.plot(p, [100 * x for x in sweep["miss"]], color=SERIES[0], label="own helmet tag missed")
    ax.plot(p, [100 * x for x in sweep["next"]], color=SERIES[1], label="next person in the queue read")
    ax.plot(p, [100 * x for x in sweep["adjacent"]], color=SERIES[2], label="tag in the next lane read")
    ax.axvline(chosen, color=MUTED, lw=1)
    ax.annotate(f"chosen {chosen:.0f} dBm", (chosen, 20), xytext=(4, 0), textcoords="offset points", fontsize=8.5,
                color=INK2)
    ax.set_ylim(0, 102)
    _style(ax, "Gate UHF reader power (R700 + 6 dBic, M730 helmet tag)", "conducted power (dBm)", "windows (%)")
    ax.legend(loc="upper left")
    fig.suptitle("Attendance gate: throughput and helmet-tag reading", x=0.01, ha="left", fontsize=12,
                 fontweight="bold", color=INK)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=400, help="V2P runs per scenario and policy")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=max(1, min(16, (os.cpu_count() or 2) - 2)))
    ap.add_argument("--out", default=str(HERE / "results.md"))
    args = ap.parse_args()
    N = max(20, args.runs // 5) if args.quick else args.runs
    NV = max(30, N * 3 // 4)  # V2V runs per configuration
    t_start = time.time()
    comp = load_components()
    d, ms = load_profiles()
    w = v2p.World(comp, d, ms["RDT100"])
    FIG.mkdir(parents=True, exist_ok=True)

    jobs_v2p = []
    for key in v2p.SCENARIOS:
        jobs_v2p += [(key, "tracked", ch) for ch in _chunks(list(range(10_000, 10_000 + N)), 20)]
    for key in ("S01", "S02", "S06"):
        for pol in ("worst", "tracked1"):
            jobs_v2p += [(key, pol, ch) for ch in _chunks(list(range(10_000, 10_000 + N)), 20)]
    jobs_corner = []
    for key in v2v.V1_CONFIGS:
        jobs_corner += [(key, True, ch) for ch in _chunks(list(range(20_000, 20_000 + NV)), 15)]
        jobs_corner += [(key, False, ch) for ch in _chunks(list(range(30_000, 30_000 + NV // 3)), 15)]
    jobs_pass = [(m, ch) for m in v2v.V2_MODES for ch in _chunks(list(range(40_000, 40_000 + NV)), 25)]
    n_list = (5, 10, 20, 40, 60, 80, 100)
    jobs_load = [(phy, n, rate, s) for phy in ("lora7", "gfsk38") for rate in (2.0, 5.0) for n in n_list
                 for s in range(5 if not args.quick else 2)]
    n_shift = 20 if not args.quick else 5
    jobs_att = [(cfg, g, s) for cfg in "ABCD" for g in (1, 2, 3, 4) for s in range(n_shift)]

    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init) as ex:
        f_si = ex.submit(_si_job, (4000 if not args.quick else 800, 7))
        r_v2p = [r for chunk in ex.map(_v2p_job, jobs_v2p) for r in chunk]
        r_corner = [r for chunk in ex.map(_corner_job, jobs_corner) for r in chunk]
        r_pass = [r for chunk in ex.map(_pass_job, jobs_pass) for r in chunk]
        r_load = list(ex.map(_load_job, jobs_load))
        r_att = list(ex.map(_att_job, jobs_att))
        si = f_si.result()
    t_sim = time.time() - t_start

    out = ["# Simulation results (generated)", "",
           "Produced by `sim/run_all.py` from `sim/components.toml` and `docs/tools/machine_profiles.toml`. "
           "Do not edit by hand; see [docs/13](../docs/13_component_simulation.md) for the method and discussion.", "",
           f"Runs: {N} V2P runs per scenario and policy, {NV} V2V runs per configuration, {n_shift} shifts per "
           f"attendance configuration and gate count; wall time {t_sim:.0f} s on {args.workers} processes. "
           "Seeds are fixed, so a re-run reproduces every number.", ""]
    J = {}

    # 1. sensor reach
    R, reach_rows = sensor_reach(comp, w)
    out += ["## 1. Sensor reach computed from the datasheets", "",
            md_table(["Sensor (datasheet values used)", "Condition", "90 % reach (m)", "50 % reach (m)"], reach_rows), "",
            f"Radar chirp used: 20 MHz/us x 30 us, 10 Msps complex, 192 chirps per 50 ms frame -> maximum range "
            f"{R['radar']['awr_rmax']:.0f} m (IF limited), range resolution {R['radar']['awr_res']:.2f} m. "
            f"RFID EIRP {R['rfid']['eirp']:.0f} dBm (ERP {R['rfid']['eirp'] - 2.15:.1f} dBm, India limit 36 dBm).", ""]
    fig_reach(R, FIG / "fig_sim_sensor_reach.png")

    # 2. V2P
    agg = {}
    for key, pol, r in r_v2p:
        agg.setdefault((key, pol), []).append(r)
    rows, out_rows, lat = [], {}, {"S01": {}, "S02": {}}
    for key, scn in v2p.SCENARIOS.items():
        res = agg[(key, "tracked")]
        risk = [r for r in res if r.get("at_risk")]
        safe = [r for r in res if r.get("at_risk") is False]
        if key == "S00" or key == "S06":
            continue
        out_rows[key] = []
        for c in scn["configs"]:
            col = sum(r[c]["collided"] for r in risk)
            det = sum(r[c]["alarm"] and math.isfinite(r[c]["t3"]) and r[c]["t3"] <= r["t_coll"] for r in risk)
            L = np.array([r[c]["latency"] for r in risk], float)
            fin = L[np.isfinite(L)]
            d1 = np.array([r[c]["d_first"] for r in risk if r[c]["alarm"]], float)
            lead = np.array([r[c]["lead"] for r in risk], float)
            rows.append([key, f"{c}: {v2p.CONFIGS[c]}", len(risk), f"{100 * det / max(len(risk), 1):.1f}%",
                         f"{100 * (1 - col / max(len(risk), 1)):.1f}%", fmt(np.nanmedian(d1) if d1.size else math.nan, 1),
                         fmt(risk[0]["stop"] if risk else math.nan, 1),
                         fmt(pct(fin, 50) * 1000, 0), fmt(pct(fin, 95) * 1000, 0), fmt(pct(fin, 99) * 1000, 0),
                         f"{int(np.sum(~np.isfinite(L)))}",
                         f"{100 * np.sum(fin <= 0.2) / len(L):.1f}%" if len(L) else "-",
                         fmt(pct(lead, 50), 1)])
            out_rows[key].append((c, 100 * (1 - col / max(len(risk), 1))))
            if key in lat:
                lat[key][c] = [x if math.isfinite(x) else 10.0 for x in L]
    out += ["## 2. Vehicle-to-person collision warning (RDT100, prediction policy 'tracked')", "",
            "At-risk = the person would be hit if nobody braked. Detected = first L3/L4 alarm before contact. "
            "Latency = time from entering the danger zone (in path and inside the stop band) to the L4 alarm, 0 when "
            "the alarm was already on; 'no L4' = no danger alarm before contact. Lead = time from the first alarm to "
            "the would-be contact.", "",
            md_table(["Scenario", "Configuration", "At-risk runs", "Detected", "No collision", "1st alarm at (m)",
                      "Stop zone (m)", "L4 p50 (ms)", "L4 p95 (ms)", "L4 p99 (ms)", "No L4", "L4 <= 200 ms",
                      "Lead p50 (s)"], rows), ""]
    J["v2p_rows"] = rows
    fig_v2p_outcomes(out_rows, FIG / "fig_sim_v2p_outcomes.png")
    fig_latency(lat, FIG / "fig_sim_v2p_latency.png")

    # nuisance and false alarms
    nrows = []
    for c in v2p.SCENARIOS["S06"]["configs"]:
        res = agg[("S06", "tracked")]
        nrows.append([f"{c}: {v2p.CONFIGS[c]}", len(res), f"{100 * np.mean([r[c]['alarm'] for r in res]):.1f}%"])
    frows = []
    res0 = agg[("S00", "tracked")]
    for c in v2p.SCENARIOS["S00"]["configs"]:
        k = sum(r[c]["alarm"] for r in res0)
        frows.append([f"{c}: {v2p.CONFIGS[c]}", len(res0), k, f"{100 * k / len(res0):.1f}"])
    out += ["### 2.1 Nuisance (S06) and false alarms (S00)", "",
            "S06: a worker 5-12 m beside the corridor of a reversing truck, standing or walking parallel; any L3/L4 "
            "alarm is a nuisance alarm (target <= 15 %; radar-only baseline 42 % [P8]).", "",
            md_table(["Configuration", "Runs", "Runs with an L3/L4 alarm"], nrows), "",
            "S00: reversing with rocks and berm segments behind the truck (Poisson mean 4, 80 % already in the twin's "
            "static map) and nobody present.", "",
            md_table(["Configuration", "Manoeuvres", "False L3/L4 alarms", "Per 100 manoeuvres"], frows), ""]
    J["nuisance"], J["false_alarms"] = nrows, frows

    # policy trade-off
    prow, pts = [], []
    for pol, lab in (("worst", "worst-case disk (docs/06 s.2)"), ("tracked", "tracked velocity, 2 sigma"),
                     ("tracked1", "tracked velocity, 1 sigma")):
        risk = [r for k in ("S01", "S02") for r in agg[(k, pol)] if r.get("at_risk")]
        col = 100 * sum(r["C"]["collided"] for r in risk) / max(len(risk), 1)
        nui = 100 * np.mean([r["C"]["alarm"] for r in agg[("S06", pol)]])
        safe = [r for k in ("S01", "S02") for r in agg[(k, pol)] if r.get("at_risk") is False]
        pre = 100 * np.mean([r["C"]["alarm"] for r in safe]) if safe else math.nan
        prow.append([lab, len(risk), f"{col:.2f}%", f"{nui:.1f}%", f"{pre:.1f}%"])
        pts.append((lab, nui, col))
    out += ["### 2.2 Path-prediction policy (configuration C, UWB + LF)", "",
            md_table(["Policy", "At-risk runs (S01+S02)", "Contact", "S06 nuisance", "Alarms for not-at-risk S01/S02"],
                     prow), ""]
    J["policy"] = prow
    fig_policy(pts, FIG / "fig_sim_v2p_policy.png")

    # start-inhibit
    srows = []
    for cat, r in si["rows"].items():
        srows.append([cat, r["n"]] + [f"{100 * r[k] / max(r['n'], 1):.1f}%" for k in ("A", "B", "LF", "C", "C7")])
    out += ["### 2.3 Start-inhibit at key-on (S03, truck at rest)", "",
            f"Share of people for whom start is blocked, by true distance from the hull. Start-inhibit radius "
            f"{si['r_si']:.1f} m. Correct = 100 % inside the radius and under the body; unnecessary = above 5.2 m "
            f"(target <= 1 %). Decision ready {si['decision_s']:.2f} s after key-on (boot 0.5 s assumed + 4 LF slots + "
            "3 UWB polls; requirement <= 1 s).", "",
            md_table(["True position", "People", "A RFID (front + rear antennas)", "B UWB only", "LF only",
                      "C UWB + LF fused", "C + canopy anchor U7"], srows), ""]
    J["start_inhibit"] = srows
    fig_start_inhibit(si, FIG / "fig_sim_start_inhibit.png")

    # 3. V2V
    crow = []
    cagg = {}
    for key, conflict, r in r_corner:
        cagg.setdefault((key, conflict), []).append(r)
    for key, cfg in v2v.V1_CONFIGS.items():
        res = [r for r in cagg[(key, True)] if r["conflict"]]
        both = np.array([min(r["lead_truck"], r["lead_lmv"]) for r in res], float)  # NaN if a driver never alarmed
        silent = ~np.isfinite(both)
        nofa = cagg[(key, False)]
        crow.append([cfg["label"], len(res), f"{100 * np.mean([r['collided'] for r in res]):.1f}%",
                     f"{100 * np.mean(np.nan_to_num(both, nan=-1.0) >= 4.0):.1f}%",
                     f"{100 * np.mean(np.nan_to_num(both, nan=-1.0) >= 5.9):.1f}%", f"{100 * silent.mean():.1f}%",
                     fmt(pct(both[~silent], 5), 1), f"{100 * np.mean([r['pdr_direct'][0] for r in res]):.0f}%",
                     f"{100 * np.mean([r['pdr_any'][0] for r in res]):.0f}%",
                     f"{100 * np.mean([r['alarm_truck'] or r['alarm_lmv'] for r in nofa]):.1f}%"])
    out += ["## 3. Vehicle-to-vehicle conflict warning", "",
            "### 3.1 Blind bench corner (S05): loaded 100 t truck at 30 km/h vs LMV at 40 km/h", "",
            "Lead = time from the later of the two drivers' first L3 alarm to the would-be contact (requirement "
            "R-CA-8 >= 4 s; S05 asks L3 >= 6 s, i.e. as soon as TTC reaches the 6 s L3 threshold). PDR = share of the "
            "LMV's beacons the truck received over the whole approach. 'Alarms, no conflict' = runs where the two "
            "pass 7-12 s apart.", "",
            md_table(["Configuration", "Conflicts", "Contact", "Both alarmed >= 4 s", "Both >= 6 s",
                      "A driver never alarmed", "Lead p5 when both alarmed (s)", "PDR direct", "PDR direct + relay",
                      "Alarms, no conflict"], crow), "",
            "All configurations use pure ALOHA (no slot timing), the worst case for collisions; a GNSS-time-slotted "
            "MAC would remove most of them (see docs/13).", ""]
    J["corner"] = crow
    prow2 = []
    pagg = {}
    for mode, r in r_pass:
        pagg.setdefault(mode, []).append(r)
    for mode, lab in v2v.V2_MODES.items():
        res = pagg[mode]
        prow2.append([lab, len(res), f"{res[0]['margin']:.2f} m", f"{100 * np.mean([r['nuisance_any'] for r in res]):.1f}%"])
    out += ["### 3.2 Two 100 t trucks passing in adjacent lanes (10 m centre to centre, 3.9 m between bodies)", "",
            md_table(["GNSS (ZED-F9P mode)", "Passes", "Uncertainty margin (1 m + 2 sigma_rel)",
                      "Passes with a nuisance L3/L4"], prow2), ""]
    J["passing"] = prow2
    load = {}
    for phy, n, rate, r in r_load:
        load.setdefault((phy, rate), {}).setdefault(n, []).append(r)
    load_m = {k: {n: dict(pdr=float(np.nanmean([x["pdr"] for x in v])), aoi95=float(np.nanmean([x["aoi95"] for x in v])),
                      offered=float(np.mean([x["offered"] for x in v])))
                  for n, v in d_.items()} for k, d_ in load.items()}
    lrow = []
    for n in n_list:
        row = [n]
        for key in (("lora7", 2.0), ("lora7", 5.0), ("gfsk38", 2.0), ("gfsk38", 5.0)):
            x = load_m[key][n]
            row.append(f"{100 * x['pdr']:.0f}% / {x['aoi95']:.1f} s")
        lrow.append(row)
    air = SubGhz(comp, "lora7").airtime_s * 1000, SubGhz(comp, "gfsk38").airtime_s * 1000
    out += ["### 3.3 Channel load on one 865 MHz channel (delivered within 300 m / 95th-percentile age of information)", "",
            f"Beacon airtime for 24 bytes: LoRa SF7/125 kHz {air[0]:.1f} ms, GFSK 38.4 kb/s {air[1]:.1f} ms.", "",
            md_table(["Vehicles", "LoRa SF7, 2 Hz", "LoRa SF7, 5 Hz", "GFSK 38.4, 2 Hz", "GFSK 38.4, 5 Hz"], lrow), ""]
    J["load"] = lrow
    fig_v2v_links(comp, FIG / "fig_sim_v2v_links.png")
    fig_channel(load_m, FIG / "fig_sim_v2v_channel.png")
    co_rows, co = coexistence(comp)
    out += ["### 3.4 Coexistence: a UHF RFID reader next to the 865 MHz V2V radio (same band in India)", "",
            f"Reader EIRP {co['eirp']:.0f} dBm; the SX1262 tolerates about {co['tolerable']:.0f} dBm at 1 MHz offset "
            f"(blocking 88 dB above sensitivity + 3 dB, D8). Free-space separation needed: {co['d_free']:.0f} m.", "",
            md_table(["Separation", "Reader power at the V2V radio", "Tolerable", "Result"], co_rows), ""]
    J["coexistence"] = co_rows

    # 4. attendance
    shift = {}
    for r in r_att:
        shift.setdefault(r["cfg"], {}).setdefault(r["gates"], []).append(r)
    shift_m = {c: {g: {k: float(np.mean([x[k] for x in v])) for k in ("wait_p50", "wait_p95", "wait_max", "service_mean",
                                                                         "service_p95", "last_out_min", "late",
                                                                         "exceptions", "misattributed", "false_flags")}
                   for g, v in d_.items()} for c, d_ in shift.items()}
    arow = []
    for c in "ABCD":
        for g in (1, 2):
            x = shift_m[c][g]
            arow.append([f"{c}: {att.CONFIGS[c]}", g, f"{x['service_mean']:.1f} s", f"{x['service_p95']:.1f} s",
                         f"{60.0 / x['service_mean']:.1f}", f"{x['wait_p95'] / 60:.1f} min", f"{x['last_out_min']:+.1f} min",
                         f"{x['late']:.0f}", f"{x['exceptions']:.2f}", f"{x['false_flags']:.1f}"])
    out += ["## 4. Attendance with biometric + helmet", "",
            "### 4.1 Throughput at a shift change (300 workers arriving over 30 min, peak 10 min before the shift)", "",
            md_table(["Configuration", "Gates", "Service mean", "Service p95", "Workers/min/gate", "Wait p95",
                      "Last through vs shift start", "Late workers", "Supervisor exceptions", "False PPE flags"], arow), ""]
    J["attendance"] = arow
    crow2 = []
    for c in "ABCD":
        allr = [x for g in shift[c] for x in shift[c][g]]
        caught = {v: sum(x["caught"][v] for x in allr) for v in att.VIOLATIONS}
        pres = {v: sum(x["present"][v] for x in allr) for v in att.VIOLATIONS}
        crow2.append([f"{c}"] + [f"{100 * caught[v] / max(pres[v], 1):.0f}% ({pres[v]})" for v in att.VIOLATIONS])
    a = comp["assumptions"]
    crow2.append(["Camera helmet detector (alternative)", f"-", f"{100 * a['vision_recall']:.0f}%*",
                  f"{100 * a['vision_recall']:.0f}%*", f"{100 * a['vision_recall']:.0f}%", "-", "-"])
    ws = att.WornSensor(comp)
    rng_c = np.random.default_rng(17)
    thr = a["cap_threshold_pf"]
    cap_only = {s_: float(np.mean([ws.capacitance_pf(rng_c, s_) >= thr for _ in range(20000)]))
                for s_ in ("worn_ok", "carried_hand", "carried_underarm")}
    out += ["### 4.2 Violations caught at the gate (all gate counts pooled; number of cases in brackets)", "",
            md_table(["Configuration", "Strap open", "Carried in hand", "Carried under arm", "No helmet",
                      "Wearing someone else's helmet", "Personal unit dead"], crow2), "",
            "\\* A camera detector sees a helmet that is not on the head only if it is out of frame; it cannot read "
            "the strap, the owner or the personal unit. Recall from SHWD mAP@0.5 0.84-0.94 [E30].", "",
            "The 100 % for carried helmets in C and D needs all three cues (FDC1004 capacitance, IMU tilt and the strap "
            "switch) to be fooled at once. With the capacitance cue alone (threshold "
            f"{thr:.1f} pF): carried in hand caught {100 * (1 - cap_only['carried_hand']):.1f} %, carried under the arm "
            f"caught {100 * (1 - cap_only['carried_underarm']):.1f} %, correctly worn helmets falsely flagged "
            f"{100 * (1 - cap_only['worn_ok']):.2f} %. The electrode geometry and the cue probabilities are assumptions "
            "to be replaced by bench measurements.", ""]
    J["cap_only"] = cap_only
    J["caught"] = crow2
    sweep = att.uhf_power_sweep(comp, list(range(8, 31, 2)), n=4000 if not args.quick else 1000)
    srow = [[p, f"{100 * m:.2f}%", f"{100 * nx:.1f}%", f"{100 * ad:.1f}%", "yes" if ok else "no"]
            for p, m, nx, ad, ok in zip(sweep["power"], sweep["miss"], sweep["next"], sweep["adjacent"], sweep["erp_ok"])]
    out += ["### 4.3 Gate UHF reader power (1.5 s window)", "",
            md_table(["Conducted power (dBm)", "Own tag missed", "Next in queue read", "Next lane read", "Within 4 W ERP"],
                     srow), ""]
    J["uhf_sweep"] = srow
    fig_attendance(shift_m, sweep, a["uhf_gate_tx_dbm"], FIG / "fig_sim_attendance.png")
    frow = [[lab, f"{p:.2e}", f"{n50:,.0f}"] for lab, p, n50 in att.false_match_table(comp, a["shift_workers"])]
    out += ["### 4.4 Outsider acceptance with the datasheet FAR (0.001 % per template compared)", "",
            md_table(["Matching mode", "Per attempt", "Attempts until a 50 % chance of one false acceptance"], frow), ""]
    J["false_match"] = frow
    fs = att.first_sighting(comp)
    out += ["### 4.5 Roll-call: first in-pit sighting of the personal unit after the gate", "",
            f"Event-driven heartbeat <= 60 s, 98 % delivery: median {fs['p50']:.0f} s, 99th percentile {fs['p99']:.0f} s, "
            f"share not seen within 5 min {100 * fs['p_late_5min']:.3f} %. The twin can therefore flag "
            "'checked in but not seen' after 5 min without false alerts.", ""]
    J["first_sighting"] = fs

    # 5. power cross-check
    p_rows, p = power_crosscheck(comp)
    out += ["## 5. Datasheet cross-check of the wearable power budget (docs/05 s.6)", "",
            md_table(["Item", "Indicative value in design_calcs.py", "Datasheet value"], p_rows), "",
            f"Event-driven advantage over polling: {p['poll_new'] / p['event_new']:.1f}x with datasheet currents "
            f"({p['poll_old'] / p['event_old']:.1f}x with the indicative ones).", ""]
    J["power"] = p
    out += ["## Figures", ""] + [f"![{n}](../docs/figures/{n}.png)" for n in (
        "fig_sim_sensor_reach", "fig_sim_v2p_outcomes", "fig_sim_v2p_latency", "fig_sim_v2p_policy",
        "fig_sim_start_inhibit", "fig_sim_v2v_links", "fig_sim_v2v_channel", "fig_sim_attendance")] + [""]
    pathlib.Path(args.out).write_text("\n".join(out) + "\n", encoding="utf-8")
    (HERE / "results.json").write_text(json.dumps(J, indent=1, default=float), encoding="utf-8")
    print("\n".join(out))
    print(f"\nTotal {time.time() - t_start:.0f} s")


if __name__ == "__main__":
    main()
