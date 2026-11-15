"""
apps/growth_os/services/outreach_generator.py
AI-Powered, Multi-Sector Outreach Copy Generation Engine for Kodafriq GrowthOS.
Drafts personalized, high-conversion email and LinkedIn messages tailored to
Healthcare, IT, and Finance employer leads, referencing active vacancies
and pre-matched candidate dossiers.
"""
import logging
from django.conf import settings
from apps.growth_os.models import EmployerLead, LeadContact, HiringSignal, TalentReverseMatch, OutreachMessage

logger = logging.getLogger(__name__)


def get_sector_tag(vertical: str) -> str:
    """Categorizes IndustryVertical into broad sector tag."""
    v = (vertical or '').upper()
    if any(k in v for k in ['IT', 'SOFTWARE', 'CLOUD', 'DEVOPS', 'CYBER', 'DATA', 'QA', 'SUPPORT']):
        return 'IT'
    elif any(k in v for k in ['FINANCE', 'ACCOUNT']):
        return 'FINANCE'
    return 'HEALTHCARE'


def format_candidate_highlights(matches) -> str:
    """Formats bullet points of pre-matched candidate qualifications."""
    bullets = []
    for idx, tm in enumerate(matches, start=1):
        cand = tm.candidate
        name_alias = f"Candidate #KF-{str(tm.id)[:4].upper()}"
        headline = cand.headline or "Certified Clinical / Technical Specialist"
        skills = ", ".join(tm.matched_skills[:3]) if tm.matched_skills else "Core domain competencies"
        exp = f"{cand.years_of_experience} yrs exp" if cand.years_of_experience else "Verified experienced"
        avail = cand.get_availability_status_display()
        bullets.append(f"  • {name_alias} ({headline}): {skills} | {exp} | {avail}")
    return "\n".join(bullets)


def generate_outreach_pitch(
    lead: EmployerLead,
    contact: LeadContact = None,
    channel: str = OutreachMessage.Channel.EMAIL,
    sequence_step: int = 1,
    base_url: str = 'https://kodafriq.com',
    request=None
) -> OutreachMessage:
    """
    Synthesizes a personalized outreach message draft for an employer lead.
    Creates an OutreachMessage in DRAFT_PENDING_APPROVAL status.
    """
    if request:
        base_url = request.build_absolute_uri('/')[:-1]

    if not contact:
        contact = lead.primary_contact

    recipient_name = contact.full_name if contact else "Hiring Team"
    first_name = recipient_name.split()[0] if recipient_name != "Hiring Team" else "there"

    # Identify primary vacancy to reference
    vacancy = lead.vacancies.filter(is_active=True).first()
    role_title = vacancy.job_title if vacancy else "specialized operational roles"
    days_open = vacancy.days_open if vacancy else 15

    # Retrieve top reverse-matched candidates
    matches = lead.talent_matches.select_related('candidate', 'candidate__user').order_by(
        '-is_shortlisted', '-match_score'
    )[:3]

    candidate_bullets = format_candidate_highlights(matches) if matches else (
        "  • Pre-assessed, employer-ready talent available for immediate remote deployment\n"
        "  • Full timezone overlap with US EST/CST business hours\n"
        "  • Rigorously vetted on clinical & technical competencies"
    )

    shortlist_url = f"{base_url.rstrip('/')}/growth-os/shortlist/{lead.id}/"
    sector = get_sector_tag(lead.industry_vertical)

    # Sequence Generation Logic
    if channel == OutreachMessage.Channel.LINKEDIN:
        # LinkedIn InMail format (concise, high impact, under 200 words)
        if sequence_step == 1:
            subject = f"Candidate shortlist for {lead.company_name} ({role_title})"
            body = (
                f"Hi {first_name},\n\n"
                f"I noticed {lead.company_name} is actively hiring for a {role_title}.\n\n"
                f"At Kodafriq, we maintain an active pool of pre-vetted specialists who match your specific operational requirements. "
                f"I put together a private, anonymized shortlist of 3 qualified candidates ready for immediate interviews:\n\n"
                f"{shortlist_url}\n\n"
                f"All candidates are tested on domain competency, work on your timezone, and come with a 2-week risk-free trial.\n\n"
                f"Would you be open to reviewing their profiles or having a brief 10-minute intro call this week?\n\n"
                f"Best regards,\n"
                f"The Kodafriq Partnerships Team"
            )
        else:
            subject = f"Quick follow-up regarding {role_title} at {lead.company_name}"
            body = (
                f"Hi {first_name}, following up on my previous note. Our candidates matching your {role_title} vacancy "
                f"are still available for immediate deployment. You can inspect their verified credentials and availability here:\n\n"
                f"{shortlist_url}\n\n"
                f"Would tomorrow or Thursday work for a quick introductory chat?\n\n"
                f"Best,\n"
                f"Kodafriq Partnerships"
            )
    else:
        # Email Outreach Format
        if sequence_step == 1:
            # Step 1: Initial Hook & Pitch
            if sector == 'HEALTHCARE':
                subject = f"Vetted {role_title} talent for {lead.company_name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"I saw that {lead.company_name} is currently looking for a {role_title}"
                    f"{' (open for over ' + str(days_open) + ' days)' if days_open >= 30 else ''}.\n\n"
                    f"Given how critical denial reduction, accurate coding, and steady cash flow are right now, "
                    f"I wanted to reach out directly. At Kodafriq, we specialize in deploying rigorously vetted, "
                    f"AAPC/AHIMA-certified medical coders, billing specialists, and RCM auditors.\n\n"
                    f"Based on your vacancy, our matching engine selected 3 candidates who align with your systems:\n\n"
                    f"{candidate_bullets}\n\n"
                    f"You can review their full verified assessment scores and clinical work histories on this private shortlist page:\n"
                    f"👉 {shortlist_url}\n\n"
                    f"All talent comes with full US business hours overlap and a 2-week risk-free placement guarantee.\n\n"
                    f"Do you have 10 minutes this Thursday or Friday for a quick introductory conversation?\n\n"
                    f"Warm regards,\n\n"
                    f"Business Development Team\n"
                    f"Kodafriq Healthcare & Talent Solutions\n"
                    f"https://kodafriq.com"
                )
            elif sector == 'IT':
                subject = f"Pre-vetted {role_title} candidates for {lead.company_name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"I noticed that {lead.company_name} has an active opening for a {role_title}.\n\n"
                    f"Finding qualified senior engineering talent with proven production experience can be a bottleneck. "
                    f"At Kodafriq, we maintain a dedicated network of vetted software engineers, DevOps/cloud architects, and cybersecurity specialists.\n\n"
                    f"Here are 3 pre-screened candidates matching your tech requirements:\n\n"
                    f"{candidate_bullets}\n\n"
                    f"You can inspect their verified technical scores, GitHub contributions, and availability here:\n"
                    f"👉 {shortlist_url}\n\n"
                    f"Our engineers work in full sync with your sprint cadence and timezone, backed by our 2-week trial period.\n\n"
                    f"Would you be open to a 10-minute discovery call this week to see if any of these candidates fit your roadmap?\n\n"
                    f"Best regards,\n\n"
                    f"Talent Acquisition Solutions\n"
                    f"Kodafriq Global\n"
                    f"https://kodafriq.com"
                )
            else:
                # Finance / General
                subject = f"Qualified {role_title} talent for {lead.company_name}"
                body = (
                    f"Hi {first_name},\n\n"
                    f"I noticed that {lead.company_name} is currently hiring for a {role_title}.\n\n"
                    f"At Kodafriq, we support organizations by providing pre-vetted, experienced finance, accounting, and operations professionals.\n\n"
                    f"We’ve compiled a tailored shortlist of qualified specialists who can step in immediately:\n\n"
                    f"{candidate_bullets}\n\n"
                    f"You can review their credentials and software experience here:\n"
                    f"👉 {shortlist_url}\n\n"
                    f"Could we schedule a quick 10-minute introductory call this week to discuss your team's needs?\n\n"
                    f"Best regards,\n\n"
                    f"Kodafriq Partnerships Team\n"
                    f"https://kodafriq.com"
                )

        elif sequence_step == 2:
            # Step 2: Value-Add & Risk Reversal Follow-Up (Day 4)
            subject = f"Re: Vetted {role_title} talent for {lead.company_name}"
            body = (
                f"Hi {first_name},\n\n"
                f"Following up on my note from earlier this week regarding your open {role_title} position.\n\n"
                f"I know how busy hiring cycles can be. What makes Kodafriq different is speed and zero placement risk:\n"
                f"  1. Immediate Onboarding: Candidates are available to start within 48 to 72 hours.\n"
                f"  2. Two-Week Risk-Free Trial: If a candidate isn't the perfect fit in the first 14 days, you pay nothing.\n"
                f"  3. Cost Efficiency: Achieve 40-60% savings on operational payroll without compromising quality.\n\n"
                f"You can review your dedicated candidate shortlist here:\n"
                f"👉 {shortlist_url}\n\n"
                f"Would you have 10 minutes for a brief chat this Friday?\n\n"
                f"Best regards,\n\n"
                f"Business Development Team\n"
                f"Kodafriq\n"
                f"https://kodafriq.com"
            )

        else:
            # Step 3: Break-Up & Long-Term Nurture (Day 8)
            subject = f"Closing the loop regarding {role_title} at {lead.company_name}"
            body = (
                f"Hi {first_name},\n\n"
                f"I haven't heard back, so I assume you've either filled the {role_title} role or priorities have shifted for {lead.company_name} — which is completely understandable.\n\n"
                f"I will close your file for now and won't follow up further so I don't crowd your inbox.\n\n"
                f"Your private candidate shortlist will remain accessible for the next 30 days should your staffing needs change:\n"
                f"👉 {shortlist_url}\n\n"
                f"Wishing {lead.company_name} continued growth, and feel free to reach out anytime if we can assist with future recruitment.\n\n"
                f"Warm regards,\n\n"
                f"Kodafriq Partnerships Team\n"
                f"https://kodafriq.com"
            )

    # Save to database in DRAFT_PENDING_APPROVAL status
    outreach = OutreachMessage.objects.create(
        lead=lead,
        contact=contact,
        channel=channel,
        sequence_step=sequence_step,
        subject=subject,
        body_text=body,
        status=OutreachMessage.Status.DRAFT_PENDING_APPROVAL
    )

    return outreach

