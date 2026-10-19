"""Vehicle-to-person (V2P) collision warning: Monte Carlo over the scenario library (docs/10 s.6)
with datasheet sensor models.

Method: open loop, then analytic braking.
1. The truck runs at constant speed. Every detection layer runs on its own schedule (UWB discovery
   blinks and 1-20 Hz ranging, LF coil slots, radar frames, RFID inventory rounds), and each
   configuration's alarm level is recorded every 10 ms with the latencies of docs/06 s.11.
2. The operator brakes after the first L3/L4 alarm plus a log-normal reaction time; the truck
   decelerates at a_eff from its Machine Safety Profile; the person keeps moving (no evasive action).
3. All configurations share the same person, motion and sensor noise (common random numbers), so
   differences between them come from the sensors and logic, not from luck.
"""
from __future__ import annotations

import heapq
import math

import numpy as np

from common import dc, lognormal
from sensors import Ars408, FmcwRadar, LfShell, UhfRfid, UwbRanging

DT = 0.01
BUFFER = 1.0      # docs/06 s.1: mirrors, overhangs, tag-on-helmet vs body extent
GROWTH = 0.5      # m/s: growth of the predicted person disk (changes in walking, beyond the track velocity)
PROC_S = 0.010    # NLOS screen + solve + track (docs/06 s.11)
ACT_S = 0.020     # cab buzzer and display actuation (docs/06 s.11)
HOLD_S = 0.5      # exit hysteresis (docs/06 s.6)
BOOT_S = 0.5      # safety-controller boot at key-on (docs/06 s.12 says < 1 s; assumed)

CONFIGS = {
    "A": "UHF RFID presence (R700 + M730)",
    "B": "UWB only (6 x DWM3000)",
    "C": "UWB + LF (DWM3000 + AS3932)",
    "D": "UWB + LF + radar (AWR1843AOP)",
    "E": "UWB + LF + radar (ARS 408-21)",
    "Bv": "UWB only, vehicle PSD limit",
    "Cv": "UWB + LF, vehicle PSD limit",
}

SCENARIOS = {
    "S01": dict(title="Reversing 10 km/h toward a standing or walking worker", v_kmh=-10.0, kind="behind",
                postures={"standing": 1.0}, tagged=True, configs=["A", "B", "C", "D", "E"]),
    "S02": dict(title="Reversing 10 km/h, worker bending, crouching or lying", v_kmh=-10.0, kind="behind_low",
                postures={"bending": 0.40, "crouching": 0.35, "lying": 0.25}, tagged=True,
                configs=["A", "B", "C", "D", "E"]),
    "S06": dict(title="Worker beside (not in) the path of a reversing truck", v_kmh=-10.0, kind="beside",
                postures={"standing": 1.0}, tagged=True, configs=["A", "B", "C", "D", "E"]),
    "S08": dict(title="Reversing 10 km/h, untagged person", v_kmh=-10.0, kind="behind",
                postures={"standing": 0.70, "crouching": 0.20, "lying": 0.10}, tagged=False,
                configs=["C", "D", "E"]),
    "SF": dict(title="Forward 30 km/h, loaded, 1:16 downgrade, worker on the haul road", v_kmh=30.0,
               kind="ahead", postures={"standing": 1.0}, tagged=True, configs=["A", "B", "C", "Bv", "Cv"]),
    "S00": dict(title="Reversing 10 km/h with no person (clutter only)", v_kmh=-10.0, kind="empty",
                postures={"standing": 1.0}, tagged=False, configs=["A", "C", "D", "E"]),
}

LF_HEIGHT = {"standing": 1.10, "bending": 0.90, "crouching": 0.60, "lying": 0.25}
RADAR_HEIGHT = {"standing": 1.00, "bending": 0.90, "crouching": 0.60, "lying": 0.20}


# ---------------------------------------------------------------------------------------------
# Machine and geometry
# ---------------------------------------------------------------------------------------------
class Truck:
    def __init__(self, m: dict, d: dict, comp: dict):
        self.m, self.d = m, d
        self.L2, self.W2 = m["length_m"] / 2, m["width_m"] / 2
        self.bmin = np.array([-self.L2, -self.W2, 0.0])
        self.bmax = np.array([self.L2, self.W2, m["body_height_m"]])
        S = dc.placement(m)
        # pilot fit: six hull anchors (the canopy anchor U7 is phase 2, docs/11 s.4.1)
        self.anchors = np.array([[s["x"], s["y"], s["z"]] for s in S
                                 if s["sensor"] == "UWB anchor" and s["id"] != "U7"], float)
        self.anchors_full = np.array([[s["x"], s["y"], s["z"]] for s in S if s["sensor"] == "UWB anchor"], float)
        kinds = {"F1": "front", "F2": "rear"}
        self.coils, self.coils_keyon = [], []
        for s in S:
            if s["sensor"].startswith("LF coil"):
                yaw = math.radians(float(s["yaw"]))
                base = dict(pos=(s["x"], s["y"], s["z"]), axis=(math.cos(yaw), math.sin(yaw), 0.0))
                kind = kinds.get(s["id"], "side")
                self.coils.append(dict(base, r_on=comp["assumptions"]["lf_r_on_m"][kind]))
                self.coils_keyon.append(dict(base, r_on=comp["assumptions"]["lf_r_on_keyon_m"][kind]))
        self.rear_mount = np.array([-(self.L2 + 0.15), 0.0, 1.0])
        self.front_mount = np.array([self.L2 + 0.15, 0.0, 1.0])
        self.a_eff = m["a_brake_mps2"] - d["g"] * m.get("design_grade", 0.0)
        self.r_si = dc.zones(m, d, 0.0)[0]

    def hull_dist(self, x, y):
        dx = np.maximum(np.abs(x) - self.L2, 0.0)
        dy = np.maximum(np.abs(y) - self.W2, 0.0)
        return np.hypot(dx, dy)

    def hull_dist1(self, x, y):
        dx = max(abs(x) - self.L2, 0.0)
        dy = max(abs(y) - self.W2, 0.0)
        return math.hypot(dx, dy)

    def los(self, p3, anchors=None):
        """True per anchor where the anchor -> point segment clears the body box (slab test)."""
        A = self.anchors if anchors is None else anchors
        D = p3[None, :] - A
        inside = (A >= self.bmin) & (A <= self.bmax)
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (self.bmin[None, :] - A) / D
            t2 = (self.bmax[None, :] - A) / D
        par = np.abs(D) < 1e-12
        lo = np.where(par, np.where(inside, -np.inf, np.inf), np.minimum(t1, t2))
        hi = np.where(par, np.where(inside, np.inf, -np.inf), np.maximum(t1, t2))
        tmin = np.maximum(lo.max(1), 0.0)
        tmax = np.minimum(hi.min(1), 1.0)
        return ~(tmin <= tmax)


class Zones:
    """Zone sizes for the current speed plus the path-prediction policy:
    'worst'    - docs/06 s.2 as written: the person is assumed to stand still and the reachable disk
                 grows at v_ped = 1.5 m/s;
    'tracked'  - the person's tracked velocity is used and the disk grows with twice the track's
                 velocity uncertainty (at least 0.3 m/s);
    'tracked1' - as 'tracked' with one velocity sigma (a less conservative point on the same curve)."""

    def __init__(self, truck: Truck, v: float, policy: str = "tracked"):
        self.stop, self.warn, self.aware = dc.zones(truck.m, truck.d, abs(v) * 3.6)
        self.r_si = truck.r_si
        self.v = v
        self.policy = policy
        self.v_ped = truck.d["v_ped_mps"]
        self.static_v = np.array([-v, 0.0])
        self.sign = 1.0 if v > 0 else -1.0
        self.horizon = max(6.0, self.warn / max(abs(v), 0.1))
        self.L2, self.W2 = truck.L2, truck.W2

    def d_long(self, x):
        return (x - self.L2) if self.sign > 0 else (-self.L2 - x)


def ttc_path(p, vrel, r0, Z: Zones, growth: float = GROWTH):
    """Swept-path test (body frame, straight travel): when the leading face reaches the person's
    position along the travel axis, is the predicted disk (radius r0 + growth*t) inside the corridor
    the face sweeps? Returns (in_path, ttc). A person already alongside the body is not in the swept
    path; close proximity beside the body is handled by the hull-distance rules in risk_level."""
    ahead = Z.d_long(p[0])
    closing = -Z.sign * vrel[0]
    if ahead < -0.5 or closing <= 0.05:
        return False, math.inf
    t_face = max(ahead, 0.0) / closing
    if t_face > Z.horizon:
        return False, math.inf
    y = p[1] + vrel[1] * t_face
    if abs(y) <= Z.W2 + r0 + growth * t_face:
        return True, t_face
    return False, math.inf


class CvTrack:
    """Constant-velocity Kalman filter in the machine body frame. Prior: the person stands still in
    the world, so the relative velocity starts at -v_truck with a 0.8 m/s spread."""

    Q_ACC = 0.5  # m^2/s^3, white-acceleration PSD of a walking person (assumed)

    def __init__(self, z, sigma, prior_v, t):
        self.prior_v = np.asarray(prior_v, float)
        self.x = np.array([z[0], z[1], prior_v[0], prior_v[1]], float)
        self.P = np.diag([sigma ** 2, sigma ** 2, 0.64, 0.64])
        self.t = t

    def _fq(self, dt):
        F = np.eye(4)
        F[0, 2] = F[1, 3] = dt
        q, d2, d3 = self.Q_ACC, dt * dt / 2.0, dt ** 3 / 3.0
        Q = q * np.array([[d3, 0, d2, 0], [0, d3, 0, d2], [d2, 0, dt, 0], [0, d2, 0, dt]])
        return F, Q

    def update(self, z, sigma, t):
        F, Q = self._fq(max(t - self.t, 1e-3))
        x = F @ self.x
        P = F @ self.P @ F.T + Q
        R = np.eye(2) * sigma ** 2
        S = P[:2, :2] + R
        y = np.asarray(z, float) - x[:2]
        d2 = float(y @ np.linalg.solve(S, y))
        if d2 > 9.21:  # soft gate (99 %, 2 dof): down-weight jumps such as NLOS outliers
            S = P[:2, :2] + R * (d2 / 9.21)
        K = P[:, :2] @ np.linalg.inv(S)
        self.x = x + K @ y
        self.P = P - K @ P[:2, :]
        dv = self.x[2:] - self.prior_v  # a person walks at most ~2.5 m/s in the world
        sp = math.hypot(dv[0], dv[1])
        if sp > 2.5:
            self.x[2:] = self.prior_v + dv * (2.5 / sp)
        self.t = t

    def predict(self, t):
        """(position, velocity, 1-sigma position, 1-sigma velocity) at time t."""
        dt = t - self.t
        if dt > 0:
            F, Q = self._fq(dt)
            x, P = F @ self.x, F @ self.P @ F.T + Q
        else:
            x, P = self.x, self.P
        sp = math.sqrt(max(0.5 * (P[0, 0] + P[1, 1]), 1e-6))
        sv = math.sqrt(max(0.5 * (P[2, 2] + P[3, 3]), 1e-6))
        return x[:2], x[2:], sp, sv


def risk_level(p, vrel, sigma, Z: Zones, truck: Truck, sigma_v: float = 0.25) -> int:
    """Alarm level from a tracked position (docs/06 s.3, path-based per docs/06 s.2). The predicted
    disk starts at 2 sigma + buffer and grows with twice the track's velocity uncertainty."""
    r0 = 2.0 * sigma + BUFFER
    if Z.policy == "worst":
        in_path, ttc = ttc_path(p, Z.static_v, r0, Z, Z.v_ped)
    else:
        k = 1.0 if Z.policy == "tracked1" else 2.0
        in_path, ttc = ttc_path(p, vrel, r0, Z, max(0.3, k * sigma_v))
    dh = truck.hull_dist1(p[0], p[1]) - 2.0 * sigma
    if (in_path and (Z.d_long(p[0]) <= Z.stop or ttc <= 2.0)) or dh <= 1.0:
        return 4
    if (in_path and ttc <= 4.0) or dh <= Z.r_si:
        return 3
    if in_path or dh <= Z.warn:
        return 2
    if dh <= Z.aware:
        return 1
    return 0


class Hold:
    """Level holder: rises immediately, falls only after HOLD_S of lower readings."""

    def __init__(self):
        self.lvl, self.pending, self.t_pend = 0, None, 0.0

    def update(self, t, lvl):
        if lvl >= self.lvl:
            self.lvl, self.pending = lvl, None
        else:
            if self.pending is None:
                self.t_pend = t
            self.pending = lvl

    def level(self, t):
        if self.pending is not None and t - self.t_pend >= HOLD_S:
            self.lvl, self.pending = self.pending, None
        return self.lvl


# ---------------------------------------------------------------------------------------------
# Sensor state machines
# ---------------------------------------------------------------------------------------------
class UwbState:
    """Discovery blinks, session, rate-adaptive DS-TWR fixes, Gauss-Newton solve, alpha-beta track."""

    def __init__(self, uwb: UwbRanging, comp: dict, truck: Truck, rng, v, anchors=None):
        a = comp["assumptions"]
        self.uwb, self.truck = uwb, truck
        self.A = truck.anchors if anchors is None else anchors
        self.rates = a["uwb_rates_hz"]
        self.blink_s = a["uwb_blink_s"]
        self.cal_bias = rng.uniform(-comp["uwb"]["ranging_accuracy_m"], comp["uwb"]["ranging_accuracy_m"],
                                    len(self.A))
        self.session = False
        self.next_blink = rng.uniform(0.0, self.blink_s)
        self.next_fix = math.inf
        self.next_pred = 0.1
        self.track = None  # dict(p, v, sigma, t)
        self.t_last_ok = -math.inf
        self.raw_level = 0
        self.prior_v = np.array([-v, 0.0])  # a static person moves at -v_truck in the body frame

    def _solve(self, A, r, z, p0):
        """Damped Gauss-Newton (Levenberg-Marquardt) for (x, y) with the tag height known."""
        p = p0.copy()
        J = res = None
        for _ in range(10):
            dx, dy, dz = p[0] - A[:, 0], p[1] - A[:, 1], z - A[:, 2]
            dist = np.maximum(np.sqrt(dx * dx + dy * dy + dz * dz), 1e-6)
            J = np.column_stack((dx / dist, dy / dist))
            res = r - dist
            step = np.linalg.solve(J.T @ J + 0.01 * np.eye(2), J.T @ res)
            ns = math.hypot(step[0], step[1])
            if ns > 2.0:
                step *= 2.0 / ns
            p += step
            if ns < 1e-3:
                break
        return p, res, J

    def fix(self, rng, t, p3, body_nlos):
        A = self.A
        d = np.linalg.norm(A - p3[None, :], axis=1)
        ok, r, sig = self.uwb.measure(rng, d, body_nlos, self.cal_bias)
        ok &= self.truck.los(p3, A)
        idx = np.flatnonzero(ok)
        if idx.size == 0:
            return None
        self.t_last_ok = t
        if idx.size == 1:  # range only: fail-safe level from the range itself
            i = idx[0]
            rr = r[i] - 0.15
            return ("range", rr, A[i])
        Ai, ri, si = A[idx], r[idx], sig[idx]
        if self.track is not None and t - self.track.t < 1.0:
            p0 = self.track.predict(t)[0].copy()
        else:
            c = Ai[:, :2].mean(0)
            n = c / max(np.linalg.norm(c), 1e-6)
            p0 = c + n * ri.mean()
        p, res, J = self._solve(Ai, ri, p3[2], p0.astype(float))
        if idx.size >= 4 and np.max(np.abs(res)) > 0.4:  # residual screen: drop the worst anchor once
            keep = np.argsort(np.abs(res))[:-1]
            p, res, J = self._solve(Ai[keep], ri[keep], p3[2], p)
            si = si[keep]
        if np.max(np.abs(res)) > 3.0 or math.hypot(p[0], p[1]) > 300.0:  # inconsistent: fall back to range
            i = idx[int(np.argmin(r[idx]))]
            return ("range", r[i] - 0.15, A[i])
        try:
            cov = np.linalg.inv(J.T @ J)
            sigma = float(np.mean(si)) * math.sqrt(max(np.trace(cov), 0.0))
        except np.linalg.LinAlgError:
            sigma = 3.0
        if res.size >= 3:
            sigma = max(sigma, float(np.sqrt(np.mean(res ** 2))))
        sigma = min(max(sigma, 0.05), 3.0)
        if self.track is None or t - self.track.t > 1.0:
            self.track = CvTrack(p, sigma, self.prior_v, t)
        else:
            self.track.update(p, sigma, t)
        self.track.sigma_fix = sigma
        return ("pos",)

    def level_now(self, t, Z, out):
        """Level from the current track: Kalman prediction plus the fail-loud rule of docs/06 s.10
        (a silent tag's circle grows toward the machine at walking speed)."""
        if out is not None and out[0] == "range":
            rr, a = out[1], out[2]
            ahead = (a[0] * Z.sign) > 0
            if rr <= Z.stop and ahead:
                return 4
            if rr <= Z.r_si:
                return 3
            return 2 if rr <= Z.warn else (1 if rr <= Z.aware else 0)
        if self.track is None:
            return 0
        age = t - self.track.t
        if age > 3.0:
            self.track = None
            return 0
        p, v, sp, sv = self.track.predict(t)
        if age > 0.3:
            sp += 1.5 * (age - 0.3)
        return risk_level(p, v, sp, Z, self.truck, sv)


class RadarState:
    """Per-object detection, M-of-N confirmation, person classifier gate, alpha-beta track."""

    def __init__(self, radar, comp, truck, mount, boresight, rng, v):
        a = comp["assumptions"]
        self.radar, self.truck = radar, truck
        self.mount, self.bore = mount, boresight
        self.m_req, self.n_win = a["radar_confirm"]
        self.acc, self.dwell = a["classifier_acc"], a["classifier_dwell_s"]
        self.tracks = {}
        self.next = rng.uniform(0.0, radar.frame_s)
        self.prior_v = np.array([-v, 0.0])

    def frame(self, rng, t, objs, Z):
        best = 0
        for o in objs:
            if o["known"]:
                continue
            rx, ry = o["p"][0] - self.mount[0], o["p"][1] - self.mount[1]
            rh = math.hypot(rx, ry)
            rng3 = math.hypot(rh, o["h"] - self.mount[2])
            az = math.atan2(ry, rx) - self.bore
            az = (az + math.pi) % (2 * math.pi) - math.pi
            pd = self.radar.pd1(rng3, o["rcs"], az)
            hit = rng.random() < pd
            tr = self.tracks.get(o["id"])
            if tr is None:
                tr = self.tracks[o["id"]] = dict(hist=0, conf=False, t_conf=0.0, cls=None, trk=None, miss=0)
            tr["hist"] = ((tr["hist"] << 1) | int(hit)) & ((1 << self.n_win) - 1)
            if hit:
                r_m = rh + rng.normal(0.0, self.radar.sig_r)
                az_m = az + rng.normal(0.0, self.radar.az_sigma(az))
                pm = np.array([self.mount[0] + r_m * math.cos(self.bore + az_m),
                               self.mount[1] + r_m * math.sin(self.bore + az_m)])
                sig = math.hypot(self.radar.sig_r, rh * self.radar.az_sigma(az))
                if tr["trk"] is None:
                    tr["trk"] = CvTrack(pm, sig, self.prior_v, t)
                else:
                    tr["trk"].update(pm, sig, t)
                tr["miss"] = 0
            else:
                tr["miss"] += 1
            if not tr["conf"] and bin(tr["hist"]).count("1") >= self.m_req:
                tr["conf"], tr["t_conf"], tr["cls"] = True, t, None
            if tr["conf"] and tr["miss"] >= self.n_win:  # track lost: a new one needs a new classification
                tr.update(hist=0, conf=False, cls=None, trk=None, miss=0)
                continue
            if tr["conf"] and tr["cls"] is None and t - tr["t_conf"] >= self.dwell:
                p_person = self.acc if o["person"] else 1.0 - self.acc
                tr["cls"] = rng.random() < p_person
            if tr["conf"] and tr["cls"] and tr["trk"] is not None:
                p, vv, sp, sv = tr["trk"].predict(t)
                best = max(best, risk_level(p, vv, sp, Z, self.truck, sv))
        return best


# ---------------------------------------------------------------------------------------------
# One Monte Carlo run
# ---------------------------------------------------------------------------------------------
class World:
    """Built once per process: component models and the truck."""

    def __init__(self, comp, d, m):
        self.comp, self.a = comp, comp["assumptions"]
        self.truck = Truck(m, d, comp)
        self.uwb = UwbRanging(comp)
        self.uwb_v = UwbRanging(comp, vehicle_limit=True)
        self.lf = LfShell(comp, self.truck.coils)
        self.lf_keyon = LfShell(comp, self.truck.coils_keyon)
        self.awr = FmcwRadar(comp["radar_awr1843aop"], self.a)
        self.ars = Ars408(comp["radar_ars408"], self.a)
        self.rfid = UhfRfid(comp, comp["rfid_reader"]["tx_max_dbm_poe"])


def _pick(rng, mix: dict):
    keys = list(mix)
    return keys[int(rng.choice(len(keys), p=np.array([mix[k] for k in keys]) / sum(mix.values())))]


def sample_world(scn: dict, w: World, rng):
    tr, a = w.truck, w.a
    v = scn["v_kmh"] / 3.6
    kind = scn["kind"]
    posture = _pick(rng, scn["postures"])
    vp = np.zeros(2)
    lo, hi = a["v_walk_mps"]
    if kind == "behind":
        D = rng.uniform(12.0, 45.0)
        if rng.random() < 0.6:  # in or next to the reversing corridor
            p0 = np.array([-tr.L2 - D, rng.uniform(-tr.W2 - 1.5, tr.W2 + 1.5)])
        else:  # anywhere in the +/-60 deg cone behind the truck (docs/10 S01)
            phi = math.radians(rng.uniform(-60.0, 60.0))
            p0 = np.array([-tr.L2 - D * math.cos(phi), D * math.sin(phi)])
        u, s = rng.random(), rng.uniform(lo, hi)
        if u < 0.4:
            pass
        elif u < 0.7:
            vp = np.array([0.0, s if rng.random() < 0.5 else -s])
        elif u < 0.85:
            vp = np.array([s, 0.0])
        else:
            vp = np.array([-s, 0.0])
    elif kind == "behind_low":
        D = rng.uniform(8.0, 35.0)
        if rng.random() < 0.7:
            p0 = np.array([-tr.L2 - D, rng.uniform(-tr.W2 - 1.0, tr.W2 + 1.0)])
        else:
            phi = math.radians(rng.uniform(-45.0, 45.0))
            p0 = np.array([-tr.L2 - D * math.cos(phi), D * math.sin(phi)])
        if rng.random() < 0.3:
            s = rng.uniform(0.2, 0.6)
            vp = np.array([0.0, s if rng.random() < 0.5 else -s])
    elif kind == "beside":
        side = 1.0 if rng.random() < 0.5 else -1.0
        D = rng.uniform(-5.0, 30.0)
        p0 = np.array([-tr.L2 - D, side * (tr.W2 + rng.uniform(5.0, 12.0))])
        if rng.random() < 0.5:
            s = rng.uniform(lo, hi)
            vp = np.array([s if rng.random() < 0.5 else -s, 0.0])
    elif kind == "ahead":
        D = rng.uniform(40.0, 140.0)
        p0 = np.array([tr.L2 + D, rng.uniform(-tr.W2 - 1.0, tr.W2 + 1.0)])
        if rng.random() < 0.5:
            s = rng.uniform(0.3, 1.0)
            vp = np.array([0.0, s if rng.random() < 0.5 else -s])
    else:  # empty
        D, p0 = 40.0, np.array([1e4, 1e4])
    clutter = []
    if v < 0:  # reversing: rocks and berm segments behind the truck
        for i in range(rng.poisson(a["clutter_mean_count"])):
            clutter.append(dict(id=f"c{i}", w=np.array([-tr.L2 - rng.uniform(2.0, 40.0), rng.uniform(-15.0, 15.0)]),
                                h=0.6, rcs=rng.uniform(*a["clutter_rcs_dbsm"]), person=False,
                                known=rng.random() < a["clutter_known_fraction"]))
    t_end = min(32.0, (max(D, 0.0) + 2 * tr.L2 + 15.0) / abs(v))
    return dict(v=v, p0=p0, vp=vp, posture=posture, D=D, clutter=clutter, t_end=t_end,
                facing=rng.uniform(-math.pi, math.pi), side_aspect=rng.random() < 0.5,
                rfid_body=rng.random() < {"standing": 0.5, "bending": 0.6, "crouching": 0.6, "lying": 0.7}[posture],
                t_react=float(lognormal(rng, a["t_react_median_s"], a["t_react_sigma_ln"])))


def body_nlos(anchors, p, facing, posture, a):
    """Anchors inside the sector behind the person (helmet antenna shadowed by the body)."""
    alpha = math.pi * a["uwb_p_body_nlos"][posture]
    brg = np.arctan2(anchors[:, 1] - p[1], anchors[:, 0] - p[0])
    back = facing + math.pi
    diff = np.abs((brg - back + math.pi) % (2 * math.pi) - math.pi)
    return (diff < alpha).astype(float)


def braking_outcome(w: World, s: dict, t_alarm: float, t_grid, pw):
    tr = w.truck
    v, a_eff = s["v"], tr.a_eff
    if math.isfinite(t_alarm):
        tb = t_alarm + s["t_react"]
        tau = np.clip(t_grid - tb, 0.0, abs(v) / a_eff)
        disp = np.where(t_grid < tb, v * t_grid,
                        v * tb + math.copysign(1.0, v) * (abs(v) * tau - 0.5 * a_eff * tau ** 2))
        moving = t_grid < tb + abs(v) / a_eff
    else:
        disp, moving = v * t_grid, np.ones_like(t_grid, bool)
    dh = tr.hull_dist(pw[:, 0] - disp, pw[:, 1])
    r = w.a["person_radius_m"]
    hit = (dh <= r) & moving
    mins = float(dh[moving].min()) if moving.any() else float(dh.min())
    return bool(hit.any()), mins


WARMUP_S = 4.0  # the machine was already moving: sessions and tracks exist when the scenario starts


def simulate_run(w: World, key: str, seed: int, policy: str = "tracked") -> dict:
    scn = SCENARIOS[key]
    rng = np.random.default_rng(seed)
    a, tr = w.a, w.truck
    s = sample_world(scn, w, rng)
    v = s["v"]
    Z = Zones(tr, v, policy)
    posture, tagged = s["posture"], scn["tagged"]
    person = scn["kind"] != "empty"
    tag_h = a["tag_height_m"][posture]
    cfgs = scn["configs"]

    n = int((s["t_end"] + WARMUP_S) / DT) + 1
    t_grid = np.arange(n) * DT - WARMUP_S
    pw = s["p0"][None, :] + s["vp"][None, :] * t_grid[:, None]
    pb = pw.copy()
    pb[:, 0] -= v * t_grid

    uwb_sets = []
    if tagged:
        uwb_sets.append(("uwb", UwbState(w.uwb, w.comp, tr, rng, v)))
        if "Bv" in cfgs or "Cv" in cfgs:
            uwb_sets.append(("uwb_v", UwbState(w.uwb_v, w.comp, tr, rng, v)))
    mount, bore = (tr.rear_mount, math.pi) if v < 0 else (tr.front_mount, 0.0)
    radars = []
    if v < 0 and ("D" in cfgs or "E" in cfgs):
        radars = [("awr", RadarState(w.awr, w.comp, tr, mount, bore, rng, v)),
                  ("ars", RadarState(w.ars, w.comp, tr, mount, bore, rng, v))]
    rfid_mount = np.array([mount[0], 0.0, 2.0])
    t0 = float(t_grid[0])
    for _, st in uwb_sets:
        st.next_blink += t0
        st.next_pred += t0
    for _, rs in radars:
        rs.next += t0
    next_lf = t0 + rng.uniform(0.0, w.lf.slot_s)
    lf_k = int(rng.integers(0, len(tr.coils)))
    next_rfid = t0 + rng.uniform(0.0, w.rfid.round_s)
    rcs_person = a["person_rcs_dbsm"] + a["rcs_posture_db"][posture] + (a["person_rcs_side_db"] if s["side_aspect"] else 0.0)

    holds = {k: Hold() for k in ("rfid", "uwb", "uwb_v", "lf", "awr", "ars")}
    events = []
    seq = 0
    first3 = {c: math.inf for c in cfgs}
    first4 = {c: math.inf for c in cfgs}

    def push(t_eff, src, lvl):
        nonlocal seq
        heapq.heappush(events, (t_eff, seq, src, lvl))
        seq += 1

    for k in range(n):
        t = float(t_grid[k])
        p2 = pb[k]
        if person and tagged:
            p3 = np.array([p2[0], p2[1], tag_h])
            for name, st in uwb_sets:
                if not st.session and t >= st.next_blink:
                    st.next_blink = t + st.blink_s * rng.uniform(0.9, 1.1)
                    d = np.linalg.norm(tr.anchors - p3[None, :], axis=1)
                    nl = body_nlos(tr.anchors, p2, s["facing"], posture, a)
                    heard = st.uwb.blink_heard(rng, d, nl) & tr.los(p3)
                    if heard.any():
                        st.session, st.next_fix, st.t_last_ok = True, t + 0.05, t
                if st.session and t >= st.next_fix:
                    nl = body_nlos(tr.anchors, p2, s["facing"], posture, a)
                    out = st.fix(rng, t, p3, nl)
                    lvl = st.level_now(t, Z, out)
                    st.raw_level = lvl
                    push(t + PROC_S + ACT_S, name, lvl)
                    rate = st.rates["aware" if lvl <= 1 else ("warning" if lvl == 2 else "danger")]
                    st.next_fix = t + 1.0 / rate
                    st.next_pred = t + 0.1
                    if t - st.t_last_ok > 3.0 and st.track is None:  # session lost: back to discovery
                        st.session, st.next_fix = False, math.inf
                elif st.session and t >= st.next_pred:
                    lvl = st.level_now(t, Z, None)
                    push(t + PROC_S + ACT_S, name, lvl)
                    st.next_pred = t + 0.1
            if t >= next_lf:
                lp = np.array([p2[0], p2[1], LF_HEIGHT[posture]])
                hit = w.lf.hit(rng, lp, lf_k)
                if hit:
                    push(t + rng.uniform(*w.lf.uplink) / 1000.0 + PROC_S + ACT_S, "lf", 4)
                else:
                    push(t + PROC_S, "lf", 0)
                lf_k = (lf_k + 1) % len(tr.coils)
                next_lf += w.lf.slot_s
            if "A" in cfgs and t >= next_rfid:
                dx, dy = p2[0] - rfid_mount[0], p2[1] - rfid_mount[1]
                dd = math.sqrt(dx * dx + dy * dy + (tag_h - rfid_mount[2]) ** 2)
                off = abs(math.degrees((math.atan2(dy, dx) - bore + math.pi) % (2 * math.pi) - math.pi))
                ok, _ = w.rfid.read(rng, np.array(dd), off, float(s["rfid_body"]))
                push(t + 0.03, "rfid", 4 if bool(ok) else 0)
                next_rfid += w.rfid.round_s
        due = [(name, rs) for name, rs in radars if t >= rs.next]
        if due:
            objs = [dict(id=c["id"], p=c["w"] - np.array([v * t, 0.0]), h=c["h"], rcs=c["rcs"], person=False,
                         known=c["known"]) for c in s["clutter"]]
            if person:
                objs.append(dict(id="person", p=p2, h=RADAR_HEIGHT[posture], rcs=rcs_person, person=True,
                                 known=False))
            for name, rs in due:
                lvl = rs.frame(rng, t, objs, Z)
                push(t + 0.03 + ACT_S, name, lvl)
                rs.next += rs.radar.frame_s
        while events and events[0][0] <= t:
            _, _, src, lvl = heapq.heappop(events)
            holds[src].update(t, lvl)
        lv = {src: h.level(t) for src, h in holds.items()}
        cur = {"A": lv["rfid"], "B": lv["uwb"], "C": max(lv["uwb"], lv["lf"]),
               "D": max(lv["uwb"], lv["lf"], lv["awr"]), "E": max(lv["uwb"], lv["lf"], lv["ars"]),
               "Bv": lv["uwb_v"], "Cv": max(lv["uwb_v"], lv["lf"])}
        for c in cfgs:
            L = cur[c]
            if L >= 3 and t < first3[c]:
                first3[c] = t
            if L >= 4 and t < first4[c]:
                first4[c] = t

    # ---------------- ground truth and outcomes (extended grid so a braked truck is followed to rest)
    out = dict(scn=key, seed=seed, posture=posture, tagged=tagged, dist=s["D"])
    if not person:
        for c in cfgs:
            out[c] = dict(alarm=math.isfinite(first3[c]))
        return out
    t_ext = np.arange(t0, s["t_end"] + 6.0 + abs(v) / tr.a_eff, DT)
    pw_ext = s["p0"][None, :] + s["vp"][None, :] * t_ext[:, None]
    hit0, _ = braking_outcome(w, s, math.inf, t_ext, pw_ext)
    dh0 = tr.hull_dist(pw_ext[:, 0] - v * t_ext, pw_ext[:, 1])
    r_p = a["person_radius_m"]
    t_coll = float(t_ext[int(np.argmax(dh0 <= r_p))]) if hit0 else math.inf
    t_dz = math.inf
    if hit0:
        dl = (pw_ext[:, 0] - v * t_ext - tr.L2) if v > 0 else (-tr.L2 - (pw_ext[:, 0] - v * t_ext))
        dz = (((t_coll - t_ext) <= Z.horizon) & (dl <= Z.stop) & (t_ext <= t_coll)) | (dh0 <= 1.0)
        t_dz = float(t_ext[int(np.argmax(dz))]) if dz.any() else t_coll
    out.update(at_risk=hit0, t_coll=t_coll, t_dz=t_dz, stop=Z.stop)
    for c in cfgs:
        t3, t4 = first3[c], first4[c]
        hit, mins = braking_outcome(w, s, t3, t_ext, pw_ext)
        k3 = int(round((t3 - t0) / DT)) if math.isfinite(t3) else None
        d_first = float(tr.hull_dist1(pb[k3, 0], pb[k3, 1])) if k3 is not None and k3 < n else math.nan
        lat = math.nan
        if hit0:
            if math.isfinite(t4) and t4 <= t_coll:
                lat = max(0.0, t4 - t_dz)
            else:
                lat = math.inf
        out[c] = dict(alarm=math.isfinite(t3), t3=t3, t4=t4, collided=hit, min_clear=mins, d_first=d_first,
                      latency=lat, lead=(t_coll - t3) if (hit0 and math.isfinite(t3)) else math.nan)
    return out


# ---------------------------------------------------------------------------------------------
# S03 start-inhibit at key-on (stationary truck)
# ---------------------------------------------------------------------------------------------
def _point_at_hull_distance(rng, tr: Truck, dd: float):
    L2, W2 = tr.L2, tr.W2
    seg = [2 * W2, 2 * L2, 2 * W2, 2 * L2]  # front, left, rear, right faces (counter-clockwise)
    arc = 0.5 * math.pi * dd
    total = sum(seg) + 4 * arc
    u = rng.uniform(0.0, total)
    corners = [(L2, W2), (-L2, W2), (-L2, -W2), (L2, -W2)]
    starts = [(L2, -W2), (L2, W2), (-L2, W2), (-L2, -W2)]
    dirs = [(0, 1), (-1, 0), (0, -1), (1, 0)]
    normals = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    for i in range(4):
        if u < seg[i]:
            sx, sy = starts[i]
            return np.array([sx + dirs[i][0] * u + normals[i][0] * dd, sy + dirs[i][1] * u + normals[i][1] * dd])
        u -= seg[i]
        if u < arc:
            cx, cy = corners[i]
            a0 = math.atan2(normals[i][1], normals[i][0])
            ang = a0 + u / max(dd, 1e-6)
            return np.array([cx + dd * math.cos(ang), cy + dd * math.sin(ang)])
        u -= arc
    return np.array([L2 + dd, 0.0])


def _uwb_keyon(w: World, anchors, p2, p3, facing, posture, rng):
    """Three UWB polls at key-on. Returns (block, positioned, conservative hull distance)."""
    tr = w.truck
    st = UwbState(w.uwb, w.comp, tr, rng, 0.0, anchors)
    block, fixed, d_est = False, False, math.inf
    for j in range(3):
        out = st.fix(rng, 0.05 * j, p3, body_nlos(anchors, p2, facing, posture, w.a))
        if out is None:
            continue
        if out[0] == "range":
            block |= out[1] <= tr.r_si
        else:
            fixed = True
            de = tr.hull_dist1(st.track.x[0], st.track.x[1]) - 2 * st.track.sigma_fix
            d_est = min(d_est, de)
            block |= de <= tr.r_si
    return block, fixed, d_est


def simulate_start_inhibit(w: World, n: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    tr, a = w.truck, w.a
    cats = {"0-2 m": (0.0, 2.0, 0.20), "2-4.2 m": (2.0, tr.r_si, 0.30), "grey 4.2-5.2 m": (tr.r_si, tr.r_si + 1.0, 0.10),
            "5.2-9 m": (tr.r_si + 1.0, 9.0, 0.30), "under the body": (None, None, 0.10)}
    names = list(cats)
    probs = np.array([cats[k][2] for k in names])
    rows = {k: dict(n=0, A=0, B=0, LF=0, C=0, C7=0) for k in names}
    rfid_mounts = [(np.array([tr.L2 + 0.15, 0.0, 2.0]), 0.0), (np.array([-(tr.L2 + 0.15), 0.0, 2.0]), math.pi)]
    for _ in range(n):
        cat = names[int(rng.choice(len(names), p=probs))]
        lo, hi, _ = cats[cat]
        if lo is None:
            p2 = np.array([rng.uniform(-tr.L2 + 1.0, tr.L2 - 1.0), rng.uniform(-tr.W2 + 0.6, tr.W2 - 0.6)])
            posture = "lying" if rng.random() < 0.5 else "crouching"
        else:
            p2 = _point_at_hull_distance(rng, tr, rng.uniform(max(lo, 0.05), hi))
            posture = _pick(rng, {"standing": 0.6, "bending": 0.15, "crouching": 0.15, "lying": 0.10})
        p3 = np.array([p2[0], p2[1], a["tag_height_m"][posture]])
        facing = rng.uniform(-math.pi, math.pi)
        # UWB: three polls at key-on, with the pilot anchors (6) and with the canopy anchor added (7)
        uwb6 = _uwb_keyon(w, tr.anchors, p2, p3, facing, posture, rng)
        uwb7 = _uwb_keyon(w, tr.anchors_full, p2, p3, facing, posture, rng)
        uwb_block = uwb6[0]
        # LF: full-power sweep of all coils. Fused rule: the UWB position decides where it exists; LF
        # decides where UWB cannot position the tag (under or tight against the hull) or where two or more
        # coils hear it (inside the footprint, beside the body); an LF hit also confirms a UWB fix that
        # lands just outside the zone, because NLOS bias always pushes UWB estimates outward.
        # Monotonic: LF can only add a block.
        heard, r_est = w.lf_keyon.range_estimate(rng, np.array([p2[0], p2[1], LF_HEIGHT[posture]]))
        n_heard = int(heard.sum())
        lf_only = n_heard >= 1
        lf_near = bool(np.any(heard & (r_est <= tr.r_si)))  # RSSI distance (broadside, conservative) inside the zone

        def fused(u):
            block, fixed, d_est = u
            return (block or n_heard >= 2 or lf_near
                    or (n_heard >= 1 and (not fixed or d_est <= tr.r_si + 1.0)))
        # RFID baseline: front and rear antennas only
        rf_block = False
        for m_, bore in rfid_mounts:
            dx, dy = p2[0] - m_[0], p2[1] - m_[1]
            dd = math.sqrt(dx * dx + dy * dy + (p3[2] - m_[2]) ** 2)
            off = abs(math.degrees((math.atan2(dy, dx) - bore + math.pi) % (2 * math.pi) - math.pi))
            for _r in range(4):
                ok, _ = w.rfid.read(rng, np.array(dd), off, 0.5)
                rf_block |= bool(ok)
        r = rows[cat]
        r["n"] += 1
        r["A"] += rf_block
        r["B"] += uwb_block
        r["LF"] += lf_only
        r["C"] += fused(uwb6)
        r["C7"] += fused(uwb7)
    decision_s = BOOT_S + len(tr.coils) * w.lf.slot_s + 3 * 0.05 + PROC_S
    return dict(rows=rows, decision_s=decision_s, r_si=tr.r_si)
