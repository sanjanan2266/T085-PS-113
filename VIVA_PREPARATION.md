# PS-113 · Viva Examination & Live Code Change Guide
**Format:** 15 minutes per student (including architectural Q&A and one live code modification)  
**Deliverable:** Week 3 & Final Evaluation

---

## Part 1: Core Viva Questions & Expected Responses

### Q1: Explain the Concession Stacking and 60% Cap Logic (BR-03, BR-12)
> **Interviewer:** *"Walk me through how your engine calculates concessions when a student qualifies for multiple categories and has siblings in the school."*
>
> **Your Response:**
> "Our engine evaluates concessions through a strict 5-stage mathematical pipeline:
> 1. **Category Concession:** We first check the student's category (`STAFF_WARD` = 50%, `MERIT` = 25%, `EWS` = 100% tuition + 50% other heads). By BR-03, only the single highest category applies.
> 2. **Sibling Ranking:** We rank all active, enrolled siblings in the group by Date of Birth (DOB ascending). The eldest pays full tuition (0%), the 2nd child receives 10%, and the 3rd and subsequent children receive 20% on tuition.
> 3. **Additive Stacking:** By BR-03, sibling concession stacks additively with the category concession:
>    $$\text{Raw Tuition Concession} = \text{Category}\% + \text{Sibling}\%$$
> 4. **Combined 60% Cap:** If the raw sum exceeds 60%, it is clamped to **60%** (for example, a Staff Ward who is also a 3rd child has $50\% + 20\% = 70\%$, which is capped at 60%). The only exception is standalone EWS, which receives 100% tuition.
> 5. **Plan Discount:** If the student is enrolled in the `ANNUAL` plan, the 3% discount applies **only to the post-concession net tuition**."

---

### Q2: Explain the Payment Application Waterfall (BR-07)
> **Interviewer:** *"When a partial or lump-sum payment is made, in what exact order is money applied?"*
>
> **Your Response:**
> "By BR-07, our payment processor applies funds across chronologically sorted instalments using a strict 5-stage waterfall:
> 1. **Late Fees:** Clears any accrued late fee penalties on the oldest instalment first.
> 2. **Tuition:** Clears tuition fees of that instalment.
> 3. **Other Heads:** Clears `development`, `lab`, `activity`, `exam`, and `admission` fees in that exact head order.
> 4. **Add-ons:** Clears `transport`, `hostel`, and `hostel_deposit`.
> 5. **Next Instalment:** Only when all heads of the current instalment are 100% paid does any remaining money waterfall into the next chronological instalment, repeating steps 1–4.
> 6. **Advance Credit:** Any unallocated surplus after all active instalments are satisfied is stored as `advance_credit`, which is credited on the ledger and automatically drawn down when future instalments become due."

---

### Q3: How Does Cheque Bounce Affect Dues and Late Fees? (BR-10)
> **Interviewer:** *"If a cheque was paid on April 15 and bounces on July 10, what happens to the ledger and late fees?"*
>
> **Your Response:**
> "1. A **Rs 500 bounce charge** is debited to the student's ledger.  
> 2. The original payment allocations are reversed, restoring the unpaid balances on the respective heads.  
> 3. Late fees are **retroactively recomputed as if the payment was never made**. Since July 10 is 91 days past the April 10 due date, the late fee accumulates at Rs 50/day and hits the maximum cap of **Rs 1,500.00**."

---

### Q4: How Does Sibling Re-Ranking Work Mid-Year? (BR-02, BR-09)
> **Interviewer:** *"If the eldest child in a sibling group withdraws in Term 1, how are the remaining siblings affected?"*
>
> **Your Response:**
> "By BR-02, sibling concessions re-rank dynamically **effective from the next instalment** (Term 2):
> * Term 1 instalments for the remaining siblings remain untouched (already billed/paid).
> * For Term 2 and Term 3, the 2nd child becomes the eldest active child and pays full tuition (0% sibling concession).
> * The 3rd child becomes the 2nd child and receives a 10% sibling concession (down from 20%)."

---

## Part 2: Preparing for the "Live Code Change"

During the viva, the mentor will ask you to make **one live code change** on the spot. Because our engine isolates all constants and business rules in [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py), you can execute any requested change in under 30 seconds!

### Live Change Cheat Sheet

| Mentor's Request | File to Edit | Exact Line / Change |
|---|---|---|
| *"Change the combined tuition concession cap from 60% to 70%"* | [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py#L38) | Change: `COMBINED_TUITION_CAP = Decimal("0.70")` |
| *"Increase late fee rate to Rs 75/day and cap to Rs 2,000"* | [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py#L51) | Change: `LATE_FEE_PER_DAY = Decimal("75.00")`<br>`LATE_FEE_MAX_CAP = Decimal("2000.00")` |
| *"Change the April grace period from 7 days to 10 days"* | [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py#L53) | Change: `APRIL_GRACE_DAYS = 10` |
| *"Increase the cheque bounce charge from Rs 500 to Rs 750"* | [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py#L60) | Change: `CHEQUE_BOUNCE_CHARGE = Decimal("750.00")` |
| *"Change the defaulter threshold from 60 days to 45 days"* | [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py#L54) | Change: `DEFAULTER_DAYS_THRESHOLD = 45` |
| *"Add an ALUMNI concession of 15% on tuition"* | [`engine/models.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/models.py#L35) & [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py#L31) | 1. In `models.py`: add `ALUMNI = "ALUMNI"` to `ConcessionCategory`<br>2. In `rules.py`: add `"ALUMNI": {"tuition": Decimal("0.15"), "other": Decimal("0.00")}` |
| *"Change the Annual plan tuition discount from 3% to 5%"* | [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py#L14) | Change: `ANNUAL_TUITION_DISCOUNT_PERCENT = Decimal("0.05")` |
| *"Change transport mid-month cutoff from 15th to 10th"* | [`engine/rules.py`](file:///c:/Users/Sanjana/OneDrive/Desktop/T085-PS-113/engine/rules.py#L41) | Change: `TRANSPORT_MID_MONTH_CUTOFF_DAY = 10` |

---

## Part 3: Verification After Making Live Code Change
After making any live change in front of your mentor, show that your test suite immediately validates the change:
```powershell
python run_tests.py
```
This demonstrates master-level test-driven engineering, clean code decoupling, and system robustness!
