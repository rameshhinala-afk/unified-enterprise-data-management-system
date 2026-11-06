"""Generate small, deliberately messy sample source files (HR, CRM, ERP)."""
import csv
import random
from pathlib import Path

FIRST = ["Asha", "Ravi", "Meera", "Karan", "Divya", "Arjun", "Sneha", "Vikram",
         "Anita", "Rohit", "Priya", "Sanjay", "Neha", "Amit", "Pooja"]
LAST = ["Sharma", "Reddy", "Iyer", "Patel", "Nair", "Gupta", "Rao", "Singh", "Das", "Khan"]
CITIES = ["hyderabad", "Mumbai", "pune", "Chennai", "delhi", "Bengaluru"]
DEPTS = ["Engineering", "Sales", "Finance", "HR", "Operations"]


def generate(source_dir: Path, seed: int = 7) -> None:
    source_dir = Path(source_dir)
    source_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    def person(i):
        return f"{FIRST[i % len(FIRST)]} {LAST[(i * 3) % len(LAST)]}"

    # --- HR: 20 employees, with a few quality problems
    with (source_dir / "hr.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["emp_id", "full_name", "email", "department", "salary", "hire_date"])
        for i in range(20):
            name = person(i)
            email = f"{name.lower().replace(' ', '.')}{i}@acme.com"
            salary = rng.randint(40, 150) * 1000
            dept = rng.choice(DEPTS)
            if i == 3:
                email = "not-an-email"
            if i == 7:
                salary = "n/a"
            if i == 11:
                dept = ""
            w.writerow([f"E{i:03d}", f"  {name.upper()} ", email, dept, salary,
                        f"20{rng.randint(15, 25)}-0{rng.randint(1, 9)}-1{rng.randint(0, 9)}"])

    # --- CRM: 30 customers
    crm = []
    for i in range(30):
        name = person(i + 2)
        crm.append({"crm_id": f"CRM{i:04d}", "name": name,
                    "email": f"{name.lower().replace(' ', '_')}{i}@mail.com",
                    "phone": f"98{rng.randint(10000000, 99999999)}",
                    "city": rng.choice(CITIES), "updated": "2026-03-01"})
    with (source_dir / "crm.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(crm[0]))
        w.writeheader()
        w.writerows(crm)

    # --- ERP: different field names; 12 overlap CRM customers (messy formatting)
    erp = []
    for i, c in enumerate(crm[:12]):
        phone = c["phone"]
        erp.append({"account_no": f"A{i:05d}",
                    "customer_name": c["name"].upper(),
                    "e_mail": f"  {c['email'].upper()} ",
                    "telephone": f"+91 {phone[:5]}-{phone[5:]}",
                    "town": c["city"].upper(),
                    "last_modified": "2026-06-15"})   # newer than CRM -> wins
    for i in range(12, 20):                           # ERP-only customers
        name = person(i + 40)
        erp.append({"account_no": f"A{i:05d}", "customer_name": name,
                    "e_mail": f"{name.lower().replace(' ', '')}{i}@corp.com",
                    "telephone": f"+91 9{rng.randint(100000000, 999999999)}",
                    "town": rng.choice(CITIES), "last_modified": "2026-05-10"})
    with (source_dir / "erp.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(erp[0]))
        w.writeheader()
        w.writerows(erp)


DEMO_USERS = [("alice", "admin", "admin-key"), ("harry", "hr", "hr-key"),
              ("sam", "sales", "sales-key"), ("anna", "analyst", "analyst-key")]
