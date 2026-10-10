"""Phase 0 (public copy) - the raw website snapshots are not redistributed. The processed, generic tables in data/external/processed
(public-fact-to-demo mapping and sources register) are used as-is; nothing about any real company's operations or finances is used."""
from src.config import EXTERNAL


def build():
    for f in ("public_fact_to_demo_mapping.csv", "sources_register.csv", "calgary_weather_daily.csv", "alberta_holidays.csv", "economic_indicators_monthly.csv"):
        if not (EXTERNAL / f).exists():
            raise SystemExit(f"missing {f}")
