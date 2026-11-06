# PS-113 · Architectural & Business Rule Decision Log
**Project:** School Fee Management Engine  
**Milestone:** Week 3 – Full Rules  
*Format: Log every decision (Date, ID, Decision, Context, and Rationale) for viva defense.*

---

| Date | Decision ID | Decision | Context / Problem | Rationale |
|:---:|:---:|---|---|---|
| **2026-10-18** | **DEC-01** | Use Python Standard Library (`Decimal`, `dataclasses`, `enum`) without external runtime dependencies | Floating point inaccuracies in currency math; portability across evaluation machines | `decimal.Decimal` with `ROUND_HALF_UP` eliminates IEEE 754 floating point rounding drift down to the paisa. |
| **2026-10-20** | **DEC-02** | Enforce BR-12 canonical evaluation pipeline order | Precedence order when applying category concessions, sibling concessions, caps, and plan discounts | Guarantees deterministic, reproducible annual fee computation: Category (highest) $\rightarrow$ Sibling stacking $\rightarrow$ 60% Cap $\rightarrow$ 3% Annual discount. |
| **2026-10-22** | **DEC-03** | Distinguish EWS 100% standalone concession from the 60% stacking cap | BR-03 specifies EWS receives 100% tuition + 50% other heads, while stacking has a 60% cap | A standalone EWS student receives 100% tuition concession. The 60% cap strictly bounds combined category + sibling stacking (e.g. Staff ward 50% + 3rd child 20%). |
| **2026-10-24** | **DEC-04** | Last instalment absorbs rounding residue | Splitting annual fees across 10 monthly instalments or 3 term instalments creates non-divisible fractional paise | Conserves total fee to the exact cent without creating or losing revenue; January instalment absorbs residue. |
| **2026-10-26** | **DEC-05** | Restrict plan changes strictly before the first due date (10 April) | BR-01 allows plan change only before the first due date | Prevents retroactive recalculation of already invoiced or overdue instalments. |
| **2026-10-28** | **DEC-06** | Transport & Admission 15th cutoff interpretation | BR-04 & BR-08 define mid-month joining rules | Joining on or before the 15th bills the full month (or counts the month for admission); joining on or after the 16th bills half month (or excludes month). |
| **2026-10-30** | **DEC-07** | Non-pro-rating of Development Fee | BR-08 specifies development fee is never pro-rated for mid-year admissions | Development fee covers full-year campus infrastructure and capital expenditure, regardless of admission date. |
| **2026-11-01** | **DEC-08** | Dynamic sibling re-ranking effective strictly from the next instalment | Eldest sibling withdraws mid-academic year | Preserves already closed/paid historical instalments while properly adjusting upcoming future term dues for remaining siblings. |
| **2026-11-02** | **DEC-09** | Strict 5-stage payment waterfall order | BR-07 defines payment allocation hierarchy | Late fees $\rightarrow$ Tuition $\rightarrow$ Other heads $\rightarrow$ Add-ons $\rightarrow$ Next instalment. Prevents fee evasion by clearing penalties first. |
| **2026-11-03** | **DEC-10** | Cheque bounce retroactive late fee recomputation | BR-10 cheque bounce penalty and reversal | Payment is treated as void effective from original payment date; late fee accumulates continuously up to the Rs 1,500 cap + Rs 500 charge. |
| **2026-11-04** | **DEC-11** | Defaulter threshold strict inequality (`days_overdue > 60`) | BR-06 defaulter policy and hall ticket withholding | Exactly 60 days overdue is still in grace; day 61 marks the student as DEFAULTER with hall ticket WITHHELD. |
| **2026-11-05** | **DEC-12** | Transfer Certificate (TC) gatekeeper condition | BR-09 requires TC issued only when dues are zero | TC status is blocked as long as any outstanding tuition, fee head, late fee, or bounce penalty is greater than Rs 0.00. |
| **2026-11-06** | **DEC-13** | Mid-year fee revision threshold split ($\le 10\%$ vs $> 10\%$) | BR-11 fee revision approval policy | $\le 10\%$ updates upcoming future instalments only; $> 10\%$ without board approval is rejected, and with approval applies only next academic year. |
