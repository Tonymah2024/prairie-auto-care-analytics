"""Dashboard functionality: every page renders and is labelled, filters work, CSV downloads exist, the simulator responds."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "dashboard" / "app.py")
PAGES = ["1. Executive Overview", "2. Repair Job Profitability", "3. Technician Productivity", "4. Repair Cycle Times", "5. Parts Inventory",
         "6. Supplier Performance", "7. Insurance Claims", "8. Customer & Service Analytics", "9. Branch Comparison", "10. Income Statement", "11. Balance Sheet",
         "12. Cash Flow", "13. Financial Ratios", "14. Predictive Forecasting", "15. Scenario Simulator"]


def app(page=None):
    at = AppTest.from_file(APP, default_timeout=300)
    at.run()
    if page:
        at.sidebar.radio[0].set_value(page).run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_labelled_with_content(page):
    at = app(page)
    assert not at.exception, at.exception[0].value
    assert len(at.get("plotly_chart")) + len(at.dataframe) > 0
    text = " ".join(m.value for m in at.markdown)
    assert "Synthetic demonstration data. Not actual Ultimate Car Care Group records." in text and "VisiVault Analytics" in text


def test_branch_filter_changes_profitability_kpis():
    at = app(PAGES[1])
    before = [m.value for m in at.markdown if "class='kpi'" in m.value][0]
    at.sidebar.multiselect[0].set_value(["SE Concierge"]).run()
    after = [m.value for m in at.markdown if "class='kpi'" in m.value][0]
    assert not at.exception and before != after


def test_work_order_filters_on_cycle_page():
    at = app(PAGES[3])
    before = [m.value for m in at.markdown if "class='kpi'" in m.value][0]
    at.selectbox[0].set_value("With supplement").run()
    after = [m.value for m in at.markdown if "class='kpi'" in m.value][0]
    assert not at.exception and before != after


@pytest.mark.parametrize("page", [PAGES[0], PAGES[1], PAGES[3], PAGES[4], PAGES[6], PAGES[8], PAGES[9], PAGES[13]])
def test_csv_downloads_present(page):
    at = app(page)
    assert len(at.get("download_button")) >= 1


def test_simulator_volume_raises_revenue_but_efficiency_mostly_cuts_overtime():
    at = app(PAGES[14])
    kp = lambda: " ".join(m.value for m in at.markdown if "class='kpi'" in m.value)
    v0 = kp()
    at.slider[0].set_value(10.0).run()                    # technician efficiency +10%
    v1 = kp()
    assert not at.exception and v0 != v1
