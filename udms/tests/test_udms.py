import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from udms.connectors import load_crm, load_employees_into, load_erp, load_hr
from udms.db import init_db, session
from udms.mdm import norm_email, norm_phone, sync_customers
from udms.quality import run_quality
from udms.sampledata import DEMO_USERS, generate
from udms.service import DataService, NotFound, PermissionDenied


class UDMSTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.src, self.db = root / "src", root / "udms.db"
        generate(self.src)
        init_db(self.db)
        with session(self.db) as conn:
            conn.executemany("INSERT INTO users VALUES (?,?,?)", DEMO_USERS)
            load_employees_into(conn, load_hr(self.src / "hr.csv"))
            self.stats = sync_customers(
                conn, load_crm(self.src / "crm.csv") + load_erp(self.src / "erp.csv"))
            self.dq = run_quality(conn)
        self.svc = DataService(self.db)

    def tearDown(self):
        self.tmp.cleanup()

    def user(self, key):
        return self.svc.authenticate(key)

    # ---- MDM ----
    def test_normalizers(self):
        self.assertEqual(norm_email("  A@B.COM "), "a@b.com")
        self.assertEqual(norm_email("nope"), "")
        self.assertEqual(norm_phone("+91 98765-43210"), "9876543210")

    def test_duplicates_merged(self):
        # 30 CRM + 20 ERP source records, 12 overlap -> 38 golden customers
        self.assertEqual(self.stats["source_records"], 50)
        self.assertEqual(self.stats["created"], 38)
        with session(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0], 38)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM customer_xref").fetchone()[0], 50)

    def test_sync_is_idempotent(self):
        with session(self.db) as conn:
            again = sync_customers(
                conn, load_crm(self.src / "crm.csv") + load_erp(self.src / "erp.csv"))
            self.assertEqual(again["created"], 0)
            self.assertEqual(again["linked"], 0)

    def test_newest_source_wins(self):
        rows = self.svc.list(self.user("admin-key"), "customers", limit=100)
        # ERP (newer) has upper-cased towns that get re-normalized to Title Case
        self.assertTrue(all(r["city"] == r["city"].title() for r in rows))

    # ---- quality ----
    def test_quality_flags_bad_hr_rows(self):
        rules = self.dq["by_rule"]
        self.assertEqual(rules["employees.invalid_email"], 1)
        self.assertEqual(rules["employees.invalid_salary"], 1)
        self.assertEqual(rules["employees.missing_department"], 1)

    # ---- governance ----
    def test_role_permissions(self):
        with self.assertRaises(PermissionDenied):
            self.svc.list(self.user("sales-key"), "employees")
        with self.assertRaises(PermissionDenied):
            self.svc.list(self.user("hr-key"), "customers")
        with self.assertRaises(PermissionDenied):
            self.svc.audit_log(self.user("analyst-key"))

    def test_masking(self):
        hr = self.svc.list(self.user("hr-key"), "employees", limit=1)[0]
        analyst = self.svc.list(self.user("analyst-key"), "employees", limit=1)[0]
        self.assertNotEqual(hr["salary"], "***")
        self.assertEqual(analyst["salary"], "***")
        sales = self.svc.list(self.user("sales-key"), "customers", limit=1)[0]
        analyst_c = self.svc.list(self.user("analyst-key"), "customers", limit=1)[0]
        self.assertNotEqual(sales["phone"], "***")
        self.assertEqual(analyst_c["phone"], "***")

    def test_update_and_audit(self):
        updated = self.svc.update(self.user("hr-key"), "employees", "E001",
                                  {"department": "Finance"})
        self.assertEqual(updated["department"], "Finance")
        with self.assertRaises(ValueError):
            self.svc.update(self.user("hr-key"), "employees", "E001", {"emp_id": "X"})
        with self.assertRaises(NotFound):
            self.svc.get(self.user("admin-key"), "employees", "NOPE")
        actions = [r["action"] for r in self.svc.audit_log(self.user("admin-key"))]
        self.assertIn("UPDATE", actions)

    def test_denied_attempts_are_audited(self):
        with self.assertRaises(PermissionDenied):
            self.svc.list(self.user("sales-key"), "employees")
        log = self.svc.audit_log(self.user("admin-key"))
        self.assertTrue(any(r["action"] == "DENIED_READ" and r["username"] == "sam"
                            for r in log))

    def test_search(self):
        rows = self.svc.list(self.user("admin-key"), "employees", q="Engineering", limit=100)
        self.assertTrue(all(r["department"] == "Engineering" for r in rows))

    def test_bad_api_key(self):
        self.assertIsNone(self.svc.authenticate("wrong"))


if __name__ == "__main__":
    unittest.main()
