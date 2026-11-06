"""Source system connectors.

Each source has its own file layout and field names. Connectors map them to one
canonical shape so the rest of the system never needs to know about the sources.
"""
import csv
from pathlib import Path
from typing import Dict, List


def _read(path: Path) -> List[Dict[str, str]]:
    with Path(path).open(newline="") as fh:
        return list(csv.DictReader(fh))


def load_crm(path: Path) -> List[Dict]:
    """CRM columns: crm_id, name, email, phone, city, updated"""
    return [{"source": "crm", "source_id": r["crm_id"], "name": r["name"],
             "email": r["email"], "phone": r["phone"], "city": r["city"],
             "updated": r["updated"]} for r in _read(path)]


def load_erp(path: Path) -> List[Dict]:
    """ERP columns: account_no, customer_name, e_mail, telephone, town, last_modified"""
    return [{"source": "erp", "source_id": r["account_no"], "name": r["customer_name"],
             "email": r["e_mail"], "phone": r["telephone"], "city": r["town"],
             "updated": r["last_modified"]} for r in _read(path)]


def load_hr(path: Path) -> List[Dict]:
    """HR columns: emp_id, full_name, email, department, salary, hire_date"""
    out = []
    for r in _read(path):
        try:
            salary = float(r["salary"])
        except (TypeError, ValueError):
            salary = None
        out.append({"emp_id": r["emp_id"].strip(),
                    "full_name": " ".join(r["full_name"].split()).title(),
                    "email": r["email"].strip().lower(),
                    "department": r["department"].strip(),
                    "salary": salary, "hire_date": r["hire_date"].strip()})
    return out


def load_employees_into(conn, records: List[Dict]) -> int:
    """Upsert employees (idempotent)."""
    conn.executemany(
        """INSERT INTO employees (emp_id, full_name, email, department, salary, hire_date)
           VALUES (:emp_id, :full_name, :email, :department, :salary, :hire_date)
           ON CONFLICT(emp_id) DO UPDATE SET
             full_name=excluded.full_name, email=excluded.email,
             department=excluded.department, salary=excluded.salary,
             hire_date=excluded.hire_date""", records)
    return len(records)
