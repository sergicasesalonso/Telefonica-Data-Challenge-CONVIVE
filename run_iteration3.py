"""CONVIVE - runs the Iteration 3 pipeline, from the monthly CSVs to the answers, figures and dashboard tables.

    python run_iteration3.py                  every step
    python run_iteration3.py validate report  only these steps (they need only the aggregated tables)

Steps:
    aggregate   WBS 2.2.1  raw CSV -> deliverables/iteration3/2.2.1_aggregates/ (needs data/; pandas only, ~2-3 min)
    validate    WBS 2.2.2  checks of the aggregated tables -> 2.2.2_validation_log.md
    report      WBS 3.2.0-3.2.4  answers Q1-Q17, low-data neighbourhoods, figures and Markdown reports
The 3.1.6 statistics of Iteration 2 must exist (python run_iteration2.py stats), because 2.2.2 compares both paths.
"""

import sys
import time

STEPS = ["aggregate", "validate", "report"]


def main(argv):
    steps = argv or STEPS
    for step in steps:
        started = time.time()
        print(f"=== {step} ===", flush=True)
        if step == "aggregate":
            import aggregates
            aggregates.run_tourism()
            aggregates.run_mobility()
        elif step == "validate":
            import validation
            if validation.main():
                print("Validation failed: fix the aggregation before the analysis", flush=True)
                return 1
        elif step == "report":
            import research_report
            research_report.main()
        else:
            raise SystemExit(f"Unknown step {step!r}. Steps: {', '.join(STEPS)}")
        print(f"--- {step}: {time.time() - started:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
