"""
Expected Output Exporter and Reconciliation Tool for PS-113
Exports:
1. 35 visible student ledgers (STU001 to STU035) to expected_outputs/ledgers/
2. Fee demands for key students to expected_outputs/demands/
3. Instalment schedules to expected_outputs/schedules/
4. Defaulter lists as of milestone dates (2026-06-15, 2026-10-15, 2027-01-15) to expected_outputs/defaulters/
5. Automated diff checker comparing engine output with expected files.
"""
import difflib
import sys
from datetime import date
from pathlib import Path
from engine.command_processor import CommandProcessor
from engine.reports import ReportGenerator


def export_expected_outputs():
    base_dir = Path("expected_outputs")
    ledgers_dir = base_dir / "ledgers"
    demands_dir = base_dir / "demands"
    schedules_dir = base_dir / "schedules"
    defaulters_dir = base_dir / "defaulters"

    for d in [ledgers_dir, demands_dir, schedules_dir, defaulters_dir]:
        d.mkdir(parents=True, exist_ok=True)

    cmd_file = Path("sample_data") / "commands.txt"
    if not cmd_file.exists():
        print(f"Error: {cmd_file} not found. Please run scripts/generate_sample_data.py first.")
        return

    print("Executing master command workflow to generate reference outputs...")
    processor = CommandProcessor()
    processor.process_file(cmd_file)

    # 1. Export 35 visible student ledgers (STU001 to STU035)
    print("Exporting 35 visible student ledgers...")
    for i in range(1, 36):
        s_id = f"STU{i:03d}"
        student = processor.engine.students.get(s_id)
        if not student:
            continue
        txns = processor.engine.transactions.get(s_id, [])
        ledger_text = ReportGenerator.print_student_ledger(student, txns)
        out_path = ledgers_dir / f"{s_id}_ledger.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(ledger_text)

    # 2. Export Demand Notices for representative test students
    # STU001 (Eldest sibling withdrawn), STU002 (2nd child), STU003 (Staff ward 3rd child),
    # STU005 (Merit), STU020 (EWS), STU022 (Annual plan)
    print("Exporting representative Fee Demands...")
    test_students = ["STU001", "STU002", "STU003", "STU005", "STU020", "STU022"]
    for s_id in test_students:
        st = processor.engine.students.get(s_id)
        sched = processor.engine.schedules.get(s_id, [])
        if st and sched:
            demand_text = ReportGenerator.print_fee_demand(st, sched, date(2026, 4, 10))
            with open(demands_dir / f"{s_id}_demand.txt", "w", encoding="utf-8") as f:
                f.write(demand_text)

            sched_text = ReportGenerator.print_instalment_schedule(st, sched)
            with open(schedules_dir / f"{s_id}_schedule.txt", "w", encoding="utf-8") as f:
                f.write(sched_text)

    # 3. Export Defaulters Lists for milestone dates
    print("Exporting Defaulter Lists for milestone dates...")
    milestone_dates = [date(2026, 6, 15), date(2026, 10, 15), date(2027, 1, 15)]
    for m_date in milestone_dates:
        defaulters = processor.engine.get_defaulters(m_date)
        def_text = ReportGenerator.print_defaulters_list(defaulters, m_date)
        with open(defaulters_dir / f"defaulters_{m_date.isoformat()}.txt", "w", encoding="utf-8") as f:
            f.write(def_text)

    print(f"\n✅ All expected outputs successfully exported to '{base_dir}':")
    print(f" - {len(list(ledgers_dir.glob('*.txt')))} Student Ledgers in {ledgers_dir}")
    print(f" - {len(list(demands_dir.glob('*.txt')))} Fee Demands in {demands_dir}")
    print(f" - {len(list(schedules_dir.glob('*.txt')))} Instalment Schedules in {schedules_dir}")
    print(f" - {len(list(defaulters_dir.glob('*.txt')))} Defaulter Snapshots in {defaulters_dir}")


def verify_against_expected(expected_dir: Path, target_dir: Path) -> bool:
    """Compares all files in target_dir with expected_dir down to exact characters."""
    all_match = True
    expected_files = sorted(list(expected_dir.glob("*.txt")))

    if not expected_files:
        print(f"No reference files found in {expected_dir}")
        return False

    for exp_file in expected_files:
        tgt_file = target_dir / exp_file.name
        if not tgt_file.exists():
            print(f"❌ Missing file in target: {tgt_file.name}")
            all_match = False
            continue

        with open(exp_file, "r", encoding="utf-8") as f1, open(tgt_file, "r", encoding="utf-8") as f2:
            lines1 = f1.readlines()
            lines2 = f2.readlines()

        if lines1 != lines2:
            print(f"❌ Mismatch in {exp_file.name}:")
            diff = difflib.unified_diff(lines1, lines2, fromfile="expected", tofile="actual", lineterm="")
            for line in list(diff)[:15]:
                print(f"   {line}")
            all_match = False
        else:
            print(f"✔ Matched: {exp_file.name}")

    return all_match


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        exp = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("expected_outputs/ledgers")
        tgt = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("expected_outputs/ledgers")
        verify_against_expected(exp, tgt)
    else:
        export_expected_outputs()
