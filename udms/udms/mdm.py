"""Master Data Management: match + merge source records into golden records.

Matching: normalized email first, then normalized phone.
Survivorship: the most recently updated source wins for each field, but a
non-empty value is never overwritten by an empty one.
"""
import re
from datetime import date
from typing import Dict, List

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def norm_email(value) -> str:
    v = (value or "").strip().lower()
    return v if EMAIL_RE.match(v) else ""


def norm_phone(value) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-10:] if len(digits) >= 10 else ""


def clean_text(value) -> str:
    return " ".join((value or "").split())


def _find_customer(conn, source: str, source_id: str, email: str, phone: str):
    row = conn.execute(
        "SELECT customer_id FROM customer_xref WHERE source_system=? AND source_id=?",
        (source, source_id)).fetchone()
    if row:
        return row[0]
    if email:
        row = conn.execute("SELECT customer_id FROM customers WHERE email=?",
                           (email,)).fetchone()
        if row:
            return row[0]
    if phone:
        row = conn.execute("SELECT customer_id FROM customers WHERE phone=?",
                           (phone,)).fetchone()
        if row:
            return row[0]
    return None


def sync_customers(conn, records: List[Dict]) -> Dict[str, int]:
    """Merge source records into golden customers. Safe to run repeatedly."""
    stats = {"source_records": len(records), "created": 0, "linked": 0}
    today = date.today().isoformat()

    for rec in sorted(records, key=lambda r: r["updated"] or ""):
        email = norm_email(rec["email"])
        phone = norm_phone(rec["phone"])
        name = clean_text(rec["name"]).title()
        city = clean_text(rec["city"]).title()
        ts = rec["updated"] or today

        cid = _find_customer(conn, rec["source"], rec["source_id"], email, phone)
        if cid is None:
            cur = conn.execute(
                "INSERT INTO customers (name, email, phone, city, updated_at) "
                "VALUES (?,?,?,?,?)", (name, email, phone, city, ts))
            cid = cur.lastrowid
            stats["created"] += 1
        else:
            current = conn.execute("SELECT updated_at FROM customers WHERE customer_id=?",
                                   (cid,)).fetchone()[0] or ""
            if ts >= current:   # newer record wins, but never blank out good data
                conn.execute(
                    """UPDATE customers SET
                         name  = COALESCE(NULLIF(?, ''), name),
                         email = COALESCE(NULLIF(?, ''), email),
                         phone = COALESCE(NULLIF(?, ''), phone),
                         city  = COALESCE(NULLIF(?, ''), city),
                         updated_at = ? WHERE customer_id = ?""",
                    (name, email, phone, city, ts, cid))
            else:               # older record only fills gaps
                conn.execute(
                    """UPDATE customers SET
                         name  = COALESCE(NULLIF(name, ''),  ?),
                         email = COALESCE(NULLIF(email, ''), ?),
                         phone = COALESCE(NULLIF(phone, ''), ?),
                         city  = COALESCE(NULLIF(city, ''),  ?)
                       WHERE customer_id = ?""", (name, email, phone, city, cid))

        cur = conn.execute(
            "INSERT OR IGNORE INTO customer_xref VALUES (?,?,?)",
            (rec["source"], rec["source_id"], cid))
        stats["linked"] += cur.rowcount
    return stats
