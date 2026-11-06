"""
Sample Dataset Generator for PS-113 School Fee Management Engine
Generates:
1. fee_structures.csv (12 grades, 5 heads)
2. addon_rates.csv (Transport zones, Hostel types)
3. students.csv (60 students across 12 grades, 8 sibling groups, categories)
4. addons.csv (30 transport and hostel events)
5. payments.csv (350 payments with 6 bounces)
6. commands.txt (Full command file executing complete lifecycle)
"""
import csv
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path


def generate_sample_data():
    out_dir = Path("sample_data")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fee Structures for 12 Grades
    # tuition, development, lab, activity, exam
    fee_file = out_dir / "fee_structures.csv"
    with open(fee_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["grade", "tuition", "development", "lab", "activity", "exam"])
        for grade in range(1, 13):
            base_tuition = 30000 + (grade - 1) * 3000
            development = 12000 + (grade - 1) * 500
            lab = 3000 + (grade - 1) * 600 if grade >= 6 else 1500
            activity = 3000 + (grade - 1) * 200
            exam = 2000 + (grade - 1) * 200
            writer.writerow([grade, base_tuition, development, lab, activity, exam])

    # 2. Add-on Rates
    addon_file = out_dir / "addon_rates.csv"
    with open(addon_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["addon_type", "identifier", "monthly_rate", "deposit_months"])
        writer.writerow(["TRANSPORT", "Zone A", "1800.00", "0"])
        writer.writerow(["TRANSPORT", "Zone B", "2400.00", "0"])
        writer.writerow(["TRANSPORT", "Zone C", "3000.00", "0"])
        writer.writerow(["HOSTEL", "shared", "9000.00", "1"])
        writer.writerow(["HOSTEL", "single", "12000.00", "1"])

    # 3. 60 Students with 8 Sibling Groups
    # Sibling groups:
    # GRP01: STU001 (eldest), STU002 (2nd), STU003 (3rd - STAFF_WARD) -> Edge case test
    # GRP02: STU004 (eldest), STU005 (2nd - MERIT)
    # GRP03: STU006 (eldest), STU007 (2nd), STU008 (3rd)
    # GRP04: STU009 (eldest), STU010 (2nd)
    # GRP05: STU011 (eldest), STU012 (2nd), STU013 (3rd)
    # GRP06: STU014 (eldest), STU015 (2nd)
    # GRP07: STU016 (eldest), STU017 (2nd)
    # GRP08: STU018 (eldest), STU019 (2nd)
    # Others: STU020 to STU060 (EWS, MERIT, STAFF_WARD, NONE)
    students_file = out_dir / "students.csv"
    students_data = []

    names = [
        "Aarav Sharma", "Ananya Sharma", "Aditya Sharma",  # GRP01
        "Rohan Gupta", "Riya Gupta",                       # GRP02
        "Kabir Singh", "Kavya Singh", "Karan Singh",       # GRP03
        "Ishaan Patel", "Isha Patel",                      # GRP04
        "Vihaan Reddy", "Vidya Reddy", "Varun Reddy",      # GRP05
        "Dhruv Kumar", "Disha Kumar",                      # GRP06
        "Arjun Verma", "Alka Verma",                       # GRP07
        "Devansh Joshi", "Diya Joshi",                     # GRP08
    ]

    # Fill up to 60 names
    for i in range(20, 61):
        names.append(f"Student_{i:02d}")

    plans_cycle = ["TERM", "MONTHLY", "ANNUAL", "TERM", "TERM"]
    categories_cycle = ["NONE", "STAFF_WARD", "MERIT", "EWS", "NONE"]

    with open(students_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "student_id", "name", "grade", "section", "dob", "admission_date",
            "plan", "category", "previous_year_percentage", "sibling_group_id", "campus"
        ])

        for i in range(1, 61):
            s_id = f"STU{i:03d}"
            name = names[i - 1]
            grade = ((i - 1) % 12) + 1
            section = "A" if i % 2 == 1 else "B"

            # Assign sibling groups with valid dates
            if 1 <= i <= 3:
                sib_grp = "SIB_GRP_01"
                dob = date(2010 + (i - 1) * 2, 5, 10 + i)
            elif 4 <= i <= 5:
                sib_grp = "SIB_GRP_02"
                dob = date(2011 + (i - 4) * 2, 6, 10 + i)
            elif 6 <= i <= 8:
                sib_grp = "SIB_GRP_03"
                dob = date(2010 + (i - 6) * 2, 7, 10 + (i - 5))
            elif 9 <= i <= 10:
                sib_grp = "SIB_GRP_04"
                dob = date(2012 + (i - 9) * 2, 8, 10 + (i - 8))
            elif 11 <= i <= 13:
                sib_grp = "SIB_GRP_05"
                dob = date(2010 + (i - 11) * 2, 9, 10 + (i - 10))
            elif 14 <= i <= 15:
                sib_grp = "SIB_GRP_06"
                dob = date(2012 + (i - 14) * 2, 10, 10 + (i - 13))
            elif 16 <= i <= 17:
                sib_grp = "SIB_GRP_07"
                dob = date(2013 + (i - 16) * 2, 11, 10 + (i - 15))
            elif 18 <= i <= 19:
                sib_grp = "SIB_GRP_08"
                dob = date(2013 + (i - 18) * 2, 12, 10 + (i - 17))
            else:
                sib_grp = ""
                dob = date(2014 - (grade // 2), ((i - 1) % 12) + 1, ((i - 1) % 25) + 1)

            adm_date = date(2026, 4, 1)

            # Special edge case setups
            if s_id == "STU003":
                # Staff ward + 3rd sibling
                category = "STAFF_WARD"
                plan = "TERM"
                prev_pct = 82.0
            elif s_id == "STU005":
                # Merit + 2nd sibling
                category = "MERIT"
                plan = "TERM"
                prev_pct = 94.5
            elif s_id == "STU020":
                # EWS
                category = "EWS"
                plan = "TERM"
                prev_pct = 75.0
            elif s_id == "STU021":
                # Staff ward alone
                category = "STAFF_WARD"
                plan = "TERM"
                prev_pct = 80.0
            elif s_id == "STU022":
                # ANNUAL plan
                category = "NONE"
                plan = "ANNUAL"
                prev_pct = 88.0
            elif s_id == "STU023":
                # MONTHLY plan
                category = "NONE"
                plan = "MONTHLY"
                prev_pct = 78.0
            else:
                plan = plans_cycle[i % len(plans_cycle)]
                category = categories_cycle[i % len(categories_cycle)]
                prev_pct = 70.0 + (i % 25)

            campus = "CAMPUS-1" if i <= 30 else "CAMPUS-2"

            row = [
                s_id, name, grade, section, dob.isoformat(), adm_date.isoformat(),
                plan, category, f"{prev_pct:.1f}", sib_grp, campus
            ]
            writer.writerow(row)
            students_data.append(row)

    # 4. 30 Transport and Hostel Events
    addons_file = out_dir / "addons.csv"
    with open(addons_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "student_id", "addon_type", "zone_or_room", "start_date", "end_date"])

        # 20 Transport events
        # Include joined on 15th (full month) and 16th (half month)
        writer.writerow(["ADDON001", "STU001", "TRANSPORT", "Zone A", "2026-04-01", ""])
        writer.writerow(["ADDON002", "STU002", "TRANSPORT", "Zone A", "2026-04-01", ""])
        writer.writerow(["ADDON003", "STU003", "TRANSPORT", "Zone A", "2026-04-01", ""])
        writer.writerow(["ADDON004", "STU004", "TRANSPORT", "Zone B", "2026-04-01", ""])
        writer.writerow(["ADDON005", "STU005", "TRANSPORT", "Zone B", "2026-04-01", ""])
        # Edge case: Transport joined on the 15th
        writer.writerow(["ADDON006", "STU006", "TRANSPORT", "Zone C", "2026-04-15", ""])
        # Edge case: Transport joined on the 16th
        writer.writerow(["ADDON007", "STU007", "TRANSPORT", "Zone C", "2026-04-16", ""])
        writer.writerow(["ADDON008", "STU008", "TRANSPORT", "Zone A", "2026-04-01", ""])
        writer.writerow(["ADDON009", "STU009", "TRANSPORT", "Zone B", "2026-04-01", ""])
        writer.writerow(["ADDON010", "STU010", "TRANSPORT", "Zone B", "2026-04-01", ""])

        for k in range(11, 21):
            st_id = f"STU{k + 10:03d}"
            zone = "Zone A" if k % 3 == 0 else ("Zone B" if k % 3 == 1 else "Zone C")
            writer.writerow([f"ADDON{k:03d}", st_id, "TRANSPORT", zone, "2026-04-01", ""])

        # 10 Hostel events (shared and single)
        writer.writerow(["ADDON021", "STU008", "HOSTEL", "shared", "2026-04-01", ""])
        writer.writerow(["ADDON022", "STU011", "HOSTEL", "single", "2026-04-01", ""])
        writer.writerow(["ADDON023", "STU012", "HOSTEL", "shared", "2026-04-01", ""])
        writer.writerow(["ADDON024", "STU013", "HOSTEL", "shared", "2026-04-01", ""])
        writer.writerow(["ADDON025", "STU014", "HOSTEL", "single", "2026-04-01", ""])
        writer.writerow(["ADDON026", "STU015", "HOSTEL", "shared", "2026-04-01", ""])
        writer.writerow(["ADDON027", "STU025", "HOSTEL", "single", "2026-04-01", ""])
        writer.writerow(["ADDON028", "STU030", "HOSTEL", "shared", "2026-04-01", ""])
        writer.writerow(["ADDON029", "STU035", "HOSTEL", "single", "2026-04-01", ""])
        writer.writerow(["ADDON030", "STU040", "HOSTEL", "shared", "2026-04-01", ""])

    # 5. 350 Payments including 6 Bounces
    payments_file = out_dir / "payments.csv"
    bounced_payment_ids = {"PMT042", "PMT099", "PMT145", "PMT180", "PMT220", "PMT310"}

    with open(payments_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["payment_id", "student_id", "amount", "payment_date", "payment_mode", "reference", "will_bounce"])

        pmt_counter = 1
        # Generate payments across students
        # Round 1: April instalments (Apr 5 to Apr 25)
        for s_idx in range(1, 61):
            s_id = f"STU{s_idx:03d}"
            # Due date is Apr 10. Grace is 7 days (till Apr 17).
            # Edge case test: STU001 pays on 17 April (7th day of grace -> 0 late fee!)
            if s_id == "STU001":
                p_date = date(2026, 4, 17)
            elif s_idx <= 25:
                p_date = date(2026, 4, 8 + (s_idx % 8))  # within grace
            elif s_idx <= 45:
                p_date = date(2026, 4, 18 + (s_idx % 5)) # late
            else:
                p_date = date(2026, 5, 2)

            amt = 15000.00 + (s_idx % 10) * 1000.00
            mode = "CHEQUE" if pmt_counter in [42, 99, 145, 180, 220, 310] else ("UPI" if s_idx % 2 == 0 else "BANK_TRANSFER")
            pmt_id = f"PMT{pmt_counter:03d}"
            will_bounce = "YES" if pmt_id in bounced_payment_ids else "NO"

            writer.writerow([pmt_id, s_id, f"{amt:.2f}", p_date.isoformat(), mode, f"REF-{pmt_id}", will_bounce])
            pmt_counter += 1

        # Round 2: May / June payments
        for s_idx in range(1, 61):
            s_id = f"STU{s_idx:03d}"
            p_date = date(2026, 5, 5 + (s_idx % 20))
            amt = 6000.00 + (s_idx % 8) * 500.00
            mode = "CHEQUE" if pmt_counter in [42, 99, 145, 180, 220, 310] else "UPI"
            pmt_id = f"PMT{pmt_counter:03d}"
            will_bounce = "YES" if pmt_id in bounced_payment_ids else "NO"
            writer.writerow([pmt_id, s_id, f"{amt:.2f}", p_date.isoformat(), mode, f"REF-{pmt_id}", will_bounce])
            pmt_counter += 1

        # Round 3: July / August payments
        for s_idx in range(1, 61):
            s_id = f"STU{s_idx:03d}"
            p_date = date(2026, 8, 8 + (s_idx % 15))
            amt = 12000.00 + (s_idx % 6) * 1000.00
            mode = "CHEQUE" if pmt_counter in [42, 99, 145, 180, 220, 310] else "BANK_TRANSFER"
            pmt_id = f"PMT{pmt_counter:03d}"
            will_bounce = "YES" if pmt_id in bounced_payment_ids else "NO"
            writer.writerow([pmt_id, s_id, f"{amt:.2f}", p_date.isoformat(), mode, f"REF-{pmt_id}", will_bounce])
            pmt_counter += 1

        # Round 4: Sep / Oct payments
        for s_idx in range(1, 61):
            s_id = f"STU{s_idx:03d}"
            p_date = date(2026, 10, 5 + (s_idx % 15))
            amt = 5000.00 + (s_idx % 5) * 800.00
            mode = "CHEQUE" if pmt_counter in [42, 99, 145, 180, 220, 310] else "UPI"
            pmt_id = f"PMT{pmt_counter:03d}"
            will_bounce = "YES" if pmt_id in bounced_payment_ids else "NO"
            writer.writerow([pmt_id, s_id, f"{amt:.2f}", p_date.isoformat(), mode, f"REF-{pmt_id}", will_bounce])
            pmt_counter += 1

        # Round 5: Nov / Dec payments
        for s_idx in range(1, 61):
            s_id = f"STU{s_idx:03d}"
            p_date = date(2026, 12, 5 + (s_idx % 15))
            amt = 10000.00 + (s_idx % 7) * 1000.00
            mode = "CHEQUE" if pmt_counter in [42, 99, 145, 180, 220, 310] else "BANK_TRANSFER"
            pmt_id = f"PMT{pmt_counter:03d}"
            will_bounce = "YES" if pmt_id in bounced_payment_ids else "NO"
            writer.writerow([pmt_id, s_id, f"{amt:.2f}", p_date.isoformat(), mode, f"REF-{pmt_id}", will_bounce])
            pmt_counter += 1

        # Generate remaining payments up to 350
        rem_count = 350 - (pmt_counter - 1)
        for r in range(rem_count):
            s_idx = (r % 60) + 1
            s_id = f"STU{s_idx:03d}"
            p_date = date(2027, 1, 5 + (r % 20))
            amt = 4000.00 + (r % 6) * 500.00
            pmt_id = f"PMT{pmt_counter:03d}"
            mode = "CHEQUE" if pmt_id in bounced_payment_ids else "UPI"
            will_bounce = "YES" if pmt_id in bounced_payment_ids else "NO"
            writer.writerow([pmt_id, s_id, f"{amt:.2f}", p_date.isoformat(), mode, f"REF-{pmt_id}", will_bounce])
            pmt_counter += 1

    # 6. Generate master command file
    cmd_file = out_dir / "commands.txt"
    with open(cmd_file, "w", encoding="utf-8") as f:
        f.write("# ================================================================\n")
        f.write("# PS-113: School Fee Management Engine Master Command File\n")
        f.write("# Academic Year 2026-2027\n")
        f.write("# ================================================================\n\n")

        f.write("# 1. Load Fee Structures for Grades 1 to 12\n")
        f.write(f"LOAD_FEE_FILE {fee_file}\n\n")

        f.write("# 2. Enrol 60 Students with Sibling Groups and Concession Categories\n")
        f.write(f"LOAD_STUDENTS_FILE {students_file}\n\n")

        f.write("# 3. Add Transport and Hostel Add-ons (30 events)\n")
        with open(addons_file, "r", encoding="utf-8") as af:
            reader = csv.DictReader(af)
            for row in reader:
                if row["addon_type"] == "TRANSPORT":
                    f.write(f"ADD_TRANSPORT {row['student_id']} {row['zone_or_room']} {row['start_date']}\n")
                elif row["addon_type"] == "HOSTEL":
                    f.write(f"ADD_HOSTEL {row['student_id']} {row['zone_or_room']} {row['start_date']}\n")
        f.write("\n")

        f.write("# 4. Record Payments (350 payments)\n")
        f.write(f"LOAD_PAYMENTS_FILE {payments_file}\n\n")

        f.write("# 5. Process 6 Cheque Bounces\n")
        bounce_dates = {
            "PMT042": "2026-05-15",
            "PMT099": "2026-06-20",
            "PMT145": "2026-09-01",
            "PMT180": "2026-09-15",
            "PMT220": "2026-11-10",
            "PMT310": "2027-01-25",
        }
        for p_id, b_date in bounce_dates.items():
            f.write(f"BOUNCE_PAYMENT {p_id} {b_date}\n")
        f.write("\n")

        f.write("# 6. Mid-Year Admissions & Withdrawals with Sibling Re-ranking\n")
        # STU001 withdraws on 2026-07-01 with notice given 2026-06-01 (exactly 30 days before Term 2 start on 2026-08-01)
        f.write("WITHDRAW_STUDENT STU001 2026-07-01 2026-06-01 0.00\n")
        # Mid-year admission on 15th vs 16th
        f.write("ENROL_STUDENT STU061 Midyear_Aug15 5 A 2016-04-10 2026-08-15 TERM NONE 85.0 - CAMPUS-1\n")
        f.write("ENROL_STUDENT STU062 Midyear_Aug16 5 A 2016-06-12 2026-08-16 TERM NONE 82.0 - CAMPUS-1\n\n")

        f.write("# 7. Fee Revision\n")
        f.write("REVISE_FEE 5 tuition 0.05 2026-08-01 FALSE\n\n")

        f.write("# 8. Stretch Goals: Allocate Merit Scholarship Pool (Rs 1,00,000)\n")
        f.write("ALLOCATE_SCHOLARSHIP 100000.00\n\n")

        f.write("# 9. Print Sample Demands, Schedules, Ledgers, and Defaulters\n")
        f.write("PRINT_DEMAND STU003 2026-04-10\n")
        f.write("PRINT_SCHEDULE STU003\n")
        f.write("PRINT_LEDGER STU003 2026-10-15\n")
        f.write("PRINT_DEMAND STU002 2026-08-10\n")
        f.write("PRINT_LEDGER STU002 2026-10-15\n")
        f.write("PRINT_DEFAULTERS 2026-10-15\n")

    print(f"Sample data generated successfully in {out_dir}:")
    print(f" - {fee_file} (12 grades)")
    print(f" - {addon_file} (rate card)")
    print(f" - {students_file} (60 students, 8 sibling groups)")
    print(f" - {addons_file} (30 addon events)")
    print(f" - {payments_file} (350 payments with 6 bounces)")
    print(f" - {cmd_file} (master command file)")


if __name__ == "__main__":
    generate_sample_data()
