"""Governance: entity catalog, role-based access, field masking, audit trail."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Entity:
    pk: str
    columns: Tuple[str, ...]
    editable: Tuple[str, ...]
    searchable: Tuple[str, ...]


# The data catalog: only these tables / columns can ever be queried or changed.
ENTITIES: Dict[str, Entity] = {
    "employees": Entity(
        pk="emp_id",
        columns=("emp_id", "full_name", "email", "department", "salary", "hire_date"),
        editable=("full_name", "email", "department", "salary"),
        searchable=("full_name", "email", "department")),
    "customers": Entity(
        pk="customer_id",
        columns=("customer_id", "name", "email", "phone", "city", "updated_at"),
        editable=("name", "email", "phone", "city"),
        searchable=("name", "email", "city")),
}

# role -> resource -> allowed actions   (resources: entities + "quality" + "audit")
PERMISSIONS: Dict[str, Dict[str, set]] = {
    "admin":   {"employees": {"read", "write"}, "customers": {"read", "write"},
                "quality": {"read"}, "audit": {"read"}},
    "hr":      {"employees": {"read", "write"}},
    "sales":   {"customers": {"read", "write"}},
    "analyst": {"employees": {"read"}, "customers": {"read"}, "quality": {"read"}},
}

# (entity, column) -> roles that may see the real value; everyone else gets "***"
MASKED_FIELDS: Dict[Tuple[str, str], set] = {
    ("employees", "salary"): {"admin", "hr"},
    ("customers", "phone"): {"admin", "sales"},
}


@dataclass(frozen=True)
class User:
    username: str
    role: str


def can(role: str, resource: str, action: str) -> bool:
    return action in PERMISSIONS.get(role, {}).get(resource, set())


def mask_row(role: str, entity: str, row: Dict) -> Dict:
    out = dict(row)
    for (ent, col), roles in MASKED_FIELDS.items():
        if ent == entity and col in out and role not in roles:
            out[col] = "***"
    return out


def authenticate(conn, api_key: Optional[str]) -> Optional[User]:
    if not api_key:
        return None
    row = conn.execute("SELECT username, role FROM users WHERE api_key = ?",
                       (api_key,)).fetchone()
    return User(row["username"], row["role"]) if row else None


def audit(conn, username: str, action: str, entity: Optional[str] = None,
          entity_id: Optional[str] = None, detail: str = "") -> None:
    conn.execute(
        "INSERT INTO audit_log (ts, username, action, entity, entity_id, detail) "
        "VALUES (?,?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"),
         username, action, entity, None if entity_id is None else str(entity_id), detail))
