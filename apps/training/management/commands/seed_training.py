from django.core.management.base import BaseCommand
from apps.skills.models import Skill, SkillCategory
from apps.training.models import TrainingProgram, ProgramModule

class Command(BaseCommand):
    help = "Seed accredited healthcare training programs and clinical modular lessons"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding Kodafriq Accredited Training Programs..."))

        # Fetch or create skill categories
        cat_coding, _ = SkillCategory.objects.get_or_create(name="Clinical Coding")
        cat_billing, _ = SkillCategory.objects.get_or_create(name="Billing & Revenue Cycle")
        cat_comp, _ = SkillCategory.objects.get_or_create(name="Compliance & Informatics")

        # Fetch or create core skills
        skill_icd, _ = Skill.objects.get_or_create(name="ICD-10-CM Coding", defaults={"category": cat_coding, "code_standard": "ICD-10-CM"})
        skill_cpt, _ = Skill.objects.get_or_create(name="CPT Coding", defaults={"category": cat_coding, "code_standard": "CPT"})
        skill_rcm, _ = Skill.objects.get_or_create(name="Revenue Cycle Management (RCM)", defaults={"category": cat_billing, "code_standard": "RCM"})
        skill_hipaa, _ = Skill.objects.get_or_create(name="HIPAA Compliance", defaults={"category": cat_comp, "code_standard": "HIPAA"})

        programs_data = [
            {
                "title": "Advanced Inpatient ICD-10-CM & MS-DRG Clinical Optimization",
                "instructor": "Dr. Chioma Adeyemi, MD, CCS, CCDS",
                "duration_weeks": 6,
                "description": "Comprehensive inpatient clinical coding accreditation program focusing on principal diagnosis designation, Complication/Comorbidity (CC/MCC) capture, and Medicare Severity Diagnosis Related Group (MS-DRG) reimbursement alignment.",
                "curriculum_overview": "4 interactive modules covering official inpatient coding guidelines, acute organ dysfunction capture, surgical hierarchy grouping, and hospital-acquired condition reporting.",
                "skills": [skill_icd],
                "modules": [
                    {
                        "order": 1,
                        "title": "Principal Diagnosis Selection & Official Guidelines (Section II)",
                        "duration_minutes": 50,
                        "content": """The Uniform Hospital Discharge Data Set (UHDDS) defines the Principal Diagnosis as: 'that condition established after study to be chiefly responsible for occasioning the admission of the patient to the hospital.'

Key Clinical Principles:
1. Two or More Conditions Meeting Principal Definition: When two or more interrelated conditions each potentially meet the definition of principal diagnosis, either may be sequenced first unless therapy was directed primarily to one.
2. Symptoms vs Definite Diagnosis: Codes for symptoms, signs, and ill-defined conditions from Chapter 18 are NOT to be used as principal diagnosis when a related definitive diagnosis has been established.
3. Admissions Following Outpatient Surgery: When a patient is admitted post-ambulatory surgery due to a surgical complication, the complication code is sequenced as principal diagnosis. If admitted for an unrelated condition, that condition is sequenced first.""",
                        "key_takeaways": "• Establish UHDDS criteria before reviewing chart.\n• Avoid symptom coding when underlying pathology is confirmed.\n• Query physician when documentation presents conflicting etiologies."
                    },
                    {
                        "order": 2,
                        "title": "CC and MCC Capture: Optimizing DRG Severity of Illness (SOI)",
                        "duration_minutes": 55,
                        "content": """Medicare Severity DRGs (MS-DRGs) partition inpatient admissions into three tiers based on secondary diagnoses:
1. With Major Complication or Comorbidity (MCC)
2. With Complication or Comorbidity (CC)
3. Without CC/MCC

Clinical Integrity Rules:
- Acute Kidney Injury (N17.9) qualifies as a CC; Stage 4/5 CKD (N18.4, N18.5) are CCs.
- Septic shock (R65.21) and Acute Respiratory Failure (J96.00) qualify as MCCs.
- Documentation must support clinical significance: evaluated, treated, diagnostic workup ordered, increased nursing care, or extended length of stay.""",
                        "key_takeaways": "• Secondary conditions require documented clinical intervention or monitoring.\n• Single secondary MCC can elevate the base payment rate by 30%–60%.\n• Always cross-reference the MS-DRG CC/MCC exclusion list."
                    },
                    {
                        "order": 3,
                        "title": "Surgical vs Medical DRG Grouping & OR Procedure Hierarchy",
                        "duration_minutes": 45,
                        "content": """MS-DRG assignment is fundamentally divided into Medical DRGs and Surgical DRGs:
- If an Operating Room (OR) procedure is reported, the case automatically groups into a Surgical DRG within the Major Diagnostic Category (MDC).
- When a patient has multiple OR procedures, the DRG assignment is dictated by the highest ranking procedure in the surgical hierarchy.
- Non-OR procedures (e.g. diagnostic bronchoscopy, bedside paracentesis) do not shift a medical case to surgical status unless designated as DRG-affecting.""",
                        "key_takeaways": "• Confirm whether procedure code is classified as Valid OR Procedure.\n• Surgical DRGs carry higher relative weights reflecting resource intensity.\n• Review operative reports for unexpected conversions or secondary procedures."
                    },
                    {
                        "order": 4,
                        "title": "Hospital-Acquired Conditions (HAC) & Present on Admission (POA)",
                        "duration_minutes": 40,
                        "content": """Under CMS guidelines, all secondary diagnoses on inpatient claims must include a Present on Admission (POA) indicator:
- Y = Present at the time order for inpatient admission occurs
- N = Not present at the time order for inpatient admission occurs (Hospital-Acquired)
- U = Documentation insufficient to determine
- W = Clinically undetermined

CMS Hospital-Acquired Condition (HAC) Reduction Program:
If a condition designated as a CMS HAC (e.g., catheter-associated UTI, stage III/IV pressure ulcer, surgical site infection) is flagged with POA = 'N', it is stripped of CC/MCC reimbursement weight. Accurate POA assignment protects hospital quality scores and prevents penalty adjustments.""",
                        "key_takeaways": "• Thoroughly review emergency department notes and admission H&P for baseline conditions.\n• POA = N denies CC/MCC payment boost.\n• Clinical documentation queries must be initiated if onset timing is ambiguous."
                    }
                ]
            },
            {
                "title": "Outpatient CPT Procedural Coding, Modifiers & E/M MDM Guidelines",
                "instructor": "Kwesi Mensah, CPC, COC, CPMA",
                "duration_weeks": 4,
                "description": "Master outpatient procedural coding, current AMA Evaluation & Management (E/M) medical decision making guidelines, and proper utilization of surgical and unbundling modifiers.",
                "curriculum_overview": "4 modular lessons covering MDM level determination, modifier 25/59 application, add-on codes, and surgical global period boundaries.",
                "skills": [skill_cpt],
                "modules": [
                    {
                        "order": 1,
                        "title": "2021/2023 Outpatient E/M Medical Decision Making (MDM) Scoring Matrix",
                        "duration_minutes": 50,
                        "content": """Under AMA E/M guidelines, code selection for office and other outpatient visits (99202–99215) is determined exclusively by Time or Medical Decision Making (MDM).

The Three MDM Elements (Requires 2 of 3):
1. Number and Complexity of Problems Addressed:
   - Low: 2 minor problems OR 1 stable chronic illness OR 1 acute uncomplicated illness.
   - Moderate (Level 4 - 99214): 1 or more chronic illnesses with mild exacerbation OR 2 or more stable chronic illnesses OR 1 undiagnosed new problem with uncertain prognosis.
   - High (Level 5 - 99215): 1 or more chronic illnesses with severe exacerbation OR 1 acute/chronic illness posing immediate threat to life.
2. Amount and/or Complexity of Data Reviewed:
   - Tests, unique sources, independent interpretation, discussions with external physician.
3. Risk of Complications and/or Morbidity/Mortality of Patient Management:
   - Moderate: Prescription drug management, decision regarding minor surgery with risk factors.
   - High: Decision regarding elective major surgery with risk factors, drug therapy requiring intensive monitoring for toxicity.""",
                        "key_takeaways": "• Select code level based on highest 2 out of 3 MDM categories.\n• Prescription drug management automatically meets Moderate Risk.\n• Document time when total duration exceeds typical MDM threshold."
                    },
                    {
                        "order": 2,
                        "title": "Modifier 25 & Modifier 59: Accurate Unbundling & NCCI Guidelines",
                        "duration_minutes": 50,
                        "content": """Modifier 25: Significant, Separately Identifiable E/M Service by the Same Physician on the Same Day of a Procedure:
- A minor procedure (0 or 10-day global) inherently includes a pre-, intra-, and post-procedure evaluation.
- To append Modifier 25 to an E/M service on the same date, the documentation must demonstrate that the assessment went significantly beyond the routine pre-procedure check.
- A separate diagnosis is NOT required, but distinct clinical decision-making must be documented.

Modifier 59 / X{EPSU}: Distinct Procedural Service:
- Appended only when two procedures billed together are designated as bundled under the National Correct Coding Initiative (NCCI) Procedure-to-Procedure (PTP) edits, but occurred at distinct anatomic sites, separate incisions, or separate patient encounters on the same date.""",
                        "key_takeaways": "• Never append Modifier 25 solely to bypass payer denial without distinct documentation.\n• Modifier 59 is the modifier of last resort; use XE, XP, XS, XU when appropriate.\n• Maintain independent clinical rationale in the clinical note."
                    },
                    {
                        "order": 3,
                        "title": "CPT Add-On Code Rules, Parent Codes & Sequencing",
                        "duration_minutes": 40,
                        "content": """Add-on codes (identified by the + symbol in CPT) describe additional work, extended duration, or supplementary anatomical sites:
Rules for Add-On Codes:
1. Cannot be reported as primary or stand-alone services; must always accompany an approved primary/parent CPT code.
2. Exempt from the Multiple Procedure Reduction rule (Modifier 51 exempt).
3. Do not accept Modifier 50 (Bilateral); bilateral add-on procedures use dedicated add-on codes or unit reporting according to AMA guidelines.""",
                        "key_takeaways": "• Always verify parent code compatibility before submitting add-on code.\n• Do not append Modifier 51 or Modifier 50 to add-on codes.\n• Verify unit limitations specified in payer guidelines."
                    },
                    {
                        "order": 4,
                        "title": "Surgical Global Packages: Modifiers 58, 78, and 79",
                        "duration_minutes": 45,
                        "content": """Surgical procedures carry 0-day, 10-day, or 90-day global periods covering all typical post-operative follow-up care:
- Modifier 58: Staged or related procedure by the same physician during the post-op period (e.g. planned debridement followed by delayed closure).
- Modifier 78: Unplanned return to operating room for a related procedure during the post-operative period (e.g. control of post-op hemorrhage in OR). Note: reimburses intra-operative portion only; does not reset global period.
- Modifier 79: Unrelated procedure by the same physician during post-operative period (e.g. cataract surgery on fellow eye during global period of first eye). Resets new global period.""",
                        "key_takeaways": "• Modifier 78 requires return to an operating or procedure room.\n• Modifier 79 requires an unrelated clinical condition.\n• Post-op global unbundling is a high-risk OIG audit focus area."
                    }
                ]
            },
            {
                "title": "Revenue Cycle Management, Denials Resolution & Clean Claims Mastery",
                "instructor": "Amina Al-Mansoor, CRCR, CHFP",
                "duration_weeks": 4,
                "description": "Essential financial and operational billing accreditation covering patient access, claim adjustment reason codes (CARC), timely filing appeals, and clean claim rate optimization.",
                "curriculum_overview": "4 modules breaking down eligibility verification, denial analysis, appeal writing, and revenue cycle key performance indicators.",
                "skills": [skill_rcm],
                "modules": [
                    {
                        "order": 1,
                        "title": "Front-End Patient Access, Eligibility & Prior Authorization",
                        "duration_minutes": 45,
                        "content": """Up to 40% of all billing denials originate in front-end patient registration and scheduling:
Core Prevention Workflows:
1. Real-Time Eligibility (RTE) Verification: Confirming active coverage, deductible balances, co-insurance, and primary vs secondary payer order (Coordination of Benefits COB).
2. Prior Authorization Tracking: Validating that high-cost radiology, surgical, and specialty drug orders have active pre-authorization numbers attached to the encounter prior to service delivery.
3. Demographic Precision: Strict matching of patient legal name, date of birth, and subscriber ID against payer databases to prevent CO-31 and CO-16 front-end rejections.""",
                        "key_takeaways": "• Verify insurance eligibility at scheduling and date of service.\n• Document pre-auth approval numbers in designated claim fields (Box 23).\n• Ensure Coordination of Benefits order is confirmed annually."
                    },
                    {
                        "order": 2,
                        "title": "CARC & RARC Denial Root Cause Analysis",
                        "duration_minutes": 50,
                        "content": """Standard Remittance Advice (835) transactions communicate claim status using Claim Adjustment Reason Codes (CARC) and Remittance Advice Remark Codes (RARC):
Group Codes:
- CO (Contractual Obligation): Provider cannot bill the patient.
- PR (Patient Responsibility): Patient deductible, co-payment, or co-insurance.
- OA (Other Adjustment): Payer coordination adjustments.

Critical Denial Codes & Resolution:
- CO-16 (Claim lacks information): Resubmit with requested clinical documentation or corrected NPI/modifier.
- CO-18 (Duplicate claim): Audit for identical submission dates; verify adjustment/void submission standards.
- CO-97 (Bundled procedure): Review NCCI edit tables; verify if distinct anatomical site justifies unbundling modifier.""",
                        "key_takeaways": "• Group codes determine whether balance can be billed to patient.\n• Group denial trends by root cause rather than resolving line-by-line.\n• Track denial appeal turnaround times by payer."
                    },
                    {
                        "order": 3,
                        "title": "Timely Filing Limits, Appeals & Payer Grievance Protocols",
                        "duration_minutes": 45,
                        "content": """Commercial payers enforce timely filing limits ranging from 90 to 365 days from the date of service:
Appeals Framework:
1. First-Level Appeal: Re-submission with proof of timely filing (clearinghouse electronic acceptance report 999/277CA) and clinical chart documentation supporting medical necessity.
2. Second-Level Appeal: Peer-to-peer physician conference or formal written grievance addressing payer clinical policy bulletin guidelines.
3. External Review: Independent medical review organization adjudication for non-covered or experimental care disputes.""",
                        "key_takeaways": "• Clearinghouse 277CA acceptance reports serve as definitive proof of timely filing.\n• Structure appeal letters quoting specific payer medical policy criteria.\n• Log appeal deadlines in billing system work queues."
                    },
                    {
                        "order": 4,
                        "title": "Revenue Integrity Metrics: Clean Claim Rate & Days in A/R",
                        "duration_minutes": 40,
                        "content": """Industry-standard HFMA MAP Keys measure revenue cycle operational excellence:
1. Clean Claim Rate (CCR):
   $$\text{CCR} = \frac{\text{Claims Paid on First Submission}}{\text{Total Claims Submitted}} \times 100$$
   - Benchmark: $\\ge 95\%$
2. Days in Accounts Receivable (A/R Days):
   $$\text{Days in A/R} = \frac{\text{Total Accounts Receivable}}{\text{Average Daily Revenue}}$$
   - Benchmark: $< 35\text{ days}$
3. Aged A/R $> 90\text{ Days}$:
   - Benchmark: $< 15\%\text{ of total accounts receivable}$""",
                        "key_takeaways": "• Clean claim rate above 95% is the primary indicator of billing accuracy.\n• High aged A/R (>90 days) indicates denial backlogs or collection inefficiencies.\n• Monitor top denial reasons weekly in billing huddles."
                    }
                ]
            },
            {
                "title": "HIPAA Healthcare Privacy, HITECH Security & Clinical Record Compliance",
                "instructor": "Babatunde Okafor, JD, CHPS",
                "duration_weeks": 3,
                "description": "Comprehensive regulatory accreditation covering the Health Insurance Portability and Accountability Act (HIPAA), HITECH Act requirements, Business Associate agreements, and EHR security compliance.",
                "curriculum_overview": "4 modules covering the 18 PHI identifiers, minimum necessary rules, BAA requirements, and breach notification standards.",
                "skills": [skill_hipaa],
                "modules": [
                    {
                        "order": 1,
                        "title": "The 18 HIPAA Identifiers & Minimum Necessary Standard",
                        "duration_minutes": 45,
                        "content": """Under HIPAA Privacy Rule (45 CFR § 164.514), health information is classified as Protected Health Information (PHI) when linked to any of the 18 individual identifiers:
Names, geographic subdivisions smaller than a state, all dates (birth, admission, discharge), telephone numbers, fax numbers, email addresses, SSN, medical record numbers, health plan IDs, account numbers, certificate/license numbers, vehicle IDs, device identifiers/serials, URLs, IP addresses, biometric identifiers, full-face photos, any unique identifying number.

The Minimum Necessary Standard:
Covered entities and business associates must make reasonable efforts to limit access to PHI to the minimum necessary to accomplish the intended purpose of the use, disclosure, or request.""",
                        "key_takeaways": "• Data is PHI if it contains any of the 18 identifiers linked to health status.\n• The Minimum Necessary Standard applies to staff access and data transfers.\n• De-identification requires removing all 18 identifiers or expert statistical certification."
                    },
                    {
                        "order": 2,
                        "title": "Business Associate Agreements (BAA) & Subcontractor Liability",
                        "duration_minutes": 40,
                        "content": """A Business Associate (BA) is any individual or entity that creates, receives, maintains, or transmits PHI on behalf of a covered entity for a function or activity (e.g. medical coding firms, cloud billing vendors, IT support):
Under the HITECH Omnibus Rule:
1. Business Associates are directly liable under federal law for HIPAA Security Rule violations.
2. A formal Business Associate Agreement (BAA) must be executed BEFORE any PHI is disclosed or transmitted.
3. Downstream subcontractors hired by a Business Associate must sign identical BAA agreements and comply with all security controls.""",
                        "key_takeaways": "• Third-party billing and coding vendors must execute a BAA before accessing records.\n• Subcontractors are held to the same legal standards as primary business associates.\n• Failure to execute a BAA constitutes an actionable federal violation."
                    },
                    {
                        "order": 3,
                        "title": "HITECH Act 60-Day Breach Notification Protocols",
                        "duration_minutes": 45,
                        "content": """A breach is defined as the acquisition, access, use, or disclosure of unsecured PHI in a manner not permitted by the Privacy Rule which compromises the security or privacy of the data:
Breach Risk Assessment (Four Factors):
1. The nature and extent of the PHI involved (types of identifiers, risk of re-identification).
2. The unauthorized person who used or received the PHI.
3. Whether the PHI was actually acquired or viewed.
4. The extent to which the risk has been mitigated.

Notification Timelines:
- Individual Notification: Without unreasonable delay and in no case later than 60 calendar days after discovery.
- Breaches Affecting 500+ Individuals: Must notify prominent media outlets and the HHS Secretary within 60 days.
- Breaches Affecting <500 Individuals: Logged and reported to HHS annually within 60 days of the calendar year end.""",
                        "key_takeaways": "• Presume all unauthorized disclosures are breaches unless 4-factor assessment proves low probability of compromise.\n• 60 calendar days is the absolute outer statutory deadline for individual notification.\n• Breaches affecting 500+ individuals trigger public media and HHS disclosures."
                    },
                    {
                        "order": 4,
                        "title": "EHR Audit Logs, Remote Access Controls & Data Encryption",
                        "duration_minutes": 40,
                        "content": """The HIPAA Security Rule (45 CFR § 164.312) outlines Technical Safeguards required for electronic PHI (ePHI):
1. Access Controls: Unique user IDs, emergency access procedures, automatic logoff after inactivity.
2. Audit Controls: System-wide mechanisms that record and examine activity in information systems containing or using ePHI (who viewed, edited, deleted, or printed a chart).
3. Transmission Security & Encryption:
   - Data at Rest: Encrypted using AES-256 or equivalent.
   - Data in Transit: TLS 1.2 or higher over public networks.
   - End-User Remote Access: Multi-Factor Authentication (MFA) required for remote EHR/telehealth connections.""",
                        "key_takeaways": "• EHR access logs must be regularly audited for unauthorized snooping.\n• Encrypted data creates a safe harbor from breach notification requirements.\n• Multi-Factor Authentication is mandatory for remote coding and billing access."
                    }
                ]
            }
        ]

        for pdata in programs_data:
            program, created = TrainingProgram.objects.get_or_create(
                title=pdata["title"],
                defaults={
                    "instructor": pdata["instructor"],
                    "duration_weeks": pdata["duration_weeks"],
                    "description": pdata["description"],
                    "curriculum_overview": pdata["curriculum_overview"],
                    "is_active": True
                }
            )
            program.skills_covered.set(pdata["skills"])

            for mdata in pdata["modules"]:
                ProgramModule.objects.update_or_create(
                    program=program,
                    order=mdata["order"],
                    defaults={
                        "title": mdata["title"],
                        "duration_minutes": mdata["duration_minutes"],
                        "content": mdata["content"],
                        "key_takeaways": mdata["key_takeaways"]
                    }
                )

            status_str = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {status_str} program: '{program.title}' with {len(pdata['modules'])} modules"))

        self.stdout.write(self.style.SUCCESS("All 4 clinical training programs seeded successfully!"))
