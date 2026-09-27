from django.db import models
from apps.accounts.models import CandidateProfile
from apps.skills.models import Skill

class TrainingProgram(models.Model):
    title = models.CharField(max_length=200)
    instructor = models.CharField(max_length=150, default="Kodafriq Clinical Faculty")
    instructor_title = models.CharField(max_length=150, default="Lead Clinical Faculty", blank=True, help_text="Signatory title displayed on certificate")
    certificate_subtitle = models.CharField(max_length=200, default="Certificate of Completion", blank=True, help_text="Certificate main heading, e.g. Certificate of Completion")
    accreditation_statement = models.CharField(max_length=250, default="CONTINUING CLINICAL EDUCATION & ACCREDITATION", blank=True, help_text="Accreditation sub-banner on certificate")
    description = models.TextField()
    curriculum_overview = models.TextField(blank=True)
    skills_covered = models.ManyToManyField(Skill, blank=True, related_name='training_programs')
    duration_weeks = models.PositiveIntegerField(default=4)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.duration_weeks} wks)"

    @property
    def total_modules(self):
        return self.modules.count()


class ProgramModule(models.Model):
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=1)
    duration_minutes = models.PositiveIntegerField(default=45, help_text="Estimated study duration in minutes")
    content = models.TextField(help_text="Clinical guidelines, chart scenarios, and curriculum material")
    key_takeaways = models.TextField(blank=True, help_text="Core clinical coding rules and guidelines")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('program', 'order')

    def __str__(self):
        return f"{self.program.title} - M{self.order}: {self.title}"


class TrainingEnrolment(models.Model):
    class EnrolmentStatus(models.TextChoices):
        ENROLLED = 'ENROLLED', 'Enrolled'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed & Certified'
        DROPPED = 'DROPPED', 'Withdrawn'

    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name='enrolments')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='training_enrolments')
    status = models.CharField(max_length=25, choices=EnrolmentStatus.choices, default=EnrolmentStatus.ENROLLED)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=100.00)
    final_assessment_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    certificate_id = models.CharField(max_length=50, blank=True, unique=True, null=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('program', 'candidate')

    def __str__(self):
        return f"{self.candidate.full_name} in {self.program.title} [{self.get_status_display()}]"

    @property
    def total_modules_count(self):
        return self.program.modules.count()

    @property
    def completed_modules_count(self):
        return self.module_progresses.filter(is_completed=True).count()

    @property
    def progress_percentage(self):
        total = self.total_modules_count
        if total == 0:
            return 100 if self.status == self.EnrolmentStatus.COMPLETED else 0
        completed = self.completed_modules_count
        return int(round((completed / total) * 100))


class ModuleProgress(models.Model):
    enrolment = models.ForeignKey(TrainingEnrolment, on_delete=models.CASCADE, related_name='module_progresses')
    module = models.ForeignKey(ProgramModule, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('enrolment', 'module')

    def __str__(self):
        return f"{self.enrolment.candidate.full_name} - {self.module.title} [{'Done' if self.is_completed else 'Pending'}]"


class CertificateTemplateConfig(models.Model):
    class BorderStyle(models.TextChoices):
        DOUBLE = 'double', 'Double Border (Classic Prestigious)'
        SOLID = 'solid', 'Solid Bold Border (Modern Minimal)'
        GROOVE = 'groove', 'Grooved Border (Formal Academic)'
        DUAL_FRAME = 'dual_frame', 'Dual Frame (Luxury Inset)'

    class SignatureFont(models.TextChoices):
        CAVEAT = 'Caveat', 'Caveat (Fluid Hand-drawn Script)'
        GREAT_VIBES = 'Great Vibes', 'Great Vibes (Formal Calligraphy)'
        DANCING_SCRIPT = 'Dancing Script', 'Dancing Script (Modern Script)'
        ALLURA = 'Allura', 'Allura (Classic Elegance)'

    # Faculty & Signatory
    faculty_header_text = models.CharField(
        max_length=150, 
        default="KODAFRIQ CLINICAL FACULTY",
        help_text="Header text on the top-left corner of the certificate"
    )
    signatory_name = models.CharField(
        max_length=150, 
        default="Dr. Chioma Adeyemi, MD, CCS, CCDS",
        help_text="Signatory name (e.g. Lead Clinical Faculty personnel)"
    )
    signatory_title = models.CharField(
        max_length=150, 
        default="Lead Clinical Faculty",
        help_text="Signatory title displayed beneath signature line"
    )
    signatory_signature_image = models.FileField(
        upload_to='certificates/signatures/', 
        null=True, 
        blank=True,
        help_text="Upload official signature image (transparent PNG recommended). If omitted, an elegant cursive script font is rendered."
    )
    signatory_font_family = models.CharField(
        max_length=50,
        choices=SignatureFont.choices,
        default=SignatureFont.CAVEAT,
        help_text="Cursive font family used when no signature image is uploaded"
    )

    # Branding & Header
    organization_name = models.CharField(
        max_length=100, 
        default="Kodafriq",
        help_text="Organization brand name displayed in header"
    )
    organization_logo = models.FileField(
        upload_to='certificates/logos/', 
        null=True, 
        blank=True,
        help_text="Upload custom organization logo. If empty, the standard Kodafriq brand mark is used."
    )
    accreditation_badge_text = models.CharField(
        max_length=150, 
        default="VERIFIED ACCREDITED CREDENTIAL",
        help_text="Accreditation badge in top-right corner"
    )
    accreditation_subtitle = models.CharField(
        max_length=200, 
        default="CONTINUING CLINICAL EDUCATION & ACCREDITATION",
        help_text="Subtitle under the organization logo"
    )
    certificate_title = models.CharField(
        max_length=150, 
        default="CERTIFICATE OF COMPLETION",
        help_text="Main heading on the certificate"
    )
    certifies_statement = models.CharField(
        max_length=150, 
        default="This hereby certifies that",
        help_text="Introductory text before candidate's name"
    )
    fulfillment_statement = models.TextField(
        default="has successfully fulfilled all academic curriculum requirements, practical clinical coding audits, and quality standards for:",
        help_text="Curriculum completion statement before program title"
    )

    # Color Scheme & Aesthetics
    primary_border_color = models.CharField(
        max_length=20, 
        default="#006fe6",
        help_text="Outer border color and primary brand accents (HEX or CSS color)"
    )
    secondary_border_color = models.CharField(
        max_length=20, 
        default="#0284c7",
        help_text="Inner border accent and subtitle color (HEX or CSS color)"
    )
    seal_color = models.CharField(
        max_length=20, 
        default="#10b981",
        help_text="Accredited circular seal border and shield color"
    )
    seal_background = models.CharField(
        max_length=20, 
        default="#ecfdf5",
        help_text="Accredited circular seal background fill"
    )
    seal_title = models.CharField(
        max_length=50, 
        default="VERIFIED",
        help_text="Text displayed in the circular security seal"
    )
    seal_subtitle = models.CharField(
        max_length=50, 
        default="ACCREDITED",
        help_text="Subtext displayed in the circular security seal"
    )
    border_style = models.CharField(
        max_length=20, 
        choices=BorderStyle.choices, 
        default=BorderStyle.DOUBLE,
        help_text="Border framing style for the certificate"
    )

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Certificate Design Configuration"
        verbose_name_plural = "Certificate Design Configuration"

    def __str__(self):
        return f"Certificate Template Configuration (Updated {self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else 'Active'})"

    def save(self, *args, **kwargs):
        # When an active configuration is saved, ensure it is the singular active config
        if self.is_active:
            CertificateTemplateConfig.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        config = cls.objects.filter(is_active=True).order_by('-updated_at', '-id').first()
        if not config:
            config = cls.objects.order_by('-updated_at', '-id').first()
        if not config:
            config = cls.objects.create(is_active=True)
        return config


class TrainingMaterial(models.Model):
    class MaterialType(models.TextChoices):
        DOCUMENT = 'DOCUMENT', 'Document (PDF, Word DOCX, Excel, Slides)'
        VIDEO = 'VIDEO', 'Video Upload (MP4, WebM, MOV)'
        VIDEO_EMBED = 'VIDEO_EMBED', 'External Video Link (YouTube, Vimeo, Loom)'
        AUDIO = 'AUDIO', 'Audio Lecture / Podcast (MP3, WAV)'
        RESOURCE = 'RESOURCE', 'Clinical Cheat Sheet / Guide'
        EXTERNAL = 'EXTERNAL', 'External Clinical Reference URL'

    program = models.ForeignKey(
        TrainingProgram,
        on_delete=models.CASCADE,
        related_name='materials',
        null=True,
        blank=True,
        help_text="Associated training program"
    )
    module = models.ForeignKey(
        ProgramModule,
        on_delete=models.CASCADE,
        related_name='materials',
        null=True,
        blank=True,
        help_text="Optional specific module this material belongs to"
    )
    title = models.CharField(
        max_length=200,
        help_text="Descriptive title (e.g., 'ICD-10-CM Official Coding Guidelines 2026', 'Clinical Audit Walkthrough Video')"
    )
    description = models.TextField(
        blank=True,
        help_text="Brief notes or instructions for students"
    )
    material_type = models.CharField(
        max_length=25,
        choices=MaterialType.choices,
        default=MaterialType.DOCUMENT,
        help_text="Type of curriculum resource"
    )
    file = models.FileField(
        upload_to='training/materials/%Y/%m/',
        null=True,
        blank=True,
        help_text="Upload video (MP4), document (PDF, DOCX, XLSX, PPTX), or audio file"
    )
    external_url = models.URLField(
        blank=True,
        help_text="Direct URL if hosted externally (YouTube, Vimeo, Loom, Google Drive, AWS S3)"
    )
    is_downloadable = models.BooleanField(
        default=True,
        help_text="Allow enrolled candidates to download this file directly"
    )
    order = models.PositiveIntegerField(
        default=1,
        help_text="Display order sequence within the module/program"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Training Material & Upload"
        verbose_name_plural = "Training Materials & Uploads"

    def __str__(self):
        dest = self.module.title if self.module else (self.program.title if self.program else "General")
        return f"[{self.get_material_type_display()}] {self.title} ({dest})"

    def save(self, *args, **kwargs):
        # Auto-link program from module if not explicitly set
        if self.module and not self.program:
            self.program = self.module.program
        super().save(*args, **kwargs)

    @property
    def file_extension(self):
        if self.file and self.file.name:
            import os
            _, ext = os.path.splitext(self.file.name)
            return ext.lower().replace('.', '')
        return ''

    @property
    def file_size_display(self):
        if self.file:
            try:
                size = self.file.size
                if size < 1024:
                    return f"{size} B"
                elif size < 1024 * 1024:
                    return f"{size / 1024:.1f} KB"
                else:
                    return f"{size / (1024 * 1024):.1f} MB"
            except Exception:
                return ""
        return ""

    @property
    def is_video(self):
        return self.material_type in [self.MaterialType.VIDEO, self.MaterialType.VIDEO_EMBED] or self.file_extension in ['mp4', 'webm', 'mov', 'm4v']

    @property
    def is_pdf(self):
        return self.file_extension == 'pdf'

    @property
    def is_doc(self):
        return self.file_extension in ['doc', 'docx', 'odt', 'rtf', 'txt']

    @property
    def is_sheet(self):
        return self.file_extension in ['xls', 'xlsx', 'csv']

    @property
    def embed_url(self):
        if self.external_url:
            url = self.external_url
            if 'youtube.com/watch?v=' in url:
                video_id = url.split('watch?v=')[1].split('&')[0]
                return f"https://www.youtube.com/embed/{video_id}"
            elif 'youtu.be/' in url:
                video_id = url.split('youtu.be/')[1].split('?')[0]
                return f"https://www.youtube.com/embed/{video_id}"
            elif 'vimeo.com/' in url and 'player.vimeo.com' not in url:
                video_id = url.split('vimeo.com/')[1].split('?')[0]
                return f"https://player.vimeo.com/video/{video_id}"
            return url
        return ''
