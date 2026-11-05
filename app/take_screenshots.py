"""Starts the dashboard headless on localhost and saves one PNG per view with Playwright.

Run:  python app/take_screenshots.py
Output: deliverables/iteration2/screenshots/ (aggregated values only).
"""

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deliverables" / "iteration2" / "screenshots"
PORT = 8599
URL = f"http://localhost:{PORT}"

VIEWS = [("Q3", "q3_kpis"), ("Q2", "q2_monthly"), ("Q5", "q5_yoy"), ("Q4", "q4_weekday"), ("Q1", "q1_map"), ("Q6", "q6_trips")]


def wait_for_server(timeout=90):
    limit = time.time() + timeout
    while time.time() < limit:
        try:
            urllib.request.urlopen(f"{URL}/_stcore/health", timeout=2)
            return
        except OSError:
            time.sleep(1)
    raise RuntimeError("The dashboard did not start")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/dashboard.py", "--server.headless", "true",
                               "--server.port", str(PORT), "--server.address", "localhost", "--browser.gatherUsageStats", "false"],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors = []
    try:
        wait_for_server()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1500, "height": 1100}, device_scale_factor=1.5)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL)
            page.get_by_text("Q6 · Trips, not people").wait_for(timeout=120000)
            page.wait_for_timeout(6000)
            if page.locator('[data-testid="stException"]').count():
                errors.append("Streamlit exception on the page")
            page.screenshot(path=OUT / "00_overview_top.png")
            for prefix, name in VIEWS:
                heading = page.get_by_role("heading", name=f"{prefix} ·")
                container = page.locator('[data-testid="stVerticalBlock"]').filter(has=heading).last
                container.scroll_into_view_if_needed()
                page.wait_for_timeout(2500)
                container.screenshot(path=OUT / f"{name}.png")
                print(OUT / f"{name}.png")
            browser.close()
    finally:
        server.terminate()
    if errors:
        print("ERRORS:", errors)
        sys.exit(1)
    print("Screenshots done, no page errors")


if __name__ == "__main__":
    main()
