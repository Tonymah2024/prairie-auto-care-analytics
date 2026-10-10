"""Synthetic data: validation suite clean, volumes in the requested range, reproducibility."""
import hashlib

import pandas as pd
import pytest

from src.config import SYNTH, TABLES


def test_all_data_checks_pass():
    dq = pd.read_csv(TABLES / "data_validation_checks.csv")
    assert len(dq) >= 30
    assert (dq.violations == 0).all(), dq[dq.violations > 0]


def test_repair_order_volume_in_range_and_three_branches():
    ro = pd.read_csv(SYNTH / "repair_orders.csv", low_memory=False)
    n = (ro.pre_period == 0).sum()
    assert 15000 <= n <= 25000
    assert set(ro.branch_id) == {"BR-SEC", "BR-CCC", "BR-NFS"}


def test_all_required_tables_exist():
    need = ["branches", "customers", "vehicles", "repair_orders", "repair_estimates", "insurance_claims", "technicians", "technician_timesheets", "job_assignments",
            "parts_catalogue", "parts_inventory_movements", "supplier_purchase_orders", "service_appointments", "customer_invoices", "payments", "operating_expenses"]
    for t in need:
        assert (SYNTH / f"{t}.csv").exists(), t
    assert (TABLES / "fin_chart_of_accounts.csv").exists() and (TABLES / "fin_fixed_asset_register.csv").exists()


def test_every_table_labelled_synthetic():
    for p in SYNTH.glob("*.csv"):
        assert (pd.read_csv(p, usecols=["data_status"], low_memory=False).data_status == "SYNTHETIC").all(), p.name


def test_insurers_and_suppliers_fictional():
    for t, col in (("insurers", "insurer_name"), ("suppliers", "supplier_name")):
        assert pd.read_csv(SYNTH / f"{t}.csv")[col].str.contains("fictional", case=False).all()


@pytest.mark.slow
def test_generator_reproducible(tmp_path):
    from src.generate import synthetic
    h = lambda: hashlib.md5((SYNTH / "repair_orders.csv").read_bytes()).hexdigest()
    a = h()
    synthetic.main()
    assert h() == a
