"""CONVIVE - runs the Iteration 2 data pipeline on the real data, from the CSVs to the dashboard tables.

    python run_iteration2.py                 every step
    python run_iteration2.py quality stats   only these steps

Steps: build, inventory, inspect, levels, quality, clean, stats, maps.
"""

import pickle
import sys
import time

import cleaning
import levels as lv
import loaders as L
import quality as q

STATE = L.PROCESSED_DIR / "_pipeline_state.pkl"    # results shared between steps (git-ignored)


def _state():
    return pickle.loads(STATE.read_bytes()) if STATE.exists() else {}


def _save(**values):
    state = _state()
    state.update(values)
    STATE.write_bytes(pickle.dumps(state))


def step_build(con):
    return L.build_parquet()


def step_inventory(con):
    table = q.inventory(con)
    print(q.write_inventory(table))
    return table


def step_inspect(con):
    results = q.inspection(con)
    print(q.write_inspection(results))
    return results


def step_levels(con):
    levels, report = lv.build_geographic_levels(con)
    print(lv.write_geographic(levels, report))
    temporal = lv.temporal_report(con)
    print(lv.write_temporal(temporal))
    _save(temporal=temporal, geo=report)
    return levels, report, temporal


def step_quality(con):
    results = q.run_quality(con)
    temporal = _state().get("temporal") or lv.temporal_report(con)
    print(q.write_quality(results, q.problems_text(results, temporal)))
    _save(quality=results)
    return results


def step_clean(con, force=False):
    temporal = _state().get("temporal") or lv.temporal_report(con)
    totals = cleaning.clean_all(con, temporal["incomplete"], force=force)
    log = cleaning.cleaning_log(con, totals)
    print(cleaning.write_log(log, totals))
    return totals, log


def step_stats(con):
    import descriptives
    return descriptives.run(con)


def step_maps(con):
    import descriptives
    return descriptives.export_maps()


STEPS = {"build": step_build, "inventory": step_inventory, "inspect": step_inspect, "levels": step_levels,
         "quality": step_quality, "clean": step_clean, "stats": step_stats, "maps": step_maps}


def main(names=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    con = L.connect()
    for name in names or STEPS:
        started = time.time()
        print(f"--- {name}", flush=True)
        STEPS[name](con)
        print(f"--- {name} done in {time.time() - started:.0f}s", flush=True)
    con.close()


if __name__ == "__main__":
    main(sys.argv[1:])
