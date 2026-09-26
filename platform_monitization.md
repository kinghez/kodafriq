# Platform Monetization & Payment Architecture
**Kodafriq Data Management Limited**  
*Document Version: 1.0.0 | Status: Architecture & Strategy Specification*

---

## 1. Executive Vision: Transactional Healthcare Talent Marketplace

This is the single most transformative business feature for **Kodafriq**. Moving from a talent directory to a full **transactional healthcare talent marketplace** (similar to the Upwork, Deel, or Toptal models) positions Kodafriq to earn recurring, scalable revenue every single week a candidate is actively working.

Kodafriq connects global healthcare employers (hospitals, physician practices, billing agencies, health systems, and health-tech enterprises across North America, Europe, and the Middle East) with pre-vetted, highly trained healthcare professionals across Africa. Instead of allowing employers to hire candidates and take them off-platform, Kodafriq manages the entire engagement lifecycle: **Contracts, Timesheet Tracking, Quality Auditing, Invoicing, Escrow, and Automated Cross-Border Payouts**.

---

## 2. Comprehensive Healthcare Talent Scope

Kodafriq is **not** limited to medical billing. Kodafriq represents a comprehensive, multi-disciplinary healthcare workforce covering high-demand global remote and hybrid specialties:

| Specialty Domain | Typical Roles & Skills | Typical Engagement Model |
| :--- | :--- | :--- |
| **Medical Billing & Revenue Cycle Management (RCM)** | Charge entry, claims submission, denial management, accounts receivable (A/R) follow-up, payment posting. | Hourly / Weekly or Monthly Retainer |
| **Medical Coding & Auditing** | Inpatient (ICD-10-CM/PCS), Outpatient (CPT/HCPCS), Risk Adjustment (HCC), Emergency Department (ED) coding, Clinical Coding Audits. | Hourly or Per-Chart Milestones |
| **Clinical Documentation Improvement (CDI)** | Clinical chart review, physician query management, DRG optimization, medical necessity validation. | Hourly / Dedicated Retainer |
| **Health Information Management (HIM)** | Release of Information (ROI), electronic health record (EHR) data management, compliance auditing, HIPAA data stewardship. | Monthly Retainer / Full-Time |
| **Telehealth & Clinical Support** | Virtual patient intake, triage coordination, appointment scheduling, prior authorization specialists. | Hourly / Shift-Based |
| **Medical Virtual Assistance (MVA)** | Provider inbox management, prescription refill coordination, lab order tracking, patient recall. | Hourly / Dedicated Weekly |
| **Healthcare Data & Analytics** | Clinical registry data abstraction, quality measure reporting (MIPS/HEDIS), healthcare analytics. | Milestone / Project-Based |

---

## 3. The Core Economics & Calculation Model

The monetization model guarantees that **candidates receive 100% of their stated hourly or project rate**, while Kodafriq charges a dynamic, transparent service markup to the employer.

### Calculation Breakdown (Example: $7.00/hr Candidate Rate)
- **Candidate Stated Rate ($R$)**: **$7.00 / hour** (Net earnings guaranteed to talent).
- **Kodafriq Service Markup ($M$)**: **10%** ($0.70 / hour), dynamically managed in Django Admin via `PlatformFeeConfig`.
- **Employer Total Billed ($T$)**: **$7.70 / hour**.

```
[ Employer Pays: $7.70/hr ]
         │
         ├──► $7.00/hr (90.9%) ──► Talent Earnings (Bank / Local Mobile Money)
         └──► $0.70/hr  (9.1%) ──► Kodafriq Platform Revenue (Retained Fee)
```

### Gateway Processing Fees (Protecting Kodafriq's Margin)
Payment gateways (e.g., Flutterwave) charge a card/interchange processing fee (typically **2.9% + $0.30** for international cards, or **1.4%** for local transfers). To ensure Kodafriq’s 10% platform fee is preserved:
- **Transparent Payment Fee Model (Upwork Standard)**: The invoice explicitly details:
  1. Professional Healthcare Services ($7.00/hr)
  2. Kodafriq Talent Verification & Platform Fee ($0.70/hr)
  3. Payment Processing Fee (Passed through or standardized at 2.9%)
- This guarantees Kodafriq retains its exact net 10% revenue margin on every billable hour.

---

## 4. The Dual Disbursement Engine: Option A vs. Option B

To accommodate both long-term dedicated healthcare staff and project-based short-term engagements, Kodafriq uses a **Hybrid Dual Disbursement Model**:

```
                       ┌───────────────────────────────┐
                       │   Employer Invoice Payment    │
                       └───────────────┬───────────────┘
                                       │
                      Is this Long-Term or Short-Term?
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌───────────────────────────────────────┐   ┌───────────────────────────────────────┐
│     OPTION A: Subaccount Split        │   │    OPTION B: Platform Escrow Pool     │
│   (Long-Term / Weekly Full Hire)      │   │    (Short-Term / Bulk Milestones)     │
├───────────────────────────────────────┤   ├───────────────────────────────────────┤
│ • Real-time Flutterwave split         │   │ • 100% funded upfront into Escrow     │
│ • 10% fee directly to Kodafriq Main   │   │ • Kodafriq holds funds safely         │
│ • 90% straight to Candidate Subaccount│   │ • Talent delivers chart batch/project │
│ • Zero manual payout friction         │   │ • Employer reviews & approves work    │
│ • Ideal for recurring weekly staff    │   │ • Kodafriq triggers payout transfer   │
└───────────────────────────────────────┘   └───────────────────────────────────────┘
```

### Option A: Direct Subaccount Split (For Ongoing Full-Time & Long-Term Hires)
1. **Candidate Onboarding**: When a talent is hired, their verified bank details (account number, bank code, BVN/identity verification) are registered with Flutterwave via the Subaccount API (`/v3/subaccounts`).
2. **Weekly Execution**: When the employer's weekly invoice is debited:
   - Kodafriq passes `subaccounts: [{"id": candidate_subaccount_id, "transaction_charge_type": "flat", "transaction_charge": 7.00}]`.
   - Flutterwave automatically splits the settlement at the gateway level: Kodafriq's bank receives the 10% platform fee, and the candidate's bank receives the 90% net earnings.
3. **Best For**: Full-time remote coders, dedicated billers, and long-term assistants working standard weekly hours.

### Option B: Platform Escrow & Milestone Payout (For Short Contracts & Bulk Work)
1. **Upfront Escrow Deposit**: For fixed deliverables (e.g., coding 500 backlogged patient charts or conducting a billing audit), the employer pays the full contract amount into Kodafriq's Escrow account upfront before work begins.
2. **Delivery & Inspection Window**:
   - The candidate submits the deliverable or logs the completed milestone batch.
   - The employer receives an automatic notification and has a 3 to 5 business day inspection window.
3. **Disbursement Release**:
   - Upon employer sign-off (or automatic acceptance after the review window closes without dispute), Kodafriq releases the funds:
     - 10% is moved to Kodafriq's earned revenue ledger.
     - 90% is disbursed to the candidate's bank account via Flutterwave Transfer API (`/v3/transfers`).
4. **Dispute Protection**: If deliverables fail quality standards, Kodafriq’s clinical mediation team inspects the work and can issue full or partial refunds without chasing funds from the candidate.

---

## 5. Weekly Billing Lifecycle (The Upwork-Style Engine)

The platform operates on a synchronized **Weekly Timesheet & Billing Cycle**:

```
[ MON - SUN ] ──► Talent logs daily hours & notes (Charts coded, claims resolved)
[ SUN 23:59 ] ──► Timesheet locks automatically; Draft Weekly Invoice generated
[ MON 09:00 ] ──► Employer notified: 3-day Review Window opens
[ MON - WED ] ──► Employer reviews hours, asks questions, or approves
[ THU 00:01 ] ──► Invoice charged to Employer's payment method (Card / Direct Debit)
[ FRI 12:00 ] ──► Funds disbursed to Talent (Option A split or Option B transfer)
```

1. **Daily Work Logging**: Talents log their daily hours directly on their dashboard with mandatory work summaries (e.g., *"Coded 42 outpatient records, resolved 8 prior authorization denials"*).
2. **Weekly Timesheet Lock**: Every Sunday at midnight (UTC), the week's timesheet automatically locks against further edits.
3. **Employer Review Window (Mon–Wed)**: Employers can inspect daily logs. If an employer takes no action by Wednesday midnight, the timesheet is **auto-approved**.
4. **Automated Thursday Processing**: Kodafriq initiates payment collection via Flutterwave using the employer's pre-authorized card or billing profile.
5. **Friday Payout Settlement**: Candidates receive their weekly funds every Friday.

---

## 6. Global Multi-Currency Support & Cross-Border Settlement

Kodafriq serves international healthcare clients and pan-African medical talent. The billing engine supports multi-currency conversion:

### Employer Billing Currencies
Employers are invoiced and charged in their domestic business currency:
- **USD ($)** — United States, Middle East, International
- **GBP (£)** — United Kingdom & NHS contractors
- **EUR (€)** — European healthcare providers
- **CAD (C$)** — Canadian clinical practices
- **AUD (A$)** — Australian healthcare systems

### Candidate Payout Currencies
Candidates receive payouts in their local currency without exorbitant wire transfer fees:
- **NGN (₦)** — Nigeria (Direct NIP Bank Transfer)
- **KES (KSh)** — Kenya (M-Pesa & Bank Transfer)
- **GHS (GH₵)** — Ghana (Mobile Money & Bank Transfer)
- **ZAR (R)** — South Africa (EFT / Bank Transfer)
- **RWF / UGX** — Rwanda, Uganda, and regional clinical hubs
- **USD ($)** — Domiciliary accounts for senior consultants

### FX Rate Handling
- Invoices are pegged to the contract base currency (typically USD).
- Flutterwave provides real-time spot FX rates at transaction time, guaranteeing candidates receive the exact local equivalent without exchange risk falling on Kodafriq.

---

## 7. Preventing Disintermediation ("Don't Take Talent Off-Platform")

To ensure clients and candidates do not circumvent the platform after meeting:

### 1. High-Value Platform Incentives (Why They Want to Stay)
- **For Candidates**:
  - **Guaranteed Payment**: No chasing overseas clients for unpaid invoices; payment is secured in escrow or charged automatically.
  - **Kodafriq Verified Score & Career Growth**: Every billable hour logged on Kodafriq increases the candidate’s platform rank, verified badges, and unlocks eligibility for higher-tier rates.
  - **Continuing Education**: Active platform workers get ongoing access to specialized coding updates (ICD-11, annual CPT revisions, HIPAA re-certification).
- **For Employers**:
  - **Instant Replacement Guarantee**: If a coder falls ill or underperforms, Kodafriq provides a replacement candidate within 24–48 hours with zero hiring fees.
  - **HIPAA & Compliance Shield**: Kodafriq maintains identity verification, clean background checks, and audit trails required by healthcare regulators.
  - **Consolidated Accounting**: One monthly/weekly tax-compliant invoice covering multiple contractors, eliminating international 1099/W-8BEN contractor tax headaches.

### 2. Platform Safeguards
- **In-App Messaging & Contact Masking**: Before a formal contract is funded, communication is restricted to Kodafriq’s secure portal. Direct phone numbers and email addresses are automatically masked.
- **Contractual Non-Circumvention (MSA)**: Both parties sign an enforceable Master Services Agreement upon registration with a **24-month non-circumvention clause** and an official platform **Buyout Fee** (e.g., $3,500 or 15% of annual compensation) if an employer wishes to hire a candidate directly onto their local payroll.

---

## 8. Technical Architecture in Kodafriq

To ensure modularity and high test coverage, two dedicated apps will be added to the Django backend:

```
apps/
├── contracts/               # Engagement agreements, timesheets & milestones
│   ├── models.py            # Contract, Timesheet, TimesheetEntry, Milestone, DisputeCase
│   ├── views.py             # Contract creation, Timesheet logger, Approval interface
│   └── urls.py
└── billing/                 # Invoicing, Flutterwave, Escrow & Disbursements
    ├── models.py            # Invoice, PaymentTransaction, CandidatePayoutAccount, PlatformFeeConfig
    ├── services/
    │   ├── flutterwave.py   # Flutterwave API SDK (Subaccounts, Charges, Transfers)
    │   ├── invoicing.py     # Automated weekly invoice generator
    │   └── fx_converter.py  # Multi-currency rate converter
    ├── webhooks.py          # Secure Flutterwave webhook listener (Signature Verification)
    └── views.py             # Checkout page, Payout management, Financial analytics
```

### Core Database Entities

```
+-----------------------------------+
|             Contract              |
+-----------------------------------+
| - id: UUID                        |
| - employer: EmployerProfile       |
| - candidate: CandidateProfile     |
| - job: JobPost                    |
| - contract_type: HOURLY/MILESTONE |
| - disbursement_mode: OPTION_A/B   |
| - rate_per_hour: Decimal          |
| - kodafriq_fee_percent: Decimal   |  (e.g., 10.00%)
| - weekly_hour_limit: Integer      |  (e.g., 40 hrs)
| - status: PENDING/ACTIVE/COMPLETED|
+-----------------+-----------------+
                  | 1:N
                  ▼
+-----------------------------------+       +-----------------------------------+
|             Timesheet             |       |              Invoice              |
+-----------------------------------+       +-----------------------------------+
| - contract: Contract              |       | - contract: Contract              |
| - week_start_date: Date           | 1:1   | - timesheet: Timesheet (Optional) |
| - total_hours: Decimal            |◄─────►| - talent_earnings: Decimal        |
| - status: SUBMITTED/APPROVED/PAID |       | - kodafriq_fee: Decimal           |
+-----------------+-----------------+       | - processing_fee: Decimal         |
                  | 1:N                     | - total_amount: Decimal           |
                  ▼                         | - currency: USD/EUR/GBP           |
+-----------------------------------+       | - status: UNPAID/PAID/DISBURSED   |
|          TimesheetEntry           |       | - flutterwave_tx_ref: String      |
+-----------------------------------+       +-----------------+-----------------+
| - date: Date                      |                         |
| - hours_worked: Decimal           |                         ▼
| - charts_coded_count: Integer     |       +-----------------------------------+
| - work_description: Text          |       |        PaymentTransaction         |
+-----------------------------------+       +-----------------------------------+
                                            | - flw_transaction_id: String      |
                                            | - amount: Decimal                 |
                                            | - webhook_payload: JSON           |
                                            | - verified: Boolean               |
                                            +-----------------------------------+
```

---

## 9. Strategic Go-To-Market Decision: Deploy Now vs. Deploy With Payments

### The Question:
> *"Should I deploy the platform now the way it is so users can start registering, or should I complete the payout/monetization first before deploying everything together?"*

### Recommendation: **DEPLOY NOW (Soft Launch / Phase 1: Talent Acquisition)**

#### Why Deploying Now is the Winning Strategy:
1. **Solving the Marketplace "Cold Start" Problem**:
   - A marketplace cannot function without high-quality inventory. If an employer registers tomorrow and sees an empty talent pool, they leave and never return.
   - Deploying now allows you to immediately begin onboarding clinical coders, billers, and healthcare talents across Africa. Candidates can build their profiles, upload resumes, verify certificates, and showcase their talents.
2. **De-risking Live User Experience**:
   - Live candidates will test authentication, profile completeness, mobile responsiveness, and resume viewing on real-world mobile devices and varying internet connections.
   - Any bugs can be polished with real candidate feedback before financial transactions are turned on.
3. **Parallel Engineering Velocity**:
   - While the marketing/recruitment team runs talent acquisition, the engineering team can build and test `apps/contracts/` and `apps/billing/` in an isolated, secure staging environment with Flutterwave Sandbox credentials.
4. **Phased Rollout Timeline**:
   - **Phase 1 (Immediate / This Week)**: Live deployment of existing platform. Open registration for healthcare talents and early-access employers.
   - **Phase 2 (Next 2–3 Weeks)**: Ship `contracts` and `billing` modules. Turn on Option A & Option B payment flows when the first wave of verified candidates is ready for hire.

---

## 10. Summary & Next Actions

| Step | Objective | Timeline |
| :--- | :--- | :--- |
| **1. Deploy Current Platform** | Push current mobile-optimized platform to production. Open talent registration. | Immediate |
| **2. Register Flutterwave Merchant Account** | Set up business credentials, obtain API keys (Secret Key, Public Key, Encryption Key, Webhook Secret Hash). | Days 1–2 |
| **3. Implement `apps/contracts`** | Build `Contract`, `Timesheet`, and `Milestone` models + UI dashboards. | Week 1 |
| **4. Implement `apps/billing` & Webhooks** | Build Invoice generation, Option A (Split) & Option B (Escrow/Transfer) handlers. | Week 2 |
| **5. End-to-End Sandbox Simulation** | Test full loop: Offer -> Contract -> Timesheet -> Invoice -> Flutterwave Card Pay -> Split/Transfer. | Week 3 |
| **6. Full Commercial Launch** | Enable payment gateways on production. | Week 3 |
