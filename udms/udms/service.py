"""Application service: every read/write goes through authorization + audit."""
from pathlib import Path
from typing import Dict, List, Optional

from . import governance as gov
from .db import session
from .governance import ENTITIES, User


class PermissionDenied(Exception):
    pass


class NotFound(Exception):
    pass


class DataService:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    # ---------- helpers ----------
    def authenticate(self, api_key: Optional[str]) -> Optional[User]:
        with session(self.db_path) as conn:
            return gov.authenticate(conn, api_key)

    def _authorize(self, conn, user: User, resource: str, action: str) -> None:
        if not gov.can(user.role, resource, action):
            gov.audit(conn, user.username, f"DENIED_{action.upper()}", resource)
            conn.commit()  # keep the audit row even though we raise
            raise PermissionDenied(f"{user.role} may not {action} {resource}")

    @staticmethod
    def _entity(name: str):
        if name not in ENTITIES:
            raise NotFound(f"unknown entity: {name}")
        return ENTITIES[name]

    # ---------- entity access ----------
    def list(self, user: User, entity: str, q: Optional[str] = None,
             limit: int = 50, offset: int = 0) -> List[Dict]:
        ent = self._entity(entity)
        with session(self.db_path) as conn:
            self._authorize(conn, user, entity, "read")
            sql = f"SELECT {', '.join(ent.columns)} FROM {entity}"
            params: list = []
            if q:
                sql += " WHERE " + " OR ".join(f"{c} LIKE ?" for c in ent.searchable)
                params += [f"%{q}%"] * len(ent.searchable)
            sql += f" ORDER BY {ent.pk} LIMIT ? OFFSET ?"
            rows = conn.execute(sql, params + [limit, offset]).fetchall()
            gov.audit(conn, user.username, "READ", entity, None,
                      f"q={q!r} rows={len(rows)}")
            return [gov.mask_row(user.role, entity, dict(r)) for r in rows]

    def get(self, user: User, entity: str, key) -> Dict:
        ent = self._entity(entity)
        with session(self.db_path) as conn:
            self._authorize(conn, user, entity, "read")
            row = conn.execute(
                f"SELECT {', '.join(ent.columns)} FROM {entity} WHERE {ent.pk} = ?",
                (key,)).fetchone()
            if row is None:
                raise NotFound(f"{entity}/{key} not found")
            gov.audit(conn, user.username, "READ", entity, key)
            return gov.mask_row(user.role, entity, dict(row))

    def update(self, user: User, entity: str, key, changes: Dict) -> Dict:
        ent = self._entity(entity)
        bad = [c for c in changes if c not in ent.editable]
        if bad:
            raise ValueError(f"fields not editable: {bad}")
        if not changes:
            raise ValueError("no changes supplied")
        with session(self.db_path) as conn:
            self._authorize(conn, user, entity, "write")
            sets = ", ".join(f"{c} = ?" for c in changes)
            if entity == "customers":
                sets += ", updated_at = date('now')"
            cur = conn.execute(f"UPDATE {entity} SET {sets} WHERE {ent.pk} = ?",
                               list(changes.values()) + [key])
            if cur.rowcount == 0:
                raise NotFound(f"{entity}/{key} not found")
            gov.audit(conn, user.username, "UPDATE", entity, key,
                      "fields=" + ",".join(changes))
        return self.get(user, entity, key)

    # ---------- governance resources ----------
    def quality_report(self, user: User) -> List[Dict]:
        with session(self.db_path) as conn:
            self._authorize(conn, user, "quality", "read")
            gov.audit(conn, user.username, "READ", "quality")
            return [dict(r) for r in conn.execute(
                "SELECT entity, ref, rule, detail, run_ts FROM dq_issues ORDER BY entity, rule, ref")]

    def audit_log(self, user: User, limit: int = 100) -> List[Dict]:
        with session(self.db_path) as conn:
            self._authorize(conn, user, "audit", "read")
            return [dict(r) for r in conn.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]
