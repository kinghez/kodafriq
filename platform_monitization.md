# Platform Monetization & Payment Architecture
**Kodafriq Data Management Limited**  
*Document Version: 1.1.0 | Status: Architecture & Strategy Specification (Earnings Ledger Model)*

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
Payment gateways (e.g., Flutterwave & Paystack) charge interchange/processing fees. To ensure Kodafriq's 10% platform fee is preserved:
- **Transparent Payment Fee Model (Upwork Standard)**: The invoice explicitly details:
  1. Professional Healthcare Services ($7.00/hr)
  2. Kodafriq Talent Verification & Platform Fee ($0.70/hr)
  3. Payment Processing Fee (Passed through or standardized at 2.9%)
- This guarantees Kodafriq retains its exact net 10% revenue margin on every billable hour.

---

## 4. The Earnings Ledger Architecture (Business State vs. Custodial Wallet)

This is a **far cleaner, regulatory-safe, and technically superior architecture**.

By building an **Earnings Ledger** rather than a financial wallet, Kodafriq avoids acting as a bank or holding custodial funds. Django does not hold candidate deposits—it acts as the **source of truth for business transaction states, timesheets, and accounting audit trails**, while the licensed payment infrastructure (**Paystack Ghana** & **Flutterwave**) handles the actual movement of money.

### 4.1 The Candidate's Experience: "Kodafriq Earnings" Ledger

On the candidate's dashboard, they see a transparent, executive summary of their earnings state:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        KODAFRIQ EARNINGS                               │
├───────────────────┬───────────────────┬────────────────────────────────┤
│    AVAILABLE      │      PENDING      │          PAID TO DATE          │
│     $1,240        │       $350        │             $4,820             │
│ (Queued for next  │ (Hours logged or  │ (Total lifetime disbursements  │
│      payout)      │   under review)   │    sent to your MoMo/Bank)     │
├───────────────────┴───────────────────┴────────────────────────────────┤
│  Next Payout: $1,240 scheduled for Friday, Oct 3, 2026                 │
│  Destination: MTN Mobile Money (+233 24 ••• ••45)                      │
└────────────────────────────────────────────────────────────────────────┘
```

#### What each state represents in the database:
1. **`Pending` ($350)**: Timesheet hours logged by the candidate that are either in progress, awaiting the employer's review window, or invoiced and pending employer settlement.
2. **`Available` ($1,240)**: Hours/deliverables approved and settled by the employer, queued for disbursement in the upcoming scheduled payout run.
3. **`Paid to Date` ($4,820)**: Historical sum of all disbursements successfully settled directly into the candidate’s MoMo wallet (Paystack Ghana) or bank account (Flutterwave).
4. **`Next Payout`**: Real-time sum of `Available` earnings set to trigger on the next disbursement cycle.

### 4.2 The Database Record: Tracking Business State, Not Custody

Every engagement generates clean, traceable transaction records:

```
Contract:          #KD-1042
Talent:            Jane Doe
Specialty:         Inpatient Clinical Coding (ICD-10-CM/PCS)
Period:            Sep 15 – Sep 21, 2026 (40 hours @ $17.50/hr)
------------------------------------------------------------------
Gross Invoiced:    $770.00   (Employer Billed: $700 talent + $70 platform markup)
Kodafriq Fee:      $70.00    (10% Platform Revenue)
Talent Net:        $700.00   (100% of candidate's agreed rate)
------------------------------------------------------------------
Payment Status:    SETTLED   (Employer card debited via Flutterwave)
Gateway Charge ID: flw_tx_849204128
Payout Status:     COMPLETED (Transferred via Paystack Ghana MoMo)
Gateway Payout ID: pstk_trf_9921045
Settlement Date:   2026-09-25 10:14 UTC
```

### 4.3 Separation of Concerns: Django vs. Payment Rails

```
                ┌──────────────────────────────────────┐
                │          DJANGO APPLICATION          │
                │        (Business State Engine)       │
                ├──────────────────────────────────────┤
                │ • Timesheet tracking & chart logs    │
                │ • Invoicing & rate calculations      │
                │ • Candidate Earnings Ledger state    │
                │ • Webhook receivers & audit trails   │
                └───────────────┬──────────────────────┘
                                │
               Direct API calls & Webhook events
                                │
            ┌───────────────────┴───────────────────┐
            ▼                                       ▼
┌───────────────────────┐               ┌───────────────────────┐
│     FLUTTERWAVE       │               │    PAYSTACK GHANA     │
│ (Money Rails - Global)│               │  (Money Rails - MoMo) │
├───────────────────────┤               ├───────────────────────┤
│ • International card  │               │ • Ghana Cedi (GHS)    │
│   charges (USD/GBP)   │               │ • MTN MoMo, Telecel,  │
│ • Gateway-level split │               │   AT Money transfers  │
│ • Pan-African bank    │               │ • Local Ghana bank    │
│   transfer payouts    │               │   account transfers   │
└───────────────────────┘               └───────────────────────┘
```

- **Django never touches user deposits**: If a transaction fails, it flags `Payout Status: FAILED` and triggers an alert.
- **Auditing is straightforward**: Every dollar earned matches a verified timesheet or milestone deliverable.
- **Compliance**: Kodafriq operates strictly as a marketplace software platform, eliminating the need for banking or money-transmitter licenses.

---

## 5. The Dual Disbursement Engine: Option A vs. Option B

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
1. **Candidate Onboarding**: When a talent is hired, their verified bank or mobile money details are registered with the payment rail via the Subaccount API.
2. **Weekly Execution**: When the employer's weekly invoice is debited:
   - Kodafriq specifies the split parameters at charge time.
   - The payment gateway automatically splits the settlement at the gateway level: Kodafriq's merchant account receives the platform markup, and the candidate receives their net earnings directly.
3. **Best For**: Full-time remote coders, dedicated billers, and long-term assistants working standard weekly hours.

### Option B: Platform Escrow & Milestone Payout (For Short Contracts & Bulk Work)
1. **Upfront Escrow Deposit**: For fixed deliverables (e.g., coding 500 backlogged patient charts or conducting a billing audit), the employer pays the full contract amount into Kodafriq's Escrow account upfront before work begins.
2. **Delivery & Inspection Window**:
   - The candidate submits the deliverable or logs the completed milestone batch.
   - The employer receives an automatic notification and has a 3 to 5 business day inspection window.
3. **Disbursement Release**:
   - Upon employer sign-off (or automatic acceptance after the review window closes without dispute), Kodafriq releases the funds:
     - 10% is marked as earned Kodafriq revenue.
     - Net earnings are disbursed to the candidate's verified Mobile Money wallet (Paystack Ghana) or bank account (Flutterwave).
4. **Dispute Protection**: If deliverables fail quality standards, Kodafriq's clinical mediation team inspects the work and can issue full or partial refunds without chasing funds from the candidate.

---

## 6. Weekly Billing Lifecycle (The Upwork-Style Engine)

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
5. **Friday Payout Settlement**: Candidates receive their weekly funds every Friday into their chosen destination (MoMo or Bank).

---

## 7. Global Multi-Currency Support & Cross-Border Settlement

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
- **GHS (GH₵)** — Ghana (MTN MoMo, Telecel Cash, AT Money, & Local Bank Accounts via Paystack Ghana)
- **NGN (₦)** — Nigeria (Direct NIP Bank Transfer via Flutterwave)
- **KES (KSh)** — Kenya (M-Pesa & Bank Transfer via Flutterwave)
- **ZAR (R)** — South Africa (EFT / Bank Transfer)
- **RWF / UGX** — Rwanda, Uganda, and regional clinical hubs
- **USD ($)** — Domiciliary accounts for senior consultants

### FX Rate Handling
- Invoices are pegged to the contract base currency (typically USD).
- Payment gateways provide real-time spot FX rates at transaction time, guaranteeing candidates receive the exact local equivalent without exchange risk falling on Kodafriq.

---

## 8. Preventing Disintermediation ("Don't Take Talent Off-Platform")

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
- **In-App Messaging & Contact Masking**: Before a formal contract is funded, communication is restricted to Kodafriq’s secure portal. Direct phone numbers and email addresses are automatically masked. *(Implemented via `apps/dashboard/contact_filter.py`)*.
- **Contractual Non-Circumvention (MSA)**: Both parties sign an enforceable Master Services Agreement upon registration with a **24-month non-circumvention clause** and an official platform **Buyout Fee** (e.g., $3,500 or 15% of annual compensation) if an employer wishes to hire a candidate directly onto their local payroll.

---

## 9. Technical Architecture in Kodafriq

To ensure modularity, high test coverage, and strict separation between business state and money rails, two dedicated apps are architected:

```
apps/
├── contracts/               # Engagement agreements, timesheets & milestones
│   ├── models.py            # Contract, Timesheet, TimesheetEntry, Milestone, DisputeCase
│   ├── views.py             # Contract creation, Timesheet logger, Approval interface
│   ├── forms.py
│   └── urls.py
└── billing/                 # The Earnings Ledger, Gateways & Payout Engine
    ├── models.py            # ContractInvoice, CandidatePayoutProfile, PaymentTransaction, PlatformFeeConfig
    ├── services/
    │   ├── paystack_ghana.py # Paystack Ghana MoMo & Bank Transfer Client (GHS)
    │   ├── flutterwave.py    # Flutterwave API SDK (USD/GBP Card Charges, Pan-African Transfers)
    │   └── invoicing.py      # Automated weekly invoice & ledger state generator
    ├── webhooks.py          # Secure Webhook listeners (Paystack & Flutterwave signature verification)
    └── views.py             # Earnings ledger view, Employer checkout, Admin audit dashboard
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
|             Timesheet             |       |          ContractInvoice          |
+-----------------------------------+       |      (Earnings Ledger Record)     |
+ - contract: Contract              |       +-----------------------------------+
| - week_start_date: Date           | 1:1   | - contract: Contract              |
| - total_hours: Decimal            |◄─────►| - timesheet: Timesheet (Optional) |
| - status: SUBMITTED/APPROVED/PAID |       | - gross_amount: Decimal           |
+-----------------+-----------------+       | - talent_earnings: Decimal        |
                  | 1:N                     | - kodafriq_fee: Decimal           |
                  ▼                         | - processing_fee: Decimal         |
+-----------------------------------+       | - payment_status: PENDING/SETTLED |
|          TimesheetEntry           |       | - payout_status: PENDING/COMPLETED|
+-----------------------------------+       | - gateway_charge_ref: String      |
| - date: Date                      |       | - gateway_payout_ref: String      |
| - hours_worked: Decimal           |       +-----------------+-----------------+
| - charts_coded_count: Integer     |                         |
| - work_description: Text          |                         ▼
+-----------------------------------+       +-----------------------------------+
                                            |        PaymentTransaction         |
                                            +-----------------------------------+
                                            | - gateway: PAYSTACK / FLUTTERWAVE |
                                            | - transaction_id: String          |
                                            | - amount: Decimal                 |
                                            | - status: SUCCESS / FAILED        |
                                            | - webhook_payload: JSON           |
                                            +-----------------------------------+
```

---

## 10. Implementation Roadmap for the Earnings Ledger

### Phase 1: `apps/contracts/`
- Build `Contract` model linking `EmployerProfile`, `CandidateProfile`, and `JobPost`.
- Build `Timesheet` and `TimesheetEntry` models for daily hours & clinical work notes (charts coded, denials appealed).
- Build `Milestone` model for fixed deliverable contracts.
- Candidate timesheet logging UI & Employer review/approval interface.

### Phase 2: `apps/billing/` (The Earnings Ledger)
- Build `ContractInvoice` ledger model:
  - Tracks `gross_amount`, `talent_earnings`, `kodafriq_fee`, `payment_status`, and `payout_status`.
- Build `CandidatePayoutProfile` model:
  - Destination details: Paystack Ghana MoMo (MTN, Telecel, AT Money) and Pan-African Bank accounts (Flutterwave).
- Candidate Earnings Ledger properties:
  - `pending_earnings` (unapproved hours or pending settlement)
  - `available_earnings` (approved and settled, queued for next payout run)
  - `lifetime_paid` (total disbursed to date)
  - `next_payout_amount` and scheduled payout date.

### Phase 3: Candidate & Employer UI
- **Candidate Dashboard**:
  - The executive "KODAFRIQ EARNINGS" card (`Available`, `Pending`, `Paid to Date`, `Next Payout`, destination details).
  - Detailed historical earnings statement table.
- **Employer Dashboard**:
  - Weekly timesheet review and approval interface.
  - One-click invoice payment checkout.

### Phase 4: Payment Gateway Integration & Webhooks
- Paystack Ghana integration for Mobile Money (MoMo) & local GHS bank disbursements.
- Flutterwave integration for international card charging (USD/GBP) and pan-African transfers.
- Secure HMAC webhook handlers for real-time transaction reconciliation.

---

## 11. Summary & Action Plan

| Step | Objective | Output |
| :--- | :--- | :--- |
| **1. Specification Alignment** | Establish non-custodial Earnings Ledger architecture in documentation. | `platform_monitization.md` v1.1.0 |
| **2. Contracts Module** | Create `apps/contracts` with `Contract`, `Timesheet`, and `Milestone`. | Models, Admin, & Migrations |
| **3. Earnings Ledger Module** | Create `apps/billing` with `ContractInvoice`, `CandidatePayoutProfile`, & `PlatformFeeConfig`. | Ledger Models, Admin, & Migrations |
| **4. User Interfaces** | Candidate Earnings Dashboard card + Employer Timesheet Review. | HTML Templates & responsive CSS |
| **5. Payment Rail Integrations** | Paystack Ghana MoMo & Flutterwave Card/Payout SDKs. | Services & Webhook Handlers |
