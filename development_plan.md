# 🏥 KODAFRIQ DATA MANAGEMENT SOLUTIONS
## Digital Healthcare Talent Verification & Employer Matching Platform
### Comprehensive Technical Architecture, Product Specification & Development Roadmap

---

## 📌 Executive Summary

**Kodafriq Data Management Solutions**, led by **Eugenia Gomoawa Tawiah** (Managing Director / Founder & Product Lead), is establishing a premier digital platform designed to bridge the trust and verification gap between healthcare professionals and medical employers/facilities.

Initial vertical focus:
- **Medical Coding** (ICD-10-CM, CPT, HCPCS, DRG, Inpatient & Outpatient Coding, Risk Adjustment)
- **Medical Billing & Claims Processing**
- **Revenue Cycle Management (RCM)** (Denial Management, Accounts Receivable, Insurance Verification)

Rather than functioning as an unverified CV database or simple job board, **Kodafriq** operates as a verifiable talent intelligence platform where healthcare professionals prove competency through structured profiles, proctored/timed assessments, verifiable credentials, and training records, yielding a standardized **Kodafriq Verified Score**.

---

## 🎯 Target User Personas & Core Journeys

| Role | Primary Objectives | Key Capabilities |
| :--- | :--- | :--- |
| **Healthcare Candidate** | Build a credible, employer-ready professional identity | • Register & complete verified profile<br>• Self-report skills & submit verification evidence<br>• Take timed domain assessments (ICD-10, CPT, RCM)<br>• Track Kodafriq Verified Score (0–100%)<br>• Browse jobs & receive employer invitations |
| **Healthcare Employer** | Source certified, tested, and reliable healthcare talent | • Register company & undergo Kodafriq accreditation<br>• Search & filter candidates by verified skills & scores<br>• Review anonymous/standardized candidate portfolios<br>• Post job vacancies with strict skill prerequisites<br>• View match suitability score (%) & shortlist/hire |
| **Kodafriq Administrator** | Maintain platform integrity, assessment rigor, and growth | • Review & approve employer registrations<br>• Verify candidate skill evidence & assign *Kodafriq Verified* status<br>• Manage assessment questions, time limits, and passing marks<br>• Configure weights for the Verified Score engine<br>• Track training programs, certifications, and export reports |

---

## 🎨 Design System & UI Aesthetics

To deliver an ultra-premium, high-profile software product that rivals global SaaS platforms:

### 1. Color Palette Tokens
- **Primary / Brand Navy**: `#0A1128` / `#090E1A` (Deep executive background)
- **Surface Dark Slate**: `#0F172A` / `#1E293B` (Layered cards and sidebars)
- **Brand Electric Cyan**: `#00D2D3` / `#0EA5E9` (Interactive actions, focal points)
- **Healthcare Emerald**: `#10B981` (Verified trust badges, success indicators)
- **Warm Amber**: `#F59E0B` (Assessed / In-progress status)
- **Subtle Slate Border**: `rgba(255, 255, 255, 0.08)` / `#334155`
- **Text Crisp White**: `#F8FAFC` & **Muted Text**: `#94A3B8`

### 2. Typography & Hierarchy
- **Primary Font**: `Plus Jakarta Sans` via Google Fonts
- **Monospace/Numeric Font**: `Space Grotesk` (for scores, assessment timers, and medical codes)

### 3. Visual Components & Polish
- **Glow & Glassmorphism**: Frosted glass navigation headers with subtle backdrop blur (`backdrop-filter: blur(12px)`).
- **Verified Seal Badge**: Shimmering emerald badge with shield checkmark.
- **Score Radial / Circular Gauge**: Dynamic circular SVG progress indicating Kodafriq Verified Score (0–100%).
- **Skill 3-Tier Status Pills**:
  - `Self-Reported`: Neutral slate with outline badge.
  - `Assessed`: Sky blue / amber badge with lightning icon.
  - `Kodafriq Verified`: Vibrant emerald badge with certified shield checkmark.

---

## 🏗️ Technical Architecture & Stack

- **Backend Framework**: Django 5.x / 6.1 (Python 3.12)
- **Frontend Architecture**: Modern Server-Rendered Django Templates enhanced with CSS Custom Properties, Vanilla JavaScript components (instant SSR performance, zero SPA bloat, full SEO friendliness, clean accessibility).
- **Database**: PostgreSQL / SQLite for rapid development and production scalability.
- **Media & Evidence Storage**: Secure file handling for resumes, certificates, and employer verifications.
- **Export Engine**: `openpyxl` & `csv` for operational and executive reporting.

---

## 📊 Core Data Entities & Schema

1. **`User`** (`AbstractUser`):
   - `email`, `role` (`CANDIDATE`, `EMPLOYER`, `ADMIN`), `is_email_verified`, `created_at`.
2. **`CandidateProfile`**:
   - `user`, `headline`, `bio`, `phone`, `location`, `years_of_experience`, `availability_status`, `desired_salary_range`, `kodafriq_verified_score`, `is_employer_ready`.
3. **`EmployerProfile`**:
   - `user`, `company_name`, `industry`, `website`, `contact_person_title`, `company_size`, `approval_status` (`PENDING`, `APPROVED`, `REJECTED`).
4. **`SkillCategory` & `Skill`**:
   - `name` (e.g., ICD-10-CM, CPT, HCPCS, DRG, Denial Management), `code_standard`, `category`, `description`.
5. **`CandidateSkill`**:
   - `candidate`, `skill`, `status` (`SELF_REPORTED`, `ASSESSED`, `KODAFRIQ_VERIFIED`), `evidence_file`, `verified_by`, `verified_at`.
6. **`Assessment`**:
   - `category`, `primary_skill`, `title`, `duration_minutes`, `pass_mark_percentage`, `is_active`.
7. **`Question` & `AnswerChoice`**:
   - `assessment`, `prompt`, `explanation`, choices with `is_correct`.
8. **`AssessmentAttempt` & `CandidateResponse`**:
   - `candidate`, `assessment`, `score_percentage`, `passed`, `started_at`, `completed_at`.
9. **`ScoreWeightConfig` & `ScoreLog`**:
   - Dynamic weight configuration:
     - Assessment Performance: **40%**
     - Work Performance: **25%**
     - Training: **15%**
     - Professional Experience: **10%**
     - Professional Readiness: **10%**
10. **`TrainingProgram` & `TrainingEnrolment`**:
    - Program curriculum, duration, attendance tracking, completion records, certificate issuance.
11. **`Job` & `JobRequiredSkill`**:
    - `employer`, `title`, `job_type`, `min_years_experience`, `min_score_required`, `status`.
12. **`Application` & `Shortlist`**:
    - `job`, `candidate`, `match_percentage`, `status` (`APPLIED`, `REVIEWED`, `SHORTLISTED`, `INTERVIEW`, `OFFERED`, `REJECTED`).
13. **`AuditLog`**:
    - Administrative approval trails, score recalculation logs, and verification history.

---

## 🧮 Kodafriq Verified Score Calculation Formula

$$\text{Verified Score} = (S_{\text{assess}} \times 0.40) + (S_{\text{work}} \times 0.25) + (S_{\text{train}} \times 0.15) + (S_{\text{exp}} \times 0.10) + (S_{\text{ready}} \times 0.10)$$

Where:
- $S_{\text{assess}}$: Average percentage obtained across passed domain assessments (0–100).
- $S_{\text{work}}$: Verified work review/manager rating evidence (0–100).
- $S_{\text{train}}$: Completed Kodafriq or accredited training programs (0–100).
- $S_{\text{exp}}$: Scaled score based on verified clinical/billing years of experience (0–100).
- $S_{\text{ready}}$: Professional readiness indicators (profile completeness, communication, background check status) (0–100).

---

## 🤝 Rule-Based Employer Matching Algorithm

The platform calculates a **Match Suitability Score (0–100%)** between a candidate and an open job:

$$\text{Match \%} = (\text{Skills Match Ratio} \times 0.50) + (\text{Experience Match Ratio} \times 0.25) + (\text{Verified Score Ratio} \times 0.25)$$

---

## 📅 Project Phases & Interactive Development Checklist

### Phase 1: Project Kickoff, Architecture & Core Setup
- [x] **Task 1.1**: Initialize Django project (`config`) and modular app architecture (`core`, `accounts`, `skills`, `assessments`, `scoring`, `employers`, `training`, `dashboard`).
- [x] **Task 1.2**: Configure environment settings, database configuration, static files, and media directories.
- [x] **Task 1.3**: Design and implement the global UI Design System (`kodafriq.css`, Google Fonts Plus Jakarta Sans, dark slate/navy theme, cyan & emerald accents, responsive navbar, and footer).
- [x] **Task 1.4**: Setup custom `User` model with role-based segregation (`CANDIDATE`, `EMPLOYER`, `ADMIN`).
- [x] **Task 1.5**: Populate initial 13 healthcare domain skills (ICD-10-CM, CPT, DRG, RCM) and default 5-component scoring weights.
- [x] **Task 1.6**: Build high-profile flagship landing page (`templates/core/home.html`) showcasing verified talent cards, score gauges, and healthcare sectors.

### Phase 2: Candidate Profile & Structured Portfolio Engine
- [x] **Task 2.1**: Implement Candidate Dashboard with profile completion progress bar and readiness checklist.
- [x] **Task 2.2**: Develop multi-step profile builder (Personal Info, Employment History, Education, AAPC/AHIMA Certifications).
- [x] **Task 2.3**: Candidate public "Kodafriq Verified Talent Card" with privacy safeguards.
- [x] **Task 2.4**: Candidate resume upload and document management.

### Phase 3: Healthcare Skills & 3-Tier Verification Workflow
- [x] **Task 3.1**: Candidate skill management interface (add skills, select proficiency level, self-report).
- [x] **Task 3.2**: Evidence submission portal (upload certification, supervisory letters, billing audits).
- [x] **Task 3.3**: Admin Verification Queue with document preview, approval, rejection notes, and status promotion to `Kodafriq Verified`.
- [x] **Task 3.4**: Verification history log and audit trail.

### Phase 4: Assessment Engine (Timed MCQs, Auto-Scoring & Randomization)
- [x] **Task 4.1**: Assessment question bank with medical coding and RCM clinical scenarios.
- [x] **Task 4.2**: Candidate Assessment Hub with test catalog, guidelines, and attempt limits.
- [x] **Task 4.3**: Timed exam interface with real-time countdown timer, question navigation, and auto-submit on timeout.
- [x] **Task 4.4**: Real-time auto-grading engine recording attempt timestamps, percentage, and pass/fail status.
- [x] **Task 4.5**: Automatic candidate skill upgrade to `Assessed` upon passing assessment.

### Phase 5: Kodafriq Verified Score Engine & Analytics
- [x] **Task 5.1**: Build dynamic score calculation service executing the weighted formula.
- [x] **Task 5.2**: Admin Score Weighting configuration panel to calibrate component weights in real time.
- [x] **Task 5.3**: Animated circular SVG score gauge on candidate dashboard with breakdown drawer.
- [x] **Task 5.4**: Historical score progression logs.

### Phase 6: Employer Portal & Talent Discovery
- [x] **Task 6.1**: Employer registration and company verification workflow.
- [x] **Task 6.2**: Admin employer review and approval queue.
- [x] **Task 6.3**: Advanced Talent Search & Filter engine (filter by verified skill, minimum score, experience level, readiness).
- [x] **Task 6.4**: Employer Candidate Dossier view with skills radar and verification badges.
- [x] **Task 6.5**: Shortlisting and candidate talent pool management.

### Phase 7: Job Postings, Application Pipeline & Match Engine
- [x] **Task 7.1**: Employer Job Posting interface with skill requirements and experience thresholds.
- [x] **Task 7.2**: Candidate Job Discovery and one-click application engine.
- [x] **Task 7.3**: Rule-based matching engine calculating candidate suitability percentage for jobs.
- [x] **Task 7.4**: Employer Application Tracking pipeline (Applied, Reviewed, Shortlisted, Interviewing, Offered).

### Phase 8: Healthcare Training & Certification Tracking
- [x] **Task 8.1**: Admin Training Program management (curriculum, schedule, prerequisites).
- [x] **Task 8.2**: Candidate program enrollment, attendance tracking, and completion records.
- [x] **Task 8.3**: Verifiable digital certificate generation with unique Kodafriq Certificate IDs.

### Phase 9: Admin Command Center, Moderation & Analytics
- [ ] **Task 9.1**: Executive Admin KPI Dashboard (total candidates, verified percentage, active jobs, employer placements).
- [ ] **Task 9.2**: Score distribution charts and assessment pass rate analytics.
- [ ] **Task 9.3**: Multi-entity search and moderation controls.
- [ ] **Task 9.4**: One-click CSV and Excel data exports for platform reporting.

### Phase 10: Notifications, Security Hardening & Audit Logging
- [ ] **Task 10.1**: In-app notifications center with unread counters.
- [ ] **Task 10.2**: Email notification triggers (registration verification, assessment results, employer interest, verification approvals).
- [ ] **Task 10.3**: Audit logging tracking administrative approvals and score adjustments.
- [ ] **Task 10.4**: Role-based access control (RBAC) decorators and permission checks.

### Phase 11: Production Polish, QA Testing & Handover
- [ ] **Task 11.1**: End-to-end user testing across Candidate, Employer, and Admin workflows.
- [ ] **Task 11.2**: Performance optimization and asset minification.
- [ ] **Task 11.3**: Seed demo data (sample candidates, verified skills, assessments, jobs, and employer accounts).
- [ ] **Task 11.4**: Source code packaging, environment documentation, and handover package for Eugenia & the Kodafriq team.

---

## 🏆 MVP Completion & Acceptance Criteria

The platform is officially deemed production-ready and complete when:
1. Candidate can register, build structured profile, upload credentials, and view verified status.
2. Candidate can complete timed domain assessments with instant scoring and record updates.
3. Employer can register, get verified, search verified talent via multi-parameter filters, and post jobs.
4. Matching engine calculates candidate suitability percentage for jobs.
5. Admin can moderate users, assign *Kodafriq Verified* status, adjust scoring weights, and export data.
6. Responsive, premium UI renders seamlessly across desktop, tablet, and mobile devices.
