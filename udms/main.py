"""CLI.

    python main.py demo                       # create DB, sample data, sync, quality
    python main.py sync                       # re-run ingestion + master data merge
    python main.py quality                    # re-run data quality checks
    python main.py search customers hyd --key sales-key
    python main.py audit --key admin-key
    python main.py serve --port 8000
"""
import argparse
import json

from udms import config
from udms.api import serve
from udms.connectors import load_crm, load_employees_into, load_erp, load_hr
from udms.db import init_db, session
from udms.mdm import sync_customers
from udms.quality import run_quality
from udms.sampledata import DEMO_USERS, generate
from udms.service import DataService, NotFound, PermissionDenied


def do_sync() -> dict:
    src = config.SOURCE_DIR
    with session(config.DB_PATH) as conn:
        employees = load_employees_into(conn, load_hr(src / "hr.csv"))
        customers = sync_customers(conn, load_crm(src / "crm.csv") + load_erp(src / "erp.csv"))
        quality = run_quality(conn)
        n = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    return {"employees_loaded": employees, "customer_sync": customers,
            "golden_customers": n, "quality": quality}


def main() -> int:
    p = argparse.ArgumentParser(description="Unified Enterprise Data Management System")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    sub.add_parser("sync")
    sub.add_parser("quality")
    s = sub.add_parser("search")
    s.add_argument("entity")
    s.add_argument("text", nargs="?")
    s.add_argument("--key", required=True, help="API key, e.g. admin-key")
    a = sub.add_parser("audit")
    a.add_argument("--key", required=True)
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default=config.API_HOST)
    sv.add_argument("--port", type=int, default=config.API_PORT)
    args = p.parse_args()

    service = DataService(config.DB_PATH)

    if args.cmd == "demo":
        generate(config.SOURCE_DIR)
        init_db(config.DB_PATH)
        with session(config.DB_PATH) as conn:
            conn.executemany("INSERT OR REPLACE INTO users VALUES (?,?,?)", DEMO_USERS)
        print(json.dumps(do_sync(), indent=2))
        print("\nDemo users (username, role, api key):")
        for u in DEMO_USERS:
            print("  ", u)
    elif args.cmd == "sync":
        print(json.dumps(do_sync(), indent=2))
    elif args.cmd == "quality":
        with session(config.DB_PATH) as conn:
            print(json.dumps(run_quality(conn), indent=2))
    elif args.cmd in ("search", "audit"):
        user = service.authenticate(args.key)
        if user is None:
            print("Invalid API key")
            return 1
        try:
            data = (service.list(user, args.entity, args.text) if args.cmd == "search"
                    else service.audit_log(user))
        except (PermissionDenied, NotFound) as exc:
            print(f"Error: {exc}")
            return 1
        print(json.dumps(data, indent=2))
    elif args.cmd == "serve":
        serve(service, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
