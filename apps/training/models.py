from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
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

    # Monetization, Pricing & Creator Attribution
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_training_programs',
        help_text="The Kodafriq staff/creator who owns this course and earns tuition revenue"
    )
    creator_share_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('70.00'),
        help_text="Percentage of tuition revenue disbursed to the creator (e.g. 70.00%, Kodafriq retains 30%)"
    )
    is_free = models.BooleanField(
        default=True,
        help_text="Designate if this training program is completely free to enroll"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Tuition / Enrollment fee (if not free)"
    )
    currency = models.CharField(
        max_length=10,
        default='USD',
        choices=[
            ('USD', 'USD ($)'),
            ('GHS', 'GHS (GH₵)'),
            ('EUR', 'EUR (€)'),
            ('GBP', 'GBP (£)'),
        ],
        help_text="Currency for tuition fee"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        pricing_str = "Free" if not self.is_paid else self.formatted_price
        return f"{self.title} ({self.duration_weeks} wks) [{pricing_str}]"

    @property
    def total_modules(self):
        return self.modules.count()

    @property
    def is_paid(self):
        return (not self.is_free) and self.price is not None and self.price > Decimal('0.00')

    @property
    def formatted_price(self):
        if not self.is_paid:
            return "Free"
        symbols = {'USD': '$', 'GHS': 'GH₵', 'EUR': '€', 'GBP': '£'}
        symbol = symbols.get(self.currency, f"{self.currency} ")
        return f"{symbol}{self.price:.2f}"


class ProgramModule(models.Model):
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=1)
    duration_minutes = models.PositiveIntegerField(default=45, help_text="Estimated study duration in minutes")
    content = models.TextField(help_text="Clinical guidelines, chart scenarios, and curriculum material")
    key_takeaways = models.TextField(blank=True, help_text="Core clinical coding rules and guidelines")

    # Knowledge Check & Quiz Gate
    has_quiz = models.BooleanField(
        default=False,
        help_text="Require candidates to pass a module quiz before unlocking the next module"
    )
    quiz_pass_percentage = models.PositiveIntegerField(
        default=70,
        help_text="Minimum score percentage required to pass module quiz (default 70%)"
    )
    quiz_title = models.CharField(
        max_length=200,
        blank=True,
        default="Module Knowledge Check",
        help_text="Title shown above the quiz questions"
    )
    quiz_instructions = models.TextField(
        blank=True,
        default="Test your understanding of the clinical guidelines and core concepts before progressing. A minimum passing score of 70% is required.",
        help_text="Instructions displayed to candidates before taking the quiz"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        unique_together = ('program', 'order')

    def __str__(self):
        quiz_indicator = " [Quiz]" if self.requires_quiz else ""
        return f"{self.program.title} - M{self.order}: {self.title}{quiz_indicator}"

    @property
    def total_quiz_questions(self):
        return self.quiz_questions.count()

    @property
    def requires_quiz(self):
        return self.has_quiz and self.total_quiz_questions > 0


class ModuleQuizQuestion(models.Model):
    module = models.ForeignKey(ProgramModule, on_delete=models.CASCADE, related_name='quiz_questions')
    order = models.PositiveIntegerField(default=1)
    prompt = models.TextField(help_text="The question prompt for candidates")
    explanation = models.TextField(
        blank=True,
        help_text="Clinical rationale or guideline reference displayed after quiz completion"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Module Quiz Question"
        verbose_name_plural = "Module Quiz Questions"

    def __str__(self):
        return f"{self.module.title} - Q{self.order}: {self.prompt[:60]}"


class ModuleQuizOption(models.Model):
    question = models.ForeignKey(ModuleQuizQuestion, on_delete=models.CASCADE, related_name='options')
    order = models.PositiveIntegerField(default=1)
    text = models.CharField(max_length=400)
    is_correct = models.BooleanField(default=False, help_text="Designate if this option is the correct answer")

    class Meta:
        ordering = ['order', 'id']
        verbose_name = "Quiz Choice / Option"
        verbose_name_plural = "Quiz Choices / Options"

    def __str__(self):
        status = "✓" if self.is_correct else "✗"
        return f"Q{self.question.order} Option {self.order} [{status}]: {self.text[:40]}"


class TrainingCoupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'PERCENTAGE', 'Percentage Discount (%)'
        FIXED = 'FIXED', 'Fixed Amount Discount'

    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique coupon promo code (e.g. FIRST50, SKEP100, WELCOME). Case-insensitive."
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Internal notes (e.g. '100% discount for first 50 registered candidates')"
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('100.00'),
        help_text="Discount value: enter 100 for 100%, or a flat number like 40 for $40 off"
    )
    max_redemptions = models.PositiveIntegerField(
        default=50,
        null=True,
        blank=True,
        help_text="Maximum total allowed redemptions across all users (e.g. 50). Leave blank for unlimited."
    )
    times_redeemed = models.PositiveIntegerField(
        default=0,
        help_text="Total number of successful enrolments that used this coupon"
    )
    max_redemptions_per_user = models.PositiveIntegerField(
        default=1,
        help_text="Maximum times a single candidate can redeem this coupon (default 1)"
    )
    applicable_programs = models.ManyToManyField(
        'TrainingProgram',
        blank=True,
        related_name='coupons',
        help_text="Specific programs this coupon applies to. Leave empty to apply to all programs."
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiration date & time. Leave blank for no expiration."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Global toggle to activate/deactivate this coupon instantly"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Training Promotional Coupon"
        verbose_name_plural = "Training Promotional Coupons"

    def __str__(self):
        val_str = f"{self.discount_value}% OFF" if self.discount_type == self.DiscountType.PERCENTAGE else f"${self.discount_value} OFF"
        uses = f"{self.times_redeemed}/{self.max_redemptions}" if self.max_redemptions else f"{self.times_redeemed}/∞"
        return f"Coupon [{self.code}] - {val_str} (Uses: {uses})"

    def clean(self):
        if self.code:
            self.code = self.code.strip().upper()

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        if self.valid_until and timezone.now() > self.valid_until:
            return True
        return False

    @property
    def is_fully_redeemed(self):
        if self.max_redemptions is not None and self.times_redeemed >= self.max_redemptions:
            return True
        return False

    def calculate_discount(self, original_price):
        """
        Calculates (discount_amount, final_price) given an original price.
        """
        orig = Decimal(str(original_price or '0.00'))
        if orig <= Decimal('0.00'):
            return Decimal('0.00'), Decimal('0.00')

        if self.discount_type == self.DiscountType.PERCENTAGE:
            pct = Decimal(str(self.discount_value)) / Decimal('100.00')
            discount = (orig * pct).quantize(Decimal('0.01'))
        else:
            discount = Decimal(str(self.discount_value)).quantize(Decimal('0.01'))

        discount = min(orig, max(Decimal('0.00'), discount))
        final_price = max(Decimal('0.00'), orig - discount).quantize(Decimal('0.01'))
        return discount, final_price

    def validate_for_candidate(self, program, candidate_profile=None):
        """
        Validates coupon availability for a specific program and candidate.
        Returns: (is_valid: bool, error_message: str, discount_amount: Decimal, final_price: Decimal)
        """
        orig_price = program.price if program.is_paid else Decimal('0.00')

        if not self.is_active:
            return False, "This promotional coupon code is inactive or disabled.", Decimal('0.00'), orig_price

        if timezone.now() < self.valid_from:
            return False, "This promotional coupon is not yet valid.", Decimal('0.00'), orig_price

        if self.is_expired:
            return False, "This promotional coupon code has expired.", Decimal('0.00'), orig_price

        if self.is_fully_redeemed:
            return False, f"This promotional offer has reached its limit of {self.max_redemptions} redemptions.", Decimal('0.00'), orig_price

        # Check program restriction
        if self.applicable_programs.exists() and not self.applicable_programs.filter(id=program.id).exists():
            return False, "This coupon code cannot be applied to this specific training program.", Decimal('0.00'), orig_price

        # Check candidate per-user redemption limit
        if candidate_profile:
            user_redemptions = CouponRedemption.objects.filter(coupon=self, candidate=candidate_profile).count()
            if user_redemptions >= self.max_redemptions_per_user:
                return False, "You have already used this promotional coupon code.", Decimal('0.00'), orig_price

        discount_amount, final_price = self.calculate_discount(orig_price)
        return True, "Coupon code is valid and applied.", discount_amount, final_price


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

    # Payment & Coupon tracking
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    coupon_used = models.ForeignKey(TrainingCoupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='enrolments')
    payment_reference = models.CharField(max_length=100, blank=True, default='')

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


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(TrainingCoupon, on_delete=models.CASCADE, related_name='redemptions')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='coupon_redemptions')
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name='coupon_redemptions')
    enrolment = models.ForeignKey(TrainingEnrolment, on_delete=models.SET_NULL, null=True, blank=True, related_name='redemptions')
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    final_price_paid = models.DecimalField(max_digits=10, decimal_places=2)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-redeemed_at']
        verbose_name = "Coupon Redemption Audit"
        verbose_name_plural = "Coupon Redemption Audits"

    def __str__(self):
        return f"{self.candidate.full_name} redeemed [{self.coupon.code}] for {self.program.title} (-${self.discount_amount})"


class ModuleProgress(models.Model):
    enrolment = models.ForeignKey(TrainingEnrolment, on_delete=models.CASCADE, related_name='module_progresses')
    module = models.ForeignKey(ProgramModule, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    quiz_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    quiz_passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('enrolment', 'module')

    def __str__(self):
        quiz_status = f", Quiz: {self.quiz_score}%" if self.quiz_score is not None else ""
        return f"{self.enrolment.candidate.full_name} - {self.module.title} [{'Done' if self.is_completed else 'Pending'}{quiz_status}]"


class ModuleQuizAttempt(models.Model):
    enrolment = models.ForeignKey(TrainingEnrolment, on_delete=models.CASCADE, related_name='quiz_attempts')
    module = models.ForeignKey(ProgramModule, on_delete=models.CASCADE, related_name='quiz_attempts')
    score_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    total_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-attempted_at']
        verbose_name = "Module Quiz Attempt"
        verbose_name_plural = "Module Quiz Attempts"

    def __str__(self):
        result = "PASSED" if self.passed else "FAILED"
        return f"{self.enrolment.candidate.full_name} - {self.module.title}: {self.score_percentage}% [{result}]"


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


class TrainingPayment(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Payment'
        SUCCESSFUL = 'SUCCESSFUL', 'Paid & Enrolled'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'

    class Gateway(models.TextChoices):
        FLUTTERWAVE = 'FLUTTERWAVE', 'Flutterwave'
        PAYSTACK = 'PAYSTACK', 'Paystack'
        COUPON_FREE = 'COUPON_FREE', '100% Promo Coupon (Free)'
        MANUAL = 'MANUAL', 'Manual Admin Waiver'

    class CreatorPayoutStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Creator Payout'
        PAID = 'PAID', 'Settled / Disbursed to Creator'
        NOT_APPLICABLE = 'N/A', 'N/A (Free Enrollment)'

    payment_ref = models.CharField(max_length=100, unique=True, db_index=True)
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE, related_name='payments')
    candidate = models.ForeignKey(CandidateProfile, on_delete=models.CASCADE, related_name='training_payments')
    enrolment = models.ForeignKey('TrainingEnrolment', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='training_creator_earnings',
        help_text="The staff creator who earned revenue on this course purchase"
    )

    # Financial Ledger
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='USD')

    # Creator & Platform Split
    creator_share_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('70.00'))
    creator_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Payout Tracking to Creator
    creator_payout_status = models.CharField(max_length=20, choices=CreatorPayoutStatus.choices, default=CreatorPayoutStatus.PENDING)
    creator_paid_at = models.DateTimeField(null=True, blank=True)
    creator_payout_note = models.CharField(max_length=255, blank=True, default='')

    coupon = models.ForeignKey('TrainingCoupon', on_delete=models.SET_NULL, null=True, blank=True, related_name='training_payments')
    gateway = models.CharField(max_length=25, choices=Gateway.choices, default=Gateway.FLUTTERWAVE)
    gateway_reference = models.CharField(max_length=150, blank=True, default='')
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    raw_response = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Course Tuition Payment"
        verbose_name_plural = "Course Tuition Payments"

    def __str__(self):
        return f"{self.payment_ref} - {self.candidate.full_name} for {self.program.title} [{self.get_status_display()}]"

    def mark_successful(self, gateway_ref='', raw_data=None):
        self.status = self.PaymentStatus.SUCCESSFUL
        self.gateway_reference = str(gateway_ref or self.payment_ref)
        self.settled_at = timezone.now()
        if raw_data:
            self.raw_response = raw_data
        
        # Calculate splits
        if self.net_amount_paid <= Decimal('0.00'):
            self.creator_payout_status = self.CreatorPayoutStatus.NOT_APPLICABLE
            self.creator_earnings = Decimal('0.00')
            self.platform_fee = Decimal('0.00')
        else:
            pct = Decimal(str(self.creator_share_percent)) / Decimal('100.00')
            self.creator_earnings = (self.net_amount_paid * pct).quantize(Decimal('0.01'))
            self.platform_fee = max(Decimal('0.00'), self.net_amount_paid - self.creator_earnings).quantize(Decimal('0.01'))
            self.creator_payout_status = self.CreatorPayoutStatus.PENDING
        self.save()

