"""Central configuration for the Prairie Auto Care Analytics demonstration (VisiVault Analytics Ltd.).

Prairie Auto Care Group is a FICTIONAL multi-location Calgary collision repair and car care business. Its business
model (three Calgary locations, service lines, opening hours, OEM-certified collision work, direct billing of insurers)
is inspired by a public Calgary auto care group's website (retrieved RETRIEVAL_DATE). Calgary daily weather
(Environment and Climate Change Canada), Alberta statutory holidays and Bank of Canada rates are REAL public data.
Every operational and financial record is SYNTHETIC and generated with a fixed SEED.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW_EXTERNAL = DATA / "external" / "raw"
EXTERNAL = DATA / "external" / "processed"
SYNTH = DATA / "synthetic"
DB_PATH = DATA / "prairie_auto_care_synthetic.db"
SQL_DIR = ROOT / "sql"
DOCS = ROOT / "docs"
OUT = ROOT / "outputs"
CHARTS = OUT / "charts"
TABLES = OUT / "tables"
REPORTS = OUT / "reports"
MODELS = OUT / "models"
FIN_OUT = OUT / "finance"

SEED = 20240103
START = "2024-01-01"
END = "2026-09-30"
FORECAST_START = "2026-10-01"
FORECAST_MONTHS = 12
RETRIEVAL_DATE = "2026-10-09"

APP_NAME = "Prairie Auto Care Analytics"
COMPANY = "Prairie Auto Care Group (fictional)"
ATTRIBUTION = "Developed by VisiVault Analytics Ltd."
SYNTHETIC_LABEL = "Synthetic demonstration data. Not actual Ultimate Car Care Group records."
APP_BANNER = "Developed by VisiVault Analytics Ltd. — Synthetic demonstration data. Not actual Ultimate Car Care Group records."
FIN_LABEL = "SIMULATED FINANCIAL INFORMATION — synthetic demonstration accounts of a fictional auto care group"

# VisiVault brand palette (from the VisiVault website CSS variables); SERIES = validated 4-slot categorical order
BRAND = {
    "brand": "#2a78d6", "brand_dark": "#184f95", "brand_light": "#eaf2fc",
    "accent": "#4a3aa7", "accent_light": "#efeaf9", "teal": "#0d9488",
    "navy": "#0b1120", "navy2": "#10192e", "bg": "#f9f9f7", "muted": "#52514e",
    "subtle": "#898781", "good": "#0ca30c", "warn": "#d97706", "bad": "#c2410c",
}
SERIES = ["#2a78d6", "#0d9488", "#4a3aa7", "#d97706"]

for p in (EXTERNAL, SYNTH, DOCS, CHARTS, TABLES, REPORTS, MODELS, FIN_OUT):
    p.mkdir(parents=True, exist_ok=True)
