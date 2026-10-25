"""Assemble portable notebooks using one identical prompt/schema definition."""
import ast
import json
import runpy
from pathlib import Path

root = Path(__file__).resolve().parents[1]
config = (root / "notebooks/03_test_first20_ai_functions.py").read_text().split("# COMMAND ----------", 1)[0]
checks = runpy.run_path(str(root / "quality/build_first20_validation.py"))["validation_sql"]
checks = checks.replace("workspace.hnjob.test_first20_validation", "workspace.hnjob.model_benchmark_checks")
checks = checks.replace("workspace.hnjob.test_first20_results r", "workspace.hnjob.model_benchmark_parsed r")
checks = checks.replace("SELECT r.test_rank, r.comment_id", "SELECT r.model, r.test_rank, r.comment_id")
# Score raw outputs: no model-specific corrections or header enrichment.
header = config + "\nBENCHMARK_CHECK_SQL = " + repr(checks) + "\n# COMMAND ----------\n"
(root / "notebooks/04_compare_models.py").write_text(header + (root / "pipeline/compare_models_body.py").read_text())
bulk = root / "pipeline/extract_all_body.py"
if bulk.exists():
    (root / "notebooks/05_extract_all_posts.py").write_text(config + "\n# COMMAND ----------\n" + bulk.read_text())
