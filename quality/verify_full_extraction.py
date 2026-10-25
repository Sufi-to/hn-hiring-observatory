"""Verify persisted extraction outputs without invoking any AI functions."""
import concurrent.futures
import datetime
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "tom"
WAREHOUSE = "616681d29d918fc1"


def cli(*args):
    response = subprocess.run(
        ["databricks", *args, "--profile", PROFILE, "-o", "json"],
        capture_output=True, text=True, timeout=90,
    )
    if response.returncode:
        raise RuntimeError(response.stderr.strip())
    return json.loads(response.stdout)


def query(statement):
    response = cli("api", "post", "/api/2.0/sql/statements", "--json", json.dumps({
        "warehouse_id": WAREHOUSE, "statement": statement, "wait_timeout": "10s",
    }))
    while response["status"]["state"] in {"PENDING", "RUNNING"}:
        time.sleep(2)
        response = cli("api", "get", "/api/2.0/sql/statements/" + response["statement_id"])
    if response["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(json.dumps(response["status"]))
    assert not response["manifest"].get("truncated"), "Verification result was truncated"
    names = [c["name"] for c in response["manifest"]["schema"]["columns"]]
    return [dict(zip(names, row)) for row in response.get("result", {}).get("data_array", [])]


def main():
    statements = [s.strip() for s in (ROOT / "sql/verify_full_extraction.sql").read_text().split(";") if s.strip()]
    queries = dict(zip(["coverage", "missing_inputs", "quality", "monthly_coverage"], statements))
    queries["view_counts"] = """SELECT 'post_skills' AS view_name, count(*) AS rows FROM workspace.hnjob.post_skills
      UNION ALL SELECT 'post_countries', count(*) FROM workspace.hnjob.post_countries
      UNION ALL SELECT 'post_salaries', count(*) FROM workspace.hnjob.post_salaries
      UNION ALL SELECT 'post_processing_coverage', count(*) FROM workspace.hnjob.post_processing_coverage"""
    queries["provenance"] = """SELECT model, prompt_hash, extraction_version, count(*) AS posts
      FROM workspace.hnjob.post_attributes GROUP BY model, prompt_hash, extraction_version"""
    queries["run"] = """SELECT * FROM workspace.hnjob.all_extraction_runs ORDER BY started_at DESC LIMIT 1"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        pending = {name: executor.submit(query, sql) for name, sql in queries.items()}
        results = {name: future.result() for name, future in pending.items()}
    coverage = results["coverage"][0]
    assert int(coverage["posts"]) == int(coverage["distinct_posts"]) == int(coverage["successful_posts"]) == 40065
    assert int(coverage["incomplete_posts"]) == 0
    assert int(coverage["selected_models"]) == int(coverage["prompt_versions"]) == 1
    assert int(coverage["months"]) == 82
    assert (coverage["first_month"], coverage["last_month"]) == ("2020-01", "2026-10")
    assert int(results["missing_inputs"][0]["missing_inputs"]) == 0
    assert all(int(row["incomplete_posts"]) == 0 for row in results["monthly_coverage"])
    assert len(results["view_counts"]) == 4
    assert all(int(row["rows"]) > 0 for row in results["view_counts"])
    assert results["provenance"][0]["model"] == "databricks-gpt-oss-120b"
    assert results["run"][0]["status"] == "complete"
    report = {
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "job_id": 5181643003890, "job_run_id": 30070794346507,
        "profile": PROFILE, "namespace": "workspace.hnjob", "status": "complete",
        "checks": results,
        "limitations": [
            "Successful processing and schema checks do not establish semantic accuracy of all extracted facts.",
            "The model comparison used 20 development posts, not a held-out corpus-wide evaluation.",
            "Attributes are per post; one post may advertise multiple vacancies with different requirements.",
            "Evidence and country review flags require source inspection; unknown salary fields remain unknown.",
            "October 2026 is a partial month; deleted/dead source text cannot be recovered from the HN API.",
        ],
    }
    (ROOT / "quality/full-extraction-results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({name: rows for name, rows in results.items() if name != "monthly_coverage"}, indent=2))
    print("Verified every month and all four published views; saved quality/full-extraction-results.json")


if __name__ == "__main__":
    main()
