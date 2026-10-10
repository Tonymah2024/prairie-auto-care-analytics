"""Synthetic operational data for the FICTIONAL Prairie Auto Care Group (Calgary), Oct-2023 (warm-up) to Sep-2026.

Simulation, not random tables: every repair order (RO) moves through a workflow -
inquiry -> estimate -> insurer / customer approval -> parts ordering -> capacity-constrained technician scheduling ->
repair work (with supplements for hidden damage) -> quality control -> delivery -> invoicing -> payment - and every
table is derived from the same events, so estimates, job assignments, timesheets, parts movements, purchase orders,
invoices and payments reconcile with each other by construction.

Real public inputs: Calgary daily weather (ECCC) drives collision and tire demand; Alberta holidays close the shops.
Everything else is an assumption (see params.py). Records dated before 1-Jan-2024 are flagged pre_period = 1 and are used
only to build the opening position of the simulated accounts.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np
import pandas as pd

from src.config import END, EXTERNAL, SEED, START, SYNTH
from src.generate import params as P

DAY0 = pd.Timestamp(P.SIM_START)
DAYS = pd.date_range(P.SIM_START, END, freq="D")
ND = len(DAYS)
END_I = ND - 1
START_I = int((pd.Timestamp(START) - DAY0).days)
LINE_OPS = ["BODY", "PAINT", "MECH", "CALIB", "GLASS", "DETAIL", "PPF", "PDR"]
OT_MAX = 2.0


def r2(x):
    return float(np.round(x + 1e-12, 2))


def yr(i):
    return DAYS[min(i, END_I)].year


class Gen:
    def __init__(self):
        self.rng = np.random.default_rng(SEED)
        w = pd.read_csv(EXTERNAL / "calgary_weather_daily.csv", parse_dates=["date"]).set_index("date")
        # warm-up quarter (Oct-Dec 2023) has no ECCC extract in the project: reuse the same calendar days of 2024 (flagged imputed)
        warm = w.loc["2024-10-01":"2024-12-31"].copy()
        warm.index = warm.index - pd.DateOffset(years=1)
        warm["imputed"] = True
        self.wx = pd.concat([warm, w]).reindex(DAYS).ffill()
        hol = pd.read_csv(EXTERNAL / "alberta_holidays.csv", parse_dates=["date"])
        self.holidays = set(hol.date)
        self.snow = self.wx.snow_cm.fillna(0).values
        self.tmin = self.wx.min_temp_c.fillna(0).values
        self.open = {}
        for bid, _, _, opened, sat, _ in P.BRANCHES:
            o = np.array([(d >= pd.Timestamp(opened)) and d not in self.holidays and (d.weekday() < 5 or (d.weekday() == 5 and sat > 0)) for d in DAYS])
            self.open[bid] = o
        self.weekday = np.array([d.weekday() for d in DAYS])
        self.ids = defaultdict(int)
        self.first_snow = self._first_snow_days()

    def nid(self, prefix, width=6):
        self.ids[prefix] += 1
        return f"{prefix}-{self.ids[prefix]:0{width}d}"

    # ------------------------------------------------------------------------------------------- calendar helpers
    def next_open(self, b, i, k=0):
        """k-th open day of branch b on/after day i (k=0 -> first open day >= i)."""
        o = self.open[b]
        while i < ND and not o[i]:
            i += 1
        while k > 0 and i < ND:
            i += 1
            while i < ND and not o[i]:
                i += 1
            k -= 1
        return min(i, ND)

    def biz_days(self, b, i0, i1):
        if i1 <= i0:
            return 0
        return int(self.open[b][i0 + 1:min(i1, END_I) + 1].sum())

    def _first_snow_days(self):
        fs = set()
        for y in (2023, 2024, 2025):
            idx = [i for i, d in enumerate(DAYS) if d.year == y and d.month >= 9 and self.snow[i] >= 2]
            if idx:
                fs.update(range(idx[0], min(idx[0] + 10, ND)))
        return fs

    # ------------------------------------------------------------------------------------------- staff & schedules
    def staff(self):
        rng = self.rng
        techs = []
        def new(b, role, hire, initial):
            g, wage, eff, rw = P.ROLES[role]
            t = dict(tech_id=self.nid("TEC", 3), branch_id=b, role=role, op_groups="|".join(g), hire_date=hire, termination_date=pd.NaT,
                     base_wage_2024=r2(rng.uniform(*wage)), efficiency_factor=float(np.clip(eff * rng.lognormal(0, .06), .7, 1.45)),
                     rework_factor=float(np.clip(rw * rng.lognormal(0, .2), .4, 2.5)), red_seal=int("Red Seal" in role or role in ("Refinish technician (painter)",)
                                                                                                     and rng.random() < .5))
            techs.append(t)
        for b, role, n in P.STAFF:
            for _ in range(n):
                new(b, role, pd.Timestamp("2014-01-01") + pd.Timedelta(days=int(rng.integers(0, 3500))), True)
        for d, b, role, chg in P.STAFF_CHANGES:
            d = pd.Timestamp(d)
            if chg > 0:
                for _ in range(chg):
                    new(b, role, d, False)
            else:
                cand = [t for t in techs if t["branch_id"] == b and t["role"] == role and pd.isna(t["termination_date"]) and t["hire_date"] < d]
                cand.sort(key=lambda t: t["hire_date"])
                cand[0]["termination_date"] = d
        self.techs = techs
        self.T = {t["tech_id"]: t for t in techs}
        self.sched = {}
        self.cap = {}
        self.absence = {}
        self.training = {}
        self.booked = {}
        for k, t in enumerate(techs):
            b = t["branch_id"]
            s = np.zeros(ND)
            ab = np.array([""] * ND, dtype=object)
            tr = np.zeros(ND)
            hire = int((t["hire_date"] - DAY0).days)
            term = int((t["termination_date"] - DAY0).days) if pd.notna(t["termination_date"]) else ND + 1
            groups = t["op_groups"].split("|")
            sat_rota = b in ("BR-SEC", "BR-NFS") and any(g in groups for g in ("MECH", "DETAIL", "PPF"))
            for i in range(max(0, hire), min(ND, term)):
                if not self.open[b][i]:
                    continue
                if self.weekday[i] < 5:
                    s[i] = 8.0
                elif sat_rota and (DAYS[i].isocalendar()[1] + k) % 2 == 0:
                    s[i] = 3.0
            # PTO: a summer block, a Christmas block for half the staff, the rest scattered; sick days random
            for y in sorted({d.year for d in DAYS}):
                wd = [i for i in range(ND) if DAYS[i].year == y and s[i] == 8.0]
                if not wd:
                    continue
                frac = len(wd) / 250
                summer = [i for i in wd if DAYS[i].month in (7, 8)]
                pto = []
                if summer and frac > .5:
                    st = int(rng.integers(0, max(1, len(summer) - 10)))
                    pto += summer[st:st + int(rng.choice([5, 10]))]
                if rng.random() < .5:
                    pto += [i for i in wd if DAYS[i].month == 12 and DAYS[i].day >= 22]
                rest = int(max(0, round(P.PTO_DAYS * frac) - len(pto)))
                pool = [i for i in wd if i not in set(pto)]
                pto += list(rng.choice(pool, size=min(rest, len(pool)), replace=False)) if pool and rest else []
                for i in pto:
                    ab[i] = "PTO"
                pool = [i for i in wd if ab[i] == ""]
                for i in rng.choice(pool, size=min(int(round(P.SICK_DAYS * frac + rng.integers(-1, 3))), len(pool)), replace=False) if pool else []:
                    ab[i] = "Sick"
            for i in range(ND):
                if s[i] == 8.0 and ab[i] == "" and DAYS[i].weekday() == 2 and DAYS[i].day <= 7:
                    tr[i] = 2.0                                   # monthly training session (first Wednesday)
            avail = np.where(ab == "", s, 0.0)
            self.sched[t["tech_id"]] = s
            self.absence[t["tech_id"]] = ab
            self.training[t["tech_id"]] = tr
            self.cap[t["tech_id"]] = np.maximum(0.0, (avail - tr) * P.PRODUCTIVE_SHARE)
            self.booked[t["tech_id"]] = np.zeros(ND)
        self.group_techs = defaultdict(list)
        for t in techs:
            for g in t["op_groups"].split("|"):
                self.group_techs[(t["branch_id"], g)].append(t["tech_id"])

    def tech_eff(self, tid, i):
        t = self.T[tid]
        e = t["efficiency_factor"]
        if t["role"].startswith("Apprentice"):
            e *= 1 + 0.07 * max(0.0, (DAYS[min(i, END_I)] - pd.Timestamp("2024-01-01")).days / 365)
        return e

    def has_group(self, b, g, i):
        return any(self.sched[t][i] > 0 or self._employed(t, i) for t in self.group_techs[(b, g)])

    def _employed(self, tid, i):
        t = self.T[tid]
        d = DAYS[min(i, END_I)]
        return t["hire_date"] <= d and (pd.isna(t["termination_date"]) or d < t["termination_date"])

    def performer(self, sell, svc, i):
        ops = P.SERVICES[svc]["ops"]
        if sell == "BR-SEC" and svc in ("COL_MOD", "COL_MAJ"):
            return "BR-CCC"
        if all(any(self._employed(t, i) for t in self.group_techs[(sell, g)]) for g in ops):
            return sell
        for alt in ("BR-CCC", "BR-SEC", "BR-NFS"):
            if alt != sell and self.open[alt][min(i + 3, END_I)] and all(any(self._employed(t, i) for t in self.group_techs[(alt, g)]) for g in ops):
                return alt
        return None

    # ------------------------------------------------------------------------------------------- booking (capacity)
    def pick_tech(self, b, g, i0, horizon=6):
        best, score = None, -1
        for t in self.group_techs[(b, g)]:
            free = (self.cap[t][i0:i0 + horizon] - self.booked[t][i0:i0 + horizon]).clip(min=0).sum()
            if free > score:
                best, score = t, free
        return best

    def book(self, b, g, hours, i0, pref, ready_i, max_day=7.5):
        """Book `hours` of clocked work for op group g at branch b from day i0. One technician per job per day; overtime (up to 2 h) is
        allowed once the job has waited 3+ business days. Returns chunks [(tech, day, hours)], last day, last tech."""
        rem, i, chunks = hours, i0, []
        while rem > 1e-6 and i < ND:
            if not self.open[b][i]:
                i += 1
                continue
            cands = self.group_techs[(b, g)]
            order = ([pref] if pref in cands else []) + sorted((t for t in cands if t != pref), key=lambda t: self.booked[t][i] - self.cap[t][i])
            for t in order:
                if self.cap[t][i] <= 0:
                    continue
                free = self.cap[t][i] - self.booked[t][i]
                if self.weekday[i] < 5 and self.biz_days(b, ready_i, i) >= 3:
                    free += OT_MAX
                need = min(rem, max_day)
                if free >= min(need, 0.5):
                    take = round(min(need, free), 2)
                    self.booked[t][i] += take
                    chunks.append((t, i, take))
                    rem = round(rem - take, 2)
                    pref = t
                    break
            i += 1
        last = chunks[-1][1] if chunks else None
        return chunks, last, pref

    # ------------------------------------------------------------------------------------------- demand
    def season(self, svc, i):
        d = DAYS[i]
        m, doy = d.month, d.dayofyear
        if svc in P.COLLISION or svc == "REFIN":
            f = [1.18, 1.12, 1.02, .92, .90, .90, .92, .95, .95, 1.0, 1.12, 1.17][m - 1]
            sn = self.snow[max(0, i - 2):i + 1].sum()
            f *= 1.6 if sn >= 8 else (1.3 if sn >= 2 else 1.0)
            if i in self.first_snow:
                f *= 1.4
            if self.tmin[i] < -25:
                f *= 1.2
            return f
        if svc == "TIRE":
            if (m == 10) or (m == 11 and d.day <= 20):
                f = 3.2
            elif (m == 4 and d.day >= 10) or m == 5:
                f = 2.6
            else:
                f = .35
            return f * (1.6 if i in self.first_snow else 1.0)
        if svc == "DET":
            return [.6, .6, .9, 1.35, 1.35, 1.35, 1.2, 1.2, 1.2, .95, .6, .6][m - 1]
        if svc == "PPF":
            return [.55, .55, 1.4, 1.4, 1.4, 1.4, 1.2, 1.2, .9, .9, .55, .55][m - 1]
        if svc in ("GLS_REP", "GLS_CHIP"):
            f = [.85, .85, 1.35, 1.35, 1.35, 1.1, 1.1, 1.1, .9, .9, .85, .85][m - 1]
            return f * (1.15 if self.tmin[i] < -22 else 1.0)
        if svc in ("MAINT", "MECH", "DIAG"):
            f = [1.08, 1.08, 1.0, 1.0, 1.02, 1.0, .95, .95, 1.0, 1.02, 1.0, .85][m - 1]
            return f * (1.25 if svc == "DIAG" and self.tmin[i] < -25 else 1.0)
        if svc == "ADAS":
            return [1.1, 1.05, 1.1, 1.1, 1.05, 1.0, 1.0, 1.0, .95, 1.0, 1.05, 1.1][m - 1]
        return 1.0

    def hail(self, svc, i):
        d = DAYS[i]
        for h in P.HAIL_EVENTS:
            k = (d - pd.Timestamp(h)).days
            if 0 <= k < 42:
                amp = {"PDR": 9.0, "REFIN": 2.2, "COL_MIN": 1.35}.get(svc, 1.0)
                return 1 + (amp - 1) * math.exp(-k / 14), True
        return 1.0, False

    def demand(self):
        rng = self.rng
        inq = []
        for i in range(ND):
            d = DAYS[i]
            growth = 1.06 ** ((d - pd.Timestamp("2024-01-01")).days / 365)
            for b in P.BRANCH_IDS:
                if not self.open[b][i]:
                    continue
                ramp = 1.0
                if b == "BR-SEC":
                    mo = (d.year - 2025) * 12 + d.month - 5
                    ramp = min(1.0, 0.3 + 0.7 * mo / P.SE_RAMP_MONTHS)
                for svc, s in P.SERVICES.items():
                    base = s["base"][b]
                    if base <= 0:
                        continue
                    if svc == "PPF" and d < pd.Timestamp("2025-05-01"):
                        continue                                          # paint protection launched with the SE Concierge opening
                    sat = self.weekday[i] == 5
                    if sat and svc not in ("TIRE", "MAINT", "DET", "PPF", "GLS_CHIP", "DIAG"):
                        continue
                    hf, is_hail = self.hail(svc, i)
                    lam = base / 21.7 * self.season(svc, i) * growth * hf * ramp * (0.45 if sat else (1.12 if self.weekday[i] == 0 else 1.0))
                    for _ in range(rng.poisson(lam)):
                        inq.append((i, b, svc, is_hail))
        return inq

    # ------------------------------------------------------------------------------------------- customers & vehicles
    def setup_pools(self):
        rng = self.rng
        self.customers, self.vehicles = [], []
        self.pool = defaultdict(list)
        self.fleets = []
        fleet_names = ["Bowness Plumbing & Heating", "Chinook Courier Services", "Prairie Property Management", "Westbrook Landscaping", "Rocky Ridge Electrical",
                       "Elbow Park Home Care", "Glenmore Delivery Co.", "Sundre Mobile Mechanics", "Nose Hill Realty", "McKnight HVAC Services",
                       "Bridgeland Catering", "Shepard Industrial Supply", "Crowchild Security", "Marda Loop Florists", "Deerfoot Equipment Rentals",
                       "Fish Creek Pool & Spa", "Royal Oak Dental Group", "Inglewood Brewing Logistics", "Beltline Cleaning Co.", "Tuscany Roofing",
                       "Sage Hill Home Builders", "Quarry Park Office Services"]
        for k, n in enumerate(fleet_names):
            cid = self.nid("CUS", 6)
            hb = ["BR-NFS", "BR-CCC", "BR-NFS", "BR-CCC", "BR-SEC"][k % 5]
            self.customers.append(dict(customer_id=cid, customer_type="Fleet account", account_name=f"{n} (fictional)", home_branch_id=hb,
                                       calgary_quadrant={"BR-NFS": "NE", "BR-CCC": "SE", "BR-SEC": "SE"}[hb], acquisition_channel="Commercial account",
                                       first_visit_date=pd.Timestamp(P.SIM_START), fleet_discount_pct=7.0))
            vs = [self.new_vehicle(cid, fleet=True) for _ in range(int(rng.integers(4, 14)))]
            self.fleets.append((cid, vs, hb))

    def new_vehicle(self, cid, fleet=False):
        rng = self.rng
        cats = list(P.VEHICLE_CATEGORIES)
        w = np.array([P.VEHICLE_CATEGORIES[c][0] for c in cats])
        if fleet:
            w = w * np.array([.6, .8, 2.5, .3, .6, 4.0])
        cat = cats[int(rng.choice(len(cats), p=w / w.sum()))]
        makes = [m for m, (s, cs) in P.MAKES.items() if cat in cs]
        mw = np.array([P.MAKES[m][0] for m in makes])
        make = makes[int(rng.choice(len(makes), p=mw / mw.sum()))]
        age = int(min(17, rng.geometric(1 / 6.0) - 1))
        my = 2026 - age
        vid = self.nid("VEH", 6)
        ev = cat == "EV & hybrid"
        v = dict(vehicle_id=vid, customer_id=cid, make=make, vehicle_category=cat, model_year=my,
                 powertrain=("Battery electric" if make == "Tesla" or (ev and rng.random() < .55) else ("Hybrid" if ev else "Gasoline / diesel")),
                 adas_equipped=int(rng.random() < P.VEHICLE_CATEGORIES[cat][3] * (1.0 if my >= 2018 else .35)))
        self.vehicles.append(v)
        return v

    def customer_for(self, b, svc, i):
        rng = self.rng
        if rng.random() < (0.10 if svc in ("MAINT", "TIRE", "MECH", "DIAG", "COL_MIN", "COL_MOD", "GLS_REP", "GLS_CHIP", "DET") else 0.03):
            fl = [f for f in self.fleets if f[2] == b] or self.fleets
            cid, vs, _ = fl[int(rng.integers(len(fl)))]
            return cid, vs[int(rng.integers(len(vs)))], True
        rep = {"TIRE": .55, "MAINT": .5, "DIAG": .3, "MECH": .35, "DET": .35, "PPF": .08, "GLS_CHIP": .2, "GLS_REP": .2, "ADAS": .25, "PDR": .15}.get(svc, .14)
        pool = self.pool[b]
        if pool and rng.random() < rep:
            cid, v = pool[int(rng.integers(len(pool)))]
            return cid, v, False
        cid = self.nid("CUS", 6)
        ch = ["Google search & maps", "Insurer referral", "Repeat & word of mouth", "Dealership referral", "Walk-in", "Social media", "Online booking"]
        cw = [.30, .20 if svc in P.COLLISION else .03, .18, .07, .08, .07, .10]
        cw = np.array(cw) / sum(cw)
        self.customers.append(dict(customer_id=cid, customer_type="Individual", account_name=None, home_branch_id=b,
                                   calgary_quadrant={"BR-NFS": rng.choice(["NE", "NW"]), "BR-CCC": rng.choice(["SE", "SW", "NE"]), "BR-SEC": rng.choice(["SE", "SW"])}[b],
                                   acquisition_channel=ch[int(rng.choice(len(ch), p=cw))], first_visit_date=DAYS[i], fleet_discount_pct=0.0))
        v = self.new_vehicle(cid)
        if rng.random() < .08:
            self.new_vehicle(cid)
        pool.append((cid, v))
        return cid, v, False

    # ------------------------------------------------------------------------------------------- catalogue
    def catalogue(self):
        rows, self.stocked_skus, self.so_parts = [], defaultdict(list), {}
        sup_for = {"clips": "SUP-02", "urethane": "SUP-04", "resin": "SUP-04", "oil": "SUP-06", "filter": "SUP-06", "pads": "SUP-06", "rotors": "SUP-06",
                   "wipers": "SUP-06", "battery": "SUP-06", "tire": "SUP-05", "tpms": "SUP-05", "ppf": "SUP-07"}
        for kind, (items, qty, at) in P.STOCKED.items():
            for desc, cost, mk in items:
                pid = self.nid("PRT", 5)
                rows.append(dict(part_id=pid, part_number=f"STK-{pid[-5:]}", description=desc, part_category=kind, part_type="Stocked", oem_or_aftermarket="Aftermarket / supplier brand",
                                 make=None, standard_unit_cost_2024=cost, unit_list_price_2024=r2(cost * mk), default_supplier_id=sup_for[kind],
                                 stocked_at="|".join(at)))
                self.stocked_skus[kind].append((pid, cost, mk))
        for make in P.MAKES:
            for cat, (cost, mk, use) in P.SO_PARTS.items():
                pid = self.nid("PRT", 5)
                lux = make in ("BMW", "Mercedes-Benz", "Volkswagen", "Tesla", "Genesis")
                sup = "SUP-08" if lux and cat not in ("Windshield (model-specific)", "Tire (special-order size)") else (
                    "SUP-04" if cat.startswith("Windshield") else ("SUP-05" if cat.startswith("Tire") else ("SUP-02" if use == "M" else "SUP-01")))
                rows.append(dict(part_id=pid, part_number=f"SO-{make[:3].upper()}-{pid[-5:]}", description=f"{make} {cat.lower()}", part_category=cat, part_type="Special order",
                                 oem_or_aftermarket="OEM" if sup in ("SUP-01", "SUP-08") else "Aftermarket / certified", make=make,
                                 standard_unit_cost_2024=float(cost), unit_list_price_2024=r2(cost * mk), default_supplier_id=sup, stocked_at=None))
                self.so_parts[(make, cat)] = (pid, cost, mk, sup)
        self.parts = pd.DataFrame(rows)
        self.part_cost = dict(zip(self.parts.part_id, self.parts.standard_unit_cost_2024))
        self.part_markup = dict(zip(self.parts.part_id, self.parts.unit_list_price_2024 / self.parts.standard_unit_cost_2024))
        self.part_supplier = dict(zip(self.parts.part_id, self.parts.default_supplier_id))
        self.sup = {s[0]: s for s in P.SUPPLIERS}

    def infl(self, i):
        return 1.035 ** ((DAYS[min(i, END_I)] - pd.Timestamp("2024-01-01")).days / 365)

    # ------------------------------------------------------------------------------------------- supplier lead times
    def lead(self, sup, b, i_order, kind="normal"):
        rng = self.rng
        s = self.sup[sup]
        lt = max(0.5, rng.normal(s[4], s[5]))
        late = rng.random() > s[6]
        back = 0
        if kind == "normal" and rng.random() < (0.12 if sup == "SUP-08" else 0.035):
            back = int(rng.integers(4, 19))
        promised = self.next_open(b, i_order, int(math.ceil(s[4])))
        recv = self.next_open(b, i_order, int(math.ceil(lt)) + (int(rng.integers(1, 5)) if late else 0) + back)
        return promised, recv, back > 0

    # ------------------------------------------------------------------------------------------- RO build & workflow
    def make_ros(self, inq):
        rng = self.rng
        self.ros, self.est_rows, self.claims, self.appts, self.so_lines, self.stk_lines, self.sublets = [], [], [], [], [], [], []
        ins_ids = [x[0] for x in P.INSURERS if x[0] != "INS-10"]
        ins_w = np.array([x[7] for x in P.INSURERS if x[0] != "INS-10"])
        INS = {x[0]: x for x in P.INSURERS}
        for (i, b, svc, is_hail) in inq:
            s = P.SERVICES[svc]
            cid, veh, fleet = self.customer_for(b, svc, i)
            perf = self.performer(b, svc, i)
            if perf is None:
                continue
            vc = P.VEHICLE_CATEGORIES[veh["vehicle_category"]]
            ro = dict(ro_id=self.nid("RO", 6), branch_id=b, performing_branch_id=perf, customer_id=cid, vehicle_id=veh["vehicle_id"], service_type=svc,
                      service_name=s["name"], service_line=s["line"], inquiry_day=i, hail_related=int(is_hail), fleet=fleet, warranty_of_ro=None)
            # payer
            insured_p = .95 if (is_hail and svc in ("PDR", "REFIN", "COL_MIN")) else s["insured"]
            ro["payer_type"] = "Customer pay"
            ro["insurer_id"] = None
            if rng.random() < insured_p:
                ro["payer_type"] = "Insurance"
                ro["insurer_id"] = "INS-10" if fleet and rng.random() < .5 else ins_ids[int(rng.choice(len(ins_ids), p=ins_w / ins_w.sum()))]
            elif fleet:
                ro["payer_type"] = "Fleet account"
            # labour content (billed / flat-rate hours from the estimating guide) by operation
            hrs = s["hours"] * (2.6 if is_hail and svc == "PDR" else 1.0) * vc[2] * rng.lognormal(0, s["sigma"])
            ops = dict(s["ops"])
            if "CALIB" in ops and not veh["adas_equipped"] and svc != "ADAS":
                ops["BODY" if "BODY" in ops else ("GLASS" if "GLASS" in ops else "MECH")] += ops.pop("CALIB")
            ro["est_ops"] = {g: round(hrs * sh, 1) for g, sh in ops.items() if round(hrs * sh, 1) > 0}
            if not ro["est_ops"]:
                ro["est_ops"] = {list(ops)[0]: 0.3}
            self.ros.append(ro)
            self.plan(ro, veh, INS)
        return self.ros

    def plan(self, ro, veh, INS):
        """Pre-scheduling workflow: estimate, approval, parts ordering & receipt."""
        rng = self.rng
        svc, b, perf, i = ro["service_type"], ro["branch_id"], ro["performing_branch_id"], ro["inquiry_day"]
        s = P.SERVICES[svc]
        vc = P.VEHICLE_CATEGORIES[veh["vehicle_category"]]
        estimate_based = svc in P.COLLISION or svc in ("REFIN",) or (svc == "PDR" and ro["payer_type"] == "Insurance") or svc == "MECH"
        towed = svc in ("COL_MAJ", "COL_MOD") and rng.random() < {"COL_MAJ": .6, "COL_MOD": .2}[svc]
        ro["towed_in"] = int(towed)
        chan = "Tow-in" if towed else (rng.choice(["Phone", "Online booking", "Walk-in", "Insurer referral"], p=[.42, .33, .1, .15]) if svc in P.COLLISION
                                       else rng.choice(["Phone", "Online booking", "Walk-in"], p=[.38, .5, .12]))
        ro["channel"] = chan
        if estimate_based and svc != "MECH":
            est_i = self.next_open(b, i, 0 if (towed or chan == "Walk-in") else int(rng.integers(0, 4)))
        elif chan == "Walk-in":
            est_i = self.next_open(b, i, 0)
        else:
            est_i = self.next_open(b, i, int(rng.choice([0, 1, 2, 3, 5], p=[.35, .25, .15, .15, .1])))
        ro["estimate_day"] = est_i
        # parts plan (special-order lines and stocked lines)
        so, stk = [], []
        lo, hi = s["so_lines"]
        n_so = int(rng.integers(lo, hi + 1)) if hi > 0 else 0
        if svc == "TIRE":
            n_so = 0
        cats = [c for c, (_, _, use) in P.SO_PARTS.items() if ("C" in use and svc in P.COLLISION | {"REFIN"}) or ("M" in use and svc == "MECH")
                or (use == "G" and svc == "GLS_REP")]
        if svc == "GLS_REP":
            cats = ["Windshield (model-specific)"]
        for _ in range(n_so if cats else 0):
            cat = cats[int(rng.integers(len(cats)))]
            if not veh["adas_equipped"] and cat == "Radar / ADAS sensor":
                cat = "Front bumper cover"
            pid, cost, mk, sup = self.so_parts[(veh["make"], cat)]
            if svc in ("COL_MIN", "REFIN") and ro["payer_type"] != "Insurance" and sup == "SUP-01" and rng.random() < .5:
                sup, mk = "SUP-02", 1.45                                        # customer-pay jobs often use certified aftermarket parts
            c = r2(cost * vc[1] * rng.lognormal(0, .25) * self.infl(i))
            so.append(dict(part_id=pid, supplier_id=sup, qty=1, est_unit_cost=c, unit_price=r2(c * mk), supplement=0))
        stocked = list(s["stocked"])
        if svc == "TIRE":
            sale = rng.random() < .3
            stocked = ["tpms"] if not sale else ["tire", "tpms"]
            if sale and rng.random() < .25:
                pid, cost, mk, sup = self.so_parts[(veh["make"], "Tire (special-order size)")]
                c = r2(cost * vc[1] * rng.lognormal(0, .15) * self.infl(i))
                so.append(dict(part_id=pid, supplier_id=sup, qty=4, est_unit_cost=c, unit_price=r2(c * mk), supplement=0))
                stocked = ["tpms"]
        prob = {"oil": .85, "filter": .85, "pads": .25 if svc == "MAINT" else .55, "rotors": .35, "wipers": .2, "battery": .07, "clips": .9, "urethane": 1.0,
                "resin": 1.0, "tire": 1.0, "tpms": .6, "ppf": 1.0}
        for kind in stocked:
            if rng.random() >= prob.get(kind, .5):
                continue
            skus = self.stocked_skus[kind]
            w = 1.0 / np.arange(1, len(skus) + 1) ** 0.9
            pid, cost, mk = skus[int(rng.choice(len(skus), p=w / w.sum()))]
            qlo, qhi = P.STOCKED[kind][1]
            q = int(rng.integers(qlo, qhi + 1))
            if kind == "ppf":
                q = int(max(2, round(ro["est_ops"].get("PPF", 6) * .8)))
            stk.append(dict(part_id=pid, qty=q, unit_price=r2(cost * mk * self.infl(i))))
            if kind == "ppf" and rng.random() < .4:
                pid2, c2, mk2 = skus[1]
                stk.append(dict(part_id=pid2, qty=1, unit_price=r2(c2 * mk2 * self.infl(i))))
        ro["so_plan"], ro["stk_plan"] = so, stk
        # sublet plan
        sub = []
        if towed:
            c = r2(rng.uniform(180, 450) * self.infl(i))
            sub.append(dict(vendor_id="VEN-TOW", description="Towing & storage", cost=c))
        if svc == "COL_MAJ" and rng.random() < .4 or svc == "COL_MOD" and rng.random() < .1:
            sub.append(dict(vendor_id="VEN-ALN", description="Four-wheel alignment & frame measurement (sublet)", cost=r2(rng.uniform(150, 320) * self.infl(i))))
        if svc == "COL_MAJ" and rng.random() < .08:
            sub.append(dict(vendor_id="VEN-UPH", description="Interior / upholstery repair (sublet)", cost=r2(rng.uniform(250, 900) * self.infl(i))))
        if svc == "MECH" and rng.random() < s["sublet"]:
            sub.append(dict(vendor_id="VEN-MEC", description="Specialist mechanical repair (sublet)", cost=r2(rng.uniform(300, 1200) * self.infl(i))))
        ro["sublet_plan"] = sub
        # estimate values
        yy = yr(est_i)
        drp = ro["insurer_id"] is not None and INS[ro["insurer_id"]][2].startswith("DRP")
        ro["drp"] = int(drp)
        ro["rates"] = {g: P.LABOUR_RATE[g][yy] * (P.DRP_RATE_FACTOR if drp else 1.0) for g in LINE_OPS}
        ro["mat_rate"] = P.PAINT_MATERIALS_RATE[yy]
        est_lab = sum(h * ro["rates"][g] for g, h in ro["est_ops"].items())
        est_parts = sum(l["unit_price"] * l["qty"] for l in so) + sum(l["unit_price"] * l["qty"] for l in stk)
        est_mat = ro["est_ops"].get("PAINT", 0) * ro["mat_rate"]
        est_sub = sum(x["cost"] * 1.18 for x in sub)
        ro["est_total"] = r2(est_lab + est_parts + est_mat + est_sub)
        ro["est_parts_price"] = r2(est_parts)
        ro["est_parts_cost"] = r2(sum(l["est_unit_cost"] * l["qty"] for l in so) + sum(self.part_cost[l["part_id"]] * self.infl(i) * l["qty"] for l in stk))
        # approval
        ro["status_final"] = None
        if ro["payer_type"] == "Insurance" and estimate_based:
            ins = INS[ro["insurer_id"]]
            lag = int(round(rng.gamma(2.0, ins[5] / 2.0)))
            app_i = self.next_open(b, est_i, lag)
            ratio = round(float(np.clip(rng.normal(ins[6], .02), .85, 1.0)), 4)
            ro["approval_ratio"] = ratio
            if svc in ("COL_MAJ", "COL_MOD") and rng.random() < {"COL_MAJ": .07, "COL_MOD": .012}[svc]:
                ro["status_final"] = "Total loss"
            elif rng.random() < .03:
                ro["status_final"] = "Repair declined (cash settlement)"
        elif estimate_based:
            app_i = self.next_open(b, est_i, int(rng.integers(0, 6)) if svc != "MECH" else 0)
            ro["approval_ratio"] = 1.0
            if svc == "MECH" and rng.random() < .12:
                ro["status_final"] = "Estimate declined (diagnostic fee)"
            elif svc != "MECH" and ro["payer_type"] != "Fleet account" and rng.random() < .28:
                ro["status_final"] = "Estimate declined"
        else:
            app_i = est_i
            ro["approval_ratio"] = 1.0
        ro["approval_day"] = app_i
        if ro["status_final"] is not None:
            so = []
            ro["so_plan"] = so
        # parts ordering (only once approved)
        ro["parts_ordered_day"] = None
        ro["parts_ready_day"] = app_i
        if ro["status_final"] is None and so:
            od = self.next_open(perf, app_i, int(rng.random() < .3))
            ro["parts_ordered_day"] = od
            last = od
            for ln in so:
                prom, recv, back = self.lead(ln["supplier_id"], perf, od)
                ln.update(order_day=od, promised_day=prom, received_day=recv, backorder=int(back), returned_day=None, replacement=0)
                if rng.random() < .045:                                         # wrong / damaged on arrival -> return and re-order
                    ret = self.next_open(perf, recv, int(rng.integers(0, 3)))
                    ln["returned_day"] = ret
                    p2, r2_, b2 = self.lead(ln["supplier_id"], perf, ret, kind="reorder")
                    rep = dict(ln, order_day=ret, promised_day=p2, received_day=r2_, backorder=0, returned_day=None, replacement=1)
                    so.append(rep)
                    last = max(last, r2_)
                else:
                    last = max(last, recv)
            ro["parts_ready_day"] = last

    def schedule(self):
        rng = self.rng
        INS = {x[0]: x for x in P.INSURERS}
        # vehicles that need to wait for parts are scheduled when parts are in; others on their requested date
        order = sorted(range(len(self.ros)), key=lambda k: (max(self.ros[k]["parts_ready_day"], self.ros[k]["approval_day"]), k))
        self.assign = []
        for k in order:
            ro = self.ros[k]
            self.run_job(ro, INS)
        # warranty comebacks (lifetime workmanship warranty): second pass, they use remaining capacity
        comebacks = []
        for ro in list(self.ros):
            if ro.get("delivered_day") is None or ro["status_final"] is not None or ro["warranty_of_ro"]:
                continue
            base = {"COL_MIN": .02, "COL_MOD": .035, "COL_MAJ": .05, "REFIN": .03, "MECH": .03, "MAINT": .008, "TIRE": .006, "GLS_REP": .02, "PPF": .03, "DET": .01,
                    "PDR": .015, "DIAG": .01, "GLS_CHIP": .02, "ADAS": .015}[ro["service_type"]]
            rf = np.mean([self.T[t]["rework_factor"] for t in ro.get("main_techs", [])] or [1.0])
            if rng.random() < base * rf:
                ci = ro["delivered_day"] + int(np.clip(rng.exponential(30), 4, 150))
                if ci < ND:
                    comebacks.append((ci, ro))
        comebacks.sort(key=lambda x: x[0])
        for ci, orig in comebacks:
            b = orig["branch_id"]
            perf = orig["performing_branch_id"]
            ci = self.next_open(b, ci)
            if ci >= ND:
                continue
            ops = {g: round(max(.3, h * rng.uniform(.12, .3)), 1) for g, h in orig["est_ops"].items() if g not in ("CALIB",)}
            ro = dict(ro_id=self.nid("RO", 6), branch_id=b, performing_branch_id=perf, customer_id=orig["customer_id"], vehicle_id=orig["vehicle_id"],
                      service_type=orig["service_type"], service_name=orig["service_name"], service_line=orig["service_line"], inquiry_day=ci, hail_related=0,
                      fleet=orig["fleet"], warranty_of_ro=orig["ro_id"], payer_type="Warranty (internal)", insurer_id=None, est_ops=ops, towed_in=0,
                      channel="Phone", estimate_day=ci, approval_day=ci, parts_ordered_day=None, parts_ready_day=ci, status_final=None, approval_ratio=1.0,
                      drp=0, rates={g: 0.0 for g in LINE_OPS}, mat_rate=0.0, est_total=0.0, est_parts_cost=0.0, so_plan=[], stk_plan=[], sublet_plan=[])
            if orig["so_plan"] and rng.random() < .3:
                ln = dict(orig["so_plan"][0])
                od = self.next_open(perf, ci)
                prom, recv, back = self.lead(ln["supplier_id"], perf, od)
                ln.update(order_day=od, promised_day=prom, received_day=recv, backorder=int(back), returned_day=None, replacement=0, unit_price=0.0, supplement=0)
                ro["so_plan"] = [ln]
                ro["parts_ordered_day"], ro["parts_ready_day"] = od, recv
                ro["est_parts_cost"] = ln["est_unit_cost"]
            self.ros.append(ro)
            self.run_job(ro, INS)

    def run_job(self, ro, INS):
        rng = self.rng
        svc, b, perf = ro["service_type"], ro["branch_id"], ro["performing_branch_id"]
        ready = max(ro["parts_ready_day"], ro["approval_day"])
        ro["supplement"] = None
        ro["chunks"] = []
        ro["internal_rework_hours"] = 0.0
        if ro["status_final"] in ("Estimate declined", "Repair declined (cash settlement)"):
            ro["closed_day"] = ro["approval_day"]
            return
        if ro["status_final"] in ("Total loss", "Estimate declined (diagnostic fee)"):
            g = "BODY" if ro["status_final"] == "Total loss" else "MECH"
            h = 1.5 if g == "BODY" else 1.0
            t0 = self.pick_tech(perf, g, ro["estimate_day"])
            ch, last, _ = self.book(perf, g, h, ro["estimate_day"], t0, ro["estimate_day"])
            ro["chunks"] += [(t, d, hh, g, 0) for t, d, hh in ch]
            ro["closed_day"] = max(ro["approval_day"], last if last is not None else ro["approval_day"])
            ro["work_start_day"] = ch[0][1] if ch else None
            ro["work_complete_day"] = last
            return
        if ready >= ND:
            return
        collision = svc in P.COLLISION or svc == "REFIN"
        # segments: collision = teardown (25% of body) -> [supplement] -> body -> paint -> mech -> calib
        segs = []
        ops = ro["est_ops"]
        if collision and "BODY" in ops:
            segs = [("BODY", round(ops["BODY"] * .25, 2), "teardown"), ("BODY", round(ops["BODY"] * .75, 2), "body")]
            segs += [(g, ops[g], g.lower()) for g in ("PAINT", "MECH", "CALIB") if g in ops]
        else:
            segs = [(g, h, g.lower()) for g, h in ops.items()]
        # supplement for hidden damage (estimate-based collision work)
        supp_p = {"COL_MIN": .10, "COL_MOD": .35, "COL_MAJ": .60}.get(svc, 0.0) if ro["warranty_of_ro"] is None else 0.0
        vehicle_in = ro["inquiry_day"] if ro["towed_in"] else None
        i = ready
        pref = {}
        first = None
        unfinished = False
        billed_by_op = defaultdict(float, {g: h for g, h in ops.items()})
        for si, (g, billed, tag) in enumerate(segs):
            if billed <= 0:
                continue
            if tag == "body" and ro["supplement"] is not None:
                i = max(i, ro["supplement"]["parts_ready_day"])
            if tag == "paint":
                i = i + 1 if first is not None else i
            if not self.group_techs[(perf, g)]:
                continue
            t0 = pref.get(g) or self.pick_tech(perf, g, i)
            eff = self.tech_eff(t0, i) if t0 else 1.0
            fixed_price_risk = 1.0 if ro["payer_type"] == "Insurance" else rng.lognormal(.04, .08)
            if ro["payer_type"] != "Insurance" and rng.random() < .07:
                fixed_price_risk *= rng.uniform(1.5, 2.4)                     # unforeseen complications on a fixed customer-pay quote
            actual = round(max(.2, billed / eff * rng.lognormal(0, .12) * fixed_price_risk), 2)
            if tag == "body" and ro["supplement"] is not None:
                actual = round(actual + ro["supplement"]["hours"].get("BODY", 0) / eff, 2)
            if tag == "paint" and ro["supplement"] is not None:
                actual = round(actual + ro["supplement"]["hours"].get("PAINT", 0) / eff, 2)
            ch, last, tl = self.book(perf, g, actual, i, t0, ready)
            if sum(c[2] for c in ch) < actual - 0.05:
                unfinished = True
            if not ch:
                break
            pref[g] = tl
            ro["chunks"] += [(t, d, hh, g, 0) for t, d, hh in ch]
            if first is None:
                first = ch[0][1]
            i = last
            if unfinished:
                break
            if tag == "teardown" and rng.random() < supp_p:
                ins = INS.get(ro["insurer_id"])
                lag = int(round(rng.gamma(2.0, (ins[5] if ins else 1.0) / 2.0))) if ins else int(rng.integers(0, 3))
                app = self.next_open(b, last, max(1, lag))
                share = rng.uniform(.15, .40)
                sh = {g2: round(h * share, 1) for g2, h in ops.items() if g2 in ("BODY", "PAINT")}
                supp = dict(request_day=last, approval_day=app, hours=sh, parts=[], parts_ready_day=app)
                veh_make = self.veh_make[ro["vehicle_id"]]
                vcat = self.veh_cat[ro["vehicle_id"]]
                for _ in range(int(rng.integers(1, 5))):
                    cat = ["Bumper reinforcement", "Radiator support", "Suspension arm", "Camera bracket & trim", "Door shell", "Radiator & condenser"][int(rng.integers(6))]
                    pid, cost, mk, sup = self.so_parts[(veh_make, cat)]
                    c = r2(cost * P.VEHICLE_CATEGORIES[vcat][1] * rng.lognormal(0, .25) * self.infl(app))
                    od = self.next_open(perf, app)
                    prom, recv, back = self.lead(sup, perf, od)
                    supp["parts"].append(dict(part_id=pid, supplier_id=sup, qty=1, est_unit_cost=c, unit_price=r2(c * mk), supplement=1, order_day=od,
                                              promised_day=prom, received_day=recv, backorder=int(back), returned_day=None, replacement=0))
                    supp["parts_ready_day"] = max(supp["parts_ready_day"], recv)
                ro["supplement"] = supp
                for g2, h in sh.items():
                    billed_by_op[g2] += h
        ro["billed_ops"] = {g: round(h, 1) for g, h in billed_by_op.items()}
        if not ro["chunks"]:
            return
        ro["work_start_day"] = min(d for _, d, *_ in ro["chunks"])
        last_work = max(d for _, d, *_ in ro["chunks"])
        ro["work_complete_day"] = None if unfinished else last_work             # unfinished = still in repair at the end of the simulation
        ro["vehicle_in_day"] = vehicle_in if vehicle_in is not None else ro["work_start_day"]
        if not collision and ro["warranty_of_ro"] is None:
            ro["vehicle_in_day"] = min(ro["work_start_day"], ro["vehicle_in_day"])
        ro["main_techs"] = sorted({t for t, *_ in ro["chunks"]})
        # completion promise given when the repair is scheduled: book hours at ~6.5 h/day plus a severity buffer (paint cure, QC, reassembly)
        est_days = int(math.ceil(sum(ops.values()) / 6.5)) + {"COL_MIN": 2, "COL_MOD": 3, "COL_MAJ": 5, "REFIN": 3}.get(svc, 0)
        ro["original_promised_day"] = self.next_open(b, ro["work_start_day"], est_days if collision or est_days > 1 else 0)
        ro["promised_day"] = ro["original_promised_day"]
        if ro["supplement"] is not None:                                         # promise revised once the supplement is approved and its parts are dated
            sp = ro["supplement"]
            rem = int(math.ceil(sum(v for g, v in ops.items() if g != "BODY") / 6.5 + 0.75 * ops.get("BODY", 0) / 6.5)) + 2
            ro["promised_day"] = max(ro["original_promised_day"], self.next_open(b, max(sp["approval_day"], sp["parts_ready_day"]), rem))
        if ro["work_complete_day"] is None:
            return
        # QC (collision & refinish); 4% fail -> internal rework before delivery
        qc = ro["work_complete_day"]
        if collision and rng.random() < .04:
            g = "PAINT" if "PAINT" in ops else "BODY"
            h = round(rng.uniform(.5, 2.0), 2)
            ch, last, _ = self.book(perf, g, h, qc + 1, pref.get(g), qc)
            if ch:
                ro["chunks"] += [(t, d, hh, g, 1) for t, d, hh in ch]
                ro["internal_rework_hours"] = h
                qc = last
        ro["qc_day"] = qc if not collision else self.next_open(perf, qc, int(rng.random() < .35))
        if collision:
            pick = 0 if b == "BR-SEC" else int(rng.choice([0, 1, 2, 3], p=[.4, .4, .14, .06]))
        else:
            pick = 0 if rng.random() < .88 else 1
        dd = self.next_open(b, ro["qc_day"], pick)
        ro["delivered_day"] = dd if dd <= END_I else None

    # ------------------------------------------------------------------------------------------- materialise tables
    def tables(self):
        rng = self.rng
        INS = {x[0]: x for x in P.INSURERS}
        D = lambda i: DAYS[i] if i is not None and i < ND else pd.NaT
        ro_rows, est_rows, claims, appts, inv_rows, pay_rows, asg_rows, ro_parts, sub_rows, ib_rows, so_po = [], [], [], [], [], [], [], [], [], [], []
        loaded = lambda t, i: self.T[t]["base_wage_2024"] * 1.03 ** (yr(i) - 2024) * (1 + P.PAYROLL_BURDEN)
        for ro in self.ros:
            b, perf, svc = ro["branch_id"], ro["performing_branch_id"], ro["service_type"]
            delivered = ro.get("delivered_day")
            closed = ro.get("closed_day")
            st = ro["status_final"]
            if st is None:
                if delivered is not None:
                    st = "Delivered"
                elif ro.get("work_complete_day") is not None:
                    st = "Ready for pickup"
                elif ro["chunks"]:
                    st = "In repair"
                elif ro["parts_ordered_day"] is not None and ro["parts_ready_day"] > END_I:
                    st = "Awaiting parts"
                elif ro["approval_day"] > END_I:
                    st = "Awaiting approval"
                else:
                    st = "Scheduled - waiting for technician"
            if ro["inquiry_day"] > END_I:
                continue
            billed = ro.get("billed_ops", ro["est_ops"] if st == "Delivered" else ro.get("billed_ops", ro["est_ops"]))
            if st in ("Estimate declined", "Repair declined (cash settlement)", "Total loss", "Estimate declined (diagnostic fee)"):
                billed = {}
            # assignments
            lab_cost = 0.0
            for (t, d, hh, g, rw) in ro["chunks"]:
                c = r2(hh * loaded(t, d))
                lab_cost += c
                asg_rows.append(dict(assignment_id=self.nid("ASG", 7), ro_id=ro["ro_id"], tech_id=t, branch_id=perf, work_date=DAYS[d], operation=g,
                                     clocked_hours=hh, internal_rework=rw, labour_cost_cad=c))
            # parts: special order (initial + supplement) and stocked
            so_all = list(ro["so_plan"]) + (ro["supplement"]["parts"] if ro.get("supplement") else [])
            start = ro.get("work_start_day")
            for ln in so_all:
                if ln.get("order_day") is None or ln["order_day"] > END_I:
                    continue
                lid = self.nid("POL", 7)
                ln["po_line_id"] = lid
                recv = ln["received_day"]
                issue = None
                if ln["returned_day"] is None and recv <= END_I and start is not None and ro["chunks"]:
                    issue = max(recv, start)
                    if ro.get("work_complete_day") is not None and issue > ro["work_complete_day"]:
                        issue = ro["work_complete_day"]
                    if issue > END_I:
                        issue = None
                act_cost = r2(ln["est_unit_cost"] * rng.lognormal(0, .045) * (rng.uniform(1.15, 1.45) if rng.random() < .05 else 1.0))   # 5%: price change / substitute part
                ln["actual_unit_cost"] = act_cost
                so_po.append(dict(po_line_id=lid, supplier_id=ln["supplier_id"], branch_id=perf, part_id=ln["part_id"], ro_id=ro["ro_id"],
                                  po_type="Special order", order_date=D(ln["order_day"]), promised_date=D(ln["promised_day"]),
                                  received_date=D(recv) if recv <= END_I else pd.NaT, qty_ordered=ln["qty"], unit_cost_cad=act_cost,
                                  backorder=ln["backorder"], returned_date=D(ln["returned_day"]) if ln["returned_day"] is not None and ln["returned_day"] <= END_I else pd.NaT,
                                  replacement_for_return=ln["replacement"], supplement=ln["supplement"], emergency=0))
                if ln["returned_day"] is None:
                    ro_parts.append(dict(ro_line_id=self.nid("ROL", 7), ro_id=ro["ro_id"], part_id=ln["part_id"], source="Special order", qty=ln["qty"], unit_cost_cad=act_cost,
                                         unit_price_cad=ln["unit_price"], supplement=ln["supplement"], issue_date=D(issue) if issue is not None else pd.NaT,
                                         po_line_id=lid, branch_id=perf))
            if start is not None and st not in ("Total loss", "Estimate declined (diagnostic fee)"):
                for ln in ro["stk_plan"]:
                    ro_parts.append(dict(ro_line_id=self.nid("ROL", 7), ro_id=ro["ro_id"], part_id=ln["part_id"], source="Stocked", qty=ln["qty"], unit_cost_cad=np.nan,
                                         unit_price_cad=ln["unit_price"] if ro["payer_type"] != "Warranty (internal)" else 0.0, supplement=0, issue_date=D(start),
                                         po_line_id=None, branch_id=perf))
            # sublets
            for x in ro["sublet_plan"]:
                if start is None or st in ("Total loss",):
                    continue
                sd = ro["vehicle_in_day"] if x["vendor_id"] == "VEN-TOW" else (ro.get("work_complete_day") or None)
                if sd is None or sd > END_I:
                    continue
                sub_rows.append(dict(sublet_id=self.nid("SUB", 6), ro_id=ro["ro_id"], vendor_id=x["vendor_id"], description=x["description"], sublet_date=DAYS[sd],
                                     cost_cad=x["cost"], billed_cad=r2(x["cost"] * 1.18) if ro["payer_type"] != "Warranty (internal)" else 0.0, branch_id=perf))
            ro["_lab_cost"] = lab_cost
            # post-delivery customer survey (35% response): late completion, long cycle, supplements and concierge service drive the score
            csat = np.nan
            if delivered is not None and ro["payer_type"] != "Warranty (internal)" and rng.random() < .35:
                late = ro.get("qc_day") is not None and ro.get("promised_day") is not None and ro["qc_day"] > ro["promised_day"]
                cyc = delivered - (ro.get("vehicle_in_day") or delivered)
                adj = (-0.85 if late else 0) - (0.35 if cyc > 14 else 0) - (0.1 if ro.get("supplement") else 0) + (0.15 if b == "BR-SEC" else 0) \
                    - (0.12 if ro["insurer_id"] and not ro["drp"] else 0) + (0.05 if svc in ("DET", "PPF") else 0)
                csat = float(np.clip(round(rng.normal(4.55 + adj, .6)), 1, 5))
            ro_rows.append(dict(
                ro_id=ro["ro_id"], branch_id=b, performing_branch_id=perf, interbranch=int(b != perf), customer_id=ro["customer_id"], vehicle_id=ro["vehicle_id"],
                service_type=svc, service_name=ro["service_name"], service_line=ro["service_line"], payer_type=ro["payer_type"], insurer_id=ro["insurer_id"],
                drp_insurer=ro["drp"], channel=ro["channel"], towed_in=ro["towed_in"], hail_related=ro["hail_related"], warranty_of_ro=ro["warranty_of_ro"],
                inquiry_date=D(ro["inquiry_day"]), estimate_date=D(ro["estimate_day"]), approval_date=D(ro["approval_day"]) if ro["approval_day"] <= END_I else pd.NaT,
                parts_ordered_date=D(ro["parts_ordered_day"]) if ro["parts_ordered_day"] is not None and ro["parts_ordered_day"] <= END_I else pd.NaT,
                parts_received_date=D(ro["parts_ready_day"]) if ro["parts_ordered_day"] is not None and ro["parts_ready_day"] <= END_I else pd.NaT,
                vehicle_in_date=D(ro.get("vehicle_in_day")) if ro.get("vehicle_in_day") is not None else pd.NaT,
                work_start_date=D(ro.get("work_start_day")) if ro.get("work_start_day") is not None else pd.NaT,
                work_complete_date=D(ro.get("work_complete_day")) if ro.get("work_complete_day") is not None else pd.NaT,
                qc_date=D(ro.get("qc_day")) if ro.get("qc_day") is not None and ro.get("qc_day") <= END_I else pd.NaT,
                original_promised_date=D(ro.get("original_promised_day")) if ro.get("original_promised_day") is not None and ro.get("original_promised_day") < ND else pd.NaT,
                promised_date=D(ro.get("promised_day")) if ro.get("promised_day") is not None and ro.get("promised_day") < ND else pd.NaT,
                delivered_date=D(delivered) if delivered is not None else pd.NaT,
                closed_date=D(closed) if closed is not None and closed <= END_I else (D(delivered) if delivered is not None else pd.NaT),
                status=st, supplement_count=int(ro.get("supplement") is not None),
                est_labour_hours=round(sum(ro["est_ops"].values()), 1), billed_labour_hours=round(sum(billed.values()), 1),
                clocked_labour_hours=round(sum(c[2] for c in ro["chunks"]), 2), internal_rework_hours=ro["internal_rework_hours"],
                **{f"billed_{g.lower()}_hours": round(billed.get(g, 0.0), 1) for g in LINE_OPS},
                csat_score=csat, est_total_cad=ro["est_total"], est_parts_cost_cad=ro["est_parts_cost"], approval_ratio=round(ro["approval_ratio"], 4),
                pre_period=int(ro["inquiry_day"] < START_I)))
            # estimates (initial + supplement) & claims
            ini_parts = ro.get("est_parts_price", 0.0)
            ini_lab = sum(h * ro["rates"][g] for g, h in ro["est_ops"].items())
            ini_mat = ro["est_ops"].get("PAINT", 0) * ro["mat_rate"]
            ini_sub = sum(x["cost"] * 1.18 for x in ro["sublet_plan"])
            app_status = {"Total loss": "Total loss", "Estimate declined": "Declined", "Repair declined (cash settlement)": "Declined (cash settlement)",
                          "Estimate declined (diagnostic fee)": "Declined"}.get(ro["status_final"], "Approved" if ro["approval_day"] <= END_I else "Pending")
            ratio = ro["approval_ratio"]
            if ro["payer_type"] != "Warranty (internal)":
                est_rows.append(dict(estimate_id=self.nid("EST", 6), ro_id=ro["ro_id"], estimate_type="Initial", estimate_date=D(ro["estimate_day"]),
                                     labour_hours=round(sum(ro["est_ops"].values()), 1), labour_cad=r2(ini_lab), parts_cad=r2(ini_parts), paint_materials_cad=r2(ini_mat),
                                     sublet_cad=r2(ini_sub), total_estimate_cad=r2(ini_lab + ini_parts + ini_mat + ini_sub),
                                     approved_by="Insurer" if ro["payer_type"] == "Insurance" else ("Fleet manager" if ro["payer_type"] == "Fleet account" else "Customer"),
                                     approval_date=D(ro["approval_day"]) if ro["approval_day"] <= END_I else pd.NaT, approval_status=app_status,
                                     approved_total_cad=r2((ini_lab + ini_parts + ini_mat + ini_sub) * ratio) if app_status == "Approved" else 0.0,
                                     est_parts_cost_cad=ro["est_parts_cost"]))
            sp = ro.get("supplement")
            if sp:
                s_lab = sum(h * ro["rates"][g] for g, h in sp["hours"].items())
                s_parts = sum(l["unit_price"] for l in sp["parts"])
                s_mat = sp["hours"].get("PAINT", 0) * ro["mat_rate"]
                est_rows.append(dict(estimate_id=self.nid("EST", 6), ro_id=ro["ro_id"], estimate_type="Supplement 1", estimate_date=D(sp["request_day"]),
                                     labour_hours=round(sum(sp["hours"].values()), 1), labour_cad=r2(s_lab), parts_cad=r2(s_parts), paint_materials_cad=r2(s_mat), sublet_cad=0.0,
                                     total_estimate_cad=r2(s_lab + s_parts + s_mat), approved_by="Insurer" if ro["payer_type"] == "Insurance" else "Customer",
                                     approval_date=D(sp["approval_day"]) if sp["approval_day"] <= END_I else pd.NaT,
                                     approval_status="Approved" if sp["approval_day"] <= END_I else "Pending", approved_total_cad=r2((s_lab + s_parts + s_mat) * ratio),
                                     est_parts_cost_cad=r2(sum(l["est_unit_cost"] for l in sp["parts"]))))
            if ro["payer_type"] == "Insurance":
                ins = INS[ro["insurer_id"]]
                ct = ("Comprehensive - hail" if ro["hail_related"] else ("Comprehensive - glass" if ro["service_line"] == "Glass repair" else
                      ("Collision (at fault)" if rng.random() < .5 else "DCPD (not at fault)")))
                opts, pr = P.CLAIM_TYPES[ct]
                ded = float(rng.choice(opts, p=pr))
                ro["claim_type"], ro["deductible"] = ct, ded
                n_comm = int(rng.poisson(3 + 2 * int(sp is not None) + (2 if ins[2].startswith("Non-DRP") else 0)))
                claims.append(dict(claim_id=self.nid("CLM", 6), ro_id=ro["ro_id"], insurer_id=ro["insurer_id"], claim_type=ct, claim_number=f"FICT-{rng.integers(1e7, 1e8)}",
                                   loss_date=D(max(0, ro["inquiry_day"] - int(rng.integers(0, 4)))), submitted_date=D(ro["estimate_day"]),
                                   approval_date=D(ro["approval_day"]) if ro["approval_day"] <= END_I else pd.NaT, deductible_cad=ded,
                                   estimate_value_cad=r2(ini_lab + ini_parts + ini_mat + ini_sub), approved_value_cad=r2((ini_lab + ini_parts + ini_mat + ini_sub) * ratio),
                                   supplement_count=int(sp is not None), supplement_estimate_cad=r2((s_lab + s_parts + s_mat)) if sp else 0.0,
                                   supplement_approved_cad=r2((s_lab + s_parts + s_mat) * ratio) if sp else 0.0, outcome=app_status,
                                   insurer_contacts=n_comm, admin_hours=round(0.35 * n_comm + (1.0 if sp else 0) + (0.8 if ins[2].startswith("Non-DRP") else 0.2), 2)))
            # appointment record (bookings that became ROs) + no-shows / cancellations generated separately
            appts.append(dict(appointment_id=self.nid("APT", 6), branch_id=b, customer_id=ro["customer_id"], vehicle_id=ro["vehicle_id"], channel=ro["channel"],
                              requested_service=svc, booked_on=D(ro["inquiry_day"]),
                              appointment_date=D(ro["estimate_day"] if (svc in P.COLLISION or svc == "REFIN") else (ro.get("work_start_day") or ro["estimate_day"])),
                              appointment_type="Estimate" if svc in P.COLLISION or svc == "REFIN" else ("Warranty inspection" if ro["warranty_of_ro"] else "Service"),
                              status="Completed", ro_id=ro["ro_id"]))
        self.ro_df = pd.DataFrame(ro_rows)
        self.est_df, self.claims_df, self.asg_df = pd.DataFrame(est_rows), pd.DataFrame(claims), pd.DataFrame(asg_rows)
        self.ro_parts_df, self.sub_df, self.so_po_df = pd.DataFrame(ro_parts), pd.DataFrame(sub_rows), pd.DataFrame(so_po)
        self.appts = appts
        self.no_shows()

    def no_shows(self):
        rng = self.rng
        extra = []
        for a in self.appts:
            if a["appointment_type"] == "Service" and rng.random() < .07:
                stt = "No-show" if rng.random() < .55 else "Cancelled by customer"
                extra.append(dict(a, appointment_id=self.nid("APT", 6), status=stt, ro_id=None,
                                  appointment_date=a["appointment_date"] - pd.Timedelta(days=int(rng.integers(1, 20)))))
        df = pd.DataFrame(self.appts + extra)
        df = df[df.appointment_date <= pd.Timestamp(END)]
        df.loc[df.booked_on > df.appointment_date, "booked_on"] = df.appointment_date
        self.appt_df = df.sort_values(["booked_on", "appointment_id"]).reset_index(drop=True)

    # ------------------------------------------------------------------------------------------- stocked-parts inventory & procurement
    def inventory(self):
        """Weekly (s,S) review of stocked parts per branch, set from average demand (the CURRENT, non-seasonal policy); a shortfall at issue time
        triggers an emergency same-day order from a local dealer at a premium. Special-order parts move receipt -> job -> issue."""
        rng = self.rng
        rp = self.ro_parts_df
        stk = rp[(rp.source == "Stocked") & rp.issue_date.notna()].copy()
        stk["day"] = ((stk.issue_date - DAY0).dt.days).astype(int)
        dem = stk.groupby(["branch_id", "part_id"]).qty.sum() / (ND / 7)
        policy = {}
        for (b, p), wk in dem.items():
            sup = self.part_supplier[p]
            lt = self.sup[sup][4] / 5
            s_ = max(1, int(math.ceil(wk * (lt + 1) * 1.0)))
            S_ = s_ + max(2, int(math.ceil(wk * 2)))
            policy[(b, p)] = (s_, S_)
        on = {k: (0 if k[0] == "BR-SEC" else S) for k, (s, S) in policy.items()}
        se_stock_day = int((pd.Timestamp("2025-04-24") - DAY0).days)
        pipeline = defaultdict(list)       # (b,p) -> [(arrive_day, qty, po_line_id)]
        moves, po_rows = [], []
        cost_layer = {}                    # moving-average cost per (b,p)
        for (b, p), (s_, S_) in policy.items():
            c = r2(self.part_cost[p] * self.infl(0) * 0.985)
            cost_layer[(b, p)] = c
            if b == "BR-SEC":
                continue
            moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=DAY0 - pd.Timedelta(days=1), branch_id=b, part_id=p, movement_type="OPENING_BALANCE",
                              inventory_state="stock", quantity=S_, unit_cost_cad=c, value_cad=r2(S_ * c), ro_id=None, po_line_id=None))
        by_day = defaultdict(list)
        for r in stk.itertuples():
            by_day[r.day].append(r)
        unit_cost_line = {}
        for d in range(ND):
            # receipts due today
            for (b, p), lst in list(pipeline.items()):
                keep = []
                for (arr, q, lid, uc) in lst:
                    if arr == d:
                        old_q, old_c = on[(b, p)], cost_layer[(b, p)]
                        on[(b, p)] += q
                        cost_layer[(b, p)] = r2((max(old_q, 0) * old_c + q * uc) / max(old_q + q, 1)) if old_q + q > 0 else uc
                        moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=DAYS[d], branch_id=b, part_id=p, movement_type="RECEIPT", inventory_state="stock",
                                          quantity=q, unit_cost_cad=uc, value_cad=r2(q * uc), ro_id=None, po_line_id=lid))
                    else:
                        keep.append((arr, q, lid, uc))
                pipeline[(b, p)] = keep
            # issues
            for r in by_day.get(d, []):
                k = (r.branch_id, r.part_id)
                if on[k] < r.qty:                                                # stockout -> emergency order received same day
                    q = int(r.qty - on[k])
                    sup = self.part_supplier[r.part_id]
                    uc = r2(self.part_cost[r.part_id] * self.infl(d) * (1 + self.sup[sup][7]))
                    lid = self.nid("POL", 7)
                    po_rows.append(dict(po_line_id=lid, supplier_id=sup, branch_id=r.branch_id, part_id=r.part_id, ro_id=r.ro_id, po_type="Emergency (stockout)",
                                        order_date=DAYS[d], promised_date=DAYS[d], received_date=DAYS[d], qty_ordered=q, unit_cost_cad=uc, backorder=0, returned_date=pd.NaT,
                                        replacement_for_return=0, supplement=0, emergency=1))
                    old_q, old_c = on[k], cost_layer[k]
                    on[k] += q
                    cost_layer[k] = r2((max(old_q, 0) * old_c + q * uc) / (old_q + q))
                    moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=DAYS[d], branch_id=r.branch_id, part_id=r.part_id, movement_type="RECEIPT", inventory_state="stock",
                                      quantity=q, unit_cost_cad=uc, value_cad=r2(q * uc), ro_id=r.ro_id, po_line_id=lid))
                c = cost_layer[k]
                on[k] -= r.qty
                unit_cost_line[r.ro_line_id] = c
                moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=DAYS[d], branch_id=r.branch_id, part_id=r.part_id, movement_type="ISSUE_TO_RO", inventory_state="stock",
                                  quantity=-r.qty, unit_cost_cad=c, value_cad=-r2(r.qty * c), ro_id=r.ro_id, po_line_id=None))
            # weekly review (Mondays); the new SE branch is stocked up-front before opening
            if self.weekday[d] == 0 or d == se_stock_day:
                for k, (s_, S_) in policy.items():
                    b, p = k
                    if b == "BR-SEC" and d < se_stock_day:
                        continue
                    if d == se_stock_day and b != "BR-SEC":
                        continue
                    pos = on[k] + sum(q for _, q, _, _ in pipeline[k])
                    if pos <= s_:
                        q = S_ - pos
                        sup = self.part_supplier[p]
                        prom, recv, back = self.lead(sup, b, d, kind="stock")
                        uc = r2(self.part_cost[p] * self.infl(d) * rng.lognormal(0, .02))
                        lid = self.nid("POL", 7)
                        po_rows.append(dict(po_line_id=lid, supplier_id=sup, branch_id=b, part_id=p, ro_id=None, po_type="Stock replenishment", order_date=DAYS[d],
                                            promised_date=DAYS[prom] if prom < ND else pd.NaT, received_date=DAYS[recv] if recv <= END_I else pd.NaT, qty_ordered=q,
                                            unit_cost_cad=uc, backorder=0, returned_date=pd.NaT, replacement_for_return=0, supplement=0, emergency=0))
                        if recv <= END_I:
                            pipeline[k].append((recv, q, lid, uc))
            # quarterly cycle counts: small adjustments; December write-off of damaged / obsolete items
            if DAYS[d].is_quarter_end:
                for k in list(policy)[:: 7]:
                    if on[k] > 3 and rng.random() < .25:
                        q = -int(rng.integers(1, 3)) if rng.random() < .8 else 1
                        typ = "WRITE_OFF_OBSOLETE" if DAYS[d].month == 12 and q < 0 else "CYCLE_COUNT_ADJ"
                        on[k] += q
                        moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=DAYS[d], branch_id=k[0], part_id=k[1], movement_type=typ, inventory_state="stock",
                                          quantity=q, unit_cost_cad=cost_layer[k], value_cad=r2(q * cost_layer[k]), ro_id=None, po_line_id=None))
        # special-order parts: receipt (job state) -> issue to RO / return to supplier
        for r in self.so_po_df.itertuples():
            if pd.isna(r.received_date):
                continue
            moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=r.received_date, branch_id=r.branch_id, part_id=r.part_id, movement_type="RECEIPT", inventory_state="job",
                              quantity=r.qty_ordered, unit_cost_cad=r.unit_cost_cad, value_cad=r2(r.qty_ordered * r.unit_cost_cad), ro_id=r.ro_id, po_line_id=r.po_line_id))
            if pd.notna(r.returned_date):
                moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=r.returned_date, branch_id=r.branch_id, part_id=r.part_id, movement_type="RETURN_TO_SUPPLIER",
                                  inventory_state="job", quantity=-r.qty_ordered, unit_cost_cad=r.unit_cost_cad, value_cad=-r2(r.qty_ordered * r.unit_cost_cad), ro_id=r.ro_id,
                                  po_line_id=r.po_line_id))
        so = rp[(rp.source == "Special order") & rp.issue_date.notna()]
        for r in so.itertuples():
            moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=r.issue_date, branch_id=r.branch_id, part_id=r.part_id, movement_type="ISSUE_TO_RO", inventory_state="job",
                              quantity=-r.qty, unit_cost_cad=r.unit_cost_cad, value_cad=-r2(r.qty * r.unit_cost_cad), ro_id=r.ro_id, po_line_id=r.po_line_id))
        rp.loc[rp.source == "Stocked", "unit_cost_cad"] = rp.loc[rp.source == "Stocked", "ro_line_id"].map(unit_cost_line)
        self.ro_parts_df = rp
        self.moves = moves
        self.po_df = pd.concat([self.so_po_df, pd.DataFrame(po_rows)], ignore_index=True)
        self.policy = pd.DataFrame([dict(branch_id=b, part_id=p, reorder_point=s, order_up_to=S) for (b, p), (s, S) in policy.items()])

    def materials(self):
        """Paint & refinish materials (billed per paint hour) and detailing chemicals (cost only), issued to ROs at the start of the
        paint / detail operation. Weekly top-up to 2.5 weeks of trailing use from the paint supplier; an emergency top-up is received
        the same day if a job would take the balance below zero. Valued in CAD (unit = $1)."""
        rng = self.rng
        a = self.asg_df
        ro = self.ro_df.set_index("ro_id")
        hrs = a.groupby(["ro_id", "operation"]).clocked_hours.sum()
        rows = []
        first = a[a.internal_rework == 0].groupby(["ro_id", "operation"]).work_date.min().reset_index()
        for r in first[first.operation.isin(["PAINT", "DETAIL", "PPF"])].itertuples():
            o = ro.loc[r.ro_id]
            if r.operation == "PAINT":
                billed = o.billed_paint_hours if o.payer_type != "Warranty (internal)" else hrs[(r.ro_id, "PAINT")]
                val = r2(billed * P.PAINT_MATERIALS_RATE[r.work_date.year] * P.PAINT_MATERIALS_COST_RATIO * rng.lognormal(0, .08))
                kind = "Paint & refinish materials"
            else:
                val = r2(hrs[(r.ro_id, r.operation)] * P.DETAIL_MATERIALS_PER_HOUR * self.infl(int((r.work_date - DAY0).days)) * rng.lognormal(0, .1))
                kind = "Detailing chemicals & supplies"
            if val > 0:
                rows.append(dict(ro_id=r.ro_id, branch_id=o.performing_branch_id, issue_date=r.work_date, material_type=kind, cost_cad=val))
        iss = pd.DataFrame(rows)
        moves, po_rows = [], []
        for (b, kind), g in iss.groupby(["branch_id", "material_type"]):
            pid = "MAT-PAINT" if kind.startswith("Paint") else "MAT-DETAIL"
            daily = g.groupby("issue_date").cost_cad.sum()
            bal = 0.0
            if b != "BR-SEC":
                bal = r2(daily.sum() / (ND / 7) * 2.5)
                moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=DAY0 - pd.Timedelta(days=1), branch_id=b, part_id=pid, movement_type="OPENING_BALANCE",
                                  inventory_state="materials", quantity=bal, unit_cost_cad=1.0, value_cad=bal, ro_id=None, po_line_id=None))
            by_day = {d: list(gg.itertuples()) for d, gg in g.groupby("issue_date")}

            def receive(d, v, emergency):
                nonlocal bal
                v = r2(v)
                lid = self.nid("POL", 7)
                po_rows.append(dict(po_line_id=lid, supplier_id="SUP-03", branch_id=b, part_id=pid, ro_id=None,
                                    po_type="Materials replenishment" + (" (emergency)" if emergency else ""), order_date=d - pd.Timedelta(days=0 if emergency else 3),
                                    promised_date=d, received_date=d, qty_ordered=v, unit_cost_cad=1.0, backorder=0, returned_date=pd.NaT, replacement_for_return=0,
                                    supplement=0, emergency=int(emergency)))
                moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=d, branch_id=b, part_id=pid, movement_type="RECEIPT", inventory_state="materials",
                                  quantity=v, unit_cost_cad=1.0, value_cad=v, ro_id=None, po_line_id=lid))
                bal = r2(bal + v)
            for d in DAYS:
                if d.weekday() == 0:
                    trail = daily[(daily.index < d) & (daily.index >= d - pd.Timedelta(days=14))].sum() / 2
                    tgt = trail * 2.5 * rng.uniform(.95, 1.05)
                    if tgt - bal > 1:
                        receive(d, tgt - bal, False)
                for r in by_day.get(d, []):
                    if bal < r.cost_cad:
                        receive(d, r.cost_cad - bal + 50.0, True)
                    bal = r2(bal - r.cost_cad)
                    moves.append(dict(movement_id=self.nid("MOV", 7), movement_date=d, branch_id=b, part_id=pid, movement_type="ISSUE_TO_RO", inventory_state="materials",
                                      quantity=-r.cost_cad, unit_cost_cad=1.0, value_cad=-r.cost_cad, ro_id=r.ro_id, po_line_id=None))
        self.mat_issues = iss
        self.moves += moves
        self.po_df = pd.concat([self.po_df, pd.DataFrame(po_rows)], ignore_index=True)

    # ------------------------------------------------------------------------------------------- invoices & payments
    def billing(self):
        rng = self.rng
        INS = {x[0]: x for x in P.INSURERS}
        ro = self.ro_df
        parts = self.ro_parts_df.groupby("ro_id").apply(lambda g: (g.qty * g.unit_price_cad).sum(), include_groups=False)
        sub = self.sub_df.groupby("ro_id").billed_cad.sum() if len(self.sub_df) else pd.Series(dtype=float)
        claims = self.claims_df.set_index("ro_id")
        inv, pay, ib = [], [], []
        rates = {r["ro_id"]: (r["rates"], r["mat_rate"], r.get("deductible", 0.0)) for r in self.ros}
        costs = self.ro_cost_components()
        for r in ro.itertuples():
            if r.status not in ("Delivered", "Total loss", "Estimate declined (diagnostic fee)"):
                continue
            idate = r.delivered_date if r.status == "Delivered" else r.closed_date
            if pd.isna(idate):
                continue
            rt, mr, ded = rates[r.ro_id]
            if r.status == "Total loss":
                comp = dict(labour=0.0, parts=0.0, materials=0.0, sublet=0.0, fees=P.TEARDOWN_FEE)
            elif r.status.startswith("Estimate declined"):
                comp = dict(labour=0.0, parts=0.0, materials=0.0, sublet=0.0, fees=P.DIAG_DECLINE_FEE * self.infl(int((idate - DAY0).days)))
            else:
                lab = sum(getattr(r, f"billed_{g.lower()}_hours") * rt[g] for g in LINE_OPS)
                comp = dict(labour=lab, parts=float(parts.get(r.ro_id, 0.0)), materials=r.billed_paint_hours * mr, sublet=float(sub.get(r.ro_id, 0.0)), fees=0.0)
                if r.payer_type == "Insurance":
                    comp = {k: v * r.approval_ratio for k, v in comp.items()}
            comp = {k: r2(v) for k, v in comp.items()}
            disc = 0.0
            late = pd.notna(r.qc_date) and pd.notna(r.promised_date) and (r.qc_date - r.promised_date).days >= 2
            if r.payer_type == "Fleet account":
                disc = r2(comp["labour"] * .07)
            elif r.payer_type == "Customer pay" and late and r.status == "Delivered":
                disc = r2((comp["labour"] + comp["parts"]) * rng.uniform(.10, .20))   # service-recovery (goodwill) discount on late customer-pay jobs
            elif r.payer_type == "Customer pay" and rng.random() < .08:
                disc = r2(comp["labour"] * .10)
            subtotal = r2(sum(comp.values()) - disc)
            if r.payer_type == "Warranty (internal)":
                subtotal = 0.0
            base = dict(ro_id=r.ro_id, branch_id=r.branch_id, invoice_date=idate, service_line=r.service_line, labour_cad=comp["labour"], parts_cad=comp["parts"],
                        paint_materials_cad=comp["materials"], sublet_cad=comp["sublet"], fees_cad=comp["fees"], discount_cad=disc)
            splits = []
            if r.payer_type == "Insurance":
                ded_amt = min(float(ded), subtotal) if r.status == "Delivered" else 0.0
                if ded_amt > 0:
                    splits.append(("Customer (deductible)", r.customer_id, ded_amt))
                splits.append(("Insurer", r.insurer_id, r2(subtotal - ded_amt)))
            elif r.payer_type == "Fleet account":
                splits.append(("Fleet account", r.customer_id, subtotal))
            elif r.payer_type == "Warranty (internal)":
                splits.append(("Warranty (no charge)", r.customer_id, 0.0))
            else:
                splits.append(("Customer", r.customer_id, subtotal))
            for k, (bt, who, amt) in enumerate(splits):
                share = amt / subtotal if subtotal else (1.0 if k == 0 else 0.0)
                iid = self.nid("INV", 6)
                gst = r2(amt * P.GST)
                row = dict(base, invoice_id=iid, bill_to_type=bt, bill_to_id=who, share_of_ro=round(share, 6), subtotal_cad=r2(amt), gst_cad=gst, total_cad=r2(amt + gst))
                inv.append(row)
                total = r2(amt + gst)
                if total <= 0:
                    continue
                if bt.startswith("Customer"):
                    tender = rng.choice(["Credit card", "Debit", "E-transfer"], p=[.68, .27, .05])
                    pay.append(dict(payment_id=self.nid("PAY", 7), invoice_id=iid, payment_date=idate, payer_type=bt, tender=str(tender), amount_cad=total,
                                    short_pay_adjustment_cad=0.0))
                elif bt == "Insurer":
                    ins = INS[who]
                    lag = max(3, int(rng.normal(ins[3], ins[4])))
                    if rng.random() < .004:
                        lag += int(rng.integers(40, 90))
                    pdte = idate + pd.Timedelta(days=lag)
                    short = r2(total * rng.uniform(.02, .08)) if rng.random() < .025 else 0.0
                    if pdte <= pd.Timestamp(END):
                        pay.append(dict(payment_id=self.nid("PAY", 7), invoice_id=iid, payment_date=pdte, payer_type="Insurer", tender="EFT", amount_cad=r2(total - short),
                                        short_pay_adjustment_cad=short))
                else:
                    lag = max(10, int(rng.normal(33, 7)))
                    pdte = idate + pd.Timedelta(days=lag)
                    if pdte <= pd.Timestamp(END):
                        pay.append(dict(payment_id=self.nid("PAY", 7), invoice_id=iid, payment_date=pdte, payer_type="Fleet account", tender="EFT", amount_cad=total,
                                        short_pay_adjustment_cad=0.0))
            if r.interbranch and r.status == "Delivered":
                c = costs.get(r.ro_id, {})
                tp = r2(c.get("parts", 0) + c.get("materials", 0) + c.get("sublet", 0) + r.billed_labour_hours * P.INTERNAL_LABOUR_RATE)
                ib.append(dict(transfer_id=self.nid("IBT", 6), ro_id=r.ro_id, selling_branch_id=r.branch_id, performing_branch_id=r.performing_branch_id,
                               transfer_date=idate, service_type=r.service_type, transfer_price_cad=tp,
                               basis="Parts, materials & sublet at cost + billed hours x internal labour rate"))
        self.inv_df, self.pay_df, self.ib_df = pd.DataFrame(inv), pd.DataFrame(pay), pd.DataFrame(ib)

    def ro_cost_components(self):
        rp = self.ro_parts_df[self.ro_parts_df.issue_date.notna()]
        out = defaultdict(dict)
        for k, v in (rp.qty * rp.unit_cost_cad).groupby(rp.ro_id).sum().items():
            out[k]["parts"] = v
        for k, v in self.mat_issues.groupby("ro_id").cost_cad.sum().items():
            out[k]["materials"] = v
        if len(self.sub_df):
            for k, v in self.sub_df.groupby("ro_id").cost_cad.sum().items():
                out[k]["sublet"] = v
        return out

    # ------------------------------------------------------------------------------------------- timesheets & opex
    def timesheets(self):
        rows = []
        a = self.asg_df.groupby(["tech_id", "work_date"]).clocked_hours.sum()
        for t in self.techs:
            tid = t["tech_id"]
            s, ab, tr, cap = self.sched[tid], self.absence[tid], self.training[tid], self.cap[tid]
            for i in range(ND):
                if s[i] <= 0 and (tid, DAYS[i]) not in a.index:
                    continue
                prod = float(a.get((tid, DAYS[i]), 0.0))
                avail = s[i] if ab[i] == "" else 0.0
                reg_cap = cap[i]
                ot = round(max(0.0, prod - reg_cap) / P.PRODUCTIVE_SHARE, 2) if prod > reg_cap + 1e-6 else 0.0
                rows.append(dict(timesheet_id=self.nid("TS", 7), tech_id=tid, branch_id=t["branch_id"], work_date=DAYS[i], scheduled_hours=s[i],
                                 absence_type=ab[i] or None, paid_absence_hours=s[i] if ab[i] else 0.0, training_hours=tr[i], available_hours=round(avail, 2),
                                 overtime_hours=ot, attended_hours=round(avail + ot, 2), productive_hours=round(prod, 2),
                                 hourly_wage_cad=r2(t["base_wage_2024"] * 1.03 ** (DAYS[i].year - 2024))))
        self.ts_df = pd.DataFrame(rows)

    def opex(self):
        rng = self.rng
        months = pd.period_range(P.SIM_START, END, freq="M")
        card = self.pay_df[self.pay_df.tender.isin(["Credit card", "Debit"])].merge(self.inv_df[["invoice_id", "branch_id"]], on="invoice_id")
        card_m = card.groupby([card.branch_id, card.payment_date.dt.to_period("M")]).amount_cad.sum()
        rows, staff_rows = [], []
        for m in months:
            infl = (1 + P.OPEX_INFLATION) ** (m.year - 2024)
            winter = m.month in (11, 12, 1, 2, 3)
            for b, plan in P.OPEX_PLAN.items():
                row = dict(month=m.to_timestamp(), branch_id=b)
                if b == "HO":
                    stf = sum(n * sal for role, n, sal in plan["staff"] if role != "Marketing coordinator" or m >= pd.Period("2025-01", "M"))
                    launch = 25000.0 if str(m) in ("2025-04", "2025-05") else 0.0
                    row.update(staff_wages_cad=r2(stf * infl * (1 + P.STAFF_BURDEN)), marketing_cad=r2((plan["marketing"] + launch) * infl * rng.uniform(.9, 1.1)),
                               insurance_cad=r2(plan["insurance"] * infl * (1.15 if m >= pd.Period("2025-05", "M") else 1.0)), professional_fees_cad=r2(plan["professional"] * infl * rng.uniform(.85, 1.25)),
                               software_it_cad=r2(plan["software"] * infl), training_certification_cad=r2(plan["training"] * infl * (2.5 if m.month == 1 else 1.0)))
                else:
                    if b == "BR-SEC" and m < pd.Period(P.SE_LEASE_START, "M"):
                        continue
                    opened = m >= pd.Period("2025-05", "M") or b != "BR-SEC"
                    stf = sum(n * sal for role, n, sal in plan["staff"]) if (opened or m >= pd.Period("2025-04", "M")) else 0.0
                    row.update(staff_wages_cad=r2(stf * infl * (1 + P.STAFF_BURDEN)), rent_cad=r2(plan["rent"] * infl), cam_property_tax_cad=r2(plan["cam"] * infl),
                               utilities_cad=r2((plan["util_winter"] if winter else plan["util_summer"]) * infl * rng.uniform(.92, 1.08) * (1 if opened else .4)),
                               shop_supplies_cad=r2(plan["supplies"] * infl * rng.uniform(.9, 1.1) * (1 if opened else .1)),
                               equipment_maintenance_cad=r2(plan["equip_maint"] * infl * rng.uniform(.7, 1.4) * (1 if opened else 0)),
                               software_it_cad=r2(plan["software"] * infl * (1 if opened else .5)), network_certification_fees_cad=r2(plan["network_fees"] * infl * (1 if opened else 0)),
                               courier_waste_cad=r2(plan["courier_waste"] * infl * rng.uniform(.85, 1.15) * (1 if opened else 0)),
                               courtesy_vehicles_concierge_cad=r2(plan["courtesy"] * infl * (1 if opened else 0)),
                               card_processing_fees_cad=r2(card_m.get((b, m), 0.0) * P.CARD_FEE_RATE))
                rows.append(row)
        self.opex_df = pd.DataFrame(rows).fillna(0.0)

    # ------------------------------------------------------------------------------------------- run & save
    def run(self):
        self.staff()
        self.setup_pools()
        self.catalogue()
        inq = self.demand()
        self.make_ros_with_vehicle_maps(inq)
        self.schedule()
        self.tables()
        self.inventory()
        self.materials()
        self.billing()
        self.timesheets()
        self.opex()

    def make_ros_with_vehicle_maps(self, inq):
        self.veh_make, self.veh_cat = {}, {}
        orig = self.new_vehicle

        def wrapped(cid, fleet=False):
            v = orig(cid, fleet)
            self.veh_make[v["vehicle_id"]] = v["make"]
            self.veh_cat[v["vehicle_id"]] = v["vehicle_category"]
            return v
        self.new_vehicle = wrapped
        for v in self.vehicles:
            self.veh_make[v["vehicle_id"]] = v["make"]
            self.veh_cat[v["vehicle_id"]] = v["vehicle_category"]
        self.make_ros(inq)

    def save(self):
        lab = "SYNTHETIC"
        branches = pd.DataFrame([dict(branch_id=b, branch_name=n, role=r, opened_date=o, saturday_hours=s, repair_bays=bays,
                                      weekday_hours="08:00-17:00", saturday_open="10:00-13:00" if s else "Closed") for b, n, r, o, s, bays in P.BRANCHES])
        cust = pd.DataFrame(self.customers)
        veh = pd.DataFrame(self.vehicles)
        used_c = set(self.ro_df.customer_id) | set(self.appt_df.customer_id)
        cust = cust[cust.customer_id.isin(used_c)]
        veh = veh[veh.customer_id.isin(cust.customer_id)]
        techs = pd.DataFrame(self.techs)
        ins = pd.DataFrame(P.INSURERS, columns=["insurer_id", "insurer_name", "insurer_category", "payment_days_mean", "payment_days_sd", "approval_days_mean",
                                                "approval_ratio_mean", "share_of_claims"])
        sup = pd.DataFrame(P.SUPPLIERS, columns=["supplier_id", "supplier_name", "supplier_type", "payment_terms_days", "lead_time_mean_days", "lead_time_sd_days",
                                                 "on_time_target", "emergency_premium"])
        vend = pd.DataFrame(P.SUBLET_VENDORS + [("VEN-UTIL", "Utility provider", "Utilities"), ("VEN-OPS", "Operating vendors (various)", "Operating")],
                            columns=["vendor_id", "vendor_name", "vendor_type"])
        mats = pd.DataFrame([dict(part_id="MAT-PAINT", part_number="MAT-PAINT", description="Paint & refinish materials (valued in CAD)", part_category="materials",
                                  part_type="Materials", oem_or_aftermarket="Paint system", make=None, standard_unit_cost_2024=1.0, unit_list_price_2024=None,
                                  default_supplier_id="SUP-03", stocked_at="BR-CCC|BR-NFS|BR-SEC"),
                             dict(part_id="MAT-DETAIL", part_number="MAT-DETAIL", description="Detailing chemicals & supplies (valued in CAD)", part_category="materials",
                                  part_type="Materials", oem_or_aftermarket="Supplier brand", make=None, standard_unit_cost_2024=1.0, unit_list_price_2024=None,
                                  default_supplier_id="SUP-03", stocked_at="BR-CCC|BR-NFS|BR-SEC")])
        parts = pd.concat([self.parts, mats], ignore_index=True)
        moves = pd.DataFrame(self.moves).sort_values(["movement_date", "movement_id"]).reset_index(drop=True)
        out = {"branches": branches, "customers": cust, "vehicles": veh, "repair_orders": self.ro_df, "repair_estimates": self.est_df, "insurers": ins,
               "insurance_claims": self.claims_df, "technicians": techs, "technician_timesheets": self.ts_df, "job_assignments": self.asg_df, "parts_catalogue": parts,
               "ro_part_lines": self.ro_parts_df, "parts_inventory_movements": moves, "suppliers": sup, "supplier_purchase_orders": self.po_df,
               "stock_policy_current": self.policy, "sublet_lines": self.sub_df, "sublet_vendors": vend, "service_appointments": self.appt_df,
               "customer_invoices": self.inv_df, "payments": self.pay_df, "interbranch_transfers": self.ib_df, "materials_issues": self.mat_issues,
               "operating_expenses": self.opex_df}
        for name, df in out.items():
            df = df.copy()
            df["data_status"] = lab
            df.to_csv(SYNTH / f"{name}.csv", index=False, date_format="%Y-%m-%d")
        return {k: len(v) for k, v in out.items()}


def main():
    g = Gen()
    g.run()
    return g.save()


if __name__ == "__main__":
    import time
    t = time.time()
    print(main(), f"{time.time() - t:.0f}s")
