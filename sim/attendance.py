"""Shift-entry attendance with biometric + helmet checks at the gate / lamp-room dock.

Attendance is valid only when (1) the fingerprint verifies the person, (2) the person's own issued
helmet with its personal unit (SPU) is present, and (3) the helmet is worn and the SPU passes its self-test.
The SPU is the collision-avoidance tag, so this check is what ties a person to the tag that protects them.

Configurations
  A  Fingerprint 1:N only (GT-521F52) - today's attendance terminal
  B  Fingerprint 1:N + the person's helmet UHF tag must be read (GT-521F52 + Impinj R700/M730)
  C  Helmet UHF tags claim the identity, fingerprint 1:k on the claimed templates (R503), SPU worn and
     self-test status over 865 MHz (SX1262), FDC1004 worn sensor
  D  The SPU itself claims the identity by UWB ranging to a gate anchor (DWM3000), fingerprint 1:1 (R503),
     worn and self-test status in the same UWB exchange

Outputs: service time and throughput per gate, queue waits for a shift change, exceptions, PPE violations
caught, false matches (misattributed records), and the UHF reader-power trade-off.
"""
from __future__ import annotations

import math

import numpy as np

from common import lognormal
from sensors import FingerprintReader, UhfRfid, WornSensor

CONFIGS = {
    "A": "Fingerprint 1:N only (GT-521F52)",
    "B": "Fingerprint 1:N + helmet UHF tag present (GT-521F52 + R700/M730)",
    "C": "Helmet UHF claim + fingerprint 1:k (R503) + SPU worn/self-test",
    "D": "SPU UWB claim + fingerprint 1:1 (R503) + SPU worn/self-test",
}
VIOLATIONS = ("strap_open", "carried_hand", "carried_underarm", "no_helmet", "swapped", "spu_dead")
HOST_1TON_S = 1.0  # gate computer matches the captured template against the full gallery


class Gate:
    def __init__(self, comp: dict, uhf_tx_dbm: float | None = None):
        self.comp, self.a = comp, comp["assumptions"]
        self.r503 = FingerprintReader(comp["fp_r503"], self.a, "1to1")
        self.gt521 = FingerprintReader(comp["fp_gt521f52"], self.a, "1toN")
        self.rfid = UhfRfid(comp, self.a["uhf_gate_tx_dbm"] if uhf_tx_dbm is None else uhf_tx_dbm)
        self.worn = WornSensor(comp)

    # -- UHF: which helmet tags are read during the verification window
    def uhf_reads(self, rng, own_present, carried, queue_next, adjacent, window_s):
        a, rf = self.a, self.rfid
        n = max(1, int(window_s / rf.round_s))

        def read(d, off, body):
            persist = rng.normal(0.0, a["rfid_shadow_db"])
            fast = rng.normal(0.0, 1.5, n)
            fwd = rf.p_tag(d, off, body) + persist + fast
            rev = rf.p_backscatter(d, off, body) + 2 * persist + 2 * fast
            return bool(np.any((fwd >= rf.sens_tag) & (rev >= rf.sens_rdr)))

        own = own_present and read(rng.uniform(*a["own_tag_m"]) + (0.5 if carried else 0.0), rng.uniform(0, 20),
                                   float(rng.random() < (0.5 if carried else 0.2)))
        nxt = queue_next and read(rng.uniform(*a["queue_spacing_m"]), rng.uniform(10, 35), float(rng.random() < 0.2))
        adj = adjacent and read(rng.uniform(*a["adjacent_lane_m"]), rng.uniform(40, 70), float(rng.random() < 0.5))
        return own, nxt, adj

    # -- one fingerprint attempt; returns (time, genuine accepted, false match)
    def attempt(self, rng, reader, w, others):
        t = reader.attempt_s(rng)
        if w["fte"]:
            return t, False, False
        ok = reader.genuine_accepted(rng, w["difficult"])
        fm = others > 0 and reader.impostor_accepted(rng, others)
        return t, ok, fm

    def serve(self, rng, cfg: str, w: dict, n_gallery: int, queue_next: bool, adjacent: bool) -> dict:
        a = self.a
        st = w["helmet"]
        out = dict(time=a["t_walk_in_s"], admitted=True, caught=None, exception=False, misattributed=False)
        helmet_present = st != "no_helmet"
        carried = st.startswith("carried")

        def supervisor():
            out["time"] += a["t_supervisor_s"]
            out["exception"] = True

        if cfg in ("A", "B"):
            for _ in range(a["max_attempts"]):
                t, ok, fm = self.attempt(rng, self.gt521, w, n_gallery - 1)
                out["time"] += t
                if ok or fm:
                    out["misattributed"] = fm and not ok
                    break
            else:
                if w["fte"]:
                    out["time"] += a["t_alternate_credential_s"]
                else:
                    supervisor()
            if cfg == "B":
                if not helmet_present:
                    out.update(caught="no_helmet", admitted=False)
                elif st == "swapped":  # the person's own tag is not in the field
                    out.update(caught="swapped")
                    out["time"] += a["t_swap_resolution_s"]
                else:
                    seen = False
                    for _ in range(3):  # initial window, then two "step closer" re-reads
                        own, _, _ = self.uhf_reads(rng, True, carried, queue_next, adjacent, 1.5)
                        if own:
                            seen = True
                            break
                        out["time"] += 2.0
                    if not seen:
                        supervisor()
            out["time"] += a["t_turnstile_s"]
            return out

        # ---- C and D: claim -> 1:k / 1:1 verification -> host 1:N fallback -> SPU status
        if cfg == "C":
            own_tag_present = helmet_present and st != "swapped"
            own, nxt, adj = self.uhf_reads(rng, helmet_present, carried, queue_next, adjacent, 1.5)
            # in the swapped case the tag that is read belongs to the colleague, not to this person
            claim_own = own and own_tag_present
            k = int(own) + int(nxt) + int(adj)
            spu_link = st != "spu_dead"  # status arrives over 865 MHz from a live SPU
        else:
            claim_own = helmet_present and st not in ("swapped", "spu_dead")
            k = int(helmet_present and st != "spu_dead")  # the SPU within 0.8 m of the reader point
            spu_link = k == 1
        reader = self.r503
        identified = False
        for _ in range(a["max_attempts"]):
            t, ok, fm = self.attempt(rng, reader, w, max(k - int(claim_own), 0))
            out["time"] += t + a["match_1to1_s"] * max(k - 1, 0)
            if ok and claim_own:
                identified = True
                break
            if fm:  # matched one of the wrong candidates
                out["misattributed"] = True
                identified = True
                break
            if ok and not claim_own:  # own template not among the claims: identify on the gate computer
                out["time"] += HOST_1TON_S
                if reader.impostor_accepted(rng, n_gallery - 1):
                    out["misattributed"] = True
                identified = True
                break
        if not identified:
            if w["fte"]:
                out["time"] += a["t_alternate_credential_s"]
            else:
                supervisor()
        # helmet / SPU checks
        if not helmet_present:
            out.update(caught="no_helmet", admitted=False)
        elif st == "swapped":
            out.update(caught="swapped")
            out["time"] += a["t_swap_resolution_s"]
        elif cfg == "C" and not claim_own:
            out["time"] += 2.0  # own tag missed: "step closer" and re-read
        if helmet_present and st != "swapped":
            if not spu_link or st == "spu_dead":
                out.update(caught="spu_dead", admitted=False)
            else:
                out["time"] += a["status_query_s"] if cfg == "C" else 0.1
                on_head, strap = self.worn.worn_flag(rng, st)
                if not on_head:
                    out["time"] += a["t_put_on_helmet_s"]
                    if carried:
                        out["caught"] = st
                    else:
                        out["false_flag"] = True  # helmet was worn correctly
                elif not strap:
                    out["time"] += a["t_fix_strap_s"]
                    if st == "strap_open":
                        out["caught"] = st
        out["time"] += a["t_turnstile_s"]
        return out


def sample_workers(rng, a: dict, n: int) -> list[dict]:
    lo, mode, hi = a["arrival_window_min"]
    arr = np.sort(rng.triangular(lo, mode, hi, n) * 60.0)
    mix = a["helmet_state_mix"]
    states, p = list(mix), np.array(list(mix.values()), float)
    out = []
    for i in range(n):
        u = rng.random()
        out.append(dict(i=i, arrival=float(arr[i]), fte=u < a["finger_fte_fraction"],
                        difficult=a["finger_fte_fraction"] <= u < a["finger_fte_fraction"] + a["finger_difficult_fraction"],
                        helmet=states[int(rng.choice(len(states), p=p / p.sum()))]))
    return out


def simulate_shift(comp: dict, cfg: str, n_gates: int, seed: int, n_workers: int | None = None) -> dict:
    """Central FIFO queue feeding n_gates identical gates (worker takes the first gate to free up)."""
    a = comp["assumptions"]
    rng_pop = np.random.default_rng(seed)
    n = n_workers or a["shift_workers"]
    workers = sample_workers(rng_pop, a, n)
    gate = Gate(comp)
    free = np.full(n_gates, -1e9)
    waits, services, ends = [], [], []
    caught = {v: 0 for v in VIOLATIONS}
    present = {v: 0 for v in VIOLATIONS}
    exc = mis = false_flags = 0
    for k, w in enumerate(workers):
        rng = np.random.default_rng((seed, k, ord(cfg)))
        g = int(np.argmin(free))
        start = max(w["arrival"], free[g])
        queue_next = k + 1 < n and workers[k + 1]["arrival"] <= start
        adjacent = n_gates > 1 and rng.random() < 0.7
        r = gate.serve(rng, cfg, w, n, queue_next, adjacent)
        free[g] = start + r["time"]
        waits.append(start - w["arrival"])
        services.append(r["time"])
        ends.append(free[g])
        if w["helmet"] in present:
            present[w["helmet"]] += 1
            caught[w["helmet"]] += r["caught"] == w["helmet"]
        exc += r["exception"]
        mis += r["misattributed"]
        false_flags += r.get("false_flag", False)
    waits, services, ends = map(np.array, (waits, services, ends))
    return dict(cfg=cfg, gates=n_gates, n=n, wait_p50=float(np.percentile(waits, 50)),
                wait_p95=float(np.percentile(waits, 95)), wait_max=float(waits.max()),
                service_mean=float(services.mean()), service_p95=float(np.percentile(services, 95)),
                last_out_min=float(ends.max() / 60.0), late=int((ends > 0.0).sum()),
                exceptions=exc, misattributed=mis, false_flags=false_flags, caught=caught, present=present)


def uhf_power_sweep(comp: dict, powers, n: int = 4000, seed: int = 5) -> dict:
    """Gate reader power vs: own helmet tag missed in a 1.5 s window, next person's tag read, tag in
    the adjacent lane read."""
    rng = np.random.default_rng(seed)
    res = dict(power=[], miss=[], next=[], adjacent=[], erp_ok=[])
    for p in powers:
        g = Gate(comp, uhf_tx_dbm=p)
        m = nx = ad = 0
        for _ in range(n):
            own, nxt, adj = g.uhf_reads(rng, True, False, True, True, 1.5)
            m += not own
            nx += nxt
            ad += adj
        res["power"].append(p)
        res["miss"].append(m / n)
        res["next"].append(nx / n)
        res["adjacent"].append(ad / n)
        res["erp_ok"].append(g.rfid.erp_ok)
    return res


def false_match_table(comp: dict, n_shift: int) -> list[tuple]:
    """Outsider acceptance: probability that a finger that is NOT the claimed person's (an outsider, or
    a colleague marking someone else) is accepted, per attempt, with the datasheet FAR applied per
    template compared. Returns (mode, probability, attempts until a 50 % chance of one acceptance)."""
    far = comp["fp_r503"]["far"]
    rows = []
    for label, k in (("1:1 (SPU claim, config D)", 1), ("1:k, k = 3 (UHF claim, config C)", 3),
                     (f"1:N, N = {n_shift} (one shift's gallery, configs A/B)", n_shift),
                     (f"1:N, N = {comp['fp_gt521f52']['capacity']} (GT-521F52 full)", comp["fp_gt521f52"]["capacity"])):
        p = 1.0 - (1.0 - far) ** k
        rows.append((label, p, math.log(0.5) / math.log(1.0 - p)))
    return rows


def first_sighting(comp: dict, n: int = 20000, seed: int = 9, heartbeat_s: float = 60.0, pdr: float = 0.98):
    """Time from the gate to the SPU's first in-pit sighting by the twin (event-driven heartbeat <= 60 s)."""
    rng = np.random.default_rng(seed)
    t = rng.uniform(0.0, heartbeat_s, n)
    lost = rng.random(n) >= pdr
    while lost.any():
        t[lost] += heartbeat_s
        lost[lost] = rng.random(lost.sum()) >= pdr
    return dict(p50=float(np.percentile(t, 50)), p99=float(np.percentile(t, 99)),
                p_late_5min=float(np.mean(t > 300.0)))
