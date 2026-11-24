"""CONVIVE - one command for the whole product, from the raw monthly files to the dashboard tables.

    python run_final.py                  everything (needs data/; about 25 minutes on a laptop)
    python run_final.py --from-tables    from the aggregated tables only (no raw data needed; about 3 minutes with the checks)
    python run_final.py --notebook       also build and execute CONVIVE_Final.ipynb

Steps:
    raw data   run_iteration2 build inventory inspect levels quality clean stats maps      WBS 2.1.x, 3.1.x, 4.2.1
               aggregates                                                                  WBS 2.2.1
    tables     validation                                                                  WBS 2.2.2
               research_report                                                             WBS 3.2.0-3.2.4
               final_outputs                                                               WBS 5.2, 5.3
    checks     tests/ and app/check_dashboard.py                                           WBS 4.3.1
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = [["run_iteration2.py"], ["run_iteration3.py", "aggregate"]]
TABLES = [["validation.py"], ["research_report.py"], ["final_outputs.py"]]
CHECKS = [["-m", "pytest", "tests", "-q"], ["app/check_dashboard.py"]]
NOTEBOOK = [["make_notebook_final.py"],
            ["-m", "jupyter", "nbconvert", "--execute", "--to", "notebook", "--inplace", "--ExecutePreprocessor.timeout=-1", "CONVIVE_Final.ipynb"]]


def run(command):
    started = time.time()
    print(f"=== {' '.join(command)}", flush=True)
    code = subprocess.run([sys.executable, *command], cwd=HERE).returncode
    print(f"--- {'done' if code == 0 else f'FAILED (exit {code})'} in {time.time() - started:.0f}s", flush=True)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from-tables", action="store_true", help="skip the steps that need the raw data")
    parser.add_argument("--notebook", action="store_true", help="also build and execute CONVIVE_Final.ipynb")
    args = parser.parse_args()
    steps = ([] if args.from_tables else RAW) + TABLES + (NOTEBOOK if args.notebook else []) + CHECKS
    for step in steps:
        code = run(step)
        if code:
            return code
    print("\nEverything is built and checked. Start the dashboard:  python -m streamlit run app/dashboard.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
