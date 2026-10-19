"""Sensor models driven by datasheet parameters (components.toml).

Each class turns datasheet numbers into what the safety controller would actually see: a range
with noise, a detection with a probability, a packet that arrives or not, a fingerprint match that
is accepted or not. Anything not on a datasheet comes from [assumptions] and is named as such.
"""
from __future__ import annotations

import math

import numpy as np

from common import C_LIGHT, K_T0, db2lin, dc, fspl_db, lognormal, p_link


# ---------------------------------------------------------------------------------------------
# UWB two-way ranging: Qorvo DWM3000 (D1, D2)
# ---------------------------------------------------------------------------------------------
class UwbRanging:
    """DS-TWR between hull anchors and a helmet tag.

    Received power = sensitivity + datasheet link budget - free-space loss - body loss + shadowing.
    D2 Table 12 gives the link budget (89 dB at 6.8 Mb/s with the 9 dB gating gain); the 1 % PER
    sensitivity anchors the frame-success curve. Range noise follows D2 Table 14 (1.5 cm at -85 dBm)
    and grows as 1/sqrt(SNR); the calibrated +/-6 cm accuracy is a fixed bias per anchor.
    """

    def __init__(self, comp: dict, vehicle_limit: bool = False):
        u, a = comp["uwb"], comp["assumptions"]
        self.f_hz = u["fc_mhz"] * 1e6
        self.sens = u["sens_dbm_6m8"]
        self.lb = float(u["link_budget_db_6m8"])
        if vehicle_limit:  # anchor -> tag transmits at the vehicle-mounted limit; the weaker leg sets the link
            self.lb -= u["tx_psd_dbm_per_mhz"] - a["uwb_vehicle_limit_dbm_per_mhz"]
        self.std_ref, self.p_ref = u["ranging_std_m"], u["ranging_std_ref_dbm"]
        self.cal = u["ranging_accuracy_m"]
        self.shadow = a["uwb_shadow_db"]
        self.body_loss = a["uwb_body_loss_db"]
        self.nlos_mean, self.nlos_sd = a["uwb_nlos_bias_mean_m"], a["uwb_nlos_sigma_m"]

    def prx_dbm(self, d, body_nlos):
        return self.sens + self.lb - fspl_db(d, self.f_hz) - self.body_loss * np.asarray(body_nlos, float)

    def sigma_m(self, prx):
        return np.clip(self.std_ref * 10.0 ** ((self.p_ref - prx) / 20.0), self.std_ref, 0.30)

    def blink_heard(self, rng, d, body_nlos):
        prx = self.prx_dbm(d, body_nlos) + rng.normal(0.0, self.shadow, np.shape(d))
        return rng.random(np.shape(d)) < p_link(prx, self.sens)

    def measure(self, rng, d, body_nlos, cal_bias):
        """Vectorised over anchors. Returns (exchange ok, measured range, 1-sigma noise)."""
        shape = np.shape(d)
        prx = self.prx_dbm(d, body_nlos) + rng.normal(0.0, self.shadow, shape)
        ok = rng.random(shape) < p_link(prx, self.sens) ** 3  # poll, response, final
        sig = self.sigma_m(prx)
        r = d + cal_bias + sig * rng.standard_normal(shape)
        nl = np.asarray(body_nlos, bool)
        r = r + nl * (rng.exponential(self.nlos_mean, shape) + rng.normal(0.0, self.nlos_sd, shape))
        return ok, r, sig

    def p_exchange_vs_distance(self, d, body_nlos=0.0, n=4000, seed=1):
        rng = np.random.default_rng(seed)
        sh = rng.normal(0.0, self.shadow, (n, 1))
        prx = self.prx_dbm(np.asarray(d)[None, :], body_nlos) + sh
        return (p_link(prx, self.sens) ** 3).mean(0)


# ---------------------------------------------------------------------------------------------
# LF magnetic shell: 125 kHz hull coils -> AS3932 3-D wake-up receiver (D3)
# ---------------------------------------------------------------------------------------------
class LfShell:
    """Dipole near field |B| ~ m/r^3 * sqrt(1 + 3cos^2(theta)) / 2, normalised so that the AS3932
    sensitivity is reached on the coil axis at r_on (set by the coil current). A 3-axis receiver
    sees the full field magnitude, so posture and orientation do not matter; the body is transparent
    at 125 kHz. +/-3 dB field error (sigma 1.5 dB) gives about +/-12 % distance error."""

    def __init__(self, comp: dict, coils: list[dict]):
        lf, a = comp["lf"], comp["assumptions"]
        self.sigma = a["lf_sigma_db"]
        self.pos = np.array([c["pos"] for c in coils], float)
        self.axis = np.array([c["axis"] for c in coils], float)
        self.r_on = np.array([c["r_on"] for c in coils], float)
        sym = 1.0 / lf["symbol_rate_sps"]
        preamble = max(lf["preamble_min_ms"] / 1000.0, 4 * sym)
        # carrier burst (4 half-bits) + preamble + 16-bit wake-up pattern + 16 data bits (machine/coil id)
        self.telegram_s = lf["settle_us"] * 1e-6 + 2 * sym + preamble + lf["pattern_bits"] * sym + 16 * sym
        self.slot_s = math.ceil(self.telegram_s * 1000 / 5.0) * 5.0 / 1000  # rounded up to 5 ms
        self.uplink = a["lf_uplink_ms"]

    def field_db(self, p):
        """Field of every coil relative to the wake-up threshold (dB) at point p (x, y, z)."""
        rv = np.asarray(p, float)[None, :] - self.pos
        r = np.maximum(np.linalg.norm(rv, axis=1), 0.2)
        cos = np.einsum("ij,ij->i", rv, self.axis) / r
        f = np.sqrt(1.0 + 3.0 * cos ** 2) / 2.0
        return 20.0 * np.log10((self.r_on / r) ** 3 * f)

    def hit(self, rng, p, k):
        return bool(self.field_db(p)[k] + rng.normal(0.0, self.sigma) >= 0.0)

    def range_estimate(self, rng, p):
        """Start-inhibit sweep: per coil, measured field -> conservative distance (broadside assumption)."""
        fd = self.field_db(p) + rng.normal(0.0, self.sigma, len(self.r_on))
        heard = fd >= 0.0
        r_est = self.r_on * 0.5 ** (1 / 3) * 10.0 ** (-fd / 60.0)
        return heard, r_est


# ---------------------------------------------------------------------------------------------
# FMCW radar chip: TI AWR1843AOP / IWR6843AOP (D4, D5) through the radar equation
# ---------------------------------------------------------------------------------------------
class FmcwRadar:
    """SNR = EIRP * RCS * lambda^2 * T_meas * N_rx / ((4 pi)^3 R^4 k T0 EINF L).

    EIRP and EINF are the datasheet's antenna-inclusive figures, so no separate antenna gains are
    needed. The beam rolls off to -8 dB (RX) and -6 dB (TX) at +/-60 deg (D4), i.e. up to 14 dB
    two-way at the edge. Detection per frame: Swerling-1 target, CFAR at P_fa."""

    def __init__(self, spec: dict, a: dict):
        self.name = spec["part"]
        self.lam = C_LIGHT / (spec["f_ghz"] * 1e9)
        self.eirp_w = float(db2lin(spec["eirp_dbm"] - 30.0))
        self.einf = float(db2lin(spec["einf_db"]))
        self.loss = float(db2lin(a["radar_loss_db"]))
        self.t_meas = a["radar_chirps"] * a["radar_tc_us"] * 1e-6
        self.n_rx = spec["n_rx"]
        slope = a["radar_slope_mhz_per_us"] * 1e12
        f_if = min(a["radar_fs_msps"] * 1e6, spec["if_bw_mhz"] * 1e6)
        self.r_max = f_if * C_LIGHT / (2.0 * slope)
        self.range_res = C_LIGHT / (2.0 * slope * a["radar_tc_us"] * 1e-6)
        self.half = math.radians(spec["beam_half_deg"])
        self.pfa = a["radar_pfa"]
        self.frame_s = a["radar_frame_ms"] / 1000.0
        self.sig_r, self.sig_az = a["radar_range_sigma_m"], math.radians(a["radar_az_sigma_deg"])

    def snr(self, r, rcs_dbsm, az=0.0):
        r = np.maximum(np.asarray(r, float), 0.5)
        edge = 14.0 * (np.asarray(az, float) / self.half) ** 2
        num = self.eirp_w * db2lin(rcs_dbsm - edge) * self.lam ** 2 * self.t_meas * self.n_rx
        return num / ((4 * math.pi) ** 3 * r ** 4 * K_T0 * self.einf * self.loss)

    def pd(self, r, rcs_dbsm, az=0.0):
        inside = (np.abs(az) <= self.half) & (np.asarray(r) <= self.r_max)
        return np.where(inside, self.pfa ** (1.0 / (1.0 + self.snr(r, rcs_dbsm, az))), 0.0)

    def pd1(self, r, rcs_dbsm, az):
        """Scalar fast path of pd() for the per-frame loop."""
        if abs(az) > self.half or r > self.r_max:
            return 0.0
        r = max(r, 0.5)
        edge = 14.0 * (az / self.half) ** 2
        snr = (self.eirp_w * 10.0 ** ((rcs_dbsm - edge) / 10.0) * self.lam ** 2 * self.t_meas * self.n_rx
               / ((4 * math.pi) ** 3 * r ** 4 * K_T0 * self.einf * self.loss))
        return self.pfa ** (1.0 / (1.0 + snr))

    def az_sigma(self, az):
        return self.sig_az


class Ars408:
    """Continental ARS 408-21 (D6): detection envelope from the datasheet, scaled to a person's RCS
    with the radar-equation law R ~ RCS^(1/4); 72 ms cycle; near-range accuracy from D6."""

    def __init__(self, spec: dict, a: dict):
        self.name = spec["part"]
        self.spec = spec
        self.frame_s = spec["cycle_ms"] / 1000.0
        self.ref = a["ars408_ref_rcs_dbsm"]
        self.half = math.radians(spec["near_edge_half_deg"])
        self.sig_r = spec["range_acc_near_m"] / 2.0
        self.r_max = spec["far_range_m"]

    def envelope(self, az, rcs_dbsm):
        s = self.spec
        a = np.degrees(np.abs(np.asarray(az, float)))
        near = np.where(a <= s["near_half_deg"], s["near_range_m"],
                        np.interp(a, [s["near_half_deg"], s["near_edge_half_deg"]],
                                  [s["near_range_m"], s["near_edge_range_m"]]))
        near = np.where(a <= s["near_edge_half_deg"], near, 0.0)
        far = np.where(a <= s["far_half_deg"], s["far_range_m"], 0.0)
        return np.maximum(near, far) * 10.0 ** ((np.asarray(rcs_dbsm, float) - self.ref) / 40.0)

    def pd(self, r, rcs_dbsm, az=0.0):
        env = self.envelope(az, rcs_dbsm)
        x = (np.asarray(r, float) - env) / np.maximum(0.05 * env, 0.5)
        return np.where(env > 0, 0.95 / (1.0 + np.exp(np.clip(x, -50, 50))), 0.0)

    def pd1(self, r, rcs_dbsm, az):
        s = self.spec
        a = math.degrees(abs(az))
        if a > s["near_edge_half_deg"]:
            return 0.0
        if a <= s["near_half_deg"]:
            near = s["near_range_m"]
        else:
            f = (a - s["near_half_deg"]) / (s["near_edge_half_deg"] - s["near_half_deg"])
            near = s["near_range_m"] + f * (s["near_edge_range_m"] - s["near_range_m"])
        env = max(near, s["far_range_m"] if a <= s["far_half_deg"] else 0.0)
        env *= 10.0 ** ((rcs_dbsm - self.ref) / 40.0)
        x = max(min((r - env) / max(0.05 * env, 0.5), 50.0), -50.0)
        return 0.95 / (1.0 + math.exp(x))

    def az_sigma(self, az):
        acc = np.interp(np.degrees(abs(az)), [0, 45, 60], self.spec["az_acc_near_deg"])
        return math.radians(acc / 2.0)


# ---------------------------------------------------------------------------------------------
# Passive UHF RFID: Impinj R700 reader + M730 helmet inlay (D9, D10)
# ---------------------------------------------------------------------------------------------
class UhfRfid:
    """Forward link (reader -> tag chip) must exceed the M730 read sensitivity; the backscatter must
    exceed the R700 receive sensitivity. Parabolic antenna beam (3 dB at the half-beamwidth)."""

    def __init__(self, comp: dict, tx_dbm: float):
        r, t, a = comp["rfid_reader"], comp["rfid_tag"], comp["assumptions"]
        self.f_hz = r["f_mhz"] * 1e6
        self.tx = tx_dbm
        self.g_ant, self.half = a["rfid_ant_gain_dbic"], a["rfid_ant_half_deg"]
        self.cable, self.pol = a["rfid_cable_db"], a["rfid_pol_loss_db"]
        self.g_tag, self.body = a["rfid_tag_gain_dbi"], a["rfid_body_loss_db"]
        self.mod, self.shadow = a["rfid_mod_loss_db"], a["rfid_shadow_db"]
        self.sens_tag, self.sens_rdr = t["read_sens_dbm"], r["rx_sens_dbm"]
        self.round_s = a["rfid_round_ms"] / 1000.0
        self.eirp = tx_dbm + self.g_ant - self.cable
        self.erp = self.eirp - 2.15
        self.erp_ok = self.erp <= r["erp_limit_dbm"]

    def _beam_loss(self, off_deg):
        return np.minimum(3.0 * (np.asarray(off_deg, float) / self.half) ** 2, 25.0)

    def p_tag(self, d, off_deg=0.0, body=0.0):
        return (self.eirp - self._beam_loss(off_deg) - fspl_db(d, self.f_hz) - self.pol + self.g_tag
                - self.body * np.asarray(body, float))

    def p_backscatter(self, d, off_deg=0.0, body=0.0):
        return (self.p_tag(d, off_deg, body) + self.g_tag - fspl_db(d, self.f_hz) - self.pol
                - self.body * np.asarray(body, float) + self.g_ant - self._beam_loss(off_deg)
                - self.cable - self.mod)

    def read(self, rng, d, off_deg=0.0, body=0.0):
        sh = rng.normal(0.0, self.shadow, np.shape(d))
        fwd = self.p_tag(d, off_deg, body) + sh
        rev = self.p_backscatter(d, off_deg, body) + 2 * sh
        return (fwd >= self.sens_tag) & (rev >= self.sens_rdr), rev


# ---------------------------------------------------------------------------------------------
# 865-867 MHz radio: Semtech SX1262 (D8)
# ---------------------------------------------------------------------------------------------
class SubGhz:
    """Log-distance path loss beyond 1 m and log-normal shadowing; extra loss for blocked paths (the
    bench-corner knife edge in v2v.py) is passed in as extra_db.
    PHY 'lora7' = LoRa SF7 / 125 kHz; 'gfsk38' = GFSK 38.4 kb/s (160 kHz, fits India's 200 kHz)."""

    def __init__(self, comp: dict, phy: str = "lora7"):
        s, a = comp["subghz"], comp["assumptions"]
        self.phy = phy
        self.f_hz = s["f_mhz"] * 1e6
        self.lam = C_LIGHT / self.f_hz
        self.sens = s["sens_lora_sf7_bw125"] if phy == "lora7" else s["sens_gfsk_38k4"]
        pay = a["beacon_payload_b"]
        self.airtime_s = (dc.lora_toa_ms(pay, 7) if phy == "lora7"
                          else dc.fsk_toa_ms(pay, bitrate=38.4e3)) / 1000.0
        self.eirp = s["tx_dbm"] + a["subghz_ant_gain_dbi"] - a["subghz_cable_db"]
        self.g_rx = a["subghz_ant_gain_dbi"] - a["subghz_cable_db"]
        self.n, self.shadow = a["pl_exponent"], a["pl_shadow_db"]
        self.capture = a["capture_db"]
        self.pl1 = float(fspl_db(1.0, self.f_hz))

    def path_loss(self, d, extra_db=0.0):
        d = np.maximum(np.asarray(d, float), 1.0)
        return self.pl1 + 10.0 * self.n * np.log10(d) + extra_db

    def prx(self, d, extra_db=0.0):
        return self.eirp + self.g_rx - self.path_loss(d, extra_db)

    def p_ok(self, prx):
        return p_link(prx, self.sens)


# ---------------------------------------------------------------------------------------------
# GNSS: u-blox ZED-F9P (D7)
# ---------------------------------------------------------------------------------------------
class GnssError:
    """Horizontal error per axis: first-order Gauss-Markov with sigma = CEP / 1.1774 (circular
    normal), plus multipath jumps for PVT/SBAS near highwalls and RTK float episodes."""

    def __init__(self, comp: dict, mode: str, baseline_m: float = 2000.0):
        g, a = comp["gnss"], comp["assumptions"]
        self.mode = mode
        cep = {"pvt": g["cep_pvt_m"], "sbas": g["cep_sbas_m"],
               "rtk": g["cep_rtk_m"] + g["rtk_ppm"] * 1e-6 * baseline_m}[mode]
        self.sigma = cep / 1.1774
        self.tau = a["gnss_tau_s"][mode]
        self.a = a
        self.rate_hz = g["rate_rtk_hz"] if mode == "rtk" else g["rate_pvt_hz"]

    def series(self, rng, t):
        """Error samples (len(t), 2) on a uniform time grid t."""
        dt = float(t[1] - t[0]) if len(t) > 1 else 0.1
        sigma = self.sigma
        if self.mode == "rtk" and rng.random() > self.a["rtk_fix_availability"]:
            sigma = self.a["rtk_float_sigma_m"]
        phi = math.exp(-dt / self.tau)
        w = rng.standard_normal((len(t), 2)) * sigma * math.sqrt(1 - phi ** 2)
        e = np.empty((len(t), 2))
        e[0] = rng.standard_normal(2) * sigma
        for k in range(1, len(t)):
            e[k] = phi * e[k - 1] + w[k]
        if self.mode in ("pvt", "sbas"):
            dur = t[-1] - t[0]
            n_jump = rng.poisson(self.a["gnss_outlier_per_min"] * dur / 60.0)
            for _ in range(n_jump):
                t0 = rng.uniform(t[0], t[-1])
                ln = rng.uniform(*self.a["gnss_outlier_s"])
                mag = rng.uniform(*self.a["gnss_outlier_m"])
                ang = rng.uniform(0, 2 * math.pi)
                sel = (t >= t0) & (t <= t0 + ln)
                e[sel] += mag * np.array([math.cos(ang), math.sin(ang)])
        return e


# ---------------------------------------------------------------------------------------------
# Fingerprint modules: Grow R503 (D11), ADH-Tech GT-521F52 (D12)
# ---------------------------------------------------------------------------------------------
class FingerprintReader:
    def __init__(self, spec: dict, a: dict, mode: str):
        self.spec, self.a, self.mode = spec, a, mode  # mode: '1to1' or '1toN'

    def attempt_s(self, rng):
        a, s = self.a, self.spec
        place = lognormal(rng, a["place_median_s"], a["place_sigma_ln"])
        if self.mode == "1toN":  # GT-521F52 identification < 1.5 s (capture + search)
            return place + rng.uniform(0.5, s["identify_s"])
        return place + s["capture_s"] + s["feature_s"] + a["match_1to1_s"]

    def genuine_accepted(self, rng, difficult: bool):
        frr = self.a["frr_difficult"] if difficult else self.spec["frr"]
        return rng.random() > frr

    def impostor_accepted(self, rng, gallery: int):
        """False match against any of `gallery` templates (1:1 -> 1, 1:k -> k, 1:N -> N)."""
        return rng.random() < 1.0 - (1.0 - self.spec["far"]) ** gallery


# ---------------------------------------------------------------------------------------------
# Helmet-worn sensing: TI FDC1004 sweatband electrode (D13) + IMU tilt + strap switch
# ---------------------------------------------------------------------------------------------
class WornSensor:
    EPS0 = 8.854e-12

    def __init__(self, comp: dict):
        self.c, self.a = comp["cap_sensor"], comp["assumptions"]
        # D13: 33.2 aF/sqrt(Hz) over the Nyquist band of the chosen output rate
        self.noise_pf = self.c["noise_af_rthz"] * 1e-18 * math.sqrt(self.c["rate_sps"] / 2.0) * 1e12

    def capacitance_pf(self, rng, state: str):
        area = self.a["cap_electrode_mm2"] * 1e-6
        if state in ("worn_ok", "strap_open", "swapped"):
            d_mm, er = rng.uniform(1.0, 4.0), 2.5
        elif state == "carried_underarm":
            d_mm, er = rng.uniform(3.0, 10.0), 1.5
        elif state == "carried_hand":
            d_mm, er = ((rng.uniform(2.0, 6.0), 1.5) if rng.random() < 0.2 else (rng.uniform(10.0, 60.0), 1.0))
        else:
            return float("nan")
        c = self.EPS0 * er * area / (d_mm * 1e-3) * 1e12
        c = min(c, self.c["range_pf"])  # converter full scale (after CAPDAC offset)
        return c + rng.normal(0.0, self.noise_pf) + rng.normal(0.0, self.a["cap_humidity_sigma_pf"])

    def worn_flag(self, rng, state: str) -> tuple[bool, bool]:
        """Returns (helmet on head, strap closed) as the personal unit would report them."""
        if state in ("no_helmet", "spu_dead"):
            return False, False
        cap_ok = self.capacitance_pf(rng, state) >= self.a["cap_threshold_pf"]
        carried = state.startswith("carried")
        tilt = rng.uniform(0.0, 180.0) if carried else abs(rng.normal(0.0, 8.0))
        strap = (rng.random() < self.a["strap_closed_when_carried"]) if carried else (state != "strap_open")
        return bool(cap_ok and tilt <= self.a["tilt_worn_max_deg"]), bool(strap)
