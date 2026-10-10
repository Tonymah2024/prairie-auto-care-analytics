"""Business parameters of the FICTIONAL Prairie Auto Care Group used by the synthetic generator.

Everything here is an ASSUMPTION chosen to be plausible for a multi-location Calgary collision & car care business in
2024-2026 (CAD). Public facts used: three locations with distinct roles, published hours, the advertised service menu,
OEM-certified collision work and direct billing of insurers. No real company's volumes, prices, staff or financial
figures are used. All insurers, suppliers, customers and staff are fictional.
"""
from __future__ import annotations

SIM_START = "2023-10-01"            # warm-up quarter (records flagged pre_period = 1) used only to build the opening position

BRANCHES = [  # id, name, role, opened, Saturday hours, bays, notes
    ("BR-SEC", "Southeast Concierge", "Newest location: detailing, paint protection, PDR, light collision; concierge drop-off/pickup; moderate & major "
     "collision repaired at Central (interbranch)", "2025-05-01", 3.0, 8),
    ("BR-CCC", "Central Collision Centre", "Collision & auto body hub: structural, refinish, ADAS calibration, OEM-certified repairs", "2016-01-01", 0.0, 14),
    ("BR-NFS", "North Full-Service", "Full-service: collision, mechanical, tires, diagnostics, glass, detailing", "2019-01-01", 3.0, 12),
]
BRANCH_IDS = [b[0] for b in BRANCHES]
BRANCH_NAME = {b[0]: b[1] for b in BRANCHES}
SE_RAMP_MONTHS = 9                   # SE demand ramps linearly to maturity over 9 months after opening

LINES = ["Collision repair", "Mechanical service", "Detailing", "Glass repair", "Other services"]

# service types: code, name, revenue line, op split {op: share of billed hours}, median billed hours, sigma, insured share,
# special-order part lines (min, max), stocked part kinds, sublet probability, monthly base demand by branch {CCC, NFS, SEC}
SERVICES = {
    "COL_MIN": dict(name="Collision repair - minor (bumper, scuffs, lamps)", line="Collision repair", ops={"BODY": .55, "PAINT": .45}, hours=6.0, sigma=.35,
                    insured=.55, so_lines=(1, 3), stocked=["clips"], sublet=.03, base={"BR-CCC": 26, "BR-NFS": 14, "BR-SEC": 13}),
    "COL_MOD": dict(name="Collision repair - moderate (panels, lamps, bumpers)", line="Collision repair", ops={"BODY": .55, "PAINT": .37, "MECH": .04, "CALIB": .04},
                    hours=15.0, sigma=.35, insured=.85, so_lines=(3, 8), stocked=["clips"], sublet=.25, base={"BR-CCC": 27, "BR-NFS": 14, "BR-SEC": 5}),
    "COL_MAJ": dict(name="Collision repair - major / structural", line="Collision repair", ops={"BODY": .58, "PAINT": .30, "MECH": .07, "CALIB": .05},
                    hours=38.0, sigma=.35, insured=.95, so_lines=(8, 18), stocked=["clips"], sublet=.70, base={"BR-CCC": 11, "BR-NFS": 5, "BR-SEC": 2}),
    "REFIN": dict(name="Auto painting & refinish", line="Collision repair", ops={"BODY": .15, "PAINT": .85}, hours=10.0, sigma=.45, insured=.05, so_lines=(0, 1),
                  stocked=[], sublet=0.0, base={"BR-CCC": 6, "BR-NFS": 3, "BR-SEC": 3}),
    "PDR": dict(name="Paintless dent repair", line="Other services", ops={"PDR": 1.0}, hours=3.5, sigma=.5, insured=.35, so_lines=(0, 0), stocked=[], sublet=0.0,
                base={"BR-CCC": 5, "BR-NFS": 3, "BR-SEC": 8}),
    "GLS_REP": dict(name="Windshield replacement", line="Glass repair", ops={"GLASS": .8, "CALIB": .2}, hours=2.2, sigma=.2, insured=.6, so_lines=(1, 1),
                    stocked=["urethane"], sublet=0.0, base={"BR-CCC": 14, "BR-NFS": 18, "BR-SEC": 5}),
    "GLS_CHIP": dict(name="Glass chip & crack repair", line="Glass repair", ops={"GLASS": 1.0}, hours=0.6, sigma=.25, insured=.5, so_lines=(0, 0), stocked=["resin"],
                     sublet=0.0, base={"BR-CCC": 10, "BR-NFS": 14, "BR-SEC": 6}),
    "ADAS": dict(name="ADAS calibration", line="Other services", ops={"CALIB": 1.0}, hours=1.6, sigma=.2, insured=.4, so_lines=(0, 0), stocked=[], sublet=0.0,
                 base={"BR-CCC": 9, "BR-NFS": 5, "BR-SEC": 0}),
    "DIAG": dict(name="Diagnostics", line="Mechanical service", ops={"MECH": 1.0}, hours=1.2, sigma=.35, insured=0.0, so_lines=(0, 0), stocked=[], sublet=0.0,
                 base={"BR-CCC": 4, "BR-NFS": 38, "BR-SEC": 4}),
    "MAINT": dict(name="Maintenance (oil, brakes, fluids)", line="Mechanical service", ops={"MECH": 1.0}, hours=1.5, sigma=.35, insured=0.0, so_lines=(0, 1),
                  stocked=["oil", "filter", "pads", "wipers", "battery"], sublet=0.0, base={"BR-CCC": 9, "BR-NFS": 128, "BR-SEC": 22}),
    "MECH": dict(name="Mechanical repairs & alignment", line="Mechanical service", ops={"MECH": 1.0}, hours=3.4, sigma=.45, insured=.12, so_lines=(0, 3),
                 stocked=["pads", "rotors"], sublet=.06, base={"BR-CCC": 6, "BR-NFS": 52, "BR-SEC": 6}),
    "TIRE": dict(name="Tires & wheels (changeovers, tire sales)", line="Mechanical service", ops={"MECH": 1.0}, hours=0.9, sigma=.25, insured=0.0, so_lines=(0, 1),
                 stocked=["tire", "tpms"], sublet=0.0, base={"BR-CCC": 4, "BR-NFS": 105, "BR-SEC": 30}),
    "DET": dict(name="Interior & exterior detailing", line="Detailing", ops={"DETAIL": 1.0}, hours=4.0, sigma=.35, insured=0.0, so_lines=(0, 0), stocked=[],
                sublet=0.0, base={"BR-CCC": 15, "BR-NFS": 16, "BR-SEC": 62}),
    "PPF": dict(name="Paint protection (film, ceramic coating)", line="Other services", ops={"PPF": 1.0}, hours=7.0, sigma=.45, insured=0.0, so_lines=(0, 0),
                stocked=["ppf"], sublet=0.0, base={"BR-CCC": 2, "BR-NFS": 2, "BR-SEC": 12}),
}
COLLISION = {"COL_MIN", "COL_MOD", "COL_MAJ"}

# labour selling rates (CAD per billed hour) by year; DRP insurers pay the negotiated door rate (x DRP_RATE_FACTOR)
LABOUR_RATE = {
    "BODY": {2023: 116, 2024: 121, 2025: 126, 2026: 131}, "PAINT": {2023: 116, 2024: 121, 2025: 126, 2026: 131},
    "MECH": {2023: 162, 2024: 168, 2025: 174, 2026: 180}, "CALIB": {2023: 195, 2024: 205, 2025: 215, 2026: 225},
    "GLASS": {2023: 115, 2024: 120, 2025: 124, 2026: 128}, "DETAIL": {2023: 82, 2024: 86, 2025: 90, 2026: 94},
    "PPF": {2023: 120, 2024: 125, 2025: 130, 2026: 136}, "PDR": {2023: 120, 2024: 125, 2025: 130, 2026: 135},
}
DRP_RATE_FACTOR = 0.97
PAINT_MATERIALS_RATE = {2023: 49.0, 2024: 51.0, 2025: 53.0, 2026: 55.0}   # billed per refinish hour
PAINT_MATERIALS_COST_RATIO = 0.55                                           # cost of paint & materials consumed / materials billed
DETAIL_MATERIALS_PER_HOUR = 6.5                                             # detailing chemicals consumed (cost, not billed separately)
INTERNAL_LABOUR_RATE = 78.0                                                 # interbranch transfer price per billed hour (+ parts/materials at cost)
DIAG_DECLINE_FEE = 165.0
TEARDOWN_FEE = 650.0                                                        # total-loss teardown, estimate & storage fee billed to the insurer
GST = 0.05

VEHICLE_CATEGORIES = {  # category: (share, parts multiplier, hours multiplier, ADAS-equipped probability)
    "Compact & sedan": (.27, .85, .95, .55), "SUV & crossover": (.36, 1.0, 1.0, .80), "Pickup truck": (.19, 1.15, 1.05, .70),
    "Luxury": (.08, 1.6, 1.15, .95), "EV & hybrid": (.06, 1.45, 1.1, .97), "Commercial van": (.04, 1.1, 1.05, .6),
}
MAKES = {  # make: (share, categories it appears in)
    "Toyota": (.15, ["Compact & sedan", "SUV & crossover", "Pickup truck", "EV & hybrid"]), "Ford": (.13, ["SUV & crossover", "Pickup truck", "Commercial van"]),
    "Honda": (.09, ["Compact & sedan", "SUV & crossover"]), "Chevrolet": (.08, ["SUV & crossover", "Pickup truck", "Commercial van"]),
    "Ram": (.07, ["Pickup truck", "Commercial van"]), "Hyundai": (.09, ["Compact & sedan", "SUV & crossover", "EV & hybrid"]),
    "Kia": (.07, ["Compact & sedan", "SUV & crossover", "EV & hybrid"]), "Genesis": (.02, ["Luxury"]), "Nissan": (.05, ["Compact & sedan", "SUV & crossover"]),
    "Mazda": (.05, ["Compact & sedan", "SUV & crossover"]), "Subaru": (.05, ["SUV & crossover"]), "Volkswagen": (.03, ["Compact & sedan", "SUV & crossover"]),
    "GMC": (.04, ["Pickup truck", "SUV & crossover"]), "BMW": (.03, ["Luxury"]), "Mercedes-Benz": (.02, ["Luxury", "Commercial van"]),
    "Tesla": (.02, ["EV & hybrid"]), "Jeep": (.01, ["SUV & crossover"]),
}
OEM_CERT_MAKES = {"Hyundai", "Kia", "Genesis"}       # collision work for these makes is weighted toward Central (OEM-certified repairs)

# special-order part categories: (base cost CAD, markup price/cost, applicable services)
SO_PARTS = {
    "Front bumper cover": (268, 1.40, "C"), "Rear bumper cover": (248, 1.40, "C"), "Bumper reinforcement": (166, 1.40, "C"), "Grille assembly": (197, 1.40, "C"),
    "Headlamp assembly": (440, 1.40, "C"), "Tail lamp assembly": (211, 1.40, "C"), "Fender": (217, 1.40, "C"), "Hood panel": (395, 1.40, "C"),
    "Door shell": (497, 1.40, "C"), "Door mirror assembly": (248, 1.40, "C"), "Quarter panel": (542, 1.40, "C"), "Radiator support": (306, 1.40, "C"),
    "Radiator & condenser": (408, 1.40, "C"), "Airbag module": (625, 1.30, "C"), "Radar / ADAS sensor": (733, 1.30, "C"), "Camera bracket & trim": (89, 1.40, "C"),
    "Suspension arm": (185, 1.40, "CM"), "Wheel / rim": (332, 1.40, "CM"), "Alternator / starter": (274, 1.42, "M"), "Strut assembly": (230, 1.42, "M"),
    "Windshield (model-specific)": (390, 1.35, "G"), "Tire (special-order size)": (172, 1.25, "T"),
}
# stocked parts: kind: (list of (description, unit cost, markup), qty per use (min, max), stocked at)
STOCKED = {
    "clips": ([("Clips & fasteners kit", 18.0, 2.2)], (1, 3), ["BR-CCC", "BR-NFS", "BR-SEC"]),
    "urethane": ([("Windshield urethane & primer kit", 32.0, 1.9)], (1, 1), ["BR-CCC", "BR-NFS", "BR-SEC"]),
    "resin": ([("Glass repair resin kit", 9.0, 2.5)], (1, 1), ["BR-CCC", "BR-NFS", "BR-SEC"]),
    "oil": ([("Synthetic engine oil 0W-20 (L)", 7.2, 1.9), ("Synthetic engine oil 5W-30 (L)", 7.0, 1.9), ("Diesel engine oil 15W-40 (L)", 6.4, 1.9)],
            (5, 8), ["BR-NFS", "BR-SEC", "BR-CCC"]),
    "filter": ([(f"Oil filter type {c}", 8.5 + i, 2.1) for i, c in enumerate("ABCDEFGH")] + [(f"Cabin air filter type {c}", 14.0 + i, 2.0) for i, c in enumerate("ABCD")],
               (1, 2), ["BR-NFS", "BR-SEC", "BR-CCC"]),
    "pads": ([(f"Brake pad set {p} - family {c}", 46.0 + 6 * i + (12 if p == 'front' else 0), 1.9) for i, c in enumerate("ABCDEF") for p in ("front", "rear")],
             (1, 2), ["BR-NFS", "BR-SEC", "BR-CCC"]),
    "rotors": ([(f"Brake rotor - family {c}", 72.0 + 9 * i, 1.75) for i, c in enumerate("ABCDEF")], (2, 2), ["BR-NFS", "BR-CCC"]),
    "wipers": ([(f"Wiper blade {s}", 11.0 + i, 2.3) for i, s in enumerate(['16"', '18"', '20"', '22"', '24"', '26"'])], (2, 2), ["BR-NFS", "BR-SEC", "BR-CCC"]),
    "battery": ([(f"Battery group {g}", 135.0 + 18 * i, 1.55) for i, g in enumerate(["35", "48", "65", "94R"])], (1, 1), ["BR-NFS", "BR-SEC"]),
    "tire": ([(f"{t} tire {s}", c, 1.28) for s, c0 in [("205/55R16", 118), ("215/60R16", 124), ("225/65R17", 152), ("235/65R17", 160), ("225/60R18", 171),
                                                      ("235/60R18", 178), ("245/60R18", 186), ("265/70R17", 205), ("275/65R18", 224), ("275/55R20", 248)]
              for t, c in (("Winter", c0 * 1.08), ("All-season", c0))], (4, 4), ["BR-NFS", "BR-SEC"]),
    "tpms": ([("TPMS sensor", 46.0, 1.9), ("Valve stem & TPMS service kit", 6.0, 3.0)], (1, 4), ["BR-NFS", "BR-SEC"]),
    "ppf": ([("Paint protection film (per metre)", 58.0, 2.0), ("Ceramic coating kit", 85.0, 2.4)], (3, 9), ["BR-SEC", "BR-CCC", "BR-NFS"]),
}

SUPPLIERS = [  # id, name, type, payment terms (days), lead time mean (days), lead sd, on-time base, emergency premium
    ("SUP-01", "Bow City OEM Parts Network (fictional)", "OEM dealer parts", 30, 1.8, 1.0, .88, .12),
    ("SUP-02", "Chinook Aftermarket Supply (fictional)", "Aftermarket & certified parts", 30, 2.8, 1.5, .80, .15),
    ("SUP-03", "Prairie Paint & Refinish Supply (fictional)", "Paint & refinish materials", 30, 1.5, 0.8, .93, .10),
    ("SUP-04", "Westline Glass Distribution (fictional)", "Auto glass", 30, 2.0, 1.2, .88, .12),
    ("SUP-05", "Rockyview Tire Wholesale (fictional)", "Tires & wheels", 30, 2.0, 1.0, .85, .10),
    ("SUP-06", "Northern Lube & Filter Co. (fictional)", "Oil, filters, brakes, batteries", 30, 1.5, 0.8, .92, .10),
    ("SUP-07", "ClearShield Film Supply (fictional)", "PPF film & ceramic coatings", 45, 4.0, 2.0, .84, .12),
    ("SUP-08", "Import Specialty Parts (fictional)", "European / luxury OEM parts", 30, 6.5, 3.5, .70, .18),
]
SUBLET_VENDORS = [("VEN-TOW", "Fictional towing partner", "Towing & storage"), ("VEN-ALN", "Fictional alignment & frame specialist", "Sublet alignment"),
                  ("VEN-MEC", "Fictional mechanical sublet shop", "Sublet mechanical"), ("VEN-UPH", "Fictional upholstery & interior repair", "Sublet interior")]

INSURERS = [  # id, fictional name, category, payment days (mean, sd), approval days (mean), approved/estimate ratio, share of claims
    ("INS-01", "Chinook Mutual Insurance (fictional)", "DRP insurer (direct repair program)", 18, 6, 0.6, .985, .17),
    ("INS-02", "Bow River General (fictional)", "DRP insurer (direct repair program)", 22, 7, 0.8, .980, .15),
    ("INS-03", "Prairie Shield Insurance (fictional)", "DRP insurer (direct repair program)", 26, 8, 1.0, .975, .12),
    ("INS-04", "Aspen Direct Insurance (fictional)", "DRP insurer (direct repair program)", 20, 6, 0.7, .985, .10),
    ("INS-05", "Kananaskis Assurance (fictional)", "Non-DRP insurer (independent appraisal)", 34, 10, 3.5, .955, .11),
    ("INS-06", "Northlight Insurance (fictional)", "Non-DRP insurer (independent appraisal)", 38, 12, 4.2, .950, .09),
    ("INS-07", "Parkland Mutual (fictional)", "Non-DRP insurer (independent appraisal)", 42, 14, 4.8, .945, .08),
    ("INS-08", "Elbow Valley General (fictional)", "Non-DRP insurer (independent appraisal)", 31, 9, 3.0, .960, .08),
    ("INS-09", "Rundle Casualty (fictional)", "Non-DRP insurer (independent appraisal)", 47, 15, 5.5, .940, .05),
    ("INS-10", "Fleet & self-insured accounts (fictional)", "Self-insured fleet / commercial", 30, 9, 1.5, .990, .05),
]
CLAIM_TYPES = {  # type: (deductible options, probabilities)
    "Collision (at fault)": ([500, 1000], [.62, .38]), "DCPD (not at fault)": ([0], [1.0]), "Comprehensive - hail": ([300, 500], [.5, .5]),
    "Comprehensive - glass": ([0, 100, 300], [.45, .25, .30]),
}
HAIL_EVENTS = ["2024-08-05", "2025-07-22", "2026-06-18"]      # SIMULATED summer hail events (dates illustrative); PDR and refinish surge for ~6 weeks

ROLES = {  # role: (op groups, hourly wage 2024 range, efficiency mean, rework multiplier)
    "Collision technician (Red Seal)": (["BODY", "PDR"], (42, 46), 1.27, 0.8),
    "Collision technician": (["BODY"], (35, 39), 1.16, 1.0),
    "Apprentice collision technician": (["BODY"], (24, 28), 0.92, 1.6),
    "Refinish technician (painter)": (["PAINT"], (38, 44), 1.28, 0.9),
    "Prep technician": (["PAINT"], (26, 30), 1.02, 1.2),
    "Mechanical technician (Red Seal)": (["MECH", "CALIB"], (42, 46), 1.24, 0.8),
    "Mechanical technician": (["MECH"], (32, 36), 1.10, 1.1),
    "Tire & lube technician": (["MECH"], (22, 25), 1.06, 1.0),
    "ADAS & diagnostic specialist": (["CALIB", "MECH"], (40, 44), 1.10, 0.8),
    "Glass technician": (["GLASS", "CALIB"], (30, 34), 1.05, 1.0),
    "PDR technician": (["PDR"], (38, 42), 1.12, 0.9),
    "Detailer": (["DETAIL"], (21, 24), 1.08, 1.0),
    "PPF & ceramic installer": (["PPF", "DETAIL"], (27, 31), 1.08, 1.0),
}
# initial staff (branch, role, count) and staffing changes (date, branch, role, +1 hire / -1 leaver)
STAFF = [
    ("BR-CCC", "Collision technician (Red Seal)", 2), ("BR-CCC", "Collision technician", 2), ("BR-CCC", "Apprentice collision technician", 1),
    ("BR-CCC", "Refinish technician (painter)", 2), ("BR-CCC", "Prep technician", 2), ("BR-CCC", "ADAS & diagnostic specialist", 1),
    ("BR-CCC", "Glass technician", 1), ("BR-CCC", "PDR technician", 1), ("BR-CCC", "Detailer", 1), ("BR-CCC", "Mechanical technician", 1),
    ("BR-NFS", "Collision technician (Red Seal)", 1), ("BR-NFS", "Collision technician", 1), ("BR-NFS", "Apprentice collision technician", 1),
    ("BR-NFS", "Refinish technician (painter)", 1), ("BR-NFS", "Prep technician", 1),
    ("BR-NFS", "Mechanical technician (Red Seal)", 2), ("BR-NFS", "Mechanical technician", 2), ("BR-NFS", "Tire & lube technician", 2),
    ("BR-NFS", "Glass technician", 1), ("BR-NFS", "Detailer", 1), ("BR-NFS", "PPF & ceramic installer", 0),
]
STAFF_CHANGES = [
("2024-06-28", "BR-CCC", "Collision technician", -1), ("2024-08-26", "BR-CCC", "Collision technician", +1),
    ("2024-09-03", "BR-NFS", "Mechanical technician", +1), ("2025-02-03", "BR-CCC", "Collision technician (Red Seal)", +1),
    ("2025-04-22", "BR-SEC", "Detailer", +2), ("2025-04-22", "BR-SEC", "PPF & ceramic installer", +1), ("2025-04-22", "BR-SEC", "Collision technician", +1),
    ("2025-04-22", "BR-SEC", "Mechanical technician", +1), ("2025-04-22", "BR-SEC", "Refinish technician (painter)", +1), ("2025-04-22", "BR-SEC", "PDR technician", +1),
    ("2025-09-02", "BR-SEC", "Detailer", +1), ("2025-09-02", "BR-SEC", "Tire & lube technician", +1), ("2025-10-14", "BR-NFS", "Mechanical technician (Red Seal)", -1),
    ("2026-01-12", "BR-NFS", "Mechanical technician (Red Seal)", +1), ("2026-01-12", "BR-SEC", "PPF & ceramic installer", +1),
    ("2026-03-30", "BR-CCC", "Refinish technician (painter)", -1), ("2026-06-01", "BR-CCC", "Refinish technician (painter)", +1),
]
PAYROLL_BURDEN = 0.15               # CPP, EI, WCB, benefits on technician wages
OT_PREMIUM = 1.5
PRODUCTIVE_SHARE = 0.88             # max share of attended hours a technician can be clocked on jobs (clean-up, meetings, waiting excluded)
PTO_DAYS = 15
SICK_DAYS = 4

# monthly operating-expense plan (2024 levels, CAD) by branch; HO = group head office (shared)
OPEX_PLAN = {
    "BR-CCC": dict(rent=26500, cam=6200, util_winter=5600, util_summer=3300, supplies=8800, equip_maint=3200, software=1500, network_fees=2600, courier_waste=1700,
                   courtesy=1200, staff=[("Branch manager", 1, 8800), ("Estimator", 2, 6600), ("Service advisor / CSR", 1, 4700), ("Parts coordinator", 1, 4900)]),
    "BR-NFS": dict(rent=24500, cam=5600, util_winter=4900, util_summer=2900, supplies=7600, equip_maint=2900, software=1500, network_fees=2400, courier_waste=1500,
                   courtesy=900, staff=[("Branch manager", 1, 8500), ("Estimator", 1, 6400), ("Service advisor / CSR", 2, 4600), ("Parts coordinator", 1, 4800)]),
    "BR-SEC": dict(rent=18500, cam=4600, util_winter=3100, util_summer=2000, supplies=4200, equip_maint=1300, software=1300, network_fees=1900, courier_waste=900,
                   courtesy=4200, staff=[("Branch manager", 1, 8200), ("Estimator", 1, 6300), ("Concierge advisor / CSR", 2, 4500)]),
    "HO": dict(marketing=9500, insurance=7400, professional=3600, software=2200, training=2600,
               staff=[("General manager / owner", 1, 14500), ("Controller", 1, 8800), ("Accounts & insurance admin", 1, 5200), ("Marketing coordinator", 1, 5300)]),
}
SE_LEASE_START = "2025-02-01"       # SE lease and fit-out start three months before opening
STAFF_BURDEN = 0.13
OPEX_INFLATION = 0.03               # applied each January
CARD_FEE_RATE = 0.0165
