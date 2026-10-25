"""Generate native SQL requests for the review stage without rerunning inference."""
import ast
import json
from pathlib import Path

tree = ast.parse(Path("notebooks/03_test_first20_ai_functions.py").read_text())
prefix = []
calls = []
seen_sql = False
for node in tree.body:
    is_sql = (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
              and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "sql")
    if is_sql:
        seen_sql = True
        calls.append(node.value.args[0])
    if not seen_sql:
        prefix.append(node)
namespace = {}
exec(compile(ast.Module(body=prefix, type_ignores=[]), "config", "exec"), namespace)
selected = []
for expression in calls:
    if not isinstance(expression, ast.JoinedStr):
        continue
    first = expression.values[0].value
    if first.startswith("CREATE TABLE IF NOT EXISTS ") or first.startswith("INSERT INTO ") or first.startswith("CREATE OR REPLACE TABLE "):
        # Only review-table creation, review inference, and the final result
        # materialization. Never evaluate the main 20-post inference expression.
        if "post_country_reviews" in ast.unparse(expression) or first.startswith("CREATE OR REPLACE TABLE "):
            selected.append(eval(compile(ast.Expression(expression), "sql", "eval"), namespace))
assert len(selected) == 3
for index, statement in enumerate(selected):
    Path(f"/tmp/hnjob-country-review-{index}.json").write_text(json.dumps({
        "warehouse_id": "616681d29d918fc1", "statement": statement, "wait_timeout": "10s"}))
