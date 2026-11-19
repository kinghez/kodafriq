# 🚀 Kodafriq GrowthOS: Full System Functional Specification & Architecture Guide

> **Document Version**: 5.0 (All Phases 1–5 Fully Implemented & Tested)  
> **Repository Location**: `apps/growth_os/`  
> **Parent Application**: [Kodafriq Data Management Solutions](https://kodafriq.com)  
> **Status**: Production Ready & Fully Tested (45/45 Unit Tests Passing ✅)

---

## 📌 1. Executive Overview & Problem Statement

### 1.1 The Marketplace "Cold-Start" Challenge
Traditional talent marketplaces and freelancing portals operate on a passive model: *build the site, onboard candidates, and wait for employers to organically discover the platform, sign up, and publish job listings*.

Kodafriq successfully onboarded and certified over **100+ vetted African professionals** across high-demand disciplines (Medical Coders with CPC/CCS credentials, Medical Billers, Claims Specialists, Software Engineers, Cloud/DevOps practitioners, and Financial Accountants). However, relying exclusively on organic employer acquisition creates a structural stalemate:
* Talents wait for job opportunities that never materialize.
* Employers do not spend time browsing an unproven platform with zero job traffic.

### 1.2 The GrowthOS Strategic Pivot: Active Outbound Acquisition
**Kodafriq GrowthOS** replaces the passive recruitment model with an **autonomous, proactive, intelligence-driven outbound acquisition engine**. Instead of waiting for employers to register:

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                                 KODAFRIQ GROWTHOS                                     │
│                     Proactive Outbound Employer Acquisition Platform                  │
└───────────────────────────────────────────────────────────────────────────────────────┘
                                          │
    ┌─────────────────────────────────────┴─────────────────────────────────────┐
    ▼                                                                           ▼
[EXTERNAL CHANNELS]                                                     [INTERNAL POOL]
- Google Search & Business Maps                                         - 100+ Vetted Candidates
- LinkedIn Jobs & Companies                                             - Medical Coders / Billers
- Indeed Hiring Intelligence                                            - Software / DevOps / Cloud
- Employer Career Portals                                               - Financial Accountants
    │                                                                           │
    ▼                                                                           ▼
[1. SOURCING & INGESTION]                                               [2. CANDIDATE PROFILE]
Discovers companies hiring in target markets                           Real-time skills, availability,
Normalizes domains, dedupes records                                    credentials & readiness score
    │                                                                           │
    └─────────────────────────────────────┬─────────────────────────────────────┘
                                          ▼
                             [3. DUAL-SCORING ENGINE]
                       ┌─────────────────────────────────────┐
                       │ Hiring Intent Score (0–100%)        │
                       │ Talent Fit Score    (0–100%)        │
                       └──────────────────┬──────────────────┘
                                          ▼
                             [4. 4-TIER MATRIX ROUTING]
                       ┌─────────────────────────────────────┐
                       │ Tier 1: High Intent + High Fit      │ ──► Immediate BD Outreach
                       │ Tier 2: Low Intent  + High Fit      │ ──► Nurture / Watchlist
                       │ Tier 3: High Intent + Low Fit       │ ──► Skill Acquisition Signal
                       │ Tier 4: Low Intent  + Low Fit       │ ──► Long-term Dormant
                       └──────────────────┬──────────────────┘
                                          ▼
                             [5. REVERSE MATCHING ENGINE]
                       Directly maps open vacancies to qualified
                       available candidates in Kodafriq pool
                                          ▼
                             [6. AI OUTREACH & SHORTLIST]
                       Generates 3-step personalized outreach pitches;
                       Produces secure public shareable shortlist dossiers
                                          ▼
                             [7. 10-STAGE KANBAN SALES CRM]
                       Visual stage transitions, task logs, call notes,
                       and overdue follow-up alerts
                                          ▼
                             [8. 1-CLICK CONVERSION ENGINE]
                       Transfers Lead -> Active EmployerProfile + User
                       and generates formal employment contracts
                                          ▼
                             [9. AUTONOMOUS MAINTENANCE]
                       Daily vacancy polling, persistent vacancy detection,
                       intent score degradation, dormant lead archiving,
                       real-time candidate availability sync, weekly BD digest
```

---

## 🌐 2. Multi-Sector Extensibility Architecture

While initially designed to solve staffing shortages in **Healthcare & Clinical Operations**, GrowthOS is architected with a modular domain and taxonomy schema that supports multiple industries without schema migrations:

### Supported Verticals (`IndustryVertical` Choices)
1. **Healthcare & Clinical Operations**:
   * Medical Coding (Inpatient, Outpatient, Risk Adjustment, DRG, HCC)
   * Medical Billing & Accounts Receivable (AR Follow-Up, Denials Management)
   * Revenue Cycle Management (RCM) & Clinical Documentation Improvement (CDI)
   * Healthcare BPO & Practice Management Networks
2. **Information Technology & Cloud Infrastructure**:
   * Software Engineering (Fullstack, Frontend, Backend, Python, React)
   * Cloud Architecture, DevOps & SRE (AWS, GCP, Kubernetes, CI/CD, Terraform)
   * Cybersecurity & SOC Monitoring
   * IT Technical Support & Helpdesk
   * Data Engineering, Analytics & AI Ops
3. **Finance & Business Operations**:
   * Accounting, Bookkeeping & Controller Services
   * Financial Analysis, Risk Management & Fintech Operations
   * Cross-Industry Customer Success, Operations & BPO

---

## 🏗️ 3. Phased Functional Breakdown

GrowthOS was engineered and deployed across 5 sequential, rigorously tested development phases:

```
========================================================================================
PHASE 1: Core Foundation & Lead CRM Database
PHASE 2: Sourcing Engine & Hiring Intent Scoring
PHASE 3: Talent Reverse-Matching & AI Outreach Generator
PHASE 4: Interactive Kanban Pipeline, Conversion Engine & Follow-Up Reminders
PHASE 5: Autonomous Continuous Acquisition & Ecosystem Automation
========================================================================================
```

---

### 🏛️ Phase 1: Core Foundation & Lead CRM Database

Phase 1 established the foundational data layer, relational schema, and staff management workspace.

#### Key Models (`apps/growth_os/models.py`)
1. **`EmployerLead`**: The central entity representing a prospective employer organization.
   * Identifiers: `id` (UUID), `company_name`, `domain` (canonical unique normalized domain slug), `website`, `careers_url`, `city`, `state`, `country`.
   * Classification: `industry_vertical`, `company_size`, `source`, `status` (`LEAD`, `QUALIFIED`, `IN_PIPELINE`, `CONVERTED`, `UNQUALIFIED`, `ARCHIVED`).
   * Scores: `hiring_intent_score` ($0-100$), `talent_fit_score` ($0-100$), and computed `priority_tier` ($1-4$).
   * Conversion tracking: `converted_employer_profile` (OneToOne to `EmployerProfile`), `converted_at`.
2. **`LeadContact`**: Organizational decision-makers (VP of RCM, Head of Talent, CTO, Director of Engineering).
   * Fields: `full_name`, `job_title`, `email`, `phone`, `linkedin_url`, `is_primary`, `verification_status` (`UNVERIFIED`, `VERIFIED_VALID`, `BOUNCED`).
3. **`HiringSignal`**: Specific open job positions or hiring alerts detected for an employer.
   * Fields: `job_title`, `role_category`, `job_url`, `raw_description`, `extracted_skills` (JSON array), `date_detected`, `days_open`, `is_persistent`, `is_active`.
4. **`CRMOpportunity`**: Sales pipeline state for each lead.
   * Stages: 10 structured phases from discovery to closed placement.
   * Economics: `estimated_monthly_deal_value`, `estimated_talent_count`, `next_follow_up_date`.
5. **`CRMActivity`**: Comprehensive touchpoint history.
   * Types: `NOTE`, `CALL`, `EMAIL_SENT`, `EMAIL_REPLY`, `MEETING`, `CONTRACT_SENT`, `STAGE_CHANGE`.

#### The Dual-Scoring Philosophy
Rather than prioritizing leads solely by company size, GrowthOS calculates two independent dimensions:
* **Hiring Intent Score ($S_{intent} \in [0, 100]$)**: How urgently is this employer looking to hire right now?
* **Talent Fit Score ($S_{fit} \in [0, 100]$)**: How well does Kodafriq’s current available talent match their specific job requirements?

#### The 4-Tier Matrix
* **Tier 1 (Priority Target)**: Intent $\ge 60\%$ AND Fit $\ge 60\%$. High hiring urgency + immediate available talent. Handled via automated priority outreach.
* **Tier 2 (Nurture Pool)**: Intent $< 60\%$ AND Fit $\ge 60\%$. Strong talent match but no urgent job vacancies. Maintained in quarterly nurture sequence.
* **Tier 3 (Acquisition Gap)**: Intent $\ge 60\%$ AND Fit $< 60\%$. Urgent hiring needs, but Kodafriq lacks ready candidates. Serves as a recruiting signal for Kodafriq's talent sourcers.
* **Tier 4 (Dormant / Low Priority)**: Intent $< 60\%$ AND Fit $< 60\%$.

---

### 🔍 Phase 2: Sourcing Engine & Hiring Intent Scoring

Phase 2 automated the discovery of employers and the algorithmic detection of hiring urgency.

#### 1. Multi-Source Lead Discovery
* **Discovery Hub UI** (`/growth-os/discovery/`): Staff can enter Boolean queries (e.g., *"Medical billing companies in Texas hiring coders"* or *"Fintech startups hiring backend engineers"*).
* **Automatic Domain Deduplication**: All ingested company URLs are stripped to their root domain slug (e.g., `https://www.optum.com/careers?id=123` $\rightarrow$ `optum.com`), preventing duplicate leads.
* **CSV Bulk Ingestion**: Staff can upload CSV files of leads with column auto-mapping (`company_name`, `website`, `careers_url`, `country`, `industry_vertical`).

#### 2. Career Page & Vacancy Scraper (`apps/growth_os/services/scraper.py`)
* Performs non-intrusive scraping of employer career portals.
* Extracts hiring keywords, technical skills (e.g., `CPC`, `CCS`, `ICD-10-CM`, `Python`, `AWS`, `PostgreSQL`), and open job titles.

#### 3. Mathematical Formula for Hiring Intent Scoring
$$\text{Score} = \min\left(100, S_{\text{vacancies}} + S_{\text{persistent}} + S_{\text{recent}} + S_{\text{contacts}} + S_{\text{careers}}\right)$$
* **$S_{\text{vacancies}}$ (Open Roles)**: $15\text{ pts}$ per active vacancy (up to $45\text{ pts}$).
* **$S_{\text{persistent}}$ (Hiring Friction)**: $+20\text{ pts}$ if any vacancy has been open $\ge 30\text{ days}$ (indicating difficulty finding talent locally).
* **$S_{\text{recent}}$ (Recency Bonus)**: $+15\text{ pts}$ if a new vacancy was detected within the last $14\text{ days}$.
* **$S_{\text{contacts}}$ (Decision Maker Verified)**: $+20\text{ pts}$ for a verified email contact, $+10\text{ pts}$ for an unverified contact.
* **$S_{\text{careers}}$ (Career Portal Active)**: $+10\text{ pts}$ for a functional career URL.

---

### 🎯 Phase 3: Talent Reverse Matching & AI Outreach Engine

Phase 3 flipped the traditional hiring script: instead of asking employers to post a job and wait, GrowthOS starts with **Kodafriq's ready talent** and pitches them directly to matching employers.

#### 1. Reverse Matching Engine (`apps/growth_os/services/matcher.py`)
* Compares an employer's open `HiringSignal` records and industry vertical against Kodafriq's `CandidateProfile` database.
* Evaluates skill overlap, verified certifications (e.g., AAPC, AHIMA, AWS Certified Solutions Architect), remote readiness score, and candidate availability.
* Creates `TalentReverseMatch` records with dynamic compatibility scores ($45-98\%$) and explicit matching rationales.

#### 2. AI-Powered Outreach Generator (`apps/growth_os/services/outreach_generator.py`)
* Generates hyper-tailored 3-step outreach email and LinkedIn InMail cadences:
  * **Step 1 (The Value Hook)**: Acknowledges the employer’s specific open vacancy (e.g., *"Noticed your search for a Senior Medical Coder open for 42 days..."*), introduces 2 top pre-vetted candidates by first name and certification, and links to their public shortlist dossier.
  * **Step 2 (The Case Study Follow-up)**: Dispatched 4 days later if no reply; shares metrics on Kodafriq's accuracy rates, 14-day placement guarantee, and cost savings ($40-60\%$).
  * **Step 3 (The Break-up / Final Touch)**: Dispatched 7 days later; offering a final check-in before archiving the opportunity.

#### 3. Staff Review & Approval Queue (`/growth-os/outreach/`)
* **Human-in-the-Loop Safeguard**: Generated outreach pitches are never sent blindly. They are placed in an interactive review queue where staff can edit subject lines, refine pitch copy, approve and dispatch, or reject messages.

#### 4. Secure Public Shortlist Dossier (`/growth-os/shortlist/<uuid>/`)
* A polished, employer-facing candidate presentation link that can be shared via email or LinkedIn.
* Employers can view candidate qualifications, experience, skills, and anonymous performance metrics without accessing full personally identifiable information (PII).
* Includes a direct **"Interview This Candidate"** inquiry button that notifies Kodafriq staff instantly.

---

### 📊 Phase 4: Interactive Kanban Pipeline & Conversion Engine

Phase 4 provided full sales CRM pipeline visualization, commercial stage tracking, and one-click lead-to-client conversion.

#### 1. 10-Stage Interactive Kanban Pipeline (`/growth-os/pipeline/`)
* Visual drag-and-drop Kanban board spanning the entire enterprise sales lifecycle:
  1. `Stage 1: Discovered / Sourced`
  2. `Stage 2: Career Scanned & Intent Qualified`
  3. `Stage 3: Talent Reverse-Matched`
  4. `Stage 4: Outreach Approved & Dispatched`
  5. `Stage 5: Prospect Engaged / In Discussion`
  6. `Stage 6: Discovery / Candidate Presentation Meeting`
  7. `Stage 7: Candidate Interview Scheduled`
  8. `Stage 8: Contract & Pricing Proposal Sent`
  9. `Stage 9: In Final Commercial Negotiation`
  10. `Stage 10: Closed Won & Placed` (or `Closed Lost`)
* **Real-time AJAX Stage Dragging**: Dropping a card in a new lane updates `CRMOpportunity.stage`, logs a `CRMActivity` entry, and calculates updated pipeline metrics instantly.

#### 2. Follow-Up Scheduling & Overdue Alerts
* Staff can set `next_follow_up_date` on any opportunity.
* Kanban cards automatically highlight overdue follow-ups in red amber badges, ensuring no enterprise lead slips through the cracks.

#### 3. One-Click Lead Conversion Engine (`/growth-os/leads/<id>/convert/`)
* Converts a prospect in `STAGE_10_PLACEMENT_WON` into a paying platform customer in a single atomic transaction:
  * Creates or links a Kodafriq `User` account and `EmployerProfile`.
  * Generates a formal `Contract` record with agreed candidate billing terms (Hourly rate, weekly hours limit, Kodafriq 10% platform markup, and legal scope).
  * Updates `EmployerLead.status` to `CONVERTED` and references the new client profile.

---

### ⚙️ Phase 5: Autonomous Continuous Acquisition & Ecosystem Automation

Phase 5 transformed GrowthOS from a staff-assisted tool into a self-driving background engine that continuously monitors market hiring signals, maintains data hygiene, connects to external job APIs, and delivers executive intelligence.

#### 1. Multi-Source Sourcing Connectors & Registry
* **Structured Connectors (`apps/growth_os/services/connectors/`)**:
  * `LinkedInJobsConnector`: Extracts live job openings, hiring companies, and location data from public LinkedIn job feeds across healthcare, engineering, and finance verticals.
  * `IndeedJobsConnector`: Discovers hiring signals from structured Indeed search feeds and employer company profiles.
  * `Unified Connector Registry (`registry.py`)`: `search_all_connectors(query, location, limit_per_source, source_key)` coordinates searches across all connectors simultaneously, normalizes lead schemas, and deduplicates organizations by canonical domain.
* **Discovery Hub Multi-Channel Filter**: Staff can search all sourcing channels simultaneously or filter specifically for LinkedIn or Indeed.

#### 2. Automated Vacancy Polling, Aging & Persistent Demand Flagging
* Function: `poll_and_age_vacancies(crawl=False, performed_by=None)`
* Re-evaluates every active `HiringSignal` in the database:
  * Computes `days_open = (today - date_detected).days + 1`.
  * Automatically marks roles open $\ge 30\text{ days}$ as `is_persistent=True` (signaling persistent recruitment difficulty and willingness to pay premium placement fees).
  * Automatically expires and closes vacancies open $>90\text{ days}$ without activity.
  * Optionally executes active career page crawling on tracked leads.
  * Recalculates Hiring Intent Scores for all affected employers.

#### 3. Algorithmic Hiring Intent Degradation
* Function: `apply_hiring_intent_decay(days_stale=30, performed_by=None)`
* Stale leads (leads with zero active open vacancies and no updates in $30+\text{ days}$) have their `hiring_intent_score` decayed by $10\%$.
* Prevents inactive companies from permanently occupying Tier 1 priority queues.

#### 4. Automated Dormant Lead Archiving
* Function: `archive_dormant_leads(days_threshold=90, performed_by=None)`
* Safely transitions leads older than $90\text{ days}$ with zero open vacancies, no CRM touches in $60\text{ days}$, and intent scores $<25\%$ into `EmployerLead.Status.ARCHIVED`.
* Automatically logs a formal audit note in `CRMActivity`.

#### 5. Real-Time Candidate Availability & Contract Signal Sync
* Receiver Hook: [`apps/growth_os/signals.py`](file:///wsl.localhost/Ubuntu/home/kinghez/kodafriq/apps/growth_os/signals.py)
* Automatically listens to `post_save` on `CandidateProfile` and `Contract`:
  * If a candidate's availability changes to `NOT_LOOKING` or if they sign an `ACTIVE` contract, GrowthOS automatically removes them from active employer pitch shortlists (`is_shortlisted=False`) and recalculates employer talent fit scores.
  * If a candidate becomes available, the system scans relevant open vacancies and generates fresh reverse matches.

#### 6. Weekly BD Executive Digest & Commercial Pipeline Report
* Function: `generate_weekly_bd_digest()` & `send_weekly_bd_digest_email()`
* Computes 7-day executive KPIs:
  * New leads sourced by sector (Healthcare, IT/Software, Finance).
  * Active persistent vacancies ($\ge 30\text{ days}$).
  * Tier 1 High-Intent leads ready for outreach.
  * Personalized outreach volume and prospect response rate.
  * Active pipeline value ($/month) and newly won MRR.
  * Overdue CRM follow-ups requiring staff attention.
* Dispatches a branded HTML digest email to staff and executives.

#### 7. Automation Command Center & Reports Dashboards
* **Automation Dashboard (`/growth-os/automation/`)**:
  * Displays total automated executions, evaluated items, and update counters.
  * Provides one-click maintenance triggers: *Run Full Maintenance*, *Poll Vacancies*, *Apply Intent Decay*, *Archive Dormant Leads*, *Sync Candidate Pool*.
  * Full audit trail backed by the `GrowthAutomationLog` model.
* **Executive Reports View (`/growth-os/reports/`)**:
  * In-browser executive report with printable CSS layout and one-click email dispatch.

#### 8. Background Management Commands
```bash
# Run full ecosystem maintenance (vacancy aging, intent decay, dormant archiving)
python manage.py run_growth_automation --task=all

# Run vacancy poller with live career page web crawl
python manage.py run_growth_automation --task=poll_vacancies --crawl

# Test / print weekly commercial digest to console without dispatching email
python manage.py send_growth_weekly_digest --dry-run

# Dispatch weekly commercial digest email to staff or specific recipient
python manage.py send_growth_weekly_digest --email=ceo@kodafriq.com
```

---

## 🗺️ 4. Complete URL Route Map

| URL Path | View Class | Purpose | Permissions |
| :--- | :--- | :--- | :--- |
| `/growth-os/` | `GrowthOSDashboardView` | Executive command center & macro KPIs | Staff Required |
| `/growth-os/pipeline/` | `PipelineKanbanView` | 10-Stage interactive visual sales Kanban | Staff Required |
| `/growth-os/pipeline/update-stage/` | `PipelineUpdateStageAjaxView` | Drag-and-drop AJAX stage transition | Staff Required |
| `/growth-os/leads/` | `EmployerLeadListView` | Lead directory with multi-sector filters | Staff Required |
| `/growth-os/leads/add/` | `EmployerLeadCreateView` | Manual creation of employer lead | Staff Required |
| `/growth-os/leads/<uuid:pk>/` | `EmployerLeadDetailView` | Full lead dossier, vacancies & contacts | Staff Required |
| `/growth-os/leads/<uuid:pk>/edit/` | `EmployerLeadUpdateView` | Edit employer lead details | Staff Required |
| `/growth-os/leads/<uuid:pk>/convert/` | `LeadConvertView` | 1-Click lead-to-client contract engine | Staff Required |
| `/growth-os/leads/<uuid:pk>/scan-careers/` | `LeadScanCareersView` | Manual career crawl & signal scrape | Staff Required |
| `/growth-os/leads/<uuid:pk>/recalculate/` | `EmployerLeadRecalculateScoresView` | Recalculate intent and fit scores | Staff Required |
| `/growth-os/leads/<id>/contacts/add/` | `LeadContactCreateView` | Add executive/decision-maker contact | Staff Required |
| `/growth-os/contacts/<uuid:pk>/delete/` | `LeadContactDeleteView` | Delete lead contact | Staff Required |
| `/growth-os/leads/<id>/vacancies/add/` | `HiringSignalCreateView` | Log detected job opening | Staff Required |
| `/growth-os/vacancies/<uuid:pk>/toggle/` | `HiringSignalToggleView` | Toggle vacancy active/closed state | Staff Required |
| `/growth-os/leads/<id>/activities/add/` | `CRMActivityCreateView` | Record call, note, meeting, or email | Staff Required |
| `/growth-os/leads/<id>/activities/quick-log/` | `QuickActivityLogView` | Rapid activity log with follow-up date | Staff Required |
| `/growth-os/discovery/` | `EmployerDiscoveryHubView` | Multi-source discovery search console | Staff Required |
| `/growth-os/discovery/import/` | `DiscoveryLeadImportView` | Ingest single or bulk discovered leads | Staff Required |
| `/growth-os/leads/import/` | `EmployerLeadCSVImportView` | Upload CSV lead spreadsheets | Staff Required |
| `/growth-os/leads/import/sample-csv/` | `DownloadSampleCSVView` | Download standard sample CSV template | Staff Required |
| `/growth-os/outreach/` | `OutreachQueueView` | Human-in-the-loop review/approval queue | Staff Required |
| `/growth-os/leads/<id>/outreach/generate/`| `OutreachGenerateView` | Generate 3-step AI outreach cadence | Staff Required |
| `/growth-os/outreach/<uuid:pk>/approve/` | `OutreachApproveSendView` | Approve & dispatch outreach message | Staff Required |
| `/growth-os/outreach/<uuid:pk>/reject/` | `OutreachRejectView` | Reject drafted pitch | Staff Required |
| `/growth-os/outreach/<uuid:pk>/reply/` | `OutreachRecordReplyView` | Log prospect email/message response | Staff Required |
| `/growth-os/shortlist/<uuid:pk>/` | `PublicCandidateShortlistView` | Public candidate pitch presentation | Public Access |
| `/growth-os/shortlist/<uuid:pk>/inquire/` | `PublicShortlistInquireView` | Employer interview inquiry submission | Public Access |
| `/growth-os/automation/` | `GrowthAutomationDashboardView` | Automation controls & execution history | Staff Required |
| `/growth-os/reports/` | `GrowthExecutiveDigestReportView`| 7-Day BD commercial performance digest | Staff Required |

---

## 🗄️ 5. Database Schema & Migration History

```
apps/growth_os/migrations/
├── 0001_initial.py
│   Scaffolded EmployerLead, LeadContact, HiringSignal, TalentReverseMatch,
│   CRMOpportunity, and CRMActivity.
├── 0002_employerlead_converted_at_and_more.py
│   Added converted_employer_profile OneToOneField and conversion timestamp.
├── 0003_outreachmessage_sequence_step.py
│   Added sequence_step (1, 2, 3) to OutreachMessage for cadence tracking.
└── 0004_alter_employerlead_source_alter_employerlead_status_and_more.py
    Added LINKEDIN_JOBS, INDEED_JOBS, and GLASSDOOR sources; added ARCHIVED status;
    created GrowthAutomationLog model for background task audit trails.
```

---

## 🧪 6. Comprehensive Verification & Test Results

The GrowthOS test suite in [`apps/growth_os/tests.py`](file:///wsl.localhost/Ubuntu/home/kinghez/kodafriq/apps/growth_os/tests.py) covers model business logic, scoring formulas, scrapers, discovery connectors, AI outreach generation, Kanban transitions, one-click conversions, and Phase 5 background automations:

```bash
$ python manage.py test apps.growth_os
Creating test database for alias 'default'...
.............................................
----------------------------------------------------------------------
Ran 45 tests in 218.639s

OK
Destroying test database for alias 'default'...
```

**Test Coverage Highlights**:
* `GrowthOSModelTests`: Domain normalization, intent recalculation, priority tier determination.
* `GrowthOSScraperAndIntentTests`: Keyword extraction across medical coding, cloud, and engineering; intent score weights.
* `GrowthOSDiscoveryTests`: Lead deduplication, CSV bulk ingestion, missing field handling.
* `GrowthOSReverseMatchingTests`: Talent compatibility calculation, skill matching, readiness filtering.
* `GrowthOSOutreachGeneratorTests`: 3-Step cadence generation, token substitution, human approval state machine.
* `GrowthOSPublicShortlistTests`: Public shortlist rendering, security/PII sanitization, interview inquiry logging.
* `GrowthOSPhase4KanbanTests`: Kanban board data structure, AJAX stage transitions, follow-up alerts, 1-click conversion to `EmployerProfile` and `Contract`.
* `GrowthOSPhase5AutomationTests`: Vacancy aging, persistent vacancy detection ($\ge 30\text{ days}$), stale intent degradation, dormant lead archiving ($>90\text{ days}$), real-time candidate availability sync, multi-source connector registry, and management command execution.

---

## 🚀 7. Production Deployment Runbook (Hostinger VPS)

To deploy the latest GrowthOS codebase on the production Hostinger VPS:

1. **Access the VPS Terminal**:
   ```bash
   cd /var/www/kodafriq
   source venv/bin/activate
   ```
2. **Pull the Latest Commit**:
   ```bash
   git pull origin main
   ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Apply Database Migrations**:
   ```bash
   python manage.py migrate
   ```
5. **Collect Static Assets**:
   ```bash
   python manage.py collectstatic --noinput
   ```
6. **Restart Application Services**:
   ```bash
   systemctl restart kodafriq
   ```
7. **Schedule Daily Maintenance via Crontab** (Optional):
   ```bash
   crontab -e
   ```
   Add the following line to execute GrowthOS automated maintenance every morning at 03:00 AM UTC:
   ```cron
   0 3 * * * /var/www/kodafriq/venv/bin/python /var/www/kodafriq/manage.py run_growth_automation --task=all >> /var/log/growth_os_automation.log 2>&1
   0 8 * * 1 /var/www/kodafriq/venv/bin/python /var/www/kodafriq/manage.py send_growth_weekly_digest >> /var/log/growth_os_digest.log 2>&1
   ```

---

*Authored by the Google Antigravity Agentic AI Team for Kodafriq Core Engineering.*
