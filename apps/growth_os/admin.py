from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    EmployerLead, LeadContact, HiringSignal, TalentReverseMatch,
    OutreachMessage, CRMOpportunity, CRMActivity
)


class LeadContactInline(admin.TabularInline):
    model = LeadContact
    extra = 1
    fields = ('full_name', 'job_title', 'email', 'phone', 'is_primary', 'verification_status')


class HiringSignalInline(admin.TabularInline):
    model = HiringSignal
    extra = 1
    fields = ('job_title', 'role_category', 'days_open', 'is_persistent', 'is_active', 'job_url')


class CRMActivityInline(admin.TabularInline):
    model = CRMActivity
    extra = 1
    fields = ('activity_type', 'summary', 'performed_by', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(EmployerLead)
class EmployerLeadAdmin(admin.ModelAdmin):
    list_display = (
        'company_name', 'domain', 'industry_vertical', 'country',
        'hiring_intent_badge', 'talent_fit_badge', 'priority_tier_badge',
        'active_vacancies_count_display', 'status_badge', 'assigned_staff', 'created_at'
    )
    list_filter = ('status', 'industry_vertical', 'source', 'country', 'company_size')
    search_fields = ('company_name', 'domain', 'website', 'city', 'notes')
    inlines = [LeadContactInline, HiringSignalInline, CRMActivityInline]
    actions = ['recalculate_intent_scores_action', 'mark_qualified_action', 'mark_disqualified_action']

    fieldsets = (
        ('Company Overview', {
            'fields': (
                ('company_name', 'domain'),
                ('website', 'careers_url'),
                ('country', 'city'),
                ('industry_vertical', 'company_size'),
                ('source', 'status')
            )
        }),
        ('GrowthOS Dual-Score Intelligence', {
            'fields': (
                ('hiring_intent_score', 'talent_fit_score'),
                'assigned_staff',
                'converted_employer_profile'
            ),
            'description': 'Dual-score prioritization matrix. Tier 1 requires Intent >= 60 and Fit >= 60.'
        }),
        ('Internal Intelligence Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        })
    )

    def hiring_intent_badge(self, obj):
        score = obj.hiring_intent_score
        if score >= 70:
            return format_html('<span style="background:#fee2e2;color:#b91c1c;padding:3px 8px;border-radius:12px;font-weight:800;font-size:0.75rem;">{} (High)</span>', score)
        elif score >= 40:
            return format_html('<span style="background:#fef3c7;color:#b45309;padding:3px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;">{} (Moderate)</span>', score)
        return format_html('<span style="background:#f1f5f9;color:#64748b;padding:3px 8px;border-radius:12px;font-size:0.75rem;">{}</span>', score)
    hiring_intent_badge.short_description = 'Intent Score'

    def talent_fit_badge(self, obj):
        score = obj.talent_fit_score
        if score >= 70:
            return format_html('<span style="background:#ecfdf5;color:#059669;padding:3px 8px;border-radius:12px;font-weight:800;font-size:0.75rem;">{} (High)</span>', score)
        elif score >= 40:
            return format_html('<span style="background:#eff6ff;color:#0284c7;padding:3px 8px;border-radius:12px;font-weight:700;font-size:0.75rem;">{} (Moderate)</span>', score)
        return format_html('<span style="background:#f1f5f9;color:#64748b;padding:3px 8px;border-radius:12px;font-size:0.75rem;">{}</span>', score)
    talent_fit_badge.short_description = 'Talent Fit'

    def priority_tier_badge(self, obj):
        tier = obj.priority_tier
        if tier == 1:
            return mark_safe('<span style="background:#fee2e2;color:#b91c1c;padding:3px 9px;border-radius:6px;font-weight:800;font-size:0.75rem;">🔥 TIER 1 (PRIME)</span>')
        elif tier == 2:
            return mark_safe('<span style="background:#fef3c7;color:#b45309;padding:3px 9px;border-radius:6px;font-weight:700;font-size:0.75rem;">🟡 TIER 2 (GAP)</span>')
        elif tier == 3:
            return mark_safe('<span style="background:#eff6ff;color:#006fe6;padding:3px 9px;border-radius:6px;font-weight:700;font-size:0.75rem;">🔵 TIER 3 (NURTURE)</span>')
        return mark_safe('<span style="background:#f1f5f9;color:#94a3b8;padding:3px 9px;border-radius:6px;font-size:0.75rem;">⚪ TIER 4</span>')
    priority_tier_badge.short_description = 'Priority Tier'

    def active_vacancies_count_display(self, obj):
        count = obj.active_vacancies_count
        if count > 0:
            return format_html('<strong style="color:#006fe6;">{} open</strong>', count)
        return mark_safe('<span style="color:#94a3b8;">0</span>')
    active_vacancies_count_display.short_description = 'Vacancies'

    def status_badge(self, obj):
        colors = {
            'LEAD': ('#f1f5f9', '#475569'),
            'QUALIFIED': ('#eff6ff', '#006fe6'),
            'IN_PIPELINE': ('#fef3c7', '#b45309'),
            'CONVERTED': ('#ecfdf5', '#059669'),
            'DISQUALIFIED': ('#fef2f2', '#b91c1c'),
        }
        bg, text = colors.get(obj.status, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 8px;border-radius:6px;font-weight:700;font-size:0.75rem;">{}</span>',
            bg, text, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    @admin.action(description="Recalculate Hiring Intent Scores for selected leads")
    def recalculate_intent_scores_action(self, request, queryset):
        for lead in queryset:
            lead.recalculate_intent_score()
        self.message_user(request, f"Updated intent scores for {queryset.count()} employer leads.")

    @admin.action(description="Mark selected leads as QUALIFIED targets")
    def mark_qualified_action(self, request, queryset):
        queryset.update(status=EmployerLead.Status.QUALIFIED)
        self.message_user(request, f"{queryset.count()} leads marked as Qualified.")

    @admin.action(description="Mark selected leads as DISQUALIFIED")
    def mark_disqualified_action(self, request, queryset):
        queryset.update(status=EmployerLead.Status.DISQUALIFIED)
        self.message_user(request, f"{queryset.count()} leads marked as Disqualified.")


@admin.register(LeadContact)
class LeadContactAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'lead', 'job_title', 'email', 'phone', 'is_primary', 'verification_badge', 'created_at')
    list_filter = ('is_primary', 'verification_status', 'lead__industry_vertical')
    search_fields = ('full_name', 'job_title', 'email', 'lead__company_name')

    def verification_badge(self, obj):
        if obj.verification_status == LeadContact.VerificationStatus.VERIFIED_VALID:
            return mark_safe('<span style="color:#059669;font-weight:700;">✓ Verified</span>')
        elif obj.verification_status == LeadContact.VerificationStatus.BOUNCED:
            return mark_safe('<span style="color:#b91c1c;font-weight:700;">✗ Bounced</span>')
        return mark_safe('<span style="color:#94a3b8;">Unverified</span>')
    verification_badge.short_description = 'Email Status'


@admin.register(HiringSignal)
class HiringSignalAdmin(admin.ModelAdmin):
    list_display = ('job_title', 'lead', 'role_category', 'days_open', 'persistent_badge', 'is_active', 'date_detected')
    list_filter = ('role_category', 'is_persistent', 'is_active', 'date_detected')
    search_fields = ('job_title', 'lead__company_name', 'raw_description')

    def persistent_badge(self, obj):
        if obj.is_persistent:
            return mark_safe('<span style="background:#fee2e2;color:#b91c1c;padding:2px 8px;border-radius:4px;font-weight:800;font-size:0.75rem;">PERSISTENT (&gt;30d)</span>')
        return mark_safe('<span style="color:#64748b;font-size:0.75rem;">Recent</span>')
    persistent_badge.short_description = 'Duration'


@admin.register(TalentReverseMatch)
class TalentReverseMatchAdmin(admin.ModelAdmin):
    list_display = ('candidate_display', 'lead', 'vacancy', 'match_score_badge', 'is_shortlisted', 'created_at')
    list_filter = ('is_shortlisted', 'lead__industry_vertical')
    search_fields = ('candidate__user__first_name', 'candidate__user__last_name', 'lead__company_name', 'matching_rationale')

    def candidate_display(self, obj):
        return obj.candidate.full_name
    candidate_display.short_description = 'Candidate'

    def match_score_badge(self, obj):
        return format_html('<strong>{}%</strong>', obj.match_score)
    match_score_badge.short_description = 'Match Score'


@admin.register(OutreachMessage)
class OutreachMessageAdmin(admin.ModelAdmin):
    list_display = ('lead', 'contact', 'channel', 'subject_preview', 'status_badge', 'approved_by', 'sent_at')
    list_filter = ('status', 'channel', 'reply_classification')
    search_fields = ('subject', 'body_text', 'lead__company_name')

    def subject_preview(self, obj):
        return obj.subject[:60] + ('...' if len(obj.subject) > 60 else '')
    subject_preview.short_description = 'Subject'

    def status_badge(self, obj):
        colors = {
            'DRAFT_PENDING_APPROVAL': ('#fef3c7', '#b45309'),
            'APPROVED': ('#eff6ff', '#0284c7'),
            'SENT': ('#ecfdf5', '#059669'),
            'REPLIED': ('#f0fdf4', '#15803d'),
            'REJECTED': ('#fee2e2', '#b91c1c'),
            'BOUNCED': ('#fef2f2', '#991b1b'),
        }
        bg, text = colors.get(obj.status, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 8px;border-radius:6px;font-weight:700;font-size:0.75rem;">{}</span>',
            bg, text, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(CRMOpportunity)
class CRMOpportunityAdmin(admin.ModelAdmin):
    list_display = ('lead', 'stage', 'target_roles_count', 'deal_value_display', 'priority', 'win_probability_percent', 'next_follow_up_date')
    list_filter = ('stage', 'priority')
    search_fields = ('lead__company_name', 'lost_reason')

    def deal_value_display(self, obj):
        return format_html('<strong>${:.2f}/mo</strong>', obj.estimated_monthly_deal_value)
    deal_value_display.short_description = 'Estimated Value'


@admin.register(CRMActivity)
class CRMActivityAdmin(admin.ModelAdmin):
    list_display = ('lead', 'activity_type', 'summary', 'performed_by', 'created_at')
    list_filter = ('activity_type', 'created_at')
    search_fields = ('summary', 'details', 'lead__company_name')

