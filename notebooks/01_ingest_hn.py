# Databricks notebook source
"""Manual, resumable ingestion of official HN monthly hiring threads.

All network requests execute on the Databricks notebook driver. No external
download service, local archive, or third-party API key is used.
"""
import concurrent.futures
import hashlib
import html
import json
import re
import time
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen

dbutils.widgets.text("mode", "backfill")
dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("schema", "hnjob")
dbutils.widgets.text("max_threads", "0")
MODE = dbutils.widgets.get("mode")
CATALOG = dbutils.widgets.get("catalog")
SCHEMA = dbutils.widgets.get("schema")
MAX_THREADS = int(dbutils.widgets.get("max_threads"))
assert MODE in {"preflight", "backfill", "incremental", "reconcile"}
assert all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", v) for v in (CATALOG, SCHEMA))
assert MAX_THREADS >= 0
NS = f"{CATALOG}.{SCHEMA}"
BASE = "https://hacker-news.firebaseio.com/v0"
START = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp())
RUN_ID = str(uuid.uuid4())


def fetch(path):
    for attempt in range(4):
        try:
            request = Request(f"{BASE}/{path}.json", headers={"User-Agent": "HNJobMarketResearch/1.0"})
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "br", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def clean_html(value):
    parser = PlainText()
    parser.feed(value or "")
    return "".join(parser.parts).strip()


def is_hiring_thread(item):
    return bool(item and item.get("type") == "story"
                and item.get("by") == "whoishiring"
                and item.get("time", 0) >= START
                and re.fullmatch(r"Ask HN: Who is hiring\? \([A-Za-z]+ \d{4}\)",
                                 html.unescape(item.get("title", "")), re.IGNORECASE)
                and not item.get("deleted") and not item.get("dead"))


# COMMAND ----------
# Check outbound access before any table creation.
profile = fetch("user/whoishiring")
assert profile and profile.get("submitted"), "HN user submissions unavailable"
print(json.dumps({"phase": "network_verified", "submitted_items": len(profile["submitted"])}))
if MODE == "preflight":
    sample = fetch(f"item/{profile['submitted'][0]}")
    dbutils.notebook.exit(json.dumps({"network": "ok", "sample_title": sample.get("title"),
                                     "catalog": CATALOG, "schema": SCHEMA}))

# COMMAND ----------
from delta.tables import DeltaTable
from pyspark.sql import functions as F

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {NS} COMMENT 'Hacker News hiring market since January 2020'")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.raw_threads (
    thread_id BIGINT, title STRING, month STRING, posted_at TIMESTAMP,
    child_ids ARRAY<BIGINT>, raw_json STRING, fetched_at TIMESTAMP
) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.raw_comments (
    comment_id BIGINT, thread_id BIGINT, month STRING, author STRING,
    posted_at TIMESTAMP, text_html STRING, text_clean STRING, content_hash STRING,
    source_url STRING, item_type STRING, parent_id BIGINT,
    deleted BOOLEAN, dead BOOLEAN, fetch_status STRING, fetch_error STRING,
    raw_json STRING, fetched_at TIMESTAMP
) USING DELTA""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {NS}.ingestion_runs (
    run_id STRING, mode STRING, started_at TIMESTAMP, finished_at TIMESTAMP,
    status STRING, discovered_threads BIGINT, fetched_comments BIGINT, error STRING
) USING DELTA""")


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def merge_rows(table, rows, key):
    if not rows:
        return
    frame = spark.createDataFrame(rows, spark.table(f"{NS}.{table}").schema)
    target = DeltaTable.forName(spark, f"{NS}.{table}")
    builder = target.alias("t").merge(frame.alias("s"), f"t.{key} = s.{key}")
    if table == "raw_comments":
        # A transient fetch error must never replace previously retrieved text.
        builder = builder.whenMatchedUpdateAll(condition="s.fetch_status <> 'error'")
    else:
        builder = builder.whenMatchedUpdateAll()
    builder.whenNotMatchedInsertAll().execute()


def comment_record(task):
    thread, item_id = task
    stamp = now()
    try:
        item = fetch(f"item/{item_id}")
        if item is None:
            state = "unavailable"
            item = {}
        elif item.get("deleted"):
            state = "deleted"
        elif item.get("dead"):
            state = "dead"
        else:
            state = "ok"
        raw = json.dumps(item, sort_keys=True, ensure_ascii=False)
        content = json.dumps({k: item.get(k) for k in ("text", "deleted", "dead", "parent", "type")}, sort_keys=True)
        return (item_id, thread["id"], thread["month"], item.get("by"),
                datetime.fromtimestamp(item["time"], timezone.utc).replace(tzinfo=None) if item.get("time") else None,
                item.get("text"), clean_html(item.get("text")), hashlib.sha256(content.encode()).hexdigest(),
                f"https://news.ycombinator.com/item?id={item_id}", item.get("type"), item.get("parent"),
                bool(item.get("deleted")), bool(item.get("dead")), state, None, raw, stamp)
    except Exception as exc:
        return (item_id, thread["id"], thread["month"], None, None, None, None, None,
                f"https://news.ycombinator.com/item?id={item_id}", None, None,
                False, False, "error", str(exc)[:1000], None, stamp)


# COMMAND ----------
started = now()
run_row = (RUN_ID, MODE, started, None, "running", 0, 0, None)
merge_rows("ingestion_runs", [run_row], "run_id")
fetched_count = 0
threads = []
try:
    # The official account posts the monthly threads. Persist no partial manifest
    # if discovery fails: missing months must not be confused with failed fetches.
    def discover(item_id):
        return fetch(f"item/{item_id}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        for item in pool.map(discover, profile["submitted"]):
            if is_hiring_thread(item):
                item["month"] = datetime.fromtimestamp(item["time"], timezone.utc).strftime("%Y-%m")
                threads.append(item)
    threads.sort(key=lambda item: (item["month"], item["id"]))
    assert threads, "No matching hiring threads discovered"
    merge_rows("raw_threads", [(t["id"], t["title"], t["month"],
        datetime.fromtimestamp(t["time"], timezone.utc).replace(tzinfo=None), t.get("kids", []),
        json.dumps(t, sort_keys=True), now()) for t in threads], "thread_id")
    print(json.dumps({"phase": "discovered", "threads": len(threads),
                      "first_month": threads[0]["month"], "last_month": threads[-1]["month"]}))

    selected = threads[-3:] if MODE == "incremental" else threads
    existing = {r.comment_id for r in spark.table(f"{NS}.raw_comments")
                .where("fetch_status IN ('ok', 'deleted', 'dead')").select("comment_id").collect()}
    selected = [t for t in selected if MODE != "backfill" or any(i not in existing for i in t.get("kids", []))]
    if MAX_THREADS:
        selected = selected[:MAX_THREADS]
    for thread in selected:
        ids = thread.get("kids", [])
        if MODE == "backfill":
            ids = [item_id for item_id in ids if item_id not in existing]
        for offset in range(0, len(ids), 500):
            tasks = [(thread, item_id) for item_id in ids[offset:offset + 500]]
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                records = list(pool.map(comment_record, tasks))
            merge_rows("raw_comments", records, "comment_id")
            fetched_count += len(records)
        print(json.dumps({"phase": "thread_loaded", "month": thread["month"],
                          "thread_id": thread["id"], "fetched": len(ids), "run_fetched": fetched_count}), flush=True)
    merge_rows("ingestion_runs", [(RUN_ID, MODE, started, None, "raw_loaded",
                                   len(threads), fetched_count, None)], "run_id")
except Exception as exc:
    merge_rows("ingestion_runs", [(RUN_ID, MODE, started, now(), "failed", len(threads),
                                   fetched_count, str(exc)[:2000])], "run_id")
    raise

# COMMAND ----------
spark.sql(f"""CREATE VIEW IF NOT EXISTS {NS}.candidate_ads AS
 SELECT c.* FROM {NS}.raw_comments c
 JOIN {NS}.raw_threads t ON c.thread_id = t.thread_id
 WHERE c.fetch_status = 'ok' AND NOT c.deleted AND NOT c.dead
   AND c.item_type = 'comment' AND c.parent_id = c.thread_id
   AND length(trim(c.text_clean)) > 0
   AND array_contains(t.child_ids, c.comment_id)
""")
spark.sql(f"""CREATE VIEW IF NOT EXISTS {NS}.ingestion_coverage AS
 WITH months AS (
   SELECT date_format(month_date, 'yyyy-MM') AS month
   FROM explode(sequence(DATE '2020-01-01',
       trunc(current_date(), 'MM'), INTERVAL 1 MONTH)) AS m(month_date)
 ), expected AS (
   SELECT month, count(*) AS threads, sum(size(child_ids)) AS expected_comments
   FROM {NS}.raw_threads GROUP BY month
 ), current_children AS (
   SELECT thread_id, month, explode(child_ids) AS comment_id FROM {NS}.raw_threads
 ), actual AS (
   SELECT e.month, count(c.comment_id) AS retrieved_comments,
     count_if(c.fetch_status = 'ok') AS available_comments,
     count_if(c.fetch_status IN ('deleted', 'dead', 'unavailable')) AS unavailable_comments,
     count_if(c.fetch_status = 'error') AS failed_comments
   FROM current_children e LEFT JOIN {NS}.raw_comments c
     ON e.comment_id = c.comment_id AND e.thread_id = c.thread_id GROUP BY e.month
 ) SELECT m.month, coalesce(e.threads, 0) AS threads,
   coalesce(e.expected_comments, 0) AS expected_comments,
   coalesce(a.retrieved_comments, 0) AS retrieved_comments,
   coalesce(a.available_comments, 0) AS available_comments,
   coalesce(a.unavailable_comments, 0) AS unavailable_comments,
   coalesce(a.failed_comments, 0) AS failed_comments,
   coalesce(e.expected_comments, 0) - coalesce(a.retrieved_comments, 0) AS pending_comments,
   m.month = date_format(current_date(), 'yyyy-MM') AS partial_month,
   CASE WHEN e.threads IS NULL THEN 'missing_thread'
        WHEN e.threads > 1 THEN 'multiple_threads'
        WHEN a.retrieved_comments < e.expected_comments THEN 'pending'
        WHEN a.failed_comments > 0 THEN 'fetch_errors'
        ELSE 'retrieved' END AS coverage_status
 FROM months m LEFT JOIN expected e USING (month) LEFT JOIN actual a USING (month)
""")
summary = spark.sql(f"SELECT count(*) AS comments, count_if(fetch_status = 'ok') AS available FROM {NS}.raw_comments").first().asDict()
summary.update({"run_id": RUN_ID, "threads": len(threads), "fetched_this_run": fetched_count,
                "namespace": NS})
print(json.dumps(summary))
merge_rows("ingestion_runs", [(RUN_ID, MODE, started, now(), "succeeded",
                               len(threads), fetched_count, None)], "run_id")
dbutils.notebook.exit(json.dumps(summary))
