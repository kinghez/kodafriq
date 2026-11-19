from django.contrib import admin
from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    TrainingProgram, ProgramModule, ModuleLesson, LessonProgress, TrainingEnrolment, ModuleProgress,
    CertificateTemplateConfig, TrainingMaterial, TrainingCoupon,
    CouponRedemption, ModuleQuizQuestion, ModuleQuizOption, ModuleQuizAttempt,
    TrainingPayment
)
from .widgets import RichTextEditorWidget


class TrainingMaterialInline(admin.TabularInline):
    model = TrainingMaterial
    extra = 1
    fields = ('title', 'material_type', 'file', 'external_url', 'is_downloadable', 'order', 'file_preview')
    readonly_fields = ('file_preview',)
    ordering = ('order',)

    def file_preview(self, obj):
        if obj.pk:
            if obj.file:
                return format_html(
                    '<a href="{}" target="_blank" style="color:#006fe6;font-weight:700;text-decoration:none;">View Upload ({}) &nearr;</a>',
                    obj.file.url,
                    obj.file_size_display or obj.file_extension
                )
            elif obj.external_url:
                return format_html(
                    '<a href="{}" target="_blank" style="color:#0284c7;font-weight:700;text-decoration:none;">Open Link &nearr;</a>',
                    obj.external_url
                )
        return "—"
    file_preview.short_description = "Preview / Link"


class ModuleQuizOptionInline(admin.TabularInline):
    model = ModuleQuizOption
    extra = 3
    fields = ('order', 'text', 'is_correct')
    ordering = ('order',)


class ModuleLessonInline(admin.StackedInline):
    model = ModuleLesson
    extra = 0
    fields = ('order', 'title', 'lesson_type', 'content')
    ordering = ('order',)
    formfield_overrides = {
        models.TextField: {'widget': RichTextEditorWidget},
    }


class ModuleQuizQuestionInline(admin.StackedInline):
    model = ModuleQuizQuestion
    extra = 0
    fields = ('lesson', 'order', 'prompt', 'explanation')
    ordering = ('order',)


class ProgramModuleInline(admin.StackedInline):
    model = ProgramModule
    extra = 0
    fields = ('order', 'title', 'duration_minutes', 'has_quiz', 'quiz_pass_percentage', 'key_takeaways', 'content')
    ordering = ('order',)
    formfield_overrides = {
        models.TextField: {'widget': RichTextEditorWidget},
    }


class ProgramMaterialInline(admin.TabularInline):
    model = TrainingMaterial
    extra = 0
    fields = ('module', 'title', 'material_type', 'file', 'external_url', 'is_downloadable', 'order')
    ordering = ('order',)


class CouponRedemptionInline(admin.TabularInline):
    model = CouponRedemption
    extra = 0
    readonly_fields = ('candidate', 'program', 'original_price', 'discount_amount', 'final_price_paid', 'redeemed_at')
    can_delete = False
    ordering = ('-redeemed_at',)


@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'pricing_badge', 'creator_display', 'instructor', 'duration_weeks', 'total_modules_count', 'materials_count', 'certificate_preview', 'is_active', 'created_at')
    list_filter = ('is_free', 'currency', 'creator', 'is_active', 'duration_weeks')
    search_fields = ('title', 'instructor', 'description', 'curriculum_overview')
    filter_horizontal = ('skills_covered',)
    inlines = [ProgramModuleInline, ProgramMaterialInline]
    actions = ['activate_programs', 'deactivate_programs', 'make_free', 'make_paid_40']
    readonly_fields = ('certificate_preview_button',)
    formfield_overrides = {
        models.TextField: {'widget': RichTextEditorWidget},
    }

    fieldsets = (
        ('Program Information', {
            'fields': ('title', 'description', 'curriculum_overview', 'skills_covered', 'duration_weeks', 'start_date', 'end_date', 'is_active')
        }),
        ('Pricing, Monetization & Creator Attribution', {
            'fields': ('is_free', 'price', 'currency', 'creator', 'creator_share_percentage'),
            'description': 'Configure enrollment tuition fee and author attribution. The assigned Kodafriq staff creator will be credited with their revenue share (default 70%) on every student payment.'
        }),
        ('Accredited Certificate Configuration', {
            'fields': ('instructor', 'instructor_title', 'certificate_subtitle', 'accreditation_statement', 'certificate_preview_button'),
            'description': 'Configure the verifiable certificate text, signatory title, and accreditation metadata issued to candidates.'
        }),
    )

    def creator_display(self, obj):
        if obj.creator:
            return format_html('<strong>{}</strong> <span style="color:#64748b;font-size:0.75rem;">({}%)</span>', obj.creator.get_full_name() or obj.creator.email, int(obj.creator_share_percentage))
        return mark_safe('<span style="color:#94a3b8;font-style:italic;">Unassigned Staff</span>')
    creator_display.short_description = 'Creator (Staff)'

    def pricing_badge(self, obj):
        if not obj.is_paid:
            return mark_safe(
                '<span style="background:#ecfdf5;color:#059669;padding:3px 10px;border-radius:20px;font-weight:800;font-size:0.75rem;border:1px solid #a7f3d0;">FREE</span>'
            )
        return format_html(
            '<span style="background:#eff6ff;color:#006fe6;padding:3px 10px;border-radius:20px;font-weight:800;font-size:0.75rem;border:1px solid #bfdbfe;">{}</span>',
            obj.formatted_price
        )
    pricing_badge.short_description = 'Tuition / Price'

    def total_modules_count(self, obj):
        return obj.modules.count()
    total_modules_count.short_description = 'Modules'

    def materials_count(self, obj):
        return obj.materials.count()
    materials_count.short_description = 'Materials'

    def certificate_preview(self, obj):
        if obj.pk:
            return format_html(
                '<a href="/training/certificate/preview/program/{}/" target="_blank" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;background:#006fe6;color:#ffffff;border-radius:4px;font-weight:700;font-size:0.75rem;text-decoration:none;">Preview &rarr;</a>',
                obj.pk
            )
        return "-"
    certificate_preview.short_description = 'Certificate'

    def certificate_preview_button(self, obj):
        if obj.pk:
            return format_html(
                '<a href="/training/certificate/preview/program/{}/" target="_blank" style="display:inline-flex;align-items:center;gap:6px;padding:8px 16px;background:#006fe6;color:#ffffff;border-radius:6px;font-weight:700;font-size:0.85rem;text-decoration:none;box-shadow:0 2px 6px rgba(0,111,230,0.3);">Launch Live Certificate Preview &nearr;</a>'
                '<span style="display:block;margin-top:6px;font-size:0.78rem;color:#64748b;">Opens the rendered certificate layout for this program in a new tab.</span>',
                obj.pk
            )
        return "Save program to generate preview button."
    certificate_preview_button.short_description = 'Live Preview'

    @admin.action(description="Mark selected programs as Active")
    def activate_programs(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Mark selected programs as Inactive")
    def deactivate_programs(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Set selected programs as FREE")
    def make_free(self, request, queryset):
        queryset.update(is_free=True, price=0.00)

    @admin.action(description="Set selected programs to $40.00 USD (Paid)")
    def make_paid_40(self, request, queryset):
        queryset.update(is_free=False, price=40.00, currency='USD')


@admin.register(ProgramModule)
class ProgramModuleAdmin(admin.ModelAdmin):
    list_display = ('program', 'order', 'title', 'lessons_count', 'duration_minutes', 'quiz_status_badge', 'materials_count', 'created_at')
    list_filter = ('has_quiz', 'program')
    search_fields = ('title', 'content', 'key_takeaways', 'program__title')
    ordering = ('program', 'order')
    inlines = [ModuleLessonInline, ModuleQuizQuestionInline, TrainingMaterialInline]
    formfield_overrides = {
        models.TextField: {'widget': RichTextEditorWidget},
    }

    fieldsets = (
        ('Module Identification & Sequence', {
            'fields': ('program', 'order', 'title', 'duration_minutes'),
            'description': 'Configure the course module title and estimated reading/study time.'
        }),
        ('Clinical Curriculum & Rich Media Content', {
            'fields': ('content', 'key_takeaways'),
            'description': 'Use the rich text editor to format clinical text, embed images, link videos, or insert tables.'
        }),
        ('Knowledge Check & Progression Quiz Gate', {
            'fields': ('has_quiz', 'quiz_pass_percentage', 'quiz_title', 'quiz_instructions'),
            'description': 'If enabled, candidates must achieve at least the pass percentage (default 70%) on the module quiz before unlocking the next module.'
        }),
    )

    def lessons_count(self, obj):
        count = obj.lessons.count()
        return format_html('<strong>{}</strong> lessons', count) if count else mark_safe('<span style="color:#94a3b8;">1 (Synthesized)</span>')
    lessons_count.short_description = 'Lessons'

    def quiz_status_badge(self, obj):
        if not obj.has_quiz:
            return mark_safe('<span style="color:#94a3b8;font-size:0.75rem;">No Quiz (Direct Read)</span>')
        count = obj.quiz_questions.count()
        return format_html(
            '<span style="background:#fef3c7;color:#b45309;padding:3px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;border:1px solid #fde68a;">Quiz: {} Qs (Pass: {}%)</span>',
            count, obj.quiz_pass_percentage
        )
    quiz_status_badge.short_description = 'Quiz Requirement'

    def materials_count(self, obj):
        return obj.materials.count()
    materials_count.short_description = 'Materials'


@admin.register(ModuleLesson)
class ModuleLessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module_display', 'order', 'lesson_type_badge', 'has_example_box', 'quiz_questions_count', 'created_at')
    list_filter = ('lesson_type', 'module__program', 'module')
    search_fields = ('title', 'content', 'matching_title', 'module__title')
    ordering = ('module', 'order')
    formfield_overrides = {
        models.TextField: {'widget': RichTextEditorWidget},
    }

    fieldsets = (
        ('Lesson Identification & Sequencing', {
            'fields': ('module', 'order', 'title', 'lesson_type'),
            'description': 'Configure the chapter/page ordering and format (Reading Content, Terminology & Definitions, Drag-and-Drop Matching Quiz, or Multiple Choice Quiz).'
        }),
        ('Reading Content & Rich Media', {
            'fields': ('content',),
            'description': 'Main rich content. You can insert images, embed clinical videos, add tables, and format text with left/right wrapping.'
        }),
        ('CareerWize Floating Example Box (Right Margin)', {
            'fields': ('has_example_box', 'example_badge', 'example_image', 'example_caption'),
            'description': 'Renders a dedicated floating callout box on the right side of the lesson card (e.g. "EXAMPLE EX:" with an X-ray or diagram and clinical explanation).'
        }),
        ('Terminology & Audio Hint Definitions (JSON)', {
            'fields': ('terms_data',),
            'description': 'For Terminology lessons. Enter a JSON list of terms, e.g.: [{"term": "Osteomyelitis", "definition": "Bacterial infection of the bone...", "audio_hint": ""}]'
        }),
        ('Interactive Drag & Drop Matching Quiz (JSON)', {
            'fields': ('matching_title', 'matching_instructions', 'matching_pairs'),
            'description': 'For Matching Quiz lessons. Enter a JSON list of prompt-response pairs, e.g.: [{"prompt": "Tumor derived from blood cells", "response": "Multiple myeloma"}]'
        }),
    )

    def module_display(self, obj):
        return format_html('<span>{} &rarr; <strong>{}</strong></span>', obj.module.program.title[:25], obj.module.title[:30])
    module_display.short_description = 'Module'

    def lesson_type_badge(self, obj):
        colors = {
            ModuleLesson.LessonType.CONTENT: ('#eff6ff', '#1d4ed8'),
            ModuleLesson.LessonType.TERMINOLOGY: ('#ecfdf5', '#047857'),
            ModuleLesson.LessonType.MATCHING_QUIZ: ('#fef3c7', '#b45309'),
            ModuleLesson.LessonType.QUIZ: ('#f5f3ff', '#6d28d9'),
        }
        bg, text = colors.get(obj.lesson_type, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;border-radius:12px;font-weight:700;font-size:0.75rem;">{}</span>',
            bg, text, obj.get_lesson_type_display()
        )
    lesson_type_badge.short_description = 'Lesson Type'

    def quiz_questions_count(self, obj):
        count = obj.quiz_questions.count()
        return f"{count} Qs" if count else "—"
    quiz_questions_count.short_description = 'Quiz Qs'


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('enrolment', 'lesson', 'is_completed', 'matching_completed', 'completed_at')
    list_filter = ('is_completed', 'matching_completed', 'enrolment__program')
    search_fields = ('enrolment__candidate__user__first_name', 'enrolment__candidate__user__last_name', 'lesson__title')


@admin.register(ModuleQuizQuestion)
class ModuleQuizQuestionAdmin(admin.ModelAdmin):
    list_display = ('module', 'lesson', 'order', 'prompt_preview', 'options_count', 'created_at')
    list_filter = ('module__program', 'module', 'lesson')
    search_fields = ('prompt', 'explanation', 'module__title')
    ordering = ('module', 'order')
    fields = ('module', 'lesson', 'order', 'prompt', 'explanation')
    inlines = [ModuleQuizOptionInline]

    def prompt_preview(self, obj):
        return obj.prompt[:90] + ("..." if len(obj.prompt) > 90 else "")
    prompt_preview.short_description = 'Question Prompt'

    def options_count(self, obj):
        total = obj.options.count()
        correct = obj.options.filter(is_correct=True).count()
        return f"{total} choices ({correct} correct)"
    options_count.short_description = 'Choices'


@admin.register(TrainingCoupon)
class TrainingCouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_badge', 'redemption_progress', 'program_scope', 'validity_badge', 'is_active', 'created_at')
    list_filter = ('is_active', 'discount_type', 'applicable_programs')
    search_fields = ('code', 'description')
    filter_horizontal = ('applicable_programs',)
    readonly_fields = ('times_redeemed', 'redemption_progress', 'created_at', 'updated_at')
    inlines = [CouponRedemptionInline]
    actions = ['activate_coupons', 'deactivate_coupons']

    fieldsets = (
        ('Coupon Promo Code & Value', {
            'fields': ('code', 'description', 'discount_type', 'discount_value', 'is_active'),
            'description': 'Create promotion codes such as FIRST50, SKEP100, or WELCOME. Enter discount percentage (e.g. 100 for 100% off) or flat amount.'
        }),
        ('Redemption Limits & Scarcity', {
            'fields': ('max_redemptions', 'times_redeemed', 'max_redemptions_per_user', 'redemption_progress'),
            'description': 'Limit total uses (e.g. 50 students). Once reached, the coupon automatically closes and charges regular tuition.'
        }),
        ('Scope & Expiration Schedule', {
            'fields': ('applicable_programs', 'valid_from', 'valid_until'),
            'description': 'Leave applicable programs empty to allow this code across all training programs.'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def discount_badge(self, obj):
        if obj.discount_type == TrainingCoupon.DiscountType.PERCENTAGE:
            bg, text = ('#ecfdf5', '#059669') if obj.discount_value == 100 else ('#eff6ff', '#006fe6')
            return format_html(
                '<span style="background:{};color:{};padding:4px 10px;border-radius:12px;font-weight:800;font-size:0.8rem;">{}% OFF</span>',
                bg, text, int(obj.discount_value)
            )
        return format_html(
            '<span style="background:#fef3c7;color:#b45309;padding:4px 10px;border-radius:12px;font-weight:800;font-size:0.8rem;">${} OFF</span>',
            obj.discount_value
        )
    discount_badge.short_description = 'Discount'

    def redemption_progress(self, obj):
        if obj.max_redemptions:
            pct = int(round((obj.times_redeemed / obj.max_redemptions) * 100))
            color = '#ef4444' if pct >= 100 else ('#f59e0b' if pct >= 80 else '#10b981')
            return format_html(
                '<div>'
                '<span style="font-weight:800;color:{};">{} / {}</span> ({}%)'
                '<div style="width:100px;height:5px;background:#e2e8f0;border-radius:5px;overflow:hidden;margin-top:3px;">'
                '<div style="width:{}%;height:100%;background:{};"></div>'
                '</div>'
                '</div>',
                color, obj.times_redeemed, obj.max_redemptions, pct, min(100, pct), color
            )
        return f"{obj.times_redeemed} (Unlimited)"
    redemption_progress.short_description = 'Redemptions'

    def program_scope(self, obj):
        count = obj.applicable_programs.count()
        if count == 0:
            return "All Programs"
        return f"{count} Specific Program{'s' if count > 1 else ''}"
    program_scope.short_description = 'Applicable To'

    def validity_badge(self, obj):
        if not obj.is_active:
            return mark_safe('<span style="color:#ef4444;font-weight:700;">Inactive</span>')
        if obj.is_fully_redeemed:
            return mark_safe('<span style="color:#dc2626;font-weight:800;background:#fef2f2;padding:2px 8px;border-radius:4px;">Limit Reached</span>')
        if obj.is_expired:
            return mark_safe('<span style="color:#64748b;font-weight:700;">Expired</span>')
        return mark_safe('<span style="color:#059669;font-weight:700;">✓ Active &amp; Valid</span>')
    validity_badge.short_description = 'Status'

    @admin.action(description="Activate selected coupons")
    def activate_coupons(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected coupons")
    def deactivate_coupons(self, request, queryset):
        queryset.update(is_active=False)


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'coupon_code_display', 'program', 'discount_amount_display', 'final_price_paid_display', 'redeemed_at')
    list_filter = ('coupon', 'program', 'redeemed_at')
    search_fields = (
        'candidate__user__first_name',
        'candidate__user__last_name',
        'candidate__user__email',
        'coupon__code',
        'program__title'
    )
    readonly_fields = ('coupon', 'candidate', 'program', 'enrolment', 'original_price', 'discount_amount', 'final_price_paid', 'redeemed_at')

    def coupon_code_display(self, obj):
        return format_html('<strong style="color:#006fe6;">{}</strong>', obj.coupon.code)
    coupon_code_display.short_description = 'Coupon Code'

    def discount_amount_display(self, obj):
        return f"-${obj.discount_amount:.2f}"
    discount_amount_display.short_description = 'Discount Applied'

    def final_price_paid_display(self, obj):
        if obj.final_price_paid == 0:
            return mark_safe('<span style="color:#059669;font-weight:800;">$0.00 (100% Free)</span>')
        return f"${obj.final_price_paid:.2f}"
    final_price_paid_display.short_description = 'Amount Paid'

    def has_add_permission(self, request):
        return False


@admin.register(ModuleQuizAttempt)
class ModuleQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('candidate_name', 'module', 'score_display', 'result_badge', 'attempted_at')
    list_filter = ('passed', 'module__program', 'module')
    search_fields = (
        'enrolment__candidate__user__first_name',
        'enrolment__candidate__user__last_name',
        'module__title',
        'module__program__title'
    )
    readonly_fields = ('enrolment', 'module', 'score_percentage', 'total_questions', 'correct_answers', 'passed', 'attempted_at')

    def candidate_name(self, obj):
        return obj.enrolment.candidate.full_name
    candidate_name.short_description = 'Candidate'

    def score_display(self, obj):
        return f"{obj.score_percentage}% ({obj.correct_answers}/{obj.total_questions} correct)"
    score_display.short_description = 'Score'

    def result_badge(self, obj):
        if obj.passed:
            return mark_safe('<span style="background:#ecfdf5;color:#059669;padding:3px 10px;border-radius:12px;font-weight:800;font-size:0.75rem;">PASSED</span>')
        return mark_safe('<span style="background:#fef2f2;color:#dc2626;padding:3px 10px;border-radius:12px;font-weight:800;font-size:0.75rem;">FAILED (Retake Required)</span>')
    result_badge.short_description = 'Result'

    def has_add_permission(self, request):
        return False


@admin.register(TrainingMaterial)
class TrainingMaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'program', 'module', 'material_type_badge', 'file_details', 'is_downloadable', 'order', 'action_links')
    list_filter = ('material_type', 'is_downloadable', 'program')
    search_fields = ('title', 'description', 'program__title', 'module__title')
    ordering = ('program', 'module', 'order')

    fieldsets = (
        ('Material Identification', {
            'fields': ('program', 'module', 'title', 'material_type', 'description', 'order'),
            'description': 'Assign this training material to a program and an optional specific module.'
        }),
        ('File Upload or External Embed Link', {
            'fields': ('file', 'external_url', 'is_downloadable'),
            'description': 'Upload video (MP4), PDF, Word document, Excel sheet, or provide a direct video/resource URL.'
        }),
    )

    def material_type_badge(self, obj):
        colors = {
            TrainingMaterial.MaterialType.VIDEO: ('#eff6ff', '#1d4ed8'),
            TrainingMaterial.MaterialType.VIDEO_EMBED: ('#f5f3ff', '#6d28d9'),
            TrainingMaterial.MaterialType.DOCUMENT: ('#fef2f2', '#b91c1c'),
            TrainingMaterial.MaterialType.AUDIO: ('#fefce8', '#a16207'),
            TrainingMaterial.MaterialType.RESOURCE: ('#ecfdf5', '#047857'),
            TrainingMaterial.MaterialType.EXTERNAL: ('#f8fafc', '#334155'),
        }
        bg, text = colors.get(obj.material_type, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 8px;border-radius:6px;font-weight:700;font-size:0.75rem;">{}</span>',
            bg, text, obj.get_material_type_display()
        )
    material_type_badge.short_description = 'Type'

    def file_details(self, obj):
        if obj.file:
            return format_html(
                '<span><b>.{}</b> ({})</span>',
                obj.file_extension.upper(),
                obj.file_size_display
            )
        elif obj.external_url:
            return mark_safe('<span style="color:#0284c7;font-weight:600;">External Stream / Link</span>')
        return "—"
    file_details.short_description = 'File / Format'

    def action_links(self, obj):
        links = []
        if obj.file:
            links.append(format_html(
                '<a href="{}" target="_blank" style="padding:3px 8px;background:#006fe6;color:#fff;border-radius:4px;font-weight:700;font-size:0.75rem;text-decoration:none;">Download File &nearr;</a>',
                obj.file.url
            ))
        elif obj.external_url:
            links.append(format_html(
                '<a href="{}" target="_blank" style="padding:3px 8px;background:#0284c7;color:#fff;border-radius:4px;font-weight:700;font-size:0.75rem;text-decoration:none;">Open URL &nearr;</a>',
                obj.external_url
            ))
        return mark_safe('&nbsp;'.join(links)) if links else "—"
    action_links.short_description = 'Actions'


class ModuleProgressInline(admin.TabularInline):
    model = ModuleProgress
    extra = 0
    fields = ('module', 'is_completed', 'quiz_score', 'quiz_passed', 'completed_at')
    readonly_fields = ('module', 'completed_at')
    can_delete = False


@admin.register(TrainingEnrolment)
class TrainingEnrolmentAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'program', 'status', 'progress_display', 'coupon_used', 'amount_paid', 'certificate_id', 'certificate_preview', 'enrolled_at', 'completed_at')
    list_filter = ('status', 'program', 'coupon_used')
    search_fields = (
        'candidate__user__first_name',
        'candidate__user__last_name',
        'candidate__user__email',
        'certificate_id',
        'program__title'
    )
    readonly_fields = ('certificate_id', 'certificate_preview', 'enrolled_at', 'completed_at')
    inlines = [ModuleProgressInline]

    def progress_display(self, obj):
        return f"{obj.progress_percentage}% ({obj.completed_modules_count}/{obj.total_modules_count})"
    progress_display.short_description = 'Progress'

    def certificate_preview(self, obj):
        if obj.pk:
            if obj.certificate_id and obj.status == TrainingEnrolment.EnrolmentStatus.COMPLETED:
                return format_html(
                    '<a href="/training/certificate/{}/" target="_blank" style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;background:#059669;color:#ffffff;border-radius:4px;font-weight:700;font-size:0.75rem;text-decoration:none;">View Cert &rarr;</a>',
                    obj.certificate_id
                )
            return format_html(
                '<a href="/training/certificate/preview/enrolment/{}/" target="_blank" style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;background:#0284c7;color:#ffffff;border-radius:4px;font-weight:700;font-size:0.75rem;text-decoration:none;">Preview Cert &rarr;</a>',
                obj.pk
            )
        return "-"
    certificate_preview.short_description = 'Certificate'


@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ('enrolment', 'module', 'is_completed', 'quiz_score', 'quiz_passed', 'completed_at')
    list_filter = ('is_completed', 'quiz_passed', 'enrolment__program')
    search_fields = (
        'enrolment__candidate__user__first_name',
        'enrolment__candidate__user__last_name',
        'module__title',
        'enrolment__program__title'
    )


@admin.register(CertificateTemplateConfig)
class CertificateTemplateConfigAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'signatory_name', 'signatory_title', 'primary_border_color', 'live_preview_link', 'is_active', 'updated_at')
    readonly_fields = ('live_preview_button', 'updated_at')

    fieldsets = (
        ('Signatory & Faculty Authority', {
            'fields': (
                'faculty_header_text',
                'signatory_name',
                'signatory_title',
                'signatory_signature_image',
                'signatory_font_family',
            ),
            'description': 'Configure the Lead Clinical Faculty personnel, signature graphic, and title displayed on all issued certificates.'
        }),
        ('Institution Branding & Header', {
            'fields': (
                'organization_name',
                'organization_logo',
                'accreditation_badge_text',
                'accreditation_subtitle',
                'certificate_title',
                'certifies_statement',
                'fulfillment_statement',
            ),
            'description': 'Branding marks, logos, and accreditation statements.'
        }),
        ('Color Palette & Aesthetic Framing', {
            'fields': (
                'primary_border_color',
                'secondary_border_color',
                'border_style',
                'seal_color',
                'seal_background',
                'seal_title',
                'seal_subtitle',
            ),
            'description': 'Customize border outline colors, certificate framing style, and security seal colors.'
        }),
        ('Status & Live Preview', {
            'fields': (
                'is_active',
                'live_preview_button',
                'updated_at',
            )
        }),
    )

    def live_preview_link(self, obj):
        return mark_safe(
            '<a href="/training/certificate/preview/" target="_blank" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;background:#006fe6;color:#ffffff;border-radius:4px;font-weight:700;font-size:0.75rem;text-decoration:none;">Preview Cert &nearr;</a>'
        )
    live_preview_link.short_description = 'Live Preview'

    def live_preview_button(self, obj):
        return mark_safe(
            '<div style="background:#f8fafc;padding:16px;border-radius:8px;border:1px solid #cbd5e1;">'
            '<a href="/training/certificate/preview/" target="_blank" style="display:inline-flex;align-items:center;gap:8px;padding:10px 20px;background:#006fe6;color:#ffffff;border-radius:8px;font-weight:800;font-size:0.9rem;text-decoration:none;box-shadow:0 3px 10px rgba(0,111,230,0.3);">'
            '<span style="font-size:1.1rem;">&#128065;</span> Launch Live Certificate Preview &nearr;</a>'
            '<p style="margin:10px 0 0 0;font-size:0.82rem;color:#64748b;">Renders a real-time preview applying all changes (Lead Faculty name, signature, border color, logo, and seal) in a new browser tab.</p>'
            '</div>'
        )
    live_preview_button.short_description = 'Live Preview'

    def has_add_permission(self, request):
        if CertificateTemplateConfig.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(TrainingPayment)
class TrainingPaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_ref', 'program', 'candidate_display', 'creator_display',
        'net_amount_display', 'creator_earnings_display', 'platform_fee_display',
        'gateway_badge', 'payout_status_badge', 'created_at'
    )
    list_filter = ('status', 'creator_payout_status', 'gateway', 'program', 'creator', 'currency')
    date_hierarchy = 'created_at'
    search_fields = (
        'payment_ref', 'gateway_reference',
        'candidate__user__first_name', 'candidate__user__last_name', 'candidate__user__email',
        'program__title', 'creator__first_name', 'creator__last_name', 'creator__email'
    )
    readonly_fields = (
        'payment_ref', 'gateway_reference', 'program', 'candidate', 'enrolment',
        'creator', 'coupon', 'gross_amount', 'discount_amount', 'net_amount_paid',
        'currency', 'creator_share_percent', 'creator_earnings', 'platform_fee',
        'gateway', 'status', 'raw_response', 'ip_address', 'created_at', 'settled_at'
    )
    actions = ['mark_disbursed_to_creator', 'mark_pending_creator_payout']

    fieldsets = (
        ('Transaction Identification', {
            'fields': ('payment_ref', 'gateway_reference', 'program', 'candidate', 'enrolment', 'status', 'created_at', 'settled_at')
        }),
        ('Tuition Ledger & Splits', {
            'fields': (
                ('gross_amount', 'discount_amount', 'net_amount_paid', 'currency'),
                ('creator', 'creator_share_percent'),
                ('creator_earnings', 'platform_fee')
            ),
            'description': 'Itemized financial audit of course payment, promotional discounts, creator cut, and Kodafriq platform fee.'
        }),
        ('Staff Creator Payout Settlement', {
            'fields': ('creator_payout_status', 'creator_paid_at', 'creator_payout_note'),
            'description': 'Track when Kodafriq disburses earnings to the course creator/staff member.'
        }),
        ('Technical Gateway Payload', {
            'fields': ('gateway', 'coupon', 'ip_address', 'raw_response'),
            'classes': ('collapse',)
        })
    )

    def candidate_display(self, obj):
        return obj.candidate.full_name
    candidate_display.short_description = 'Enrolled Student'

    def creator_display(self, obj):
        if obj.creator:
            return format_html('<strong>{}</strong>', obj.creator.get_full_name() or obj.creator.email)
        return mark_safe('<span style="color:#94a3b8;">Unassigned Staff</span>')
    creator_display.short_description = 'Course Creator'

    def net_amount_display(self, obj):
        if obj.net_amount_paid == 0:
            return format_html('<span style="color:#059669;font-weight:800;">FREE ({} 0.00)</span>', obj.currency)
        return format_html('<strong>{} {}</strong>', obj.currency, f"{obj.net_amount_paid:.2f}")
    net_amount_display.short_description = 'Paid by Student'

    def creator_earnings_display(self, obj):
        if obj.creator_earnings == 0:
            return f"{obj.currency} 0.00"
        return format_html(
            '<strong style="color:#006fe6;">{} {}</strong> <span style="font-size:0.75rem;color:#64748b;">({}%)</span>',
            obj.currency, f"{obj.creator_earnings:.2f}", int(obj.creator_share_percent)
        )
    creator_earnings_display.short_description = 'Creator Earnings'

    def platform_fee_display(self, obj):
        if obj.platform_fee == 0:
            return f"{obj.currency} 0.00"
        return format_html('<span style="color:#059669;font-weight:700;">{} {}</span>', obj.currency, f"{obj.platform_fee:.2f}")
    platform_fee_display.short_description = 'Kodafriq Net'

    def gateway_badge(self, obj):
        colors = {
            'FLUTTERWAVE': ('#fef3c7', '#b45309'),
            'PAYSTACK': ('#eff6ff', '#006fe6'),
            'COUPON_FREE': ('#ecfdf5', '#059669'),
            'MANUAL': ('#f1f5f9', '#475569'),
        }
        bg, text = colors.get(obj.gateway, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 8px;border-radius:6px;font-weight:700;font-size:0.75rem;">{}</span>',
            bg, text, obj.get_gateway_display()
        )
    gateway_badge.short_description = 'Gateway'

    def payout_status_badge(self, obj):
        if obj.creator_payout_status == TrainingPayment.CreatorPayoutStatus.PAID:
            return mark_safe('<span style="background:#ecfdf5;color:#059669;padding:3px 10px;border-radius:12px;font-weight:800;font-size:0.75rem;">DISBURSED</span>')
        elif obj.creator_payout_status == TrainingPayment.CreatorPayoutStatus.PENDING:
            return mark_safe('<span style="background:#fef3c7;color:#b45309;padding:3px 10px;border-radius:12px;font-weight:800;font-size:0.75rem;">PENDING PAYOUT</span>')
        return mark_safe('<span style="color:#94a3b8;font-size:0.75rem;">N/A (Free)</span>')
    payout_status_badge.short_description = 'Creator Payout'

    @admin.action(description="Mark selected course earnings as DISBURSED / PAID to Course Creator")
    def mark_disbursed_to_creator(self, request, queryset):
        count = queryset.filter(creator_payout_status=TrainingPayment.CreatorPayoutStatus.PENDING).update(
            creator_payout_status=TrainingPayment.CreatorPayoutStatus.PAID,
            creator_paid_at=timezone.now(),
            creator_payout_note=f"Disbursed by {request.user.email} on {timezone.now().strftime('%Y-%m-%d')}"
        )
        self.message_user(request, f"{count} course payments marked as successfully disbursed to course creators.")

    @admin.action(description="Reset selected course earnings to PENDING Creator Payout")
    def mark_pending_creator_payout(self, request, queryset):
        count = queryset.update(
            creator_payout_status=TrainingPayment.CreatorPayoutStatus.PENDING,
            creator_paid_at=None
        )
        self.message_user(request, f"{count} course payments reset to Pending Payout.")

    def has_add_permission(self, request):
        return False

