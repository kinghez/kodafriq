import io
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable


def generate_candidate_resume_pdf(candidate) -> bytes:
    """
    Generates a high-quality, professional, 100% valid PDF Clinical Resume
    for a CandidateProfile using ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Color palette matching Kodafriq brand
    primary_color = colors.HexColor('#006fe6')
    navy_color = colors.HexColor('#091e42')
    slate_color = colors.HexColor('#475569')
    light_slate = colors.HexColor('#64748b')

    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=navy_color,
        spaceAfter=3
    )
    headline_style = ParagraphStyle(
        'DocHeadline',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=primary_color,
        spaceAfter=5
    )
    contact_style = ParagraphStyle(
        'DocContact',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=slate_color,
        spaceAfter=12
    )
    section_title_style = ParagraphStyle(
        'DocSecTitle',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=navy_color,
        spaceBefore=10,
        spaceAfter=5
    )
    body_style = ParagraphStyle(
        'DocBody',
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=5
    )
    bullet_style = ParagraphStyle(
        'DocBullet',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=3,
        leftIndent=10
    )

    story = []

    # Brand Header Bar
    brand_p = Paragraph(
        f"<b><font color='{primary_color}'>KODAFRIQ</font></b> &bull; VERIFIED HEALTHCARE TALENT RESUME &bull; AUDIT PROTOCOL ID #KF-{candidate.pk:05d}",
        ParagraphStyle('Brand', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=slate_color)
    )
    story.append(brand_p)
    story.append(Spacer(1, 6))

    # Candidate Name & Headline
    story.append(Paragraph(candidate.full_name, title_style))
    story.append(Paragraph(candidate.headline or "Clinical Coding & Healthcare Data Specialist", headline_style))

    # Contact Details
    contact_parts = []
    if getattr(candidate.user, 'email', None):
        contact_parts.append(f"Email: {candidate.user.email}")
    if candidate.phone:
        contact_parts.append(f"Phone: {candidate.phone}")
    if candidate.location:
        contact_parts.append(f"Location: {candidate.location}")
    if candidate.is_verified:
        contact_parts.append("<b><font color='#059669'>[Kodafriq Independently Verified]</font></b>")

    story.append(Paragraph(" &bull; ".join(contact_parts), contact_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=0, spaceAfter=8))

    # Professional Summary / Bio
    if candidate.bio:
        story.append(Paragraph("PROFESSIONAL SUMMARY", section_title_style))
        story.append(Paragraph(candidate.bio, body_style))
        story.append(Spacer(1, 4))

    # Core Competencies / Verified Skills
    skills = candidate.skills.all()
    if skills.exists():
        story.append(Paragraph("CLINICAL COMPETENCIES & VERIFIED SKILLS", section_title_style))
        skill_names = [f"&bull; <b>{s.name}</b> ({s.get_status_display()})" for s in skills]
        half = (len(skill_names) + 1) // 2
        col1 = "<br/>".join(skill_names[:half])
        col2 = "<br/>".join(skill_names[half:]) if half < len(skill_names) else ""
        skills_table = Table(
            [[Paragraph(col1, body_style), Paragraph(col2, body_style)]],
            colWidths=[265, 265]
        )
        skills_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(skills_table)
        story.append(Spacer(1, 4))

    # Certifications
    certs = candidate.certifications.all()
    if certs.exists():
        story.append(Paragraph("PROFESSIONAL ACCREDITATIONS & CREDENTIALS", section_title_style))
        for cert in certs:
            cert_line = f"&bull; <b>{cert.certification_name}</b> &mdash; {cert.issuing_organization}"
            if cert.credential_id:
                cert_line += f" (Credential ID: {cert.credential_id})"
            if cert.is_verified:
                cert_line += " <font color='#059669'><b>[Verified]</b></font>"
            story.append(Paragraph(cert_line, bullet_style))
        story.append(Spacer(1, 4))

    # Training Programs Completed
    trainings = candidate.training_enrolments.filter(status='COMPLETED')
    if trainings.exists():
        story.append(Paragraph("CONTINUING CLINICAL EDUCATION & TRAINING", section_title_style))
        for enr in trainings:
            tr_line = f"&bull; <b>{enr.program.title}</b> &mdash; Accredited Certificate #{enr.certificate_id or 'KF-TRN'}"
            if enr.completed_at:
                tr_line += f" (Completed {enr.completed_at.strftime('%B %Y')})"
            story.append(Paragraph(tr_line, bullet_style))
        story.append(Spacer(1, 4))

    # Work Experience
    exps = candidate.work_experiences.all().order_by('-start_date')
    if exps.exists():
        story.append(Paragraph("CLINICAL & HEALTHCARE WORK HISTORY", section_title_style))
        for exp in exps:
            date_range = f"{exp.start_date.strftime('%b %Y')} &ndash; {'Present' if exp.is_current else exp.end_date.strftime('%b %Y') if exp.end_date else ''}"
            exp_header = f"<b>{exp.job_title}</b> | <font color='{slate_color}'>{exp.organization_name}</font> <i>({date_range})</i>"
            story.append(Paragraph(exp_header, body_style))
            if exp.description:
                story.append(Paragraph(exp.description, bullet_style))
            story.append(Spacer(1, 3))

    # Footer Watermark
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.75, color=colors.HexColor('#cbd5e1'), spaceBefore=6, spaceAfter=6))
    footer_text = Paragraph(
        f"<font color='#64748b' size='7.5'>Official Clinical Credential Document &bull; Generated from Kodafriq Healthcare Platform &bull; Verify online at kodafriq.com/talent/card/{candidate.pk}/</font>",
        ParagraphStyle('Footer', alignment=1, fontName='Helvetica', fontSize=7.5, leading=9, textColor=light_slate)
    )
    story.append(footer_text)

    doc.build(story)
    return buffer.getvalue()
