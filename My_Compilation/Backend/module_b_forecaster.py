"""Canonical Module B forecasting layer (single owner).

This module is the CURRENT single owner for the Module B 168 h Iddq
forecast path (OLS baseline over burn-in hours, Arrhenius normalization
helpers, walk-forward validation, clamp/bounds handling). The similarly
named predictor kept in Backend/isolation_forest.py is a HISTORICAL /
compatibility alias and must not be treated as the live path.
"""

from __future__ import annotations

import math

FT = 168.0
MN = 8
MW = 200
TMIN = 5.0
TMAX = 150.0
TABS = 175.0


def arrhenius_ratio(tc, rc=125.0, ek=4000.0):
    try:
        t = float(tc) + 273.15
        t0 = float(rc) + 273.15
        if t <= 0 or t0 <= 0:
            return 1.0
        if not (math.isfinite(t) and math.isfinite(t0)):
            return 1.0
        return math.exp(ek * (1.0 / t0 - 1.0 / t))
    except (ValueError, OverflowError):
        return 1.0


def _fin(x):
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _ols(x, y):
    n = len(x)
    if n < 2:
        return (0.0, float(y[-1]) if y else 0.0, 0.0)
    mx = sum(x) / n
    my = sum(y) / n
    sxx = sum((v - mx) ** 2 for v in x)
    if sxx <= 0 or not math.isfinite(sxx):
        return (0.0, my, 0.0)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=False))
    s = sxy / sxx
    ic = my - s * mx
    syy = sum((v - my) ** 2 for v in y)
    if sxx > 0 and syy > 0:
        r = sxy * sxy / (sxx * syy)
    else:
        r = 0.0
    if not math.isfinite(s):
        s = 0.0
    if not math.isfinite(ic):
        ic = my
    if not math.isfinite(r):
        r = 0.0
    return (s, ic, max(0.0, min(1.0, r)))


class LinearBaselineForecaster:
    def __init__(
        self,
        lot_mean_iddq=10.0,
        lot_std_iddq=1.17,
        datasheet_limit_ua=50.0,
        dynamic_sigma=3.0,
    ):
        self.lm = float(lot_mean_iddq)
        self.ls = float(lot_std_iddq)
        self.dl = float(datasheet_limit_ua)
        self.ds = float(dynamic_sigma)
        self.ft = FT
        self.mw = MW
        self._t = []
        self._y = []

    def reset(self):
        self._t.clear()
        self._y.clear()

    def update(self, t, y):
        if not (_fin(t) and _fin(y)):
            return self._in(float(y) if _fin(y) else self.lm, len(self._t))
        self._t.append(float(t))
        self._y.append(float(y))
        if len(self._t) > self.mw:
            self._t.pop(0)
            self._y.pop(0)
        n = len(self._t)
        if n < MN or self._t[-1] == self._t[0]:
            return self._in(y, n)
        s, i, r = _ols(self._t, self._y)
        m = sum(self._y[-8:]) / min(8, len(self._y))
        fc = max(self.lm * 0.5, (1.0 - r) * m + r * (i + s * self.ft))
        dyn = self.lm + self.ds * self.ls
        sig = (r >= 0.25 and s > 0.01) or (y > self.dl)
        e = bool(((fc > self.dl) or (fc > dyn)) and sig)
        h = None
        if s > 0 and i < self.dl:
            hr = (self.dl - i) / s
            if 0 < hr < self.ft:
                h = round(hr, 1)
        return {
            "drift_slope_ua_h": round(float(s), 5),
            "forecast_168h_uA": round(float(fc), 3),
            "forecast_168h_label": f"{fc:.2f} uA",
            "drift_status": "STABLE",
            "drift_r2": round(float(r), 4),
            "early_reject_b": e,
            "hours_to_violation": h,
            "n_observations": n,
        }

    def _in(self, y, n):
        return {
            "drift_slope_ua_h": 0.0,
            "forecast_168h_uA": round(float(y), 3),
            "forecast_168h_label": "COLLECTING DATA",
            "drift_status": "INITIALIZING",
            "drift_r2": 0.0,
            "early_reject_b": False,
            "hours_to_violation": None,
            "n_observations": n,
        }


class ModuleBForecaster:
    def __init__(
        self,
        lot_mean_iddq=10.0,
        lot_std_iddq=1.17,
        datasheet_limit_ua=50.0,
        dynamic_sigma=3.0,
    ):
        self.lm = float(lot_mean_iddq)
        self.ls = float(lot_std_iddq)
        self.dl = float(datasheet_limit_ua)
        self.ds = float(dynamic_sigma)
        self.ft = FT
        self.mw = MW
        self._t = []
        self._y = []
        self._p = []
        self.last_status = "INSUFFICIENT_DATA"
        self.last_method = "none"
        self.last_explosive = False
        self.last_fallback = False
        self.last_clamped = False

    def reset(self):
        self._t.clear()
        self._y.clear()
        self._p.clear()
        self.last_status = "INSUFFICIENT_DATA"
        self.last_method = "none"
        self.last_explosive = False
        self.last_fallback = False
        self.last_clamped = False

    def estimate_future_temp(self, h=FT):
        ts = [v for v in self._p if v is not None and math.isfinite(v)]
        if len(ts) < 3:
            return (ts[-1] if ts else 125.0, False)
        rc = ts[-min(len(ts), 12) :]
        jx = max([abs(b - a) for a, b in zip(rc, rc[1:], strict=False)])
        if jx > 15.0:
            return (float(rc[-1]), False)
        sl = (rc[-1] - rc[0]) / max(1, len(rc) - 1)
        if abs(sl) < 1e-9:
            return (float(rc[-1]), True)
        return self._thelp(rc, sl, h)

    def _thelp(self, rc, sl, h):
        if len(self._t) >= len(rc):
            ps = [b - a for a, b in zip(self._t[-len(rc) :], self._t[-len(rc) + 1 :], strict=False)]
        else:
            ps = [1.0]
        ps = [d for d in ps if d > 0]
        md = sorted(ps)[len(ps) // 2] if ps else 1.0
        sph = sl / md if md > 0 else 0.0
        if abs(sph) < 1e-6:
            return (float(rc[-1]), True)
        th = float(rc[-1]) + 0.5 * sph * max(0.0, h - self._t[-1])
        if th < min(rc) - 5.0:
            th = min(rc) - 5.0
        if th > max(rc) + 10.0:
            th = max(rc) + 10.0
        if th > TABS:
            th = TABS
        if th < -50.0:
            th = -50.0
        return (th, abs(th - rc[-1]) <= 25.0)

    def phy_fc(self, h):
        xs = []
        ns = []
        for tt, yy, pp in zip(self._t, self._y, self._p, strict=True):
            if pp is None or not math.isfinite(pp):
                continue
            rr = arrhenius_ratio(pp)
            if rr <= 0 or not math.isfinite(rr):
                continue
            xs.append(tt)
            ns.append(yy / max(1e-9, rr))
        if len(xs) < MN:
            return None
        for v in ns:
            if not math.isfinite(v):
                return None
        s, i, r = _ols(xs, ns)
        th, _ok = self.estimate_future_temp(h)
        nh = i + s * h
        if not math.isfinite(nh):
            return None
        rec = nh * arrhenius_ratio(th)
        if not math.isfinite(rec):
            return None
        return (rec, s * arrhenius_ratio(th), r)

    def wf_score(self, xs, ys, model, temps=None):
        n = len(xs)
        if n < MN + 2:
            return math.inf
        k = max(2, int(n * 0.3))
        xr = xs[: n - k]
        yr = ys[: n - k]
        xe = xs[n - k :]
        ye = ys[n - k :]
        if len(xr) < 3:
            return math.inf
        pr = None
        if model == "linear":
            s, i, _z = _ols(xr, yr)
            pr = [i + s * v for v in xe]
        if model == "sqrt" and pr is None:
            xt = [(v**0.5) if v > 0 else 0.0 for v in xr]
            s, i, _z = _ols(xt, yr)
            pr = [i + s * ((v**0.5) if v > 0 else 0.0) for v in xe]
        if model == "log" and pr is None:
            s, i, _z = _ols([math.log1p(v) if v > 0 else 0.0 for v in xr], yr)
            pr = [i + s * (math.log1p(v) if v > 0 else 0.0) for v in xe]
        if model == "physics" and pr is None and temps is not None:
            qx = []
            qn = []
            for tt, yy, pp in zip(xr, yr, temps[: len(xr)], strict=False):
                if pp is None or not math.isfinite(pp):
                    continue
                qx.append(tt)
                qn.append(yy / max(1e-9, arrhenius_ratio(pp)))
            if len(qx) >= 3:
                s, i, _z = _ols(qx, qn)
                pr = []
                for v, tp in zip(xe, temps[n - k :], strict=False):
                    rr = arrhenius_ratio(tp) if (tp is not None and math.isfinite(tp)) else 1.0
                    pr.append((i + s * v) * rr)
        if pr is None:
            return math.inf
        se = []
        for p, a in zip(pr, ye, strict=False):
            if math.isfinite(p) and math.isfinite(a):
                se.append((p - a) ** 2)
        if not se:
            return math.inf
        return math.sqrt(sum(se) / len(se))

    def update(self, t, y, temperature=None, **kw):
        n0 = len(self._t)
        bad = not (_fin(t) and _fin(y))
        a0 = 0.0
        b0 = 0.0
        if not bad:
            a0 = float(t)
            b0 = float(y)
            if a0 < 0.0 or a0 > FT + 1e-9:
                bad = True
            if abs(b0) > 1e6:
                bad = True
        if bad:
            self.last_status = "LOW_CONFIDENCE" if n0 >= MN else "INSUFFICIENT_DATA"
            bb = self._y[-1] if self._y else (float(y) if _fin(y) else self.lm)
            return self._em(bb, 0.0, 0.0, n0, method="rejected_sample")
        a = float(t)
        b = float(y)
        q = None
        if temperature is not None and _fin(temperature):
            q = float(temperature)
            if q < -50.0 or q > 300.0:
                q = None
        self._t.append(a)
        self._y.append(b)
        self._p.append(q)
        while len(self._t) > self.mw:
            self._t.pop(0)
            self._y.pop(0)
            self._p.pop(0)
        n = len(self._t)
        if n < MN:
            self.last_status = "INSUFFICIENT_DATA"
            self.last_method = "none"
            return self._em(b, 0.0, 0.0, n, method="none")
        xs = list(self._t)
        ys = list(self._y)
        s_lin = self.wf_score(xs, ys, "linear")
        s_sq = self.wf_score(xs, ys, "sqrt")
        s_lg = self.wf_score(xs, ys, "log")
        s_ph = self.wf_score(xs, ys, "physics", self._p)
        sl, il, rl = _ols(xs, ys)
        raw = il + sl * self.ft
        m8 = sum(ys[-8:]) / min(8, len(ys))
        fl = max(self.lm * 0.5, (1.0 - rl) * m8 + rl * raw)
        bm = "linear"
        bf = fl
        bs = sl
        br = rl
        bsc = s_lin
        if math.isfinite(s_ph) and math.isfinite(bsc) and s_ph <= 0.95 * bsc:
            ph = self.phy_fc(self.ft)
            if ph is not None and math.isfinite(ph[0]):
                bm = "physics"
                bf = ph[0]
                bs = ph[1]
                br = ph[2]
                bsc = s_ph
        if bm == "linear" and math.isfinite(s_sq) and math.isfinite(bsc) and s_sq <= 0.90 * bsc:
            s, i, r = _ols([(v**0.5) if v > 0 else 0.0 for v in xs], ys)
            fc = i + s * (self.ft**0.5)
            if math.isfinite(fc):
                bm = "sqrt"
                bf = fc
                bs = s
                br = r
                bsc = s_sq
        if bm == "linear" and math.isfinite(s_lg) and math.isfinite(bsc) and s_lg <= 0.90 * bsc:
            s, i, r = _ols([math.log1p(v) if v > 0 else 0.0 for v in xs], ys)
            fc = i + s * math.log1p(self.ft)
            if math.isfinite(fc):
                bm = "log"
                bf = fc
                bs = s
                br = r
                bsc = s_lg
        self.last_explosive = False
        mu = sum(ys) / len(ys)
        vv = sum((v - mu) ** 2 for v in ys) / len(ys)
        ws = math.sqrt(vv) if vv >= 0 else 0.0
        ms = max(50.0, 5.0 * ws + abs(bs) * (self.ft - xs[-1]))
        boom = (not math.isfinite(bf)) or (abs(bf - ys[-1]) > ms) or (abs(bf) > 1e4)
        if boom:
            self.last_explosive = True
            fb = (
                max(self.lm * 0.5, (1.0 - br) * sum(ys[-8:]) / min(8, len(ys)) + br * raw)
                if math.isfinite(raw)
                else ys[-1]
            )
            bf = fb if math.isfinite(fb) else ys[-1]
            bm = "linear_fallback"
        self.last_fallback = bm.endswith("fallback")
        self.last_clamped = bf > TMAX or bf < TMIN
        bd = bf
        if bd > TMAX:
            bd = TMAX
        if bd < TMIN - 5.0:
            bd = TMIN - 5.0
        rev = any(b2 < b1 for b1, b2 in zip(self._t, self._t[1:], strict=False))
        dup = len(set(self._t)) < len(self._t)
        if rev:
            st = "LOW_CONFIDENCE"
        elif bm.endswith("fallback") or self.last_explosive:
            st = "LOW_CONFIDENCE"
        elif max(ys) > TMAX * 1.5 or abs(bs) > 5.0:
            st = "OOD"
        elif abs(bs) < 0.005:
            st = "STABLE_FORECAST"
        elif bm == "physics" or bm == "sqrt" or bm == "log":
            st = "NONLINEAR_REGIME"
        elif (not math.isfinite(s_lin)) or br < 0.1:
            st = "LOW_CONFIDENCE"
        else:
            st = "STABLE_FORECAST"
        if dup and st == "STABLE_FORECAST":
            st = "LOW_CONFIDENCE"
        self.last_status = st
        self.last_method = bm
        return self._em(bd, bs, br, n, method=bm, status=st)

    def _em(self, fc, slope, r2, n, method="linear", status=None):
        dyn = self.lm + self.ds * self.ls
        f = float(fc) if _fin(fc) else float(self._y[-1] if self._y else self.lm)
        st = status or self.last_status
        if n < MN:
            return {
                "drift_slope_ua_h": 0.0,
                "forecast_168h_uA": round(f, 3),
                "forecast_168h_label": f"COLLECTING DATA ({n}/{MN})",
                "drift_status": "INITIALIZING",
                "forecast_status": "INSUFFICIENT_DATA",
                "drift_r2": 0.0,
                "early_reject_b": False,
                "hours_to_violation": None,
                "n_observations": n,
                "forecast_method": method,
                "explosive_rejected": False,
                "fallback_used": False,
                "clamp_engaged": False,
            }
        lasty = self._y[-1] if self._y else f
        sg = (r2 >= 0.25 and slope > 0.01) or (f > self.dl)
        e = bool(((f > self.dl) or (f > dyn)) and sg)
        h = None
        if slope > 0:
            d = slope if abs(slope) > 1e-12 else 1e-12
            hr = (self.dl - (f - slope * self.ft)) / d
            if 0 < hr < self.ft:
                h = round(float(hr), 1)
        if st == "INSUFFICIENT_DATA" or st == "FORECAST_UNAVAILABLE":
            lb = "UNAV"
        elif (f > self.dl) and sg:
            lb = "VIOL"
        elif (f > dyn) or (lasty > dyn):
            lb = "WARN"
        else:
            lb = "SAFE"
        return {
            "drift_slope_ua_h": round(float(slope), 5),
            "forecast_168h_uA": round(float(f), 3),
            "forecast_168h_label": f"{f:.2f} uA ({lb})",
            "drift_status": st,
            "forecast_status": st,
            "drift_r2": round(float(max(0.0, min(1.0, r2))), 4),
            "early_reject_b": e,
            "hours_to_violation": h,
            "n_observations": n,
            "forecast_method": method,
            "explosive_rejected": bool(self.last_explosive),
            "fallback_used": bool(self.last_fallback),
            "clamp_engaged": bool(self.last_clamped),
        }

    def predict_168h(self, v0, v24, actual=None):
        if not (_fin(v0) and _fin(v24)):
            return {
                "slope": 0.0,
                "forecast_168h_uA": 0.0,
                "early_reject": False,
                "forecast_mae_ua": math.inf,
                "status": "FORECAST_UNAVAILABLE",
            }
        sl = (float(v24) - float(v0)) / 24.0
        fc = float(v0) + sl * self.ft
        dyn = self.lm + self.ds * self.ls
        er = (fc > self.dl) or (fc > dyn)
        mae = abs(fc - float(actual)) if (actual is not None and _fin(actual)) else 0.0
        return {
            "slope": sl,
            "forecast_168h_uA": fc,
            "projected_168h_iddq_ua": fc,
            "will_violate_static": fc > self.dl,
            "will_violate_dynamic": fc > dyn,
            "early_reject": er,
            "lead_time_saved_hours": 144.0 if er else 0.0,
            "forecast_mae_ua": mae,
            "mae": mae,
            "status": "STABLE_FORECAST",
        }
