from django.contrib import admin
from .models import Contract, Timesheet, TimesheetEntry, Milestone, DisputeCase


class TimesheetEntryInline(admin.TabularInline):
    model = TimesheetEntry
    extra = 0
    fields = ('date', 'hours_worked', 'charts_coded_count', 'work_description')


class MilestoneInline(admin.TabularInline):
    model = Milestone
    extra = 0
    fields = ('order', 'title', 'amount', 'due_date', 'status')


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = (
        'contract_ref', 'title', 'employer_company', 'candidate_name',
        'contract_type', 'rate_per_hour', 'billed_rate_per_hour', 'status', 'created_at'
    )
    list_filter = ('contract_type', 'status', 'disbursement_mode', 'currency')
    search_fields = ('contract_ref', 'title', 'employer__company_name', 'candidate__user__username', 'candidate__user__email')
    readonly_fields = ('id', 'contract_ref', 'created_at', 'updated_at')
    inlines = [MilestoneInline]

    def employer_company(self, obj):
        return obj.employer.company_name
    employer_company.short_description = "Employer"

    def candidate_name(self, obj):
        return obj.candidate.full_name
    candidate_name.short_description = "Candidate"


@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = (
        'contract_ref', 'week_start_date', 'total_hours', 'total_charts_coded',
        'talent_gross_earnings', 'kodafriq_fee', 'total_employer_charge', 'status'
    )
    list_filter = ('status', 'week_start_date')
    search_fields = ('contract__contract_ref', 'contract__employer__company_name', 'contract__candidate__user__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [TimesheetEntryInline]

    def contract_ref(self, obj):
        return obj.contract.contract_ref
    contract_ref.short_description = "Contract"


@admin.register(TimesheetEntry)
class TimesheetEntryAdmin(admin.ModelAdmin):
    list_display = ('timesheet', 'date', 'hours_worked', 'charts_coded_count', 'work_description')
    list_filter = ('date',)
    search_fields = ('timesheet__contract__contract_ref', 'work_description')


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ('contract', 'order', 'title', 'amount', 'due_date', 'status')
    list_filter = ('status',)
    search_fields = ('contract__contract_ref', 'title')


@admin.register(DisputeCase)
class DisputeCaseAdmin(admin.ModelAdmin):
    list_display = ('contract', 'raised_by', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('contract__contract_ref', 'reason', 'resolution_notes')
