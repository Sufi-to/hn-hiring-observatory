"""Read-only monitor for the authorized Databricks extraction run."""
import json
import subprocess
import time

PROFILE = "tom"
RUN_ID = "30070794346507"
REQUEST = {
    "warehouse_id": "616681d29d918fc1",
    "statement": "SELECT status, successful_posts, failed_posts, pending_posts, updated_at, error FROM workspace.hnjob.all_extraction_runs ORDER BY started_at DESC LIMIT 1",
    "wait_timeout": "5s",
}


def cli(*args):
    completed = subprocess.run(["databricks", *args, "--profile", PROFILE, "-o", "json"],
                               capture_output=True, text=True, timeout=50)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip()[:500])
    return json.loads(completed.stdout)


while True:
    started = time.monotonic()
    try:
        run = cli("jobs", "get-run", RUN_ID)
        state = run.get("state", {})
        response = cli("api", "post", "/api/2.0/sql/statements", "--json", json.dumps(REQUEST))
        statement_id = response.get("statement_id")
        if response.get("status", {}).get("state") in {"PENDING", "RUNNING"}:
            response = cli("api", "get", "/api/2.0/sql/statements/" + statement_id)
        rows = response.get("result", {}).get("data_array", [])
        report = {"job": state.get("life_cycle_state"), "result": state.get("result_state"),
                  "counts": rows[0] if rows else None}
        if state.get("state_message"):
            report["message"] = state["state_message"]
        print(json.dumps(report), flush=True)
        if state.get("life_cycle_state") in {"TERMINATED", "INTERNAL_ERROR", "SKIPPED"}:
            break
    except Exception as exc:
        print(json.dumps({"monitor_error": str(exc)[:500]}), flush=True)
    time.sleep(max(1, 45 - (time.monotonic() - started)))
