from django.contrib import admin
from django.utils.html import format_html
from .models import TrainingProgram, ProgramModule, TrainingEnrolment, ModuleProgress, CertificateTemplateConfig


class ProgramModuleInline(admin.StackedInline):
    model = ProgramModule
    extra = 1
    fields = ('order', 'title', 'duration_minutes', 'key_takeaways', 'content')
    ordering = ('order',)


@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'duration_weeks', 'total_modules_count', 'certificate_preview', 'is_active', 'created_at')
    list_filter = ('is_active', 'duration_weeks')
    search_fields = ('title', 'instructor', 'description', 'curriculum_overview')
    filter_horizontal = ('skills_covered',)
    inlines = [ProgramModuleInline]
    actions = ['activate_programs', 'deactivate_programs']
    readonly_fields = ('certificate_preview_button',)

    fieldsets = (
        ('Program Information', {
            'fields': ('title', 'description', 'curriculum_overview', 'skills_covered', 'duration_weeks', 'start_date', 'end_date', 'is_active')
        }),
        ('Accredited Certificate Configuration', {
            'fields': ('instructor', 'instructor_title', 'certificate_subtitle', 'accreditation_statement', 'certificate_preview_button'),
            'description': 'Configure the verifiable certificate text, signatory title, and accreditation metadata issued to candidates.'
        }),
    )

    def total_modules_count(self, obj):
        return obj.modules.count()
    total_modules_count.short_description = 'Modules'

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


class ModuleProgressInline(admin.TabularInline):
    model = ModuleProgress
    extra = 0
    fields = ('module', 'is_completed', 'completed_at')
    readonly_fields = ('module', 'completed_at')
    can_delete = False


@admin.register(TrainingEnrolment)
class TrainingEnrolmentAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'program', 'status', 'progress_display', 'certificate_id', 'certificate_preview', 'enrolled_at', 'completed_at')
    list_filter = ('status', 'program')
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


@admin.register(ProgramModule)
class ProgramModuleAdmin(admin.ModelAdmin):
    list_display = ('program', 'order', 'title', 'duration_minutes', 'created_at')
    list_filter = ('program',)
    search_fields = ('title', 'content', 'key_takeaways', 'program__title')
    ordering = ('program', 'order')


@admin.register(ModuleProgress)
class ModuleProgressAdmin(admin.ModelAdmin):
    list_display = ('enrolment', 'module', 'is_completed', 'completed_at')
    list_filter = ('is_completed', 'enrolment__program')
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
        return format_html(
            '<a href="/training/certificate/preview/" target="_blank" style="display:inline-flex;align-items:center;gap:4px;padding:3px 9px;background:#006fe6;color:#ffffff;border-radius:4px;font-weight:700;font-size:0.75rem;text-decoration:none;">Preview Cert &nearr;</a>'
        )
    live_preview_link.short_description = 'Live Preview'

    def live_preview_button(self, obj):
        return format_html(
            '<div style="background:#f8fafc;padding:16px;border-radius:8px;border:1px solid #cbd5e1;">'
            '<a href="/training/certificate/preview/" target="_blank" style="display:inline-flex;align-items:center;gap:8px;padding:10px 20px;background:#006fe6;color:#ffffff;border-radius:8px;font-weight:800;font-size:0.9rem;text-decoration:none;box-shadow:0 3px 10px rgba(0,111,230,0.3);">'
            '<span style="font-size:1.1rem;">&#128065;</span> Launch Live Certificate Preview &nearr;</a>'
            '<p style="margin:10px 0 0 0;font-size:0.82rem;color:#64748b;">Renders a real-time preview applying all changes (Lead Faculty name, signature, border color, logo, and seal) in a new browser tab.</p>'
            '</div>'
        )
    live_preview_button.short_description = 'Live Preview'

    def has_add_permission(self, request):
        # Enforce singleton pattern if one already exists
        if CertificateTemplateConfig.objects.exists():
            return False
        return super().has_add_permission(request)
