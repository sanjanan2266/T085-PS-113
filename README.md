# PS-113 · School Fee Management Engine

**K-12 School Administration Fee Computation, Instalments, Concessions, Late Fees, and Reconciliations**  
*Week 2 – Core Flows Implementation*

---

## 🌟 Overview
PS-113 is a complete, command-file driven School Fee Management Engine built in Python 3.10+ using only standard library modules (zero external dependencies). It implements the complete financial lifecycle of a K-12 school:
- Grade-wise fee heads (`tuition`, `development`, `lab`, `activity`, `exam`, `admission`)
- Concessions with precedence rules (`STAFF_WARD`, `MERIT`, `EWS`, and sibling ranking with dynamic re-ranking)
- Flexible instalment schedules (`ANNUAL` with 3% discount, `TERM` 40/30/30, `MONTHLY` 10 instalments with January rounding absorption)
- Add-ons with route/room pricing (`transport` zones A/B/C, `hostel` shared/single with 1-month security deposit)
- Late fee engine (Rs 50/day, April 7-day grace, Rs 1,500 cap per instalment, defaulters > 60 days with `WITHHELD` hall tickets)
- Payment reconciliation waterfall (late fee $\rightarrow$ tuition $\rightarrow$ other heads $\rightarrow$ add-ons $\rightarrow$ next instalment $\rightarrow$ advance credit)
- Cheque bounce handling (Rs 500 charge, retroactive late fee recomputations)
- Mid-year admissions & withdrawals with Transfer Certificate (TC) clearance checks
- Official reports: Fee Demand Notices, Breakdown Schedules, Running Ledgers, and Defaulter Lists

---

## 📁 Repository Directory Structure

```
T085-PS-113/
├── DESIGN.md                     # System design document with BR-01 to BR-12 registered
├── README.md                     # Project overview, usage instructions, and test guide
├── requirements.txt              # Zero external dependencies required (standard library)
├── run_tests.py                  # Test runner executing all 46 unit and integration tests
├── main.py                       # Main CLI entrypoint
│
├── engine/                       # Core engine modules
│   ├── models.py                 # Dataclasses, Enums, and financial models
│   ├── rules.py                  # Registered business rules BR-01 to BR-12 and constants
│   ├── fee_calculator.py         # Concession stacking, 60% tuition cap, 3% annual discount
│   ├── instalment_scheduler.py   # ANNUAL, TERM, MONTHLY schedules with rounding absorption
│   ├── addon_manager.py          # Transport pro-rating (15th cutoff), hostel deposit & mess
│   ├── late_fee.py               # Late fee (Rs 50/day, Rs 1500 cap), defaulters (>60 days)
│   ├── payment_waterfall.py      # Strict waterfall allocation, advance credit, cheque bounce
│   ├── admission_manager.py      # Mid-year admission, pro-rating, non-pro-rated development fee
│   ├── withdrawal_manager.py     # 30-day notice rule, TC clearance, sibling re-ranking
│   ├── fee_revision.py           # Revision <= 10% on future instalments, > 10% Board approval
│   ├── scholarship_manager.py    # Stretch goal: Merit-based scholarship fund allocation
│   ├── reports.py                # Demand notices, schedules, ledgers, defaulter lists, receipts
│   ├── command_processor.py      # Command file parser and orchestrator
│   └── cli.py                    # Command-line interface and interactive shell
│
├── sample_data/                  # Full realistic dataset
│   ├── fee_structures.csv        # Fee cards for 12 grades
│   ├── addon_rates.csv           # Transport zones & hostel rates
│   ├── students.csv              # 60 enrolled students with 8 sibling groups
│   ├── addons.csv                # 30 transport and hostel subscription events
│   ├── payments.csv              # 350 payment records including 6 cheque bounces
│   └── commands.txt              # Master command file executing complete school workflow
│
├── scripts/
│   └── generate_sample_data.py   # Deterministic sample dataset generator
│
└── tests/                        # 46 comprehensive unit & integration tests
    ├── test_concessions.py       # BR-02, BR-03, BR-12: Stacking, 60% cap, staff ward + 3rd sibling
    ├── test_instalments.py       # BR-01: ANNUAL 3%, TERM 40/30/30, MONTHLY rounding residue
    ├── test_addons.py            # BR-04, BR-05: Transport 15th/16th cutoff, hostel deposit
    ├── test_late_fees.py         # BR-06: April 7-day grace, Rs 1500 cap, defaulter > 60 days
    ├── test_waterfall.py         # BR-07: Waterfall allocation order, advance credit
    ├── test_midyear_admission.py # BR-08: Admitted on 15th vs 16th, dev fee full, Rs 10000 flat
    ├── test_withdrawal.py        # BR-09: 30-day notice, TC zero dues, sibling re-ranking
    ├── test_bounce.py            # BR-10: Rs 500 charge, reversal, retroactive late fee past cap
    ├── test_fee_revision.py      # BR-11: <=10% future instalments, >10% BOARD_APPROVED check
    ├── test_sample_dataset.py    # End-to-end integration test with full sample data
    └── test_edge_cases.py        # Dedicated tests for all 8 explicit edge cases
```

---

## 🚀 Quickstart & Usage

### 1. Run All Tests
Execute the entire test suite covering all 12 business rules and 8 edge cases:
```bash
python run_tests.py
```
*Expected Output:*
```text
======================================================================
TESTS RUN: 46
SUCCESSES: 46
FAILURES : 0
ERRORS   : 0
======================================================================
```

### 2. Run the Sample Dataset Workflow
Execute the end-to-end command file containing 12 grades, 60 students, 8 sibling groups, 30 add-on subscriptions, 350 payments with 6 bounces, mid-year withdrawals with sibling re-ranking, and sample outputs:
```bash
python main.py sample_data/commands.txt
```
or:
```bash
python main.py --run-sample
```

### 3. Run Interactive Shell
Launch the interactive command prompt:
```bash
python main.py --interactive
```
Example commands in the shell:
```text
fee-engine> PRINT_DEMAND STU003 2026-04-10
fee-engine> PRINT_SCHEDULE STU003
fee-engine> PRINT_LEDGER STU003 2026-10-15
fee-engine> PRINT_DEFAULTERS 2026-10-15
```

---

## 📜 Command File Syntax Reference

| Command | Arguments | Description |
|---|---|---|
| `LOAD_FEE_STRUCTURE` | `<grade> <tuition> <dev> <lab> <act> <exam>` | Loads individual grade fee card. |
| `LOAD_FEE_FILE` | `<path_to_csv>` | Batch loads fee cards from CSV. |
| `ENROL_STUDENT` | `<id> <name> <grade> <sec> <dob> <adm_date> <plan> [category] [prev_pct] [sibling_grp] [campus]` | Enrols student and generates schedule. |
| `LOAD_STUDENTS_FILE` | `<path_to_csv>` | Batch enrols students from CSV. |
| `CHANGE_PLAN` | `<student_id> <new_plan> <request_date>` | Changes plan (only allowed before 10 Apr). |
| `ADD_TRANSPORT` | `<student_id> <zone> <start_date>` | Subscribes to transport with pro-rating. |
| `REMOVE_TRANSPORT` | `<student_id> <end_date>` | Terminates transport subscription. |
| `ADD_HOSTEL` | `<student_id> <room_type> <start_date>` | Allocates hostel room & 1-month deposit. |
| `RECORD_PAYMENT` | `<pmt_id> <student_id> <amount> <date> <mode> [ref]` | Applies payment via waterfall algorithm. |
| `LOAD_PAYMENTS_FILE` | `<path_to_csv>` | Batch records payments from CSV. |
| `BOUNCE_PAYMENT` | `<pmt_id> <bounce_date>` | Reverses payment, debits Rs 500, recomputes late fees. |
| `WITHDRAW_STUDENT` | `<student_id> <withdrawal_date> <notice_date> [damages]` | Processes withdrawal, refunds unstarted terms tuition, re-ranks siblings. |
| `REVISE_FEE` | `<grade> <head> <percent> <date> [board_approved]` | Applies fee revision to future instalments. |
| `ALLOCATE_SCHOLARSHIP` | `<total_fund>` | Stretch goal: Allocates merit scholarship fund pool. |
| `PRINT_DEMAND` | `<student_id> [as_of_date]` | Prints Fee Demand Notice. |
| `PRINT_SCHEDULE` | `<student_id>` | Prints instalment schedule breakdown table. |
| `PRINT_LEDGER` | `<student_id> [as_of_date]` | Prints full student account statement. |
| `PRINT_DEFAULTERS` | `<as_of_date>` | Prints defaulter list with `WITHHELD` hall tickets. |

---

## 🎯 Verification of All 8 Explicit Edge Cases

1. **Staff ward who is also a 3rd sibling:**  
   Staff ward (50%) + 3rd sibling (20%) = 70% raw $\rightarrow$ capped strictly at **60%** tuition concession. Verified in `test_edge_cases.py` (`test_edge_case_1_staff_ward_third_sibling_combined_cap`).
2. **Transport joined on the 15th:**  
   Joining on 15 April bills the full month (100% of zone rate). Joining on 16 April bills half month (50%). Verified in `test_addons.py` (`test_edge_case_transport_joined_on_15th_bills_full_month`).
3. **Payment on the 7th day of grace for April:**  
   April due date 10 Apr + 7 days grace = 17 Apr. Payment on 17 Apr incurs **Rs 0** late fee. Verified in `test_late_fees.py` (`test_edge_case_payment_on_7th_day_of_grace_for_april_zero_late_fee`).
4. **Eldest sibling withdrawing mid-term with re-ranking:**  
   When eldest sibling withdraws in Term 1, 2nd child becomes eldest (0%) and 3rd becomes 2nd (10%) from Term 2 onwards. Verified in `test_withdrawal.py` (`test_edge_case_eldest_sibling_withdrawing_re_ranks_remaining_from_next_instalment`).
5. **Bounced cheque for an instalment already past the late-fee cap:**  
   Retroactively recomputes late fee hitting the max cap of **Rs 1,500.00**, plus Rs 500 bounce charge debited. Verified in `test_bounce.py` (`test_edge_case_bounced_cheque_for_instalment_already_past_late_fee_cap`).
6. **Mid-year admission on the 16th:**  
   Joining on 16 August excludes August; only 5 months remaining (50% pro-rating). Development fee is never pro-rated (100%), and flat Rs 10,000 admission fee added. Verified in `test_midyear_admission.py` (`test_edge_case_admission_on_16th_does_not_count_month`).
7. **Withdrawal notice given exactly 30 days before term start:**  
   Notice on 2 July for Term 2 starting 1 Aug (exactly 30 days) qualifies for full Term 2 unstarted tuition refund. Verified in `test_withdrawal.py` (`test_edge_case_withdrawal_notice_given_exactly_30_days_before_term_start`).
8. **Monthly plan rounding residue on the January instalment:**  
   Odd amounts split across 10 instalments: first 9 get equal quotient, 10th (January) absorbs cent residue. Verified in `test_instalments.py` (`test_monthly_plan_rounding_residue_absorbed_in_january`).

---

## 🎤 Viva Presentation Checklist
In your viva examination, be prepared to walk through:
- **Concession Stacking & Cap:** Category (highest) $\rightarrow$ Sibling rank (DOB) $\rightarrow$ Additive sum $\rightarrow$ Min(sum, 60%) $\rightarrow$ 3% Annual discount on post-concession tuition.
- **Payment Application Waterfall:** Late fees first $\rightarrow$ Oldest instalment tuition $\rightarrow$ Other heads (`dev`, `lab`, `act`, `exam`, `adm`) $\rightarrow$ Add-ons (`transport`, `hostel`) $\rightarrow$ Next instalment $\rightarrow$ Advance credit.
- **Cheque Bounce & Defaulter Impact:** Reversal of allocations, Rs 500 penalty, retroactive recalculation of late fees, and overdue $> 60$ days flagging exam hall tickets as `WITHHELD`.


---

## Week 3 – Full Business Rules & Testing

Week 3 implementation, business rule validation, edge-case tests, and viva preparation.

[View Week 3 Submission](https://github.com/sanjanan2266/T085-PS-113/tree/week3-submission)
