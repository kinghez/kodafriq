import io
import os
from decimal import Decimal
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# Hex Color Strings for HTML/ReportLab Font Tags
HEX_NAVY = '#091E42'
HEX_ACCENT = '#006FE6'
HEX_EMERALD = '#059669'
HEX_AMBER = '#D97706'
HEX_MUTED = '#64748B'
HEX_DARK = '#0F172A'

# ReportLab Color Objects for Flowable Canvas
PRIMARY_NAVY = colors.HexColor(HEX_NAVY)
ACCENT_BLUE = colors.HexColor(HEX_ACCENT)
EMERALD_GREEN = colors.HexColor(HEX_EMERALD)
EMERALD_BG = colors.HexColor('#ECFDF5')
AMBER_GOLD = colors.HexColor(HEX_AMBER)
AMBER_BG = colors.HexColor('#FFFBEB')
GRAY_BORDER = colors.HexColor('#E2E8F0')
GRAY_BG = colors.HexColor('#F8FAFC')
TEXT_DARK = colors.HexColor(HEX_DARK)
TEXT_MUTED = colors.HexColor(HEX_MUTED)


def get_pdf_styles():
    styles = getSampleStyleSheet()
    
    brand_title = ParagraphStyle(
        'BrandTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=PRIMARY_NAVY
    )
    
    brand_sub = ParagraphStyle(
        'BrandSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=ACCENT_BLUE
    )
    
    inv_title = ParagraphStyle(
        'InvTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=PRIMARY_NAVY,
        alignment=TA_RIGHT
    )
    
    inv_meta = ParagraphStyle(
        'InvMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=TEXT_MUTED,
        alignment=TA_RIGHT
    )
    
    sec_header = ParagraphStyle(
        'SecHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=PRIMARY_NAVY
    )
    
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=TEXT_DARK
    )
    
    cell_normal = ParagraphStyle(
        'CellNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=TEXT_DARK
    )

    cell_muted = ParagraphStyle(
        'CellMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=TEXT_MUTED
    )
    
    cell_right = ParagraphStyle(
        'CellRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=TEXT_DARK,
        alignment=TA_RIGHT
    )
    
    status_badge_paid = ParagraphStyle(
        'StatusBadgePaid',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=EMERALD_GREEN,
        alignment=TA_RIGHT
    )
    
    status_badge_pending = ParagraphStyle(
        'StatusBadgePending',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=AMBER_GOLD,
        alignment=TA_RIGHT
    )

    legal_text = ParagraphStyle(
        'LegalText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9.5,
        textColor=TEXT_MUTED
    )

    return {
        'brand_title': brand_title,
        'brand_sub': brand_sub,
        'inv_title': inv_title,
        'inv_meta': inv_meta,
        'sec_header': sec_header,
        'cell_bold': cell_bold,
        'cell_normal': cell_normal,
        'cell_muted': cell_muted,
        'cell_right': cell_right,
        'status_badge_paid': status_badge_paid,
        'status_badge_pending': status_badge_pending,
        'legal_text': legal_text,
    }


def generate_invoice_pdf(invoice):
    """
    Generates a high-fidelity tax-compliant clinical billing invoice PDF for employers.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    st = get_pdf_styles()
    story = []
    
    contract = invoice.contract
    employer = contract.employer
    candidate = contract.candidate
    is_settled = (invoice.payment_status == 'SETTLED')

    # 1. Header (Brand Left | Invoice Meta Right)
    left_brand = [
        Paragraph("KODAFRIQ", st['brand_title']),
        Paragraph("HEALTHCARE DATA MANAGEMENT &amp; TALENT SOLUTIONS", st['brand_sub']),
        Spacer(1, 4),
        Paragraph("Accra, Ghana &bull; Wilmington, DE, USA &bull; billing@kodafriq.com", st['cell_muted']),
    ]
    
    status_text = "PAID &bull; SETTLED" if is_settled else "ISSUED &bull; PAYMENT PENDING"
    status_style = st['status_badge_paid'] if is_settled else st['status_badge_pending']
    badge_color_hex = HEX_EMERALD if is_settled else HEX_AMBER
    
    right_meta = [
        Paragraph(f"INVOICE: <b>{invoice.invoice_ref}</b>", st['inv_title']),
        Paragraph(f"<font color='{badge_color_hex}'><b>[{status_text}]</b></font>", status_style),
        Spacer(1, 4),
        Paragraph(f"Date Issued: {invoice.created_at.strftime('%B %d, %Y')}", st['inv_meta']),
        Paragraph(f"Billing Period: {invoice.billing_period_start.strftime('%b %d')} - {invoice.billing_period_end.strftime('%b %d, %Y')}", st['inv_meta']),
        Paragraph(f"Payment Rail: {invoice.get_gateway_provider_display()}", st['inv_meta']),
    ]
    
    header_table = Table([[left_brand, right_meta]], colWidths=[310, 230])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=GRAY_BORDER, spaceAfter=14))

    # 2. Parties Grid (Billed To vs Talent & Contract)
    billed_to_content = [
        Paragraph("<b>BILLED TO (HEALTHCARE EMPLOYER)</b>", st['sec_header']),
        Spacer(1, 4),
        Paragraph(f"<b>{employer.company_name}</b>", st['cell_bold']),
        Paragraph(f"Attn: {employer.user.get_full_name() or employer.user.username}", st['cell_normal']),
        Paragraph(f"Email: {employer.user.email}", st['cell_normal']),
        Paragraph(f"Industry: {employer.industry or 'Healthcare &amp; RCM'}", st['cell_muted']),
        Paragraph(f"Location: {employer.city + ', ' if employer.city else ''}{employer.country or 'Global'}", st['cell_muted']),
    ]

    contractor_content = [
        Paragraph("<b>CLINICAL TALENT &amp; ENGAGEMENT</b>", st['sec_header']),
        Spacer(1, 4),
        Paragraph(f"<b>{candidate.user.get_full_name() or candidate.user.username}</b>", st['cell_bold']),
        Paragraph(f"Clinical Role: {candidate.headline or 'Medical Coding Specialist'}", st['cell_normal']),
        Paragraph(f"Engagement: {contract.title}", st['cell_normal']),
        Paragraph(f"Contract Ref: <b>{contract.contract_ref}</b> &bull; {contract.get_contract_type_display()}", st['cell_muted']),
    ]

    parties_table = Table([[billed_to_content, contractor_content]], colWidths=[270, 270])
    parties_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
        ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 16))

    # 3. Itemized Work Breakdown Table
    story.append(Paragraph("<b>ITEMIZED CLINICAL SERVICES &amp; CHARGES</b>", st['sec_header']))
    story.append(Spacer(1, 6))

    items_data = [
        [
            Paragraph("<b>Description / Deliverable</b>", st['cell_bold']),
            Paragraph("<b>Volume / Qty</b>", st['cell_bold']),
            Paragraph("<b>Unit Rate</b>", st['cell_right']),
            Paragraph("<b>Subtotal (USD)</b>", st['cell_right']),
        ]
    ]

    if invoice.timesheet:
        ts = invoice.timesheet
        charts_note = f" &bull; {ts.total_charts_coded} charts coded" if ts.total_charts_coded else ""
        items_data.append([
            Paragraph(
                f"<b>Clinical Abstracting &amp; Coding Services</b><br/>"
                f"<font color='{HEX_MUTED}'>Week of {ts.week_start_date.strftime('%b %d')} - {ts.week_end_date.strftime('%b %d, %Y')}{charts_note}</font>",
                st['cell_normal']
            ),
            Paragraph(f"{ts.total_hours:.2f} hrs", st['cell_normal']),
            Paragraph(f"${contract.rate_per_hour:.2f}/hr", st['cell_right']),
            Paragraph(f"${invoice.talent_earnings:.2f}", st['cell_right']),
        ])
    elif invoice.milestone:
        m = invoice.milestone
        items_data.append([
            Paragraph(
                f"<b>Milestone #{m.order}: {m.title}</b><br/>"
                f"<font color='{HEX_MUTED}'>Deliverable verified and approved by clinical supervisor</font>",
                st['cell_normal']
            ),
            Paragraph("1 Deliverable", st['cell_normal']),
            Paragraph(f"${invoice.talent_earnings:.2f}", st['cell_right']),
            Paragraph(f"${invoice.talent_earnings:.2f}", st['cell_right']),
        ])
    else:
        items_data.append([
            Paragraph(f"<b>Professional Healthcare Services</b><br/><font color='{HEX_MUTED}'>{contract.title}</font>", st['cell_normal']),
            Paragraph("1 Period", st['cell_normal']),
            Paragraph(f"${invoice.talent_earnings:.2f}", st['cell_right']),
            Paragraph(f"${invoice.talent_earnings:.2f}", st['cell_right']),
        ])

    # Platform Markup Row
    items_data.append([
        Paragraph(
            "<b>Kodafriq Managed Platform Service Fee</b><br/>"
            f"<font color='{HEX_MUTED}'>Vetted talent matching, clinical QA oversight, and payment protection ({contract.kodafriq_fee_percent:.1f}%)</font>",
            st['cell_normal']
        ),
        Paragraph(f"{contract.kodafriq_fee_percent:.1f}%", st['cell_normal']),
        Paragraph("-", st['cell_right']),
        Paragraph(f"${invoice.kodafriq_fee:.2f}", st['cell_right']),
    ])

    # Gateway Processing Fee Row
    items_data.append([
        Paragraph(
            "<b>Payment Processing &amp; Gateway Interchange</b><br/>"
            f"<font color='{HEX_MUTED}'>Pass-through secure card/bank processing fee</font>",
            st['cell_normal']
        ),
        Paragraph("Pass-through", st['cell_normal']),
        Paragraph("-", st['cell_right']),
        Paragraph(f"${invoice.processing_fee:.2f}", st['cell_right']),
    ])

    # Total Billed Row
    items_data.append([
        Paragraph("<b>TOTAL AMOUNT BILLED (USD)</b>", st['cell_bold']),
        Paragraph("", st['cell_normal']),
        Paragraph("", st['cell_normal']),
        Paragraph(f"<b>${invoice.gross_amount:.2f}</b>", st['cell_right']),
    ])

    inv_table = Table(items_data, colWidths=[290, 80, 80, 90])
    inv_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#091E42')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, GRAY_BG]),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, -1), (-1, -1), 1.5, ACCENT_BLUE),
    ]))
    story.append(inv_table)
    story.append(Spacer(1, 14))

    # 4. Settlement & Accounting Audit Trail (If settled)
    if is_settled:
        settle_cells = [
            [
                Paragraph("<b>SETTLEMENT &amp; AUDIT VERIFICATION</b>", st['sec_header']),
                Paragraph("", st['sec_header']),
            ],
            [
                Paragraph(f"<b>Gateway Reference:</b> {invoice.gateway_charge_ref or 'Verified Electronic Settlement'}", st['cell_normal']),
                Paragraph(f"<b>Settled Timestamp:</b> {invoice.settled_at.strftime('%Y-%m-%d %H:%M:%S UTC') if invoice.settled_at else 'Verified'}", st['cell_normal']),
            ],
            [
                Paragraph(f"<b>Disbursement Allocation:</b> ${invoice.talent_earnings:.2f} (Candidate Net) + ${invoice.kodafriq_fee:.2f} (Platform)", st['cell_muted']),
                Paragraph(f"<b>Payout State:</b> {invoice.get_payout_status_display()}", st['cell_muted']),
            ]
        ]
        settle_table = Table(settle_cells, colWidths=[270, 270])
        settle_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), EMERALD_BG),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#A7F3D0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1FAE5')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ]))
        story.append(settle_table)
        story.append(Spacer(1, 14))

    # 5. Regulatory & HIPAA Compliance Notice
    legal_p = Paragraph(
        "<b>REGULATORY &amp; COMPLIANCE DISCLOSURE:</b> "
        "Kodafriq operates a non-custodial clinical billing framework. Candidate compensation is held in business ledger "
        "escrow and executed via licensed financial payment rails (Paystack Ghana MoMo / Flutterwave Pan-African Banking Network). "
        "All clinical data coding adheres strictly to HIPAA Title II Administrative Simplification regulations, "
        "AHIMA/AAPC ethics standards, and international medical documentation confidentiality rules.",
        st['legal_text']
    )
    story.append(legal_p)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_BORDER, spaceAfter=8))
    
    footer_p = Paragraph(
        f"Kodafriq Platform Inc. &bull; Invoice Ref: {invoice.invoice_ref} &bull; Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} &bull; Page 1 of 1",
        st['legal_text']
    )
    story.append(footer_p)

    doc.build(story)
    buffer.seek(0)
    return buffer


def generate_candidate_statement_pdf(candidate, invoices, ledger_summary, next_payout_date=None):
    """
    Generates an executive earnings statement PDF for candidates.
    Serves as official income verification and tax documentation.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    st = get_pdf_styles()
    story = []
    user = candidate.user

    # Header
    left_brand = [
        Paragraph("KODAFRIQ", st['brand_title']),
        Paragraph("OFFICIAL TALENT EARNINGS STATEMENT", st['brand_sub']),
        Spacer(1, 4),
        Paragraph("Healthcare Professional Verified Compensation Record", st['cell_muted']),
    ]
    
    right_meta = [
        Paragraph("<b>STATEMENT OF EARNINGS</b>", st['inv_title']),
        Paragraph(f"Generated: {datetime.utcnow().strftime('%B %d, %Y')}", st['inv_meta']),
        Paragraph(f"Verified Score: <b>{candidate.kodafriq_verified_score:.1f} pts</b>", st['inv_meta']),
        Paragraph("Currency: USD ($)", st['inv_meta']),
    ]
    
    header_table = Table([[left_brand, right_meta]], colWidths=[310, 230])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=GRAY_BORDER, spaceAfter=14))

    # Candidate Profile & Payout Destination Box
    payout_prof = getattr(candidate, 'payout_profile', None)
    dest_str = "Not yet configured"
    if payout_prof and payout_prof.is_configured:
        dest_str = payout_prof.destination_summary

    p_data = [
        [
            Paragraph("<b>HEALTHCARE PROFESSIONAL</b>", st['sec_header']),
            Paragraph("<b>PAYOUT DESTINATION &amp; SCHEDULE</b>", st['sec_header']),
        ],
        [
            Paragraph(f"<b>{user.get_full_name() or user.username}</b>", st['cell_bold']),
            Paragraph(f"Destination: <b>{dest_str}</b>", st['cell_bold']),
        ],
        [
            Paragraph(f"Specialty: {candidate.headline or 'Clinical Coder & HIM Specialist'}", st['cell_normal']),
            Paragraph(f"Next Weekly Payout: <b>{next_payout_date.strftime('%A, %b %d') if next_payout_date else 'Friday Weekly Run'}</b>", st['cell_normal']),
        ],
        [
            Paragraph(f"Email: {user.email}", st['cell_muted']),
            Paragraph("Disbursement Rail: Non-Custodial Mobile Money / African Banking Network", st['cell_muted']),
        ]
    ]
    pt = Table(p_data, colWidths=[270, 270])
    pt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRAY_BG),
        ('BOX', (0, 0), (-1, -1), 1, GRAY_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(pt)
    story.append(Spacer(1, 14))

    # Financial Summary Metrics Cards
    avail_val = ledger_summary.get('available_balance', 0) if isinstance(ledger_summary, dict) else getattr(ledger_summary, 'available_balance', 0)
    pend_val = ledger_summary.get('pending_balance', 0) if isinstance(ledger_summary, dict) else getattr(ledger_summary, 'pending_balance', 0)
    paid_val = ledger_summary.get('paid_to_date', 0) if isinstance(ledger_summary, dict) else getattr(ledger_summary, 'paid_to_date', 0)

    metrics_data = [
        [
            Paragraph(
                f"<font color='{HEX_MUTED}'>AVAILABLE FOR PAYOUT</font><br/>"
                f"<font size='14' color='{HEX_EMERALD}'><b>${avail_val:.2f}</b></font><br/>"
                f"<font size='7' color='{HEX_MUTED}'>Settled, queued for Friday payout</font>",
                st['cell_normal']
            ),
            Paragraph(
                f"<font color='{HEX_MUTED}'>PENDING IN REVIEW</font><br/>"
                f"<font size='14' color='{HEX_AMBER}'><b>${pend_val:.2f}</b></font><br/>"
                f"<font size='7' color='{HEX_MUTED}'>Hours / milestones under audit</font>",
                st['cell_normal']
            ),
            Paragraph(
                f"<font color='{HEX_MUTED}'>TOTAL PAID TO DATE</font><br/>"
                f"<font size='14' color='{HEX_NAVY}'><b>${paid_val:.2f}</b></font><br/>"
                f"<font size='7' color='{HEX_MUTED}'>Lifetime completed disbursements</font>",
                st['cell_normal']
            ),
        ]
    ]
    mt = Table(metrics_data, colWidths=[180, 180, 180])
    mt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1, ACCENT_BLUE),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BFDBFE')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(mt)
    story.append(Spacer(1, 16))

    # Statement Invoices Table
    story.append(Paragraph("<b>HISTORICAL EARNINGS &amp; SETTLEMENT LEDGER</b>", st['sec_header']))
    story.append(Spacer(1, 6))

    stmt_rows = [
        [
            Paragraph("<b>Invoice Ref</b>", st['cell_bold']),
            Paragraph("<b>Contract &amp; Period</b>", st['cell_bold']),
            Paragraph("<b>Status</b>", st['cell_bold']),
            Paragraph("<b>Payout Status</b>", st['cell_bold']),
            Paragraph("<b>Net Earnings</b>", st['cell_right']),
        ]
    ]

    for inv in invoices:
        payout_color = HEX_EMERALD if inv.payout_status == 'COMPLETED' else (HEX_ACCENT if inv.payout_status == 'QUEUED' else HEX_MUTED)
        period_str = f"{inv.billing_period_start.strftime('%b %d')} - {inv.billing_period_end.strftime('%b %d, %Y')}"
        stmt_rows.append([
            Paragraph(f"<b>{inv.invoice_ref}</b>", st['cell_normal']),
            Paragraph(f"{inv.contract.title}<br/><font color='{HEX_MUTED}'>{period_str}</font>", st['cell_normal']),
            Paragraph(inv.get_payment_status_display(), st['cell_normal']),
            Paragraph(f"<font color='{payout_color}'><b>{inv.get_payout_status_display()}</b></font>", st['cell_normal']),
            Paragraph(f"<b>${inv.talent_earnings:.2f}</b>", st['cell_right']),
        ])

    st_table = Table(stmt_rows, colWidths=[110, 180, 85, 95, 70])
    st_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#091E42')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_BG]),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(st_table)
    story.append(Spacer(1, 14))

    # Footer
    footer_p = Paragraph(
        f"Official Document &bull; Kodafriq Healthcare Platform &bull; Candidate ID: {candidate.id} &bull; Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        st['legal_text']
    )
    story.append(footer_p)

    doc.build(story)
    buffer.seek(0)
    return buffer
