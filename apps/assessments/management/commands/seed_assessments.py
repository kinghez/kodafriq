from django.core.management.base import BaseCommand
from apps.skills.models import SkillCategory, Skill
from apps.assessments.models import Assessment, Question, AnswerChoice

class Command(BaseCommand):
    help = 'Seeds realistic standardized clinical assessments and questions for Kodafriq'

    def handle(self, *args, **options):
        self.stdout.write('Seeding assessments and clinical questions...')

        # Ensure categories exist
        coding_cat, _ = SkillCategory.objects.get_or_create(
            name='Medical Coding',
            defaults={'description': 'Clinical diagnosis, procedure, and facility coding standards.', 'icon_name': 'code'}
        )
        billing_cat, _ = SkillCategory.objects.get_or_create(
            name='Billing & Revenue Cycle Management',
            defaults={'description': 'Healthcare billing, claims processing, and denial management.', 'icon_name': 'credit-card'}
        )
        comp_cat, _ = SkillCategory.objects.get_or_create(
            name='Compliance & Risk Adjustment',
            defaults={'description': 'HIPAA compliance, patient privacy, and risk adjustment coding.', 'icon_name': 'shield'}
        )

        icd_skill = Skill.objects.filter(code_standard='ICD-10-CM').first()
        cpt_skill = Skill.objects.filter(code_standard='CPT').first()
        billing_skill = Skill.objects.filter(code_standard='BILLING').first()
        if not billing_skill:
            billing_skill = Skill.objects.filter(category=billing_cat).first()

        # ----------------------------------------------------
        # 1. ICD-10-CM Medical Coding Assessment
        # ----------------------------------------------------
        icd_assessment, _ = Assessment.objects.update_or_create(
            title='ICD-10-CM Diagnosis Coding Assessment',
            defaults={
                'category': coding_cat,
                'primary_skill': icd_skill,
                'description': 'Evaluates inpatient and outpatient diagnosis sequencing, combo coding, acute vs. chronic condition rules, and AHA Coding Clinic guidelines.',
                'instructions': 'You have 30 minutes to complete 5 clinical case scenarios. Select the single best answer for each case. You must achieve >=75% to earn the Assessed status.',
                'duration_minutes': 30,
                'pass_mark_percentage': 75,
                'is_active': True,
            }
        )

        # Questions for ICD-10-CM
        icd_q_data = [
            {
                'order': 1,
                'prompt': 'A 64-year-old male with long-standing Type 2 Diabetes Mellitus presents with diabetic peripheral angiopathy and gangrene of the left great toe. What is the correct ICD-10-CM coding sequence according to official coding guidelines?',
                'explanation': 'Under ICD-10-CM guidelines, diabetic angiopathy with gangrene is reported with code E11.52 (Type 2 diabetes mellitus with diabetic peripheral angiopathy with gangrene). In ICD-10-CM, combination codes capture both the diabetes, the vascular manifestation, and the gangrene without requiring a separate gangrene code.',
                'choices': [
                    ('E11.52 (Type 2 diabetes with diabetic peripheral angiopathy with gangrene)', True),
                    ('I96 (Gangrene) followed by E11.9 (Type 2 diabetes without complications)', False),
                    ('E11.9 followed by I70.261 (Atherosclerosis of extremities with gangrene)', False),
                    ('E10.52 (Type 1 diabetes with peripheral angiopathy with gangrene)', False),
                ]
            },
            {
                'order': 2,
                'prompt': 'A patient is admitted to the hospital with acute systolic heart failure and hypertensive chronic kidney disease stage 4. Per ICD-10-CM chapter guidelines, what is the appropriate sequencing of the principal diagnosis?',
                'explanation': 'Official guidelines state that when a patient has hypertension with both heart disease and chronic kidney disease, an assumed causal relationship exists. Code category I13 (Hypertensive heart and chronic kidney disease) must be sequenced first, followed by code I50.21 (Acute systolic heart failure) and N18.4 (CKD Stage 4).',
                'choices': [
                    ('I13.0 (Hypertensive heart and CKD with heart failure) + I50.21 + N18.4', True),
                    ('I50.21 (Acute systolic heart failure) as principal, followed by I10 and N18.4', False),
                    ('N18.4 (CKD Stage 4) as principal, followed by I11.0 and I50.21', False),
                    ('I10 (Essential hypertension) + I50.21 + N18.4', False),
                ]
            },
            {
                'order': 3,
                'prompt': 'When a condition is described as both "acute" (or subacute) and "chronic," and separate subentries exist in the ICD-10-CM Alphabetic Index at the same indentation level, how should the coder sequence the codes?',
                'explanation': 'According to General Coding Guideline Section I.B.8, if the same condition is described as both acute and chronic, and separate subentries exist at the same indentation level in the Alphabetic Index, the acute (subacute) code is sequenced first, followed by the chronic code.',
                'choices': [
                    ('Sequence the acute code first, followed by the chronic code.', True),
                    ('Sequence the chronic code first, followed by the acute code.', False),
                    ('Code only the acute condition, as it is the most severe presentation.', False),
                    ('Query the physician to choose either acute or chronic.', False),
                ]
            },
            {
                'order': 4,
                'prompt': 'A 58-year-old female presents for a follow-up screening mammogram. She has no signs, symptoms, or prior personal history of breast cancer, but has a strong family history of malignant neoplasm of the breast in her mother. What is the correct primary ICD-10-CM code?',
                'explanation': 'For routine screening where the patient has no current symptoms or personal history of malignancy, the encounter code Z12.31 (Encounter for screening mammogram for malignant neoplasm of breast) is sequenced first. Secondary code Z80.3 is reported for family history of breast cancer.',
                'choices': [
                    ('Z12.31 (Encounter for screening mammogram for malignant neoplasm of breast)', True),
                    ('Z80.3 (Family history of malignant neoplasm of breast) as principal diagnosis', False),
                    ('C50.919 (Malignant neoplasm of unspecified breast)', False),
                    ('R92.8 (Other abnormal and inconclusive findings on diagnostic imaging of breast)', False),
                ]
            },
            {
                'order': 5,
                'prompt': 'In ICD-10-CM coding for sepsis and septic shock, what are the mandatory coding requirements when septic shock is documented in an inpatient chart?',
                'explanation': 'Section I.C.1.d guidelines state that for septic shock, the underlying systemic infection code (e.g. A41.9) must be sequenced first, followed by code R65.21 (Severe sepsis with septic shock). Septic shock cannot be assigned as the principal diagnosis.',
                'choices': [
                    ('Code the systemic infection first (e.g., A41.9), followed by R65.21 (Severe sepsis with septic shock)', True),
                    ('Code R65.21 as principal diagnosis, followed by the infection code', False),
                    ('Code R57.9 (Shock, unspecified) alone', False),
                    ('Code R65.20 (Severe sepsis without septic shock) followed by T81.4XXA', False),
                ]
            }
        ]

        for q_dict in icd_q_data:
            q, _ = Question.objects.update_or_create(
                assessment=icd_assessment,
                order=q_dict['order'],
                defaults={'prompt': q_dict['prompt'], 'explanation': q_dict['explanation']}
            )
            for text, is_correct in q_dict['choices']:
                AnswerChoice.objects.update_or_create(question=q, text=text, defaults={'is_correct': is_correct})

        # ----------------------------------------------------
        # 2. CPT & HCPCS Procedural Coding Assessment
        # ----------------------------------------------------
        cpt_assessment, _ = Assessment.objects.update_or_create(
            title='CPT & HCPCS Procedural Coding Assessment',
            defaults={
                'category': coding_cat,
                'primary_skill': cpt_skill,
                'description': 'Validates AMA CPT coding conventions, Evaluation and Management (E/M) medical decision making (MDM), surgical global packages, and modifier assignment.',
                'instructions': 'Answer all 5 clinical procedural coding questions within 30 minutes. Pass mark is 75%.',
                'duration_minutes': 30,
                'pass_mark_percentage': 75,
                'is_active': True,
            }
        )

        cpt_q_data = [
            {
                'order': 1,
                'prompt': 'Under 2023/2024 AMA E/M guidelines for Office/Outpatient encounters (99202–99215), on what two elements can code selection be based?',
                'explanation': 'Code selection for office/outpatient visits (99202-99215) is based exclusively on either Medical Decision Making (MDM) level or Total Time on the date of encounter.',
                'choices': [
                    ('Level of Medical Decision Making (MDM) OR Total Time spent on the date of encounter', True),
                    ('History, Physical Examination, and Medical Decision Making equally weighted', False),
                    ('Number of body systems examined in the physical exam', False),
                    ('Number of clinical minutes spent exclusively in face-to-face counseling', False),
                ]
            },
            {
                'order': 2,
                'prompt': 'When a physician performs an independent, significant, separately identifiable Evaluation and Management (E/M) service on the same day as a minor surgical procedure with a 0- or 10-day global period, which modifier must be appended to the E/M code?',
                'explanation': 'Modifier 25 indicates a significant, separately identifiable evaluation and management service by the same physician on the same day of the procedure or other service.',
                'choices': [
                    ('Modifier 25', True),
                    ('Modifier 59', False),
                    ('Modifier 51', False),
                    ('Modifier 22', False),
                ]
            },
            {
                'order': 3,
                'prompt': 'A surgeon performs an appendectomy on a patient. Ten days later, within the 90-day global surgical period, the patient returns to the operating room for a wound debridement due to post-operative infection. Which modifier should be appended to the return procedure code?',
                'explanation': 'Modifier 78 indicates an unplanned return to the operating/procedure room by the same physician following initial procedure for a related procedure during the postoperative period.',
                'choices': [
                    ('Modifier 78 (Unplanned Return to the Operating/Procedure Room)', True),
                    ('Modifier 79 (Unrelated Procedure by the Same Physician)', False),
                    ('Modifier 58 (Staged or Related Procedure)', False),
                    ('Modifier 76 (Repeat Procedure by Same Physician)', False),
                ]
            },
            {
                'order': 4,
                'prompt': 'What does CPT symbol "+" preceding a code identify in the AMA CPT manual?',
                'explanation': 'The plus symbol (+) denotes an add-on code. Add-on codes describe additional work performed in conjunction with a primary service and are never reported as a stand-alone code.',
                'choices': [
                    ('An Add-on Code that must never be reported as a stand-alone code', True),
                    ('A newly revised code description for the current year', False),
                    ('A code exempt from modifier 51', False),
                    ('An FDA approval pending code', False),
                ]
            },
            {
                'order': 5,
                'prompt': 'In HCPCS Level II coding, what is the primary purpose of Level II alphanumeric codes (e.g., codes beginning with A, E, J, L)?',
                'explanation': 'HCPCS Level II codes are standardized national codes used primarily to bill for ambulance services, durable medical equipment (DME), prosthetics, orthotics, and injectable drugs (J-codes) that are not covered in CPT.',
                'choices': [
                    ('To report supplies, durable medical equipment (DME), injectables, and ambulance services not found in CPT', True),
                    ('To replace all CPT surgery codes for Medicaid patients', False),
                    ('To report international clinical inpatient DRG assignments', False),
                    ('To provide diagnostic ICD-10 replacement codes', False),
                ]
            }
        ]

        for q_dict in cpt_q_data:
            q, _ = Question.objects.update_or_create(
                assessment=cpt_assessment,
                order=q_dict['order'],
                defaults={'prompt': q_dict['prompt'], 'explanation': q_dict['explanation']}
            )
            for text, is_correct in q_dict['choices']:
                AnswerChoice.objects.update_or_create(question=q, text=text, defaults={'is_correct': is_correct})

        # ----------------------------------------------------
        # 3. Medical Billing & RCM Assessment
        # ----------------------------------------------------
        rcm_assessment, _ = Assessment.objects.update_or_create(
            title='Medical Billing & Revenue Cycle Management (RCM) Assessment',
            defaults={
                'category': billing_cat,
                'primary_skill': billing_skill,
                'description': 'Validates revenue cycle workflows, CMS-1500 and UB-04 claim forms, Claim Adjustment Reason Codes (CARCs), Remittance Advices, and denial resolution strategies.',
                'instructions': 'You have 25 minutes to complete 5 billing scenario questions. Passing score is 75%.',
                'duration_minutes': 25,
                'pass_mark_percentage': 75,
                'is_active': True,
            }
        )

        rcm_q_data = [
            {
                'order': 1,
                'prompt': 'An 835 Electronic Remittance Advice (ERA) returns with Claim Adjustment Reason Code "CO-16". What does this denial code represent and what is the required billing action?',
                'explanation': 'CARC CO-16 means "Claim/service lacks information or has submission/billing error(s)". Group code CO indicates contractual obligation. The billing specialist must check the Remittance Advice Remark Codes (RARCs) to identify missing details (e.g., NPI, modifier, or medical notes) and resubmit a corrected claim.',
                'choices': [
                    ('Claim/service lacks information or has submission errors; review remark codes and resubmit corrected claim', True),
                    ('Patient is not eligible for benefits; balance bill the patient immediately', False),
                    ('Charge exceeds maximum allowable fee; write off the amount permanently as contractual adjustment', False),
                    ('Duplicate claim submission; void the second claim', False),
                ]
            },
            {
                'order': 2,
                'prompt': 'What is the standard standard paper claim form used by physicians and outpatient healthcare professionals to bill Medicare and commercial payers?',
                'explanation': 'The CMS-1500 (HCFA-1500) is the universal claim form used by non-institutional healthcare providers and medical suppliers. Institutional providers (hospitals) use UB-04 (CMS-1450).',
                'choices': [
                    ('CMS-1500 form', True),
                    ('UB-04 (CMS-1450) form', False),
                    ('ADA Dental Claim Form', False),
                    ('CMS-1728 form', False),
                ]
            },
            {
                'order': 3,
                'prompt': 'On an Explanation of Benefits (EOB), what does Claim Adjustment Group Code "PR" signify?',
                'explanation': 'PR stands for Patient Responsibility. This group code assigns payment responsibility to the patient (e.g. copayment, coinsurance, or deductible amounts) and cannot be written off as a provider discount.',
                'choices': [
                    ('Patient Responsibility (deductible, coinsurance, or copay)', True),
                    ('Provider Reimbursement guarantee', False),
                    ('Payer Reduction penalty for late filing', False),
                    ('Prior Authorization required', False),
                ]
            },
            {
                'order': 4,
                'prompt': 'Under typical commercial and Medicare Advantage contracts, what is the consequence when a claim is filed past the contractually agreed "Timely Filing Limit"?',
                'explanation': 'Claims submitted past the timely filing limit are denied with no right to balance-bill the patient. The provider must write off the entire balance unless proof of timely submission can be established on appeal.',
                'choices': [
                    ('The claim is denied and the provider must write off the balance; balance-billing the patient is legally prohibited', True),
                    ('The claim is automatically forwarded to the patient for direct out-of-pocket payment', False),
                    ('The payer deducts a 10% late fee and pays the remainder', False),
                    ('The claim is automatically transferred to the secondary insurer', False),
                ]
            },
            {
                'order': 5,
                'prompt': 'In Revenue Cycle Management (RCM), what is the formula used to calculate the "Clean Claim Rate"?',
                'explanation': 'Clean Claim Rate = (Number of claims accepted and paid on first pass without rejection or denial / Total number of claims submitted) * 100.',
                'choices': [
                    ('(Total Claims Paid on First Pass / Total Claims Submitted) * 100', True),
                    ('(Total Dollar Amount Collected / Total Dollar Amount Billed) * 100', False),
                    ('(Number of Denied Claims / Number of Appeals Won) * 100', False),
                    ('(Average Accounts Receivable Days / Total Claims Billed) * 365', False),
                ]
            }
        ]

        for q_dict in rcm_q_data:
            q, _ = Question.objects.update_or_create(
                assessment=rcm_assessment,
                order=q_dict['order'],
                defaults={'prompt': q_dict['prompt'], 'explanation': q_dict['explanation']}
            )
            for text, is_correct in q_dict['choices']:
                AnswerChoice.objects.update_or_create(question=q, text=text, defaults={'is_correct': is_correct})

        # ----------------------------------------------------
        # 4. HIPAA Compliance Assessment
        # ----------------------------------------------------
        hipaa_assessment, _ = Assessment.objects.update_or_create(
            title='HIPAA Healthcare Privacy, Security & Compliance Assessment',
            defaults={
                'category': comp_cat,
                'primary_skill': None,
                'description': 'Tests understanding of Protected Health Information (PHI), the Minimum Necessary Rule, Business Associate Agreements (BAA), and breach notification mandates.',
                'instructions': 'Answer all 5 compliance questions within 20 minutes. Pass mark is 80%.',
                'duration_minutes': 20,
                'pass_mark_percentage': 80,
                'is_active': True,
            }
        )

        hipaa_q_data = [
            {
                'order': 1,
                'prompt': 'Under the HIPAA Privacy Rule, what is the core requirement of the "Minimum Necessary Standard"?',
                'explanation': 'The Minimum Necessary Standard requires covered entities and business associates to take reasonable steps to limit the use or disclosure of Protected Health Information (PHI) to only the minimum amount necessary to accomplish the intended purpose.',
                'choices': [
                    ('Covered entities must limit use and disclosure of PHI to the minimum necessary to accomplish the intended clinical or administrative purpose', True),
                    ('Only physicians with an active license may access medical charts', False),
                    ('Medical records must be deleted after 90 days', False),
                    ('Patients can only request one medical record page per year', False),
                ]
            },
            {
                'order': 2,
                'prompt': 'Which of the following third-party entities is required to sign a Business Associate Agreement (BAA) with a covered healthcare facility before handling patient data?',
                'explanation': 'A medical billing service that creates, receives, maintains, or transmits PHI on behalf of a covered healthcare entity is a Business Associate and must execute a BAA under HIPAA.',
                'choices': [
                    ('An outsourced medical billing and revenue cycle coding company', True),
                    ('The United States Postal Service delivering billing statements', False),
                    ('The building janitorial crew that cleans the hospital lobby', False),
                    ('An office electrical maintenance contractor', False),
                ]
            },
            {
                'order': 3,
                'prompt': 'Under the HIPAA Breach Notification Rule, within how many calendar days must a covered entity notify affected individuals and the HHS Office for Civil Rights (OCR) if an unauthorized breach affects 500 or more individuals?',
                'explanation': 'For breaches involving 500 or more individuals, covered entities must notify affected individuals and the HHS Secretary without unreasonable delay and in no case later than 60 calendar days from discovery.',
                'choices': [
                    ('Without unreasonable delay and no later than 60 calendar days from discovery', True),
                    ('Within 180 calendar days', False),
                    ('Within 1 calendar year', False),
                    ('Within 24 hours via telephone call', False),
                ]
            },
            {
                'order': 4,
                'prompt': 'Which of the following is considered Protected Health Information (PHI) under HIPAA?',
                'explanation': 'PHI includes any individually identifiable health information created or received by a covered entity, including billing records, IP addresses, diagnostic reports, and patient phone numbers.',
                'choices': [
                    ('Patient name linked with an appointment date and diagnosis code', True),
                    ('De-identified statistical data showing total regional hospital beds', False),
                    ('Public health data aggregated by state with zero individual identifiers', False),
                    ('A hospital cafeteria menu', False),
                ]
            },
            {
                'order': 5,
                'prompt': 'Under HIPAA Security Rule Technical Safeguards, what is required when transmitting electronic Protected Health Information (ePHI) across open networks?',
                'explanation': 'Under the HIPAA Security Rule (45 CFR § 164.312(e)), covered entities must implement technical security measures, notably end-to-end data encryption, to guard against unauthorized access to ePHI transmitted over an electronic communications network.',
                'choices': [
                    ('Implement end-to-end data encryption mechanisms for data in transit and at rest', True),
                    ('Send records exclusively via standard unencrypted personal email', False),
                    ('Store all passwords in an unencrypted shared document', False),
                    ('Require all patients to verbally authorize each transmission', False),
                ]
            }
        ]

        for q_dict in hipaa_q_data:
            q, _ = Question.objects.update_or_create(
                assessment=hipaa_assessment,
                order=q_dict['order'],
                defaults={'prompt': q_dict['prompt'], 'explanation': q_dict['explanation']}
            )
            for text, is_correct in q_dict['choices']:
                AnswerChoice.objects.update_or_create(question=q, text=text, defaults={'is_correct': is_correct})

        self.stdout.write(self.style.SUCCESS('Successfully seeded 4 clinical assessments and 20 standardized questions!'))
