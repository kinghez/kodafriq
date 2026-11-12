import os
import shutil
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# Paths
OUTPUT_DIR = "/home/kinghez/kodafriq/media/training/materials/it_foundations"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Brand colors
NAVY = colors.HexColor("#0A1128")
BLUE = colors.HexColor("#006FE6")
LIGHT_BLUE = colors.HexColor("#EFF6FF")
TEAL = colors.HexColor("#0D9488")
DARK_SLATE = colors.HexColor("#1E293B")
MUTED_SLATE = colors.HexColor("#475569")
LIGHT_BG = colors.HexColor("#F8FAFC")
BORDER_COLOR = colors.HexColor("#CBD5E1")
ALERT_BG = colors.HexColor("#FEF3C7")
ALERT_BORDER = colors.HexColor("#D97706")

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        # Top header line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(40, 755, 572, 755)
        
        # Header text
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(BLUE)
        self.drawString(40, 760, "KODAFRIQ DATA MANAGEMENT SOLUTIONS")
        self.setFont("Helvetica", 8)
        self.setFillColor(MUTED_SLATE)
        self.drawRightString(572, 760, "Foundational IT Skills & Digital Competency")
        
        # Bottom footer line
        self.line(40, 45, 572, 45)
        self.setFont("Helvetica", 8)
        self.drawString(40, 32, "Confidential & Educational Material © Kodafriq Academy")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 32, page_text)
        self.restoreState()


def get_custom_styles():
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=NAVY,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=MUTED_SLATE,
        spaceAfter=12
    ))
    styles.add(ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=BLUE,
        spaceBefore=14,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        'SubSectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=DARK_SLATE,
        spaceBefore=8,
        spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        'BodyCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=DARK_SLATE,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=DARK_SLATE
    ))
    styles.add(ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=DARK_SLATE,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=DARK_SLATE
    ))
    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    ))
    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=DARK_SLATE
    ))
    styles.add(ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=DARK_SLATE
    ))
    return styles


def build_callout(text, styles, alert=False):
    bg_col = ALERT_BG if alert else LIGHT_BLUE
    border_col = ALERT_BORDER if alert else BLUE
    p = Paragraph(text, styles['CalloutText'])
    t = Table([[p]], colWidths=[532])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_col),
        ('BOX', (0,0), (-1,-1), 1, border_col),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    return t


# ==============================================================================
# PDF 1: IT Remote Work Foundations Comprehensive Study Guide
# ==============================================================================
def generate_study_guide():
    filename = os.path.join(OUTPUT_DIR, "IT_Remote_Work_Foundations_Study_Guide.pdf")
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55
    )
    styles = get_custom_styles()
    story = []

    # Title & Badge
    story.append(Paragraph("Essential IT Skills & Remote Work Competency Guide", styles['DocTitle']))
    story.append(Paragraph("Comprehensive Study Handbook • Digital Workspace Operations, Productivity & Security", styles['DocSubtitle']))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceBefore=2, spaceAfter=10))

    intro_box = "<b>Course Objective:</b> This handbook prepares professionals to operate reliably, efficiently, and securely in modern remote and online workspaces. It covers foundational operating systems, cloud productivity, cybersecurity vigilance, and emergency troubleshooting."
    story.append(build_callout(intro_box, styles))
    story.append(Spacer(1, 10))

    # SECTION 1
    story.append(Paragraph("1. Computer Operating Systems & File Organization", styles['SectionHeader']))
    story.append(Paragraph(
        "A clear understanding of directory structures, document types, and file handling prevents data loss and maintains workflow integrity in corporate environments.",
        styles['BodyCustom']
    ))

    story.append(Paragraph("File vs. Folder Management", styles['SubSectionHeader']))
    story.append(Paragraph("• <b>Folder Purpose:</b> A folder (or directory) is a virtual container used to store, organize, and categorize files and subfolders logically on a storage device. Effective folder structuring (e.g., <i>Clients / 2026 / Invoices /</i>) ensures team members can locate documents instantly.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Portable Document Format (PDF):</b> The standard format designed by Adobe to present and exchange documents reliably across all platforms (Windows, Mac, iOS, Android). Its primary purpose is <b>preserving visual formatting, typography, images, and layout</b> regardless of the software, hardware, or screen size used to view it.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Preserving Master Documents:</b> When instructed to edit a document without modifying the original (such as an assessment rubric, invoice template, or contract), immediately open the file and choose <b>File &gt; Save As</b> (or duplicate the file) with a new descriptive name before making any changes.", styles['BulletCustom']))

    story.append(Spacer(1, 6))
    story.append(Paragraph("Essential Universal Keyboard Shortcuts (Windows & Web)", styles['SubSectionHeader']))

    shortcuts_data = [
        [Paragraph("Shortcut", styles['TableHeader']), Paragraph("Action / Function", styles['TableHeader']), Paragraph("Context & Best Practice", styles['TableHeader'])],
        [Paragraph("Ctrl + C", styles['TableCellBold']), Paragraph("Copy selected text / item", styles['TableCell']), Paragraph("Copies to clipboard without removing original")],
        [Paragraph("Ctrl + V", styles['TableCellBold']), Paragraph("Paste copied item", styles['TableCell']), Paragraph("Inserts clipboard contents at cursor position")],
        [Paragraph("Ctrl + X", styles['TableCellBold']), Paragraph("Cut selected item", styles['TableCell']), Paragraph("Removes item and moves it to clipboard")],
        [Paragraph("Ctrl + Z", styles['TableCellBold']), Paragraph("Undo last action", styles['TableCell']), Paragraph("Instantly reverses typos or accidental deletions")],
        [Paragraph("Ctrl + S", styles['TableCellBold']), Paragraph("Save active file", styles['TableCell']), Paragraph("Press frequently when working on offline documents")],
        [Paragraph("Windows + L", styles['TableCellBold']), Paragraph("Lock computer screen", styles['TableCell']), Paragraph("Mandatory security practice whenever stepping away")],
        [Paragraph("Ctrl+Shift+Esc", styles['TableCellBold']), Paragraph("Open Task Manager", styles['TableCell']), Paragraph("Direct access to monitor RAM, CPU, or kill frozen apps")],
        [Paragraph("Alt + Tab", styles['TableCellBold']), Paragraph("Switch between open windows", styles['TableCell']), Paragraph("Fast multitasking without touching the mouse")]
    ]
    t_short = Table(shortcuts_data, colWidths=[90, 190, 252])
    t_short.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_short)
    story.append(Spacer(1, 10))

    # SECTION 2
    story.append(Paragraph("2. Web Browsers, Cloud Collaboration & Digital Communication", styles['SectionHeader']))
    story.append(Paragraph("• <b>Web Browsers:</b> A web browser is an application software used to access, retrieve, and view web pages on the internet. Major standard browsers include <b>Google Chrome, Microsoft Edge, Mozilla Firefox, and Apple Safari</b>. Note that Google, Bing, and Yahoo are <i>search engines</i>, not browsers.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Spreadsheet Applications:</b> <b>Microsoft Excel</b> and <b>Google Sheets</b> are designed for data analysis, mathematical calculations, tabular records, budgeting, and medical billing ledgers.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Cloud Storage Services:</b> Examples include <b>Google Drive, Microsoft OneDrive, Dropbox, and Box</b>. Cloud storage provides centralized file access across devices, automated synchronization, and encrypted offsite redundancy.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Professional Email Protocols (To vs. CC vs. BCC):</b>", styles['BulletCustom']))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;– <b>To:</b> Primary individuals responsible for taking direct action.", styles['BulletCustom']))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;– <b>CC (Carbon Copy):</b> Secondary recipients included for <b>informational awareness and keeping in the loop</b>. All recipients can see CC addresses.", styles['BulletCustom']))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;– <b>BCC (Blind Carbon Copy):</b> Recipients whose email addresses are kept hidden from all other recipients.", styles['BulletCustom']))

    story.append(PageBreak())

    # SECTION 3
    story.append(Paragraph("3. Cybersecurity Hygiene & Data Protection in Remote Environments", styles['SectionHeader']))
    story.append(Paragraph(
        "Remote staff are the primary target for cyber attackers. Exercising heightened vigilance safeguards confidential patient, corporate, and financial records.",
        styles['BodyCustom']
    ))

    cyber_box = "<b>CRITICAL RULE:</b> Never click links or open attachments in unsolicited emails urging immediate action. Legitimate supervisors or IT personnel will never demand your personal login credentials via email."
    story.append(build_callout(cyber_box, styles, alert=True))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Key Security Concepts", styles['SubSectionHeader']))
    story.append(Paragraph("• <b>Phishing:</b> A fraudulent social engineering technique where cybercriminals impersonate reputable organizations, banks, or colleagues via email, text, or messaging to trick victims into revealing sensitive information, passwords, or installing malware.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Spotting Email Spoofing & Phishing:</b> Always scrutinize the exact sender email domain. For instance, an email appearing to come from <i>supervisor@kodafriq.com</i> might actually originate from <i>supervisor@kodafr1q-corp.org</i>. Look for urgent threats (\"Your account will be suspended within 1 hour\"), mismatched links, and requests to provide passwords. If suspected, verify via an independent channel (e.g. phone call or Slack).", styles['BulletCustom']))
    story.append(Paragraph("• <b>Strong Password Strategy:</b> A strong password should be a lengthy passphrase (14+ characters) combining uppercase letters, lowercase letters, numbers, and symbols (e.g., <i>Blue#Ocean2026!Lighthouse</i>). Avoid personal details, pet names, or sequential characters (123456). Utilize a verified Password Manager (such as Bitwarden or 1Password) and enable Multi-Factor Authentication (MFA).", styles['BulletCustom']))
    story.append(Paragraph("• <b>Safely Transmitting Confidential Data:</b> Never transmit sensitive client/patient records through unencrypted consumer email or public chat apps. Always use password-protected, encrypted cloud links with restricted view/download permissions (e.g., restricted Google Drive or OneDrive shared folders requiring corporate sign-in).", styles['BulletCustom']))
    story.append(Paragraph("• <b>Locking Workstations (Physical Hygiene):</b> Whenever stepping away from your workspace—even for 30 seconds—press <b>Windows Key + L</b> (or <i>Cmd + Ctrl + Q</i> on Mac) to lock the screen and prevent unauthorized physical access.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Data Backup & Redundancy:</b> Backups safeguard against hardware failure, accidental file deletion, ransomware, and theft. The gold standard is the <b>3-2-1 Rule</b>: maintain 3 copies of your data on 2 different media types, with 1 copy stored securely offsite in the cloud.", styles['BulletCustom']))

    story.append(Spacer(1, 10))

    # SECTION 4
    story.append(Paragraph("4. Remote Work Infrastructure, Hardware & Diagnostics", styles['SectionHeader']))

    story.append(Paragraph("Network & Power Resilience", styles['SubSectionHeader']))
    story.append(Paragraph("• <b>Wi-Fi (Wireless Fidelity):</b> A wireless networking technology used to connect computers, tablets, and smartphones to local networks and high-speed internet without physical Ethernet cables.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Emergency Internet Contingency:</b> If your primary home Wi-Fi or broadband drops during an important remote shift or live meeting, immediately switch to a pre-configured mobile cellular hotspot (via your smartphone) and notify your supervisor or team via text or messaging.", styles['BulletCustom']))
    story.append(Paragraph("• <b>UPS (Uninterruptible Power Supply):</b> A specialized hardware device containing a battery backup that provides instantaneous temporary electrical power during utility outages or voltage fluctuations. A UPS gives you sufficient time to save open files, avoid data corruption, and gracefully shut down your equipment.", styles['BulletCustom']))

    story.append(Spacer(1, 6))
    story.append(Paragraph("Troubleshooting Freezes, Sluggish Performance & Meetings", styles['SubSectionHeader']))
    story.append(Paragraph("• <b>Unresponsive / Frozen Computer:</b> If your system freezes completely: 1) Wait 30-60 seconds to allow background processes to settle. 2) Press <b>Ctrl + Shift + Esc</b> to open Task Manager. 3) Select the unresponsive application and click <b>End Task</b>. Only perform a hard power shutdown (holding power button for 10 seconds) as an absolute last resort.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Slow Computer During Remote Meetings:</b> Video conferencing apps (Zoom, Teams, Google Meet) require significant RAM and CPU. If your system lags, immediately close unused browser tabs, background apps, and cloud syncing tools.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Microphone Not Working in Online Meetings:</b> If participants cannot hear you: 1) Verify you are not hardware-muted (check the in-line mute switch on your headset). 2) Open the meeting platform audio settings (Zoom/Teams/Meet) and verify that the <b>correct microphone input device</b> is selected rather than a disabled system mic.", styles['BulletCustom']))

    doc.build(story, canvasmaker=NumberedCanvas)
    return filename


# ==============================================================================
# PDF 2: Cybersecurity & Safe Data Handling Quick Reference Card
# ==============================================================================
def generate_cybersecurity_cheat_sheet():
    filename = os.path.join(OUTPUT_DIR, "Cybersecurity_and_Data_Protection_Cheat_Sheet.pdf")
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55
    )
    styles = get_custom_styles()
    story = []

    story.append(Paragraph("Cybersecurity & Remote Data Protection Card", styles['DocTitle']))
    story.append(Paragraph("Quick Reference Standard Operating Procedure for Remote Healthcare & Digital Professionals", styles['DocSubtitle']))
    story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceBefore=2, spaceAfter=10))

    banner = "<b>SECURITY AWARENESS PRINCIPLE:</b> Treat every unsolicited communication, urgent transfer request, or password prompt with constructive skepticism. Data breaches are almost always preventable with proper verification procedures."
    story.append(build_callout(banner, styles))
    story.append(Spacer(1, 10))

    story.append(Paragraph("1. Phishing & Email Fraud Detection Checklist", styles['SectionHeader']))
    
    phish_data = [
        [Paragraph("Red Flag Indicator", styles['TableHeader']), Paragraph("How to Spot It", styles['TableHeader']), Paragraph("Correct Immediate Response", styles['TableHeader'])],
        [
            Paragraph("Spoofed Email Domain", styles['TableCellBold']),
            Paragraph("Look past the sender display name. E.g., 'Google Admin &lt;security@g00gle-support.co&gt;'", styles['TableCell']),
            Paragraph("Do not reply. Report to IT security immediately.", styles['TableCell'])
        ],
        [
            Paragraph("Artificial Urgency", styles['TableCellBold']),
            Paragraph("Demands action in 15 mins ('Account termination imminent', 'Immediate wire required')", styles['TableCell']),
            Paragraph("Pause. Legitimate policies do not demand frantic password submissions.", styles['TableCell'])
        ],
        [
            Paragraph("Unexpected Attachments", styles['TableCellBold']),
            Paragraph("Unsolicited invoices or archives with extensions like .zip, .exe, or .iso", styles['TableCell']),
            Paragraph("Never open or download. Verify with sender over phone or Slack first.", styles['TableCell'])
        ],
        [
            Paragraph("Credential Harvesting", styles['TableCellBold']),
            Paragraph("Links leading to fake login portals mimicking Microsoft 365, Google, or Kodafriq", styles['TableCell']),
            Paragraph("Check browser address bar: verify exact HTTPS domain name before typing credentials.", styles['TableCell'])
        ]
    ]
    t_phish = Table(phish_data, colWidths=[120, 212, 200])
    t_phish.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_phish)
    story.append(Spacer(1, 10))

    story.append(Paragraph("2. Password Hygiene & Access Controls", styles['SectionHeader']))
    story.append(Paragraph("• <b>Passphrase Architecture:</b> Replace short, complex words with long passphrases: <i>Sunny#Mountain982$Coffee</i> is exponentially harder for brute-force algorithms to crack than <i>P@ssw0rd!</i>.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Multi-Factor Authentication (MFA):</b> Always enable app-based 2FA (Google Authenticator, Microsoft Authenticator) across all work email, cloud drives, and Kodafriq accounts.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Workstation Physical Security:</b> Lock your PC screen with <b>Windows + L</b> when leaving your chair, even in a home setting.", styles['BulletCustom']))

    story.append(Spacer(1, 10))
    story.append(Paragraph("3. Confidential File Sharing Protocol", styles['SectionHeader']))
    story.append(Paragraph("When collaborating remotely with team members or clients on proprietary or medical data:", styles['BodyCustom']))
    story.append(Paragraph("1. <b>Never email raw CSV or unencrypted sheets</b> containing patient health information (PHI) or personal financial data.", styles['BulletCustom']))
    story.append(Paragraph("2. <b>Upload to authenticated company cloud storage</b> (Google Drive, OneDrive, Dropbox).", styles['BulletCustom']))
    story.append(Paragraph("3. <b>Configure strict role-based access:</b> Set link permissions to 'Specific People Only' or require company organizational sign-in.", styles['BulletCustom']))
    story.append(Paragraph("4. <b>Disable direct public link sharing:</b> Avoid setting links to 'Anyone with the link can edit'.", styles['BulletCustom']))

    story.append(Spacer(1, 10))
    story.append(Paragraph("4. The 3-2-1 Backup Rule", styles['SectionHeader']))
    backup_text = "<b>The 3-2-1 Principle:</b> Keep <b>3</b> copies of critical files (1 active working copy + 2 backups) on <b>2</b> different media formats (e.g., local hard drive + external drive), with <b>1</b> copy kept completely offsite in a secure cloud service (Google Drive, OneDrive, or AWS S3)."
    story.append(build_callout(backup_text, styles))

    doc.build(story, canvasmaker=NumberedCanvas)
    return filename


# ==============================================================================
# PDF 3: Remote Troubleshooting & System Recovery Playbook
# ==============================================================================
def generate_troubleshooting_playbook():
    filename = os.path.join(OUTPUT_DIR, "Remote_Troubleshooting_and_System_Recovery_Playbook.pdf")
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55
    )
    styles = get_custom_styles()
    story = []

    story.append(Paragraph("Remote Troubleshooting & System Recovery Playbook", styles['DocTitle']))
    story.append(Paragraph("Emergency Runbook • Resolving Freezes, Audio Glitches, Internet Drops & Power Outages", styles['DocSubtitle']))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#D97706"), spaceBefore=2, spaceAfter=10))

    banner = "<b>OPERATIONAL READINESS:</b> Technical hiccups happen in remote work. Employers and clients evaluate remote professionals by how swiftly and calmly they diagnose and resolve technical disruptions."
    story.append(build_callout(banner, styles))
    story.append(Spacer(1, 10))

    story.append(Paragraph("1. Resolving Frozen Applications & System Crashes", styles['SectionHeader']))
    story.append(Paragraph("When your cursor stops responding or an app shows '(Not Responding)':", styles['BodyCustom']))
    story.append(Paragraph("• <b>Step 1: Wait 30 to 60 seconds.</b> Heavy calculations or network calls often resolve on their own.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Step 2: Launch Task Manager.</b> Press <b>Ctrl + Shift + Esc</b> simultaneously (or <b>Ctrl + Alt + Del</b> &gt; Task Manager).", styles['BulletCustom']))
    story.append(Paragraph("• <b>Step 3: Identify & Kill the Process.</b> In the 'Processes' tab, select the frozen app and click <b>End Task</b>.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Step 4: Hard Reboot (Last Resort).</b> Only hold the power button down for 10 seconds if keyboard input is completely dead, as sudden power cuts can corrupt unsaved system files.", styles['BulletCustom']))

    story.append(Spacer(1, 10))
    story.append(Paragraph("2. Optimizing Slow Computers During Video Calls", styles['SectionHeader']))
    story.append(Paragraph("Video calls consume heavy RAM and CPU cycles. If your system stutters during a meeting:", styles['BodyCustom']))
    story.append(Paragraph("• <b>Close Background Browser Tabs:</b> Modern tabs (especially social media and video feeds) consume several gigabytes of memory.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Pause Cloud Syncing:</b> Temporarily pause Dropbox, OneDrive, or Google Drive background syncing.", styles['BulletCustom']))
    story.append(Paragraph("• <b>Turn Off Virtual Backgrounds:</b> Artificial blur and background replacement graphics place heavy demands on your computer's GPU.", styles['BulletCustom']))

    story.append(Spacer(1, 10))
    story.append(Paragraph("3. Microphone & Audio Diagnostic Matrix", styles['SectionHeader']))
    
    audio_data = [
        [Paragraph("Symptom", styles['TableHeader']), Paragraph("Likely Cause", styles['TableHeader']), Paragraph("Step-by-Step Resolution", styles['TableHeader'])],
        [
            Paragraph("Colleagues cannot hear you", styles['TableCellBold']),
            Paragraph("Hardware mute or wrong input device selected", styles['TableCell']),
            Paragraph("1. Check physical headset mute switch.<br/>2. In Zoom/Teams/Meet settings, check 'Microphone' dropdown.<br/>3. Ensure browser permissions allow microphone access.", styles['TableCell'])
        ],
        [
            Paragraph("You cannot hear meeting audio", styles['TableCellBold']),
            Paragraph("Audio output routed to wrong speaker or Bluetooth", styles['TableCell']),
            Paragraph("1. Check Windows speaker icon in taskbar.<br/>2. Confirm audio device is not routed to disconnected Bluetooth headphones.", styles['TableCell'])
        ],
        [
            Paragraph("Echo or feedback", styles['TableCellBold']),
            Paragraph("Multiple open meeting sessions or open speakers", styles['TableCell']),
            Paragraph("Wear headphones to isolate microphone from speaker output; close duplicate meeting tabs.", styles['TableCell'])
        ]
    ]
    t_audio = Table(audio_data, colWidths=[130, 160, 242])
    t_audio.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), NAVY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, LIGHT_BG]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_audio)

    story.append(Spacer(1, 10))
    story.append(Paragraph("4. Internet & Power Contingency Procedures", styles['SectionHeader']))
    story.append(Paragraph("• <b>Primary Internet Drop:</b> Immediately activate your mobile smartphone hotspot. Keep your phone tethering configured and tested beforehand. Notify your team immediately: <i>'Primary Wi-Fi experienced a brief hiccup; switching to mobile hotspot.'</i>", styles['BulletCustom']))
    story.append(Paragraph("• <b>Power Outages & UPS Systems:</b> An <b>Uninterruptible Power Supply (UPS)</b> provides battery power during electricity cuts. When the alarm sounds, immediately save all open spreadsheets/documents, safely shut down non-essential equipment, and notify your supervisor.", styles['BulletCustom']))

    doc.build(story, canvasmaker=NumberedCanvas)
    return filename

if __name__ == "__main__":
    f1 = generate_study_guide()
    f2 = generate_cybersecurity_cheat_sheet()
    f3 = generate_troubleshooting_playbook()
    print("Generated:")
    print("1:", f1)
    print("2:", f2)
    print("3:", f3)
