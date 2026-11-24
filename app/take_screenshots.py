"""Screenshots of the final dashboard: starts it headless on localhost and saves one PNG per view.

Run:  python app/take_screenshots.py            (needs: python -m playwright install chromium)
Output: deliverables/final/screenshots/ (aggregated values only, git-ignored).
"""

import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deliverables" / "final" / "screenshots"
PORT = 8602
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
    page.mouse.move(800, 500)
    page.mouse.wheel(0, -20000)
    page.wait_for_timeout(400)
    page.get_by_role("tab", name=name, exact=True).click()
    settle(page)


def pick(page, label, option):
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
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "app/dashboard.py", "--server.headless", "true", "--server.port", str(PORT),
                               "--server.address", "localhost", "--browser.gatherUsageStats", "false"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    errors, requests, shots = [], set(), []
    try:
        wait_for_server()
        with sync_playwright() as p:
            kwargs = {"executable_path": os.environ["CHROMIUM"]} if os.environ.get("CHROMIUM") else {}
            browser = p.chromium.launch(**kwargs)
            page = browser.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=2)
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: requests.add(r.url.split("/")[2]) if r.url.startswith("http") else None)

            def shot(name, scroll=0):
                if scroll:
                    page.mouse.move(1480, 600)
                    page.mouse.wheel(0, scroll)
                    settle(page, 1800)
                page.screenshot(path=OUT / f"{name}.png")
                shots.append(name)
                print(name, flush=True)

            page.goto(URL)
            page.get_by_text("How does the presence of visitors change").wait_for(timeout=180000)
            settle(page, 6000)
            shot("01_key_findings")
            shot("02_key_findings_more", 1000)
            open_tab(page, "Visitors & residents")
            shot("03_visitors_residents")
            shot("04_visitors_residents_maps", 560)
            open_tab(page, "Q1–Q6 views")
            shot("05_views")
            open_tab(page, "Overnight stays")
            shot("06_overnight")
            open_tab(page, "Research answers")
            shot("07_research_answers")
            shot("08_research_detail", 900)
            open_tab(page, "Neighbourhood explorer")
            shot("09_explorer")
            open_tab(page, "Who visits")
            shot("10_who")
            open_tab(page, "Nationalities")
            settle(page, 2500)
            shot("11_nationalities")
            shot("12_nationalities_map", 820)
            open_tab(page, "Data quality")
            shot("13_data_quality")
            shot("14_level_shifts", 700)
            open_tab(page, "Visitors & residents")
            pick(page, "District", "Ciutat Vella")
            page.get_by_text("Weekends (Sat-Sun)", exact=True).click()
            settle(page, 4000)
            shot("15_filters_ciutat_vella_weekends")
            if page.locator('[data-testid="stException"]').count():
                errors.append("Streamlit exception on the page")
            browser.close()
    finally:
        server.terminate()
    outside = sorted(h for h in requests if not h.startswith("localhost"))
    print("Hosts contacted by the page:", sorted(requests))
    if errors or outside:
        print("ERRORS:", errors, "external hosts:", outside)
        sys.exit(1)
    print(f"{len(shots)} screenshots, no page errors, no external requests")


if __name__ == "__main__":
    main()
