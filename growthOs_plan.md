# 🚀 KODAFRIQ GROWTHOS: MASTER TECHNICAL SPECIFICATION & DEVELOPMENT ROADMAP
## Employer Intelligence, Hiring Intent Detection, Talent Reverse-Matching & Acquisition Platform

**Project Code**: `growth_os`  
**Parent Product**: [Kodafriq Data Management Solutions](https://kodafriq.com)  
**Location in Repository**: `apps/growth_os/`  
**Status**: Architecture Finalized & Phase 1 Active  
**Target Sectors**: Multi-Sector Architecture supporting:
- **Healthcare & Clinical Operations**: Medical Billing, Medical Coding, RCM Companies, Healthcare BPOs, Hospital Networks.
- **Information Technology & Software**: Software Engineering, Cloud & DevOps Infrastructure, Cybersecurity, Data & AI, IT Support.
- **Finance & Accounting**: Accounting, Bookkeeping, Financial Advisory, Fintech.
- **Cross-Industry Operations**: Customer Support, BPO, Technical Operations.

---

## 📌 1. Executive Summary & Problem Statement

### The "Cold-Start" Marketplace Dilemma
Kodafriq has successfully onboarded and verified over **100+ qualified healthcare professionals** (Medical Coders, Medical Billers, Claims Specialists, and RCM Auditing Talents). However, the platform experienced zero organic employer registrations over a two-month span. 

Traditional recruitment marketplaces rely on a passive model: *publish the platform and wait for employers to find it, register, and post jobs*. For a new specialized platform, this model creates a stalemate:
1. Talents wait for jobs that never appear.
2. Employers don't visit an unproven platform with zero job traffic.

### The GrowthOS Strategic Pivot: Active Outbound Acquisition
**Kodafriq GrowthOS** fundamentally replaces the passive model with an **active, intelligence-driven outbound acquisition engine**. Instead of waiting for employers to register:
1. **Discover**: GrowthOS continuously scans and catalogues healthcare employers worldwide.
2. **Detect Intent**: It monitors public job boards, career pages, and business signals to pinpoint companies with *immediate, active, or persistent recruitment needs*.
3. **Reverse Match**: It starts with Kodafriq's **available verified candidates** and identifies the specific organizations whose current vacancies require those exact skillsets.
4. **AI-Powered Personalized Outreach**: It generates hyper-tailored outreach referencing the employer's specific open roles and pitching pre-vetted, ready-to-hire talent (with human-in-the-loop review).
5. **Manage & Convert**: It guides each prospective employer through a structured 10-stage sales CRM from initial discovery to contract signing and talent placement.

---

## 🏛️ 2. Core Architectural Pillars

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   KODAFRIQ GROWTHOS                                     │
│                     Proactive Outbound Employer Acquisition Platform                    │
└─────────────────────────────────────────────────────────────────────────────────────────┘
          │                                                     │
   [PUBLIC WEB & SOURCES]                               [KODAFRIQ INTERNAL]
          │                                                     │
  ┌───────▼──────────────────────────┐                  ┌───────▼──────────────────────────┐
  │ 1. Employer Lead Discovery       │                  │ 100+ Vetted Candidates           │
  │ 2. Automated Multi-Source Sourcing│                  │ (CPC, CCS, ICD-10, RCM, DRG)     │
  │ 3. Hiring Intent Detection       │                  │ Verified Scores (0–100%)         │
  └───────┬──────────────────────────┘                  └───────┬──────────────────────────┘
          │                                                     │
          └──────────────────────────┬──────────────────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │ 4. Reverse Matching Engine│
                       │    (Intent vs Talent Fit) │
                       └─────────────┬─────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │ 5. AI Outreach Engine     │
                       │    (Human Review Queue)   │
                       └─────────────┬─────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │ 6. Sales CRM Pipeline     │
                       │    (10-Stage Acquisition) │
                       └─────────────┬─────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │ Placed Employer & Contract│
                       │ (Platform Monetization)   │
                       └───────────────────────────┘
```

GrowthOS operates as an integrated system divided into **six functional modules**:

| Module | Core Responsibility | Primary Data Outputs |
| :--- | :--- | :--- |
| **1. Lead Discovery Engine** | Crawls & aggregates healthcare companies by specialization | `EmployerLead`, Company metadata, domain, tech stack |
| **2. Hiring Intent Detector** | Identifies active, urgent, or persistent recruitment signals | `JobVacancy`, `HiringSignal`, **Hiring Intent Score (0–100)** |
| **3. Multi-Source Sourcing** | Ingests leads from Google Search/Places, HFMA, AAPC, directories | Normalized raw company records, deduplicated entities |
| **4. Talent Reverse Matcher** | Matches open vacancies against Kodafriq registered talent pool | `TalentReverseMatch`, Match rationale, **Talent Fit Score (0–100)** |
| **5. AI Outreach Engine** | Drafts tailored email & LinkedIn messages showcasing talent | `OutreachMessage`, Approval queue, communication logs |
| **6. Sales CRM Pipeline** | Tracks companies through 10 stages from discovery to placement | `CRMOpportunity`, `CRMActivity`, Deal values, Contract conversion |

---

## 🎯 3. Detailed Functional Specifications

### Feature 1: Employer Lead Discovery Engine
* **Automated Company Discovery**: Systematically indexes companies in medical billing, medical coding, revenue cycle management, healthcare BPO, hospital groups, and multi-specialty clinics.
* **Metadata Extraction**: Scrapes and stores company website, headquarters location, employee headcounts, active career page URLs, primary business services, and public contact information.
* **Decision-Maker Identification**: Identifies executive and recruitment stakeholders (Founders, CEOs, Talent Acquisition Managers, VPs of Revenue Cycle, Operations Directors) through public directories and business networks.
* **Deduplication & Hygiene**: Validates company web domains and clean titles to prevent duplicates against the existing Kodafriq database (`EmployerProfile`).

### Feature 2: Employer Hiring Intent Detection Engine
* **Job Vacancy Monitoring**: Monitors company career pages, Google Jobs, and job boards for roles matching Kodafriq verticals:
  * Medical Coders (Inpatient, Outpatient, Risk Adjustment, DRG Auditing)
  * Medical Billers & AR Follow-Up Specialists
  * Revenue Cycle Managers & Claims Adjudicators
  * Prior Authorization Specialists & Denial Analysts
* **Persistent Vacancy Detection**: Flags job listings advertised for more than 30 or 60 days, indicating recruitment bottlenecks where Kodafriq's immediate placement proposition is strongest.
* **Hiring Intent Score (0–100)**: A dynamic metric computed from vacancy recency, total number of open roles, persistent posting duration, and organizational growth signals.

### Feature 3: Automated Multi-Source Lead Sourcing
* **Multi-Channel Ingestion**: Avoids reliance on a single data source:
  1. Google Custom Search / SerpAPI for high-intent business queries (e.g., *"Medical billing companies in Texas hiring remote coders"*).
  2. Industry association directories (HFMA, HBMA, AAPC corporate members).
  3. Healthcare BPO and outsourcing firm registries.
  4. Manual CSV bulk-import for staff business development lists.
* **Geographic & Industry Tagging**: Normalizes country (USA, UK, Canada, UAE, South Africa), healthcare domain, and outsourcing tolerance (remote-friendly, US-hours, etc.).

### Feature 4: Talent-to-Employer Reverse Matching Engine
* **Inverted Matching Model**: Instead of waiting for an employer to search Kodafriq, the system analyzes our active 100+ candidates and proactively queries: *"Which discovered employers currently have open vacancies that our candidates can fulfill today?"*
* **Candidate Match Dossier**: Groups candidates by specialty (e.g., "15 Certified Cardiology Billers", "8 Inpatient ICD-10 Coders with Verified Scores > 85%").
* **Talent Fit Score (0–100)**: Measures how accurately Kodafriq's active candidates satisfy the discovered employer’s stated requirements (experience level, certifications, software tools).

### Feature 5: AI-Powered Research & Personalized Outreach Engine
* **Contextual Company Research**: Analyzes the employer's website and job description to identify specific operational pain points (e.g., high denial rates, backlog in accounts receivable, rapid practice expansion).
* **Dynamic Pitch Generation**: Synthesizes a high-conversion, professional cold email and LinkedIn message that:
  * References their exact open vacancy.
  * Introduces anonymized matching Kodafriq candidates (e.g., *"We have 3 AAPC-certified inpatient coders scoring in the top 10% on our platform, available immediately on US EST hours"*).
  * Directs the recipient to interactive Public Talent Cards or a tailored candidate shortlist.
* **Human-in-the-Loop Review Queue**: All generated messages are held in a pending queue where the Kodafriq BD team can review, edit, approve, or reject before dispatch.
* **Reply Classification**: Categorizes incoming employer replies (*Positive / Meeting Requested*, *Information Requested*, *Not Hiring*, *Unsubscribe*).

### Feature 6: Employer Sales CRM & Opportunity Management
* **10-Stage Acquisition Pipeline**:
  ```
  1. DISCOVERED ──> 2. QUALIFIED ──> 3. HIRING_SIGNAL ──> 4. CONTACT_FOUND ──> 5. OUTREACH_SENT
        │
        └──> 6. REPLY_RECEIVED ──> 7. MEETING_BOOKED ──> 8. SHORTLIST_SENT ──> 9. INTERVIEWS ──> 10. PLACEMENT_WON
  ```
* **Deal Valuation**: Tracks expected placements, estimated monthly billing rates, and Kodafriq platform placement fees.
* **Activity Ledger**: Chronological log of emails sent, phone calls logged, notes recorded, and stage transitions.
* **1-Click Employer Account Conversion**: When an opportunity reaches `PLACEMENT_WON`, clicking "Convert to Employer" automatically registers a formal `EmployerProfile` and initializes a `Contract` in Kodafriq’s billing and timesheet system.

---

## 🧮 4. The Dual-Score Prioritization Matrix

GrowthOS prevents wasted business development effort by maintaining two distinct algorithmic scores for every employer lead:

```
                          ▲ HIGH
                          │
                          │   🟡 TIER 2: SKILL GAP           🔥 TIER 1: PRIME TARGET
                          │   High Hiring Demand              High Hiring Demand
                          │   Low Current Talent Fit          Exact Talent Fit Ready
                          │   Action: Train/Source candidates Action: Immediate AI Outreach
   HIRING INTENT SCORE    │
         (0 - 100)        │
                          │   ⚪ TIER 4: DISQUALIFIED        🔵 TIER 3: NURTURE
                          │   Low Hiring Demand               Low Hiring Demand
                          │   Low Talent Fit                  Strong Passive Talent Fit
                          │   Action: Archive or Monitor      Action: Brand Awareness/Nurture
                          │
                          └──────────────────────────────────────────────────────────►
                          LOW                       TALENT FIT SCORE (0 - 100)        HIGH
```

### Formula: Hiring Intent Score ($S_{intent}$)
$$S_{intent} = \min\left(100, \; w_v V + w_p P + w_r R + w_c C\right)$$
Where:
* $V$ = Number of active healthcare vacancies (Max 40 pts)
* $P$ = Persistent vacancy duration ($> 30\text{ days} = 25\text{ pts}$, $> 60\text{ days} = 35\text{ pts}$)
* $R$ = Recency multiplier (posted within last 7 days = 15 pts)
* $C$ = Direct decision-maker contact identified with verified email = 10 pts

### Formula: Talent Fit Score ($S_{fit}$)
$$S_{fit} = \frac{\sum_{i=1}^{k} \text{CandidateScore}_i \times \text{SkillMatchWeight}_i}{k}$$
Where:
* Matched skills between job requirements and `CandidateProfile` competencies (50 pts)
* Candidate certifications matching stated criteria (e.g. CPC, CCS, RHIA) (30 pts)
* High Kodafriq Verified Score ($> 80\%$) boost (20 pts)

---

## 🏗️ 5. Technical Architecture & File Structure

GrowthOS resides completely within `apps/growth_os/` as a first-class Django app:

```
kodafriq/
├── apps/
│   ├── growth_os/
│   │   ├── __init__.py
│   │   ├── apps.py                         # App configuration (GrowthOSConfig)
│   │   ├── models.py                       # Core database models
│   │   ├── admin.py                        # Django Admin interface & actions
│   │   ├── urls.py                         # URL routing (/growth-os/...)
│   │   ├── views.py                        # Staff views & dashboard controllers
│   │   ├── tests.py                        # Comprehensive automated test suite
│   │   ├── forms.py                        # Lead, contact & outreach forms
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── discovery.py                # Web & search directory discovery
│   │   │   ├── intent_detector.py          # Vacancy detection & intent scoring
│   │   │   ├── reverse_matcher.py          # Talent-to-job reverse matching engine
│   │   │   ├── ai_researcher.py            # Company dossier & requirement extractor
│   │   │   ├── outreach_generator.py       # Personalized email/LinkedIn copy generator
│   │   │   └── crm_service.py              # Pipeline transitions & 1-click conversion
│   │   └── management/
│   │       └── commands/
│   │           ├── run_lead_discovery.py   # CLI discovery cron runner
│   │           ├── scan_hiring_intent.py   # Periodic vacancy scanner
│   │           └── compute_talent_fits.py  # Nightly match re-scoring
├── templates/
│   └── growth_os/
│       ├── base_growth_os.html             # GrowthOS shell, navigation & subheader
│       ├── dashboard.html                  # Executive metrics & KPI cards
│       ├── lead_list.html                  # Filterable directory with dual score badges
│       ├── lead_detail.html                # 360° lead dossier & matched candidate cards
│       ├── lead_form.html                  # Manual lead creation & edit view
│       ├── pipeline_kanban.html            # 10-stage interactive sales board
│       ├── reverse_matches.html            # Candidate-to-Employer opportunity matrix
│       └── outreach_queue.html             # Human-in-the-loop review & dispatch queue
└── static/
    └── css/
        └── growth_os.css                   # Custom styles for Kanban board & badges
```

---

## 💾 6. Database Models Specification (`apps/growth_os/models.py`)

### 1. `EmployerLead`
Represents a prospective company discovered or imported into the system.
* `id` (UUID, PK)
* `company_name` (CharField, max 200, db_index=True)
* `domain` (CharField, max 150, unique=True, normalized domain e.g. `optum.com`)
* `website` (URLField)
* `country` (CharField, default='United States')
* `city` (CharField, blank=True)
* `industry_vertical` (CharField, choices: `MEDICAL_BILLING`, `MEDICAL_CODING`, `RCM_SERVICES`, `HEALTHCARE_BPO`, `HOSPITAL_CLINIC`, `OTHER`)
* `estimated_company_size` (CharField, choices: `1_10`, `11_50`, `51_200`, `201_500`, `501_PLUS`)
* `careers_url` (URLField, blank=True)
* `source` (CharField, choices: `DISCOVERY_ENGINE`, `GOOGLE_SEARCH`, `HFMA_DIRECTORY`, `MANUAL_IMPORT`, `REFERRAL`)
* `status` (CharField, choices: `LEAD`, `QUALIFIED`, `IN_PIPELINE`, `CONVERTED`, `DISQUALIFIED`, default=`LEAD`)
* `hiring_intent_score` (IntegerField, default=0, db_index=True)
* `talent_fit_score` (IntegerField, default=0, db_index=True)
* `assigned_staff` (FK to `User`, null=True, blank=True)
* `converted_employer_profile` (OneToOne to `EmployerProfile`, null=True, blank=True)
* `created_at`, `updated_at` (DateTime)

### 2. `LeadContact`
Represents an executive or decision-maker at the prospective company.
* `id` (UUID, PK)
* `lead` (FK to `EmployerLead`, related_name='contacts')
* `full_name` (CharField, max 150)
* `job_title` (CharField, max 150, e.g. "Director of Revenue Cycle")
* `email` (EmailField, blank=True)
* `phone` (CharField, blank=True)
* `linkedin_url` (URLField, blank=True)
* `is_primary` (BooleanField, default=False)
* `verification_status` (CharField, choices: `UNVERIFIED`, `VERIFIED_VALID`, `BOUNCED`, default=`UNVERIFIED`)
* `created_at` (DateTime)

### 3. `HiringSignal` / `JobVacancy`
Stores detected hiring activities and public job postings.
* `id` (UUID, PK)
* `lead` (FK to `EmployerLead`, related_name='vacancies')
* `job_title` (CharField, max 200)
* `role_category` (CharField, choices: `MEDICAL_CODER`, `MEDICAL_BILLER`, `RCM_SPECIALIST`, `AR_SPECIALIST`, `AUDITOR`, `OTHER`)
* `job_url` (URLField, blank=True)
* `raw_description` (TextField, blank=True)
* `extracted_skills` (JSONField, default=list)
* `date_detected` (DateField, default=timezone.now)
* `days_open` (PositiveIntegerField, default=1)
* `is_persistent` (BooleanField, default=False, True if days_open > 30)
* `is_active` (BooleanField, default=True)

### 4. `TalentReverseMatch`
Links an employer’s vacancy to matching candidates registered on Kodafriq.
* `id` (UUID, PK)
* `lead` (FK to `EmployerLead`, related_name='talent_matches')
* `vacancy` (FK to `HiringSignal`, null=True, blank=True, related_name='candidate_matches')
* `candidate` (FK to `CandidateProfile`, related_name='growth_employer_matches')
* `match_score` (DecimalField, max 100.00)
* `matched_skills` (JSONField, default=list)
* `matching_rationale` (TextField, explain why candidate fits the role)
* `is_shortlisted` (BooleanField, default=False)
* `created_at` (DateTime)

### 5. `OutreachMessage`
Stores generated and sent emails or LinkedIn pitches.
* `id` (UUID, PK)
* `lead` (FK to `EmployerLead`, related_name='outreaches')
* `contact` (FK to `LeadContact`, null=True, blank=True)
* `channel` (CharField, choices: `EMAIL`, `LINKEDIN`, default=`EMAIL`)
* `subject` (CharField, max 255)
* `body_text` (TextField)
* `status` (CharField, choices: `DRAFT_PENDING_APPROVAL`, `APPROVED`, `SENT`, `REPLIED`, `REJECTED`, `BOUNCED`, default=`DRAFT_PENDING_APPROVAL`)
* `approved_by` (FK to `User`, null=True, blank=True)
* `sent_at` (DateTimeField, null=True, blank=True)
* `reply_classification` (CharField, blank=True, choices: `POSITIVE_MEETING`, `INFO_REQUESTED`, `NOT_INTERESTED`, `UNSUBSCRIBE`)
* `reply_notes` (TextField, blank=True)

### 6. `CRMOpportunity`
Tracks the sales negotiation for qualified leads.
* `id` (UUID, PK)
* `lead` (OneToOneField to `EmployerLead`, related_name='crm_opportunity')
* `stage` (CharField, choices:
  `1_DISCOVERED`,
  `2_QUALIFIED`,
  `3_HIRING_SIGNAL_DETECTED`,
  `4_CONTACT_IDENTIFIED`,
  `5_OUTREACH_SENT`,
  `6_REPLY_RECEIVED`,
  `7_MEETING_SCHEDULED`,
  `8_SHORTLIST_DELIVERED`,
  `9_INTERVIEWS_IN_PROGRESS`,
  `10_PLACEMENT_WON`,
  `CLOSED_LOST`
)
* `target_roles_count` (PositiveIntegerField, default=1)
* `estimated_monthly_deal_value` (DecimalField, max_digits=10, decimal_places=2, default=0.00)
* `currency` (CharField, default='USD')
* `priority` (CharField, choices: `URGENT`, `HIGH`, `MEDIUM`, `LOW`, default=`HIGH`)
* `win_probability_percent` (PositiveIntegerField, default=20)
* `next_follow_up_date` (DateField, null=True, blank=True)
* `lost_reason` (CharField, blank=True)

### 7. `CRMActivity`
Immutable audit log of all interactions with the employer.
* `id` (UUID, PK)
* `lead` (FK to `EmployerLead`, related_name='activities')
* `activity_type` (CharField, choices: `NOTE`, `CALL`, `EMAIL_SENT`, `MEETING`, `STAGE_CHANGE`, `SHORTLIST_SENT`)
* `summary` (CharField, max 255)
* `details` (TextField, blank=True)
* `performed_by` (FK to `User`)
* `created_at` (DateTimeField, auto_now_add=True)

---

## 📅 7. Step-by-Step Phased Development Plan

```
PHASE 1: Core Foundation & Lead CRM Database  [COMPLETED & TESTED ✅]
  ├── 1.1 Scaffold apps/growth_os & register in config/settings.py
  ├── 1.2 Implement models.py, migrations, and tests (13/13 passed)
  ├── 1.3 Django Admin interfaces with bulk actions & dual-score badges
  └── 1.4 Staff UI shell, Lead Directory & Lead Detail Dossier

PHASE 2: Sourcing Engine & Hiring Intent Scorer  [COMPLETED & TESTED ✅]
  ├── 2.1 Multi-channel Sourcing (Google Search API / SerpAPI / CSV Bulk Importer)
  ├── 2.2 Career Page & Vacancy Scraper (ethical, BS4/regex role parser)
  ├── 2.3 Automated Hiring Intent Scoring Engine (V + P + R + C + U)
  ├── 2.4 Management commands: run_lead_discovery, scan_hiring_intent, import_leads_csv
  └── 2.5 Discovery Search Hub & CSV Ingestion Staff Workspace

PHASE 3: Reverse Matching & AI Outreach Generator  [COMPLETED & TESTED ✅]
  ├── 3.1 Multi-Sector Talent-to-Job Matching Engine (Healthcare, IT, and Finance)
  ├── 3.2 Talent Fit Scoring Formula
  ├── 3.3 AI-Powered Multi-Sector Outreach Generator (Step 1-3 Cadence: Email & LinkedIn)
  ├── 3.4 Staff Human-in-the-Loop Review & Approval Queue (/growth-os/outreach/)
  └── 3.5 Public Candidate Shortlist Dossier (/growth-os/shortlist/<uuid>/) with Inquiries

PHASE 4: Interactive Kanban Pipeline & Conversion Engine  ◄── (NEXT DEVELOPMENT PHASE)
  ├── 4.1 10-Stage Interactive Drag-and-Drop Kanban Board
  ├── 4.2 Activity Logging, Call/Meeting Scheduler & Follow-Up Reminders
  ├── 4.3 1-Click Conversion: EmployerLead -> Kodafriq EmployerProfile + Contract
  └── 4.4 Executive Dashboard KPI Analytics & Performance Reports
```

---

## 🛠️ 8. Developer Onboarding & Local Execution Runbook

### Prerequisites
* Python 3.12+ (in `venv`)
* SQLite (local development) / PostgreSQL (production)
* Access to Kodafriq staff superuser credentials

### Setup Commands
1. Activate virtual environment:
   ```bash
   source venv/bin/activate
   ```
2. Verify Django system check:
   ```bash
   python manage.py check
   ```
3. Run GrowthOS test suite:
   ```bash
   python manage.py test apps.growth_os -v 2
   ```

### GrowthOS Background CLI Commands
* Run discovery search:
  ```bash
  python manage.py run_lead_discovery --query="medical billing companies in Texas" --limit=25
  ```
* Rescan active vacancy intent scores:
  ```bash
  python manage.py scan_hiring_intent
  ```
* Recalculate talent fit scores against candidate pool:
  ```bash
  python manage.py compute_talent_fits
  ```

### Accessing the GrowthOS Workspace
* **Staff Command Center**: Log in as a staff/admin user and navigate to:  
  `https://kodafriq.com/growth-os/` (or `http://localhost:8000/growth-os/`)
* **Django Admin Direct**:  
  `https://kodafriq.com/admin/growth_os/`

---

## 📈 9. Key Performance Indicators (Success Metrics)

GrowthOS will be evaluated on real commercial outcomes, not vanity metrics:

| Metric | Target (Quarterly) | Evaluation Purpose |
| :--- | :--- | :--- |
| **Qualified Leads Discovered** | 500+ healthcare companies | Measures market coverage & database size |
| **High Intent Signals ($S_{intent} \ge 70$)** | 120+ active vacancies | Filters out companies not actively hiring |
| **High Talent Fit ($S_{fit} \ge 80$)** | 80+ companies matched | Ensures Kodafriq can immediately fulfill demand |
| **Outreach Response Rate** | $\ge 12\%$ | Measures copy personalization & value proposition |
| **Discovery-to-Meeting Conversion** | $\ge 5\%$ | Verifies interest in Kodafriq candidate quality |
| **First Placement Won** | 1–3 placements in 30 days | Validates product hypothesis & solves cold start |

---

*Document maintained by the Kodafriq Core Engineering Team. Update this document as subsequent phases are implemented.*

