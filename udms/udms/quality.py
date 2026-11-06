"""Data quality rules over the unified store."""
from collections import Counter
from datetime import datetime, timezone
from typing import Dict

from .mdm import EMAIL_RE


def run_quality(conn) -> Dict:
    issues = []

    emails = Counter()
    for r in conn.execute("SELECT * FROM employees"):
        ref = r["emp_id"]
        if not r["full_name"]:
            issues.append(("employees", ref, "missing_name", ""))
        if not EMAIL_RE.match(r["email"] or ""):
            issues.append(("employees", ref, "invalid_email", r["email"] or ""))
        else:
            emails[r["email"]] += 1
        if not r["department"]:
            issues.append(("employees", ref, "missing_department", ""))
        if r["salary"] is None or r["salary"] <= 0:
            issues.append(("employees", ref, "invalid_salary", str(r["salary"])))
    for email, n in emails.items():
        if n > 1:
            issues.append(("employees", email, "duplicate_email", f"{n} employees"))

    phones = Counter()
    for r in conn.execute("SELECT * FROM customers"):
        ref = str(r["customer_id"])
        if not r["name"]:
            issues.append(("customers", ref, "missing_name", ""))
        if not r["email"] and not r["phone"]:
            issues.append(("customers", ref, "no_contact_info", ""))
        if r["phone"]:
            phones[r["phone"]] += 1
    for phone, n in phones.items():
        if n > 1:
            issues.append(("customers", phone, "duplicate_phone", f"{n} customers"))

    run_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute("DELETE FROM dq_issues")
    conn.executemany(
        "INSERT INTO dq_issues (run_ts, entity, ref, rule, detail) VALUES (?,?,?,?,?)",
        [(run_ts, *i) for i in issues])
    return {"run_ts": run_ts, "total_issues": len(issues),
            "by_rule": dict(Counter(f"{i[0]}.{i[2]}" for i in issues))}
