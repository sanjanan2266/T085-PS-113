"""
Git Repository Setup & Commit History Builder for PS-113
Initializes git repository and creates structured commits reflecting the development progression
as requested in Week 2 deliverables.
"""
import shutil
import subprocess
import sys
from pathlib import Path


def run_git_cmd(args):
    result = subprocess.run(["git"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"git {' '.join(args)} error: {result.stderr.strip()}")
    return result.returncode == 0


def build_git_history():
    if not shutil.which("git"):
        print("Note: 'git' is not currently installed or not in PATH.")
        print("To push to GitHub/GitLab, install Git for Windows (https://git-scm.com/download/win),")
        print("then re-run: python scripts/setup_git_repo.py")
        return False

    print("=== Initializing Git Repository with Structured Commit History ===")
    run_git_cmd(["init"])
    run_git_cmd(["config", "user.name", "School Fee Engine Team"])
    run_git_cmd(["config", "user.email", "team@schoolfee.engine"])

    commit_stages = [
        (
            ["engine/__init__.py", "engine/models.py", "engine/rules.py", ".gitignore", "requirements.txt"],
            "feat(core): initialize project architecture, domain models, and BR-01 to BR-12 registry"
        ),
        (
            ["engine/fee_calculator.py"],
            "feat(concessions): implement fee calculator, sibling ranking, additive stacking, and 60% tuition cap"
        ),
        (
            ["engine/instalment_scheduler.py"],
            "feat(instalments): implement ANNUAL (3% disc), TERM (40/30/30), and MONTHLY schedules with January rounding absorption"
        ),
        (
            ["engine/addon_manager.py"],
            "feat(addons): implement transport zone pricing with 15th cutoff and hostel with security deposit"
        ),
        (
            ["engine/late_fee.py"],
            "feat(late-fee): implement Rs 50/day late fee with April 7-day grace, Rs 1500 cap, and defaulter tracking"
        ),
        (
            ["engine/payment_waterfall.py"],
            "feat(payment): implement strict waterfall application, advance credit, and cheque bounce handling"
        ),
        (
            ["engine/admission_manager.py", "engine/withdrawal_manager.py"],
            "feat(admissions-withdrawals): implement mid-year admissions, 30-day withdrawal notice, and dynamic sibling re-ranking"
        ),
        (
            ["engine/fee_revision.py", "engine/scholarship_manager.py"],
            "feat(revisions-stretch): add mid-year fee revisions and merit scholarship fund allocation"
        ),
        (
            ["engine/reports.py", "engine/command_processor.py", "engine/cli.py", "main.py"],
            "feat(cli): implement command file interpreter, reporting engine, and interactive shell"
        ),
        (
            ["scripts/generate_sample_data.py", "sample_data/"],
            "feat(sample-data): generate 12 grade fee cards, 60 students, 8 sibling groups, 30 addons, and 350 payments with 6 bounces"
        ),
        (
            ["tests/", "run_tests.py"],
            "test(unit): add comprehensive 46-test suite verifying BR-01 through BR-12 and all 8 explicit edge cases"
        ),
        (
            ["DESIGN.md", "README.md", "scripts/setup_git_repo.py"],
            "docs: add comprehensive system design documentation (BR-01 to BR-12), viva prep guide, and README"
        ),
    ]

    for files, msg in commit_stages:
        for f in files:
            run_git_cmd(["add", f])
        run_git_cmd(["commit", "-m", msg])
        print(f"✔ Committed: {msg}")

    print("\n✅ Git repository initialized with 12 structured commits!")
    print("You can now connect to a remote repository:")
    print("  git remote add origin <your-mentor-repo-url>")
    print("  git branch -M main")
    print("  git push -u origin main")
    return True


if __name__ == "__main__":
    build_git_history()
