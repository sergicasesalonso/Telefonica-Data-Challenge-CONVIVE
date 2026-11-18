"""Iteration 3 screenshots: starts the dashboard headless on localhost and saves PNGs of the new views and filters.

Run:  python app/take_screenshots_i3.py            (needs: playwright install chromium)
      CHROMIUM=/path/to/chrome python app/take_screenshots_i3.py   to use another Chromium build
Output: deliverables/iteration3/screenshots/ (aggregated values only, git-ignored).
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deliverables" / "iteration3" / "screenshots"
PORT = 8601
URL = f"http://localhost:{PORT}"


def wait_for_server(timeout=120):
    limit = time.time() + timeout
    while time.time() < limit:
        try:
            urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError("The dashboard did not start")


def settle(page, ms=3500):
    page.wait_for_timeout(500)
    try:
        page.locator('[data-testid="stStatusWidget"]').wait_for(state="detached", timeout=60000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def open_tab(page, name):
    page.get_by_role("tab", name=name).click()
    settle(page)


def block(page, text):
    """The bordered container (or the tab panel) that holds a heading/text."""
    return page.locator('[data-testid="stVerticalBlock"]').filter(has_text=text).last


def pick(page, label, option):
    """Select an option in a Streamlit multiselect/selectbox identified by its label."""
    box = page.locator('[data-testid="stSelectbox"], [data-testid="stMultiSelect"]').filter(has_text=label).first
    box.get_by_role("combobox").first.click()
    page.wait_for_timeout(400)
    page.keyboard.type(option[:40])
    page.wait_for_timeout(400)
    page.get_by_role("option").filter(has_text=option[:40]).first.click()
    page.keyboard.press("Escape")
    settle(page)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/dashboard.py", "--server.headless", "true",
                               "--server.port", str(PORT), "--server.address", "localhost", "--browser.gatherUsageStats", "false"],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors, shots = [], []
    try:
        wait_for_server()
        with sync_playwright() as p:
            kwargs = {"executable_path": os.environ["CHROMIUM"]} if os.environ.get("CHROMIUM") else {}
            browser = p.chromium.launch(**kwargs)
            page = browser.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=2)
            page.on("pageerror", lambda e: errors.append(str(e)))

            def shot(name, locator=None, full=False):
                path = OUT / f"{name}.png"
                if locator is None:
                    page.screenshot(path=path, full_page=full)
                else:
                    locator.scroll_into_view_if_needed()
                    page.wait_for_timeout(1200)
                    locator.screenshot(path=path)
                shots.append(path)
                print(path.name, flush=True)

            page.goto(URL)
            page.get_by_text("Q6 · Trips, not people").wait_for(timeout=180000)
            settle(page, 6000)
            shot("01_overview_filters")

            # Research answers
            open_tab(page, "Research answers Q1–Q17")
            shot("02_research_answers_table")
            pick(page, "Question in detail", "Q1 · How concentrated are visitors across the 73 neighbourhoods?")
            shot("03_research_answer_q1", block(page, "Decision rule."))
            pick(page, "Question in detail", "Q4 · Are mean daily visitors on Saturday-Sunday at least 10% above Monday-Friday?")
            shot("04_research_answer_q4", block(page, "Decision rule."))

            # Neighbourhood explorer
            open_tab(page, "Neighbourhood explorer")
            shot("05_explorer_gotic")
            pick(page, "Neighbourhood (limited to the area chosen in the sidebar)", "Verdun")
            shot("06_explorer_verdun")

            # Who visits
            open_tab(page, "Who visits")
            shot("07_who_countries")
            page.get_by_text("Province (national, T7)", exact=True).click()
            settle(page)
            shot("08_who_provinces")

            # Data quality
            open_tab(page, "Data quality")
            shot("09_data_quality")
            page.mouse.wheel(0, 1400)
            settle(page, 1500)
            shot("10_validation_log")

            # 4.2.3 filters on the Q1-Q6 views: one district, weekends
            open_tab(page, "Q1–Q6 views")
            pick(page, "District", "Ciutat Vella")
            page.get_by_text("Weekends (Sat-Sun)", exact=True).click()
            settle(page, 6000)
            shot("11_filters_district_weekend")
            q4 = block(page, "Q4 · Are daily visitors higher")
            shot("12_filtered_q4_weekday", q4)
            q1 = block(page, "Q1 · How concentrated")
            shot("13_filtered_q1_map", q1)

            if page.locator('[data-testid="stException"]').count():
                errors.append("Streamlit exception on the page")
            browser.close()
    finally:
        server.terminate()
    if errors:
        print("ERRORS:", errors)
        sys.exit(1)
    print(f"{len(shots)} screenshots, no page errors")


if __name__ == "__main__":
    main()
