from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path("D:/Project/PH-SHOWOA")
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "paper_literal"))

from prepare_and_dispatch_paper_literal_65slots import build_allocations
from harvest_paper_literal_results import (
    DEFAULT_OUTPUT_CSV,
    aggregate_results,
    check_and_download_kernels,
)


def run_polling_loop(interval_minutes: int, output_csv: Path, max_polls: int | None = None) -> None:
    allocations = build_allocations()
    total_jobs = len(allocations)
    print("=" * 75, flush=True)
    print("STARTING PAPER-LITERAL HARVEST POLLING DAEMON", flush=True)
    print(f"Target instances  : {total_jobs}", flush=True)
    print(f"Polling interval  : {interval_minutes} minutes ({interval_minutes * 60} seconds)", flush=True)
    print(f"Target CSV output : {output_csv}", flush=True)
    print("=" * 75, flush=True)

    poll_count = 0
    while True:
        poll_count += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{now_str}] === POLL CYCLE #{poll_count} START ===", flush=True)

        all_done = False
        try:
            all_done = check_and_download_kernels(allocations)
            aggregate_results(output_csv)
        except Exception as e:
            print(f"[{now_str}] Error during poll cycle #{poll_count}: {e}", flush=True)

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] === POLL CYCLE #{poll_count} FINISHED ===", flush=True)

        if all_done:
            print("\n" + "=" * 75, flush=True)
            print("ALL 65 BENCHMARK INSTANCES (1,950 RUNS) FULLY HARVESTED AND AGGREGATED!", flush=True)
            print(f"Final CSV saved to: {output_csv}", flush=True)
            print("=" * 75 + "\n", flush=True)
            break

        if max_polls is not None and poll_count >= max_polls:
            print(f"Reached max polls ({max_polls}). Exiting daemon.", flush=True)
            break

        print(f"Sleeping for {interval_minutes} minutes until next cycle...\n", flush=True)
        time.sleep(interval_minutes * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Polling Daemon for Paper-Literal Benchmark Harvest")
    parser.add_argument("--interval", type=int, default=20, help="Polling interval in minutes (default: 20)")
    parser.add_argument("--output_csv", type=Path, default=DEFAULT_OUTPUT_CSV, help="Path to aggregate results CSV")
    parser.add_argument("--max_polls", type=int, default=None, help="Maximum number of poll cycles (default: unlimited)")
    args = parser.parse_args()

    run_polling_loop(
        interval_minutes=args.interval,
        output_csv=args.output_csv,
        max_polls=args.max_polls,
    )


if __name__ == "__main__":
    main()
