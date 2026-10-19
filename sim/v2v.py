"""Vehicle-to-vehicle (V2V) conflict warning with datasheet radio (SX1262) and GNSS (ZED-F9P) models.

V1  Blind bench corner (docs/10 S05): a loaded 100 t truck and an LMV approach a junction whose inside
    corner is a bench wall. Beacons (VPB: id, pose, speed, heading) go direct, with knife-edge loss round
    the corner, or through an OC Guardian relay on a pole at the corner.
V2  Two trucks passing in adjacent haul-road lanes (no conflict): nuisance alarms by GNSS grade.
V4  Channel load: packet delivery and age of information as the number of beaconing vehicles grows.

Same open-loop + analytic-braking method as v2p.py: alarms are timed with both vehicles at constant
speed; each driver then brakes after their own first L3 alarm plus a reaction time.
"""
from __future__ import annotations

import heapq
import math

import numpy as np

from common import knife_edge_db, lognormal
from sensors import GnssError, SubGhz

DT = 0.01
CHECK_S = 0.1      # conflict check period on each VSU
HORIZON_S = 10.0
BUFFER = 1.0
CORNER = 12.0      # bench occupies x < -12 m and y < -12 m; the junction is at the origin

V1_CONFIGS = {
    "L2": dict(label="LoRa SF7, 2 Hz, direct only, RTK", phy="lora7", rate=2.0, guardian=False, gnss="rtk"),
    "L2G": dict(label="LoRa SF7, 2 Hz, Guardian relay, RTK", phy="lora7", rate=2.0, guardian=True, gnss="rtk"),
    "L5G": dict(label="LoRa SF7, 5 Hz, Guardian relay, RTK", phy="lora7", rate=5.0, guardian=True, gnss="rtk"),
    "F2G": dict(label="GFSK 38.4 kb/s, 2 Hz, Guardian relay, RTK", phy="gfsk38", rate=2.0, guardian=True, gnss="rtk"),
    "L2Gp": dict(label="LoRa SF7, 2 Hz, Guardian relay, standalone GNSS", phy="lora7", rate=2.0, guardian=True,
                 gnss="pvt"),
}
V2_MODES = {"rtk": "ZED-F9P RTK fixed (0.01 m + 1 ppm CEP)", "sbas": "ZED-F9P SBAS (1.0 m CEP)",
            "pvt": "ZED-F9P standalone (1.5 m CEP)"}


# ---------------------------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------------------------
def obb_gap(cA, hA, LA, WA, cB, hB, LB, WB):
    """Separating-axis gap between two oriented boxes (0 when they overlap). A lower bound on the
    true distance, so slightly conservative at corner-to-corner geometry. Vectorised over time."""
    cA, cB = np.atleast_2d(cA), np.atleast_2d(cB)
    hA, hB = np.broadcast_to(hA, cA.shape[:1]), np.broadcast_to(hB, cB.shape[:1])
    uA = np.stack((np.cos(hA), np.sin(hA)), -1)
    nA = np.stack((-np.sin(hA), np.cos(hA)), -1)
    uB = np.stack((np.cos(hB), np.sin(hB)), -1)
    nB = np.stack((-np.sin(hB), np.cos(hB)), -1)
    d = cB - cA
    gap = np.full(len(d), -np.inf)
    for ax in (uA, nA, uB, nB):
        rA = 0.5 * LA * np.abs((uA * ax).sum(-1)) + 0.5 * WA * np.abs((nA * ax).sum(-1))
        rB = 0.5 * LB * np.abs((uB * ax).sum(-1)) + 0.5 * WB * np.abs((nB * ax).sum(-1))
        gap = np.maximum(gap, np.abs((d * ax).sum(-1)) - rA - rB)
    return np.maximum(gap, 0.0)


def segment_hits_bench(p, q, c=CORNER):
    """Does segment p-q pass through the bench quadrant {x < -c, y < -c}?"""
    lo, hi = 0.0, 1.0
    for k in range(2):
        a, b = p[k], q[k]
        if abs(b - a) < 1e-9:
            if a >= -c:
                return False
            continue
        s = (-c - a) / (b - a)  # parameter where the coordinate crosses -c
        if b > a:   # coordinate increasing: inside (< -c) for s < s*
            hi = min(hi, s)
        else:
            lo = max(lo, s)
    return lo < hi


def corner_loss_db(radio: SubGhz, p, q, c=CORNER):
    """Knife-edge loss round the vertical bench corner, signed by whether the bench blocks the path."""
    p, q = np.asarray(p, float), np.asarray(q, float)
    e = np.array([-c, -c])
    d = q - p
    n = math.hypot(d[0], d[1])
    if n < 1e-6:
        return 0.0
    h = abs(d[0] * (e[1] - p[1]) - d[1] * (e[0] - p[0])) / n
    if not segment_hits_bench(p, q, c):
        h = -h
    d1 = max(math.hypot(*(e - p)), 1.0)
    d2 = max(math.hypot(*(q - e)), 1.0)
    v = h * math.sqrt(2.0 * (d1 + d2) / (radio.lam * d1 * d2))
    return float(knife_edge_db(v))


# ---------------------------------------------------------------------------------------------
# V1: blind bench corner
# ---------------------------------------------------------------------------------------------
class Vehicle:
    def __init__(self, m: dict, start, heading, speed):
        self.L, self.W = m["length_m"], m["width_m"]
        self.a = m["a_brake_mps2"]  # level junction
        self.start = np.asarray(start, float)
        self.h = heading
        self.u = np.array([math.cos(heading), math.sin(heading)])
        self.v = speed

    def pos(self, t, tb=math.inf):
        t = np.asarray(t, float)
        if math.isfinite(tb):
            tau = np.clip(t - tb, 0.0, self.v / self.a)
            s = np.where(t < tb, self.v * t, self.v * tb + self.v * tau - 0.5 * self.a * tau ** 2)
        else:
            s = self.v * t
        return self.start[None, :] + s[..., None] * self.u[None, :]


def _conflict_ttc(own_p, own_v, own_h, oth_p, oth_v, oth_h, dims, margin):
    tau = np.arange(0.0, HORIZON_S + 1e-9, 0.1)
    pa = own_p[None, :] + tau[:, None] * own_v[None, :]
    pb = oth_p[None, :] + tau[:, None] * oth_v[None, :]
    g = obb_gap(pa, own_h, dims[0], dims[1], pb, oth_h, dims[2], dims[3])
    hit = g <= margin
    return float(tau[int(np.argmax(hit))]) if hit.any() else math.inf


def simulate_corner(comp, ms, cfg: dict, seed: int, conflict: bool = True) -> dict:
    """One blind-corner approach. Returns lead times, outcome and link statistics."""
    rng = np.random.default_rng(seed)
    a = comp["assumptions"]
    radio = SubGhz(comp, cfg["phy"])
    truck_m, lmv_m = ms["RDT100"], ms["LMV"]
    v_t, v_l = truck_m["v_fwd_kmh"] / 3.6, lmv_m["v_fwd_kmh"] / 3.6
    t_arr = rng.uniform(26.0, 32.0)
    gap = rng.uniform(-1.2, 1.2) if conflict else float(rng.choice([-1.0, 1.0])) * rng.uniform(7.0, 12.0)
    A = Vehicle(truck_m, (-v_t * t_arr, 0.0), 0.0, v_t)                # eastbound truck
    B = Vehicle(lmv_m, (0.0, -v_l * (t_arr + gap)), math.pi / 2, v_l)  # northbound LMV
    veh = [A, B]
    t_end = t_arr + max(gap, 0.0) + 8.0
    t = np.arange(0.0, t_end, DT)
    truth = [V.pos(t) for V in veh]
    gn = GnssError(comp, cfg["gnss"])
    err = [gn.series(rng, t) for _ in veh]
    margin = BUFFER + 2.0 * math.sqrt(2.0) * gn.sigma
    t_react = [float(lognormal(rng, a["t_react_median_s"], a["t_react_sigma_ln"])) for _ in veh]
    G = np.array([-CORNER + 1.0, -CORNER + 1.0])
    nodes = (0, 1, 2) if cfg["guardian"] else (0, 1)

    def node_pos(idx, tt):
        if idx == 2:
            return G
        return truth[idx][min(int(tt / DT), len(t) - 1)]

    def prx_at(src, dst, tt):
        p, q = node_pos(src, tt), node_pos(dst, tt)
        d = max(math.hypot(q[0] - p[0], q[1] - p[1]), 1.0)
        extra = corner_loss_db(radio, p, q) if 2 not in (src, dst) else 0.0
        return float(radio.prx(d, extra)) + rng.normal(0.0, radio.shadow)

    txs = []  # dict(start, end, src, t_pay, origin)
    heap = []
    period = 1.0 / cfg["rate"]
    for i in (0, 1):
        tk = rng.uniform(0.0, period)
        while tk < t_end:
            txs.append(dict(start=tk, end=tk + radio.airtime_s, src=i, t_pay=tk, origin=i))
            heapq.heappush(heap, (txs[-1]["end"], len(txs) - 1))
            tk += period * rng.uniform(0.95, 1.05)

    def received(P, dst):
        p_sig = prx_at(P["src"], dst, P["start"])
        if rng.random() >= float(radio.p_ok(p_sig)):
            return False
        for O in txs:
            if O is P or O["start"] >= P["end"] or O["end"] <= P["start"]:
                continue
            if O["src"] == dst:  # half duplex: the receiver was transmitting
                return False
            if prx_at(O["src"], dst, O["start"]) > p_sig - radio.capture:
                return False
        return True

    last_rx = [None, None]
    sent, got_direct, got_any = [0, 0], [set(), set()], [set(), set()]
    first3, first4 = [math.inf, math.inf], [math.inf, math.inf]
    next_check = [rng.uniform(0.0, CHECK_S), rng.uniform(0.0, CHECK_S)]

    def run_checks(until):
        for vi in (0, 1):
            while next_check[vi] < min(until, t_end):
                tc = next_check[vi]
                next_check[vi] += CHECK_S
                if last_rx[vi] is None or tc - last_rx[vi][0] > 3.0:  # nothing heard, or stale
                    continue
                k = min(int(tc / DT), len(t) - 1)
                own, oth = veh[vi], veh[1 - vi]
                tp, op, ov = last_rx[vi]
                ttc = _conflict_ttc(truth[vi][k] + err[vi][k], own.u * own.v, own.h, op + ov * (tc - tp), ov,
                                    oth.h, (own.L, own.W, oth.L, oth.W), margin)
                if ttc <= 6.0 and tc < first3[vi]:
                    first3[vi] = tc
                if ttc <= 3.0 and tc < first4[vi]:
                    first4[vi] = tc

    while heap:
        e, idx = heapq.heappop(heap)
        run_checks(e)
        P = txs[idx]
        if P["src"] < 2:
            sent[P["src"]] += 1
        for dst in nodes:
            if dst in (P["src"], P["origin"]):
                continue
            if not received(P, dst):
                continue
            if dst == 2:
                ts = P["end"] + a["guardian_delay_ms"] / 1000.0
                if ts < t_end:
                    txs.append(dict(start=ts, end=ts + radio.airtime_s, src=2, t_pay=P["t_pay"], origin=P["origin"]))
                    heapq.heappush(heap, (txs[-1]["end"], len(txs) - 1))
                continue
            o = P["origin"]
            k = min(int(P["t_pay"] / DT), len(t) - 1)
            pos = truth[o][k] + err[o][k]
            vel = veh[o].u * veh[o].v + rng.normal(0.0, comp["gnss"]["vel_acc_mps"], 2)
            if last_rx[dst] is None or P["t_pay"] > last_rx[dst][0]:
                last_rx[dst] = (P["t_pay"], pos, vel)
            got_any[dst].add(P["t_pay"])
            if P["src"] != 2:
                got_direct[dst].add(P["t_pay"])
    run_checks(t_end)

    # ground truth and braking outcome
    g0 = obb_gap(truth[0], A.h, A.L, A.W, truth[1], B.h, B.L, B.W)
    t_conf = float(t[int(np.argmax(g0 <= 0.0))]) if (g0 <= 0.0).any() else math.inf
    tb = [first3[i] + t_react[i] if math.isfinite(first3[i]) else math.inf for i in (0, 1)]
    t_ext = np.arange(0.0, t_end + 10.0, DT)
    g1 = obb_gap(A.pos(t_ext, tb[0]), A.h, A.L, A.W, B.pos(t_ext, tb[1]), B.h, B.L, B.W)
    return dict(conflict=math.isfinite(t_conf), t_conf=t_conf,
                lead_truck=t_conf - first3[0] if math.isfinite(first3[0]) else math.nan,
                lead_lmv=t_conf - first3[1] if math.isfinite(first3[1]) else math.nan,
                alarm_truck=math.isfinite(first3[0]), alarm_lmv=math.isfinite(first3[1]),
                collided=bool((g1 <= 0.0).any()), min_gap=float(g1.min()),
                pdr_direct=[len(got_direct[i]) / max(sent[1 - i], 1) for i in (0, 1)],
                pdr_any=[len(got_any[i]) / max(sent[1 - i], 1) for i in (0, 1)])


# ---------------------------------------------------------------------------------------------
# V2: two trucks passing in adjacent lanes (no conflict) - nuisance by GNSS grade
# ---------------------------------------------------------------------------------------------
def simulate_passing(comp, ms, mode: str, seed: int, lane_sep: float = 10.0) -> dict:
    rng = np.random.default_rng(seed)
    m = ms["RDT100"]
    v1, v2 = m["v_fwd_kmh"] / 3.6, 25.0 / 3.6
    A = Vehicle(m, (-lane_sep / 2, -150.0), math.pi / 2, v1)
    B = Vehicle(m, (lane_sep / 2, 150.0), -math.pi / 2, v2)
    t_end = 300.0 / (v1 + v2) + 4.0
    t = np.arange(0.0, t_end, DT)
    gn = GnssError(comp, mode)
    err = [gn.series(rng, t), gn.series(rng, t)]
    margin = BUFFER + 2.0 * math.sqrt(2.0) * gn.sigma
    radio = SubGhz(comp, "lora7")
    period = 0.5
    last = [None, None]
    nuis = [False, False]
    next_b = [rng.uniform(0, period), rng.uniform(0, period)]
    hdg_sd = math.radians(comp["gnss"]["heading_acc_deg"])
    for k in range(0, len(t), int(CHECK_S / DT)):
        tc = t[k]
        for i in (0, 1):
            while next_b[i] <= tc:  # beacons from i to the other vehicle (LOS on a straight road)
                kk = min(int(next_b[i] / DT), len(t) - 1)
                pi = (A, B)[i].pos(np.array([next_b[i]]))[0]
                pj = (A, B)[1 - i].pos(np.array([next_b[i]]))[0]
                prx = radio.prx(max(math.hypot(*(pj - pi)), 1.0)) + rng.normal(0.0, radio.shadow)
                if rng.random() < float(radio.p_ok(prx)):
                    V = (A, B)[i]
                    h = V.h + rng.normal(0.0, hdg_sd)
                    vel = np.array([math.cos(h), math.sin(h)]) * V.v
                    last[1 - i] = (next_b[i], pi + err[i][kk], vel, h)
                next_b[i] += period * rng.uniform(0.95, 1.05)
        for i in (0, 1):
            if last[i] is None:
                continue
            own, oth = (A, B)[i], (A, B)[1 - i]
            own_p = own.pos(np.array([tc]))[0] + err[i][k]
            tp, op, ov, oh = last[i]
            ttc = _conflict_ttc(own_p, own.u * own.v, own.h + rng.normal(0.0, hdg_sd), op + ov * (tc - tp), ov, oh,
                                (own.L, own.W, oth.L, oth.W), margin)
            if ttc <= 6.0:
                nuis[i] = True
    return dict(nuisance_any=nuis[0] or nuis[1], nuisance=nuis, margin=margin)


# ---------------------------------------------------------------------------------------------
# V4: channel load on one 865 MHz channel
# ---------------------------------------------------------------------------------------------
def channel_load(comp, phy: str, n_veh: int, rate: float, seed: int, area_m: float = 2000.0,
                 t_sim: float = 30.0, r_link: float = 300.0) -> dict:
    """Pure ALOHA with capture: N vehicles beacon at `rate` with random phase; a packet survives if the
    link closes and no overlapping packet arrives within `capture` dB of it (or the receiver was
    transmitting). Returns delivery ratio and p95 age of information for links up to r_link."""
    rng = np.random.default_rng(seed)
    radio = SubGhz(comp, phy)
    pos = rng.uniform(-area_m / 2, area_m / 2, (n_veh, 2))
    pos[0] = 0.0  # receiver at the centre
    n_near = min(4, n_veh - 1)  # neighbours whose beacons we measure; everyone else interferes
    rr = r_link * np.sqrt(rng.uniform(0.04, 1.0, n_near))
    th = rng.uniform(0.0, 2 * math.pi, n_near)
    pos[1:1 + n_near] = np.column_stack((rr * np.cos(th), rr * np.sin(th)))
    starts, src = [], []
    for i in range(n_veh):
        tk = rng.uniform(0.0, 1.0 / rate)
        while tk < t_sim:
            starts.append(tk)
            src.append(i)
            tk += (1.0 / rate) * rng.uniform(0.9, 1.1)
    starts, src = np.array(starts), np.array(src)
    order = np.argsort(starts)
    starts, src = starts[order], src[order]
    ends = starts + radio.airtime_s
    dist = np.maximum(np.hypot(pos[src, 0], pos[src, 1]), 1.0)
    p_rx = radio.prx(dist) + rng.normal(0.0, radio.shadow, len(src))
    want = (src != 0) & (dist <= r_link)
    ok = np.zeros(len(src), bool)
    for k in np.flatnonzero(want):
        if rng.random() >= float(radio.p_ok(p_rx[k])):
            continue
        lo = np.searchsorted(starts, starts[k] - radio.airtime_s, "left")
        hi = np.searchsorted(starts, ends[k], "left")
        bad = False
        for j in range(lo, hi):
            if j == k or ends[j] <= starts[k]:
                continue
            if src[j] == 0 or p_rx[j] > p_rx[k] - radio.capture:
                bad = True
                break
        ok[k] = not bad
    pdr = ok[want].mean() if want.any() else math.nan
    gaps = []
    for i in np.unique(src[want]):
        ts = starts[(src == i) & ok]
        if ts.size >= 2:
            gaps.extend(np.diff(ts).tolist())
        elif ts.size < 2:
            gaps.append(t_sim)
    aoi95 = float(np.percentile(gaps, 95)) if gaps else math.nan
    offered = n_veh * rate * radio.airtime_s
    return dict(pdr=float(pdr), aoi95=aoi95, offered=offered, airtime_ms=radio.airtime_s * 1000)


def pdr_vs_distance(comp, phy: str, d, extra_db=0.0, n=4000, seed=3):
    rng = np.random.default_rng(seed)
    radio = SubGhz(comp, phy)
    sh = rng.normal(0.0, radio.shadow, (n, 1))
    return radio.p_ok(radio.prx(np.asarray(d)[None, :], extra_db) + sh).mean(0)
