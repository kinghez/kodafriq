from django.contrib import admin
from .models import TrainingProgram, ProgramModule, TrainingEnrolment, ModuleProgress


class ProgramModuleInline(admin.StackedInline):
    model = ProgramModule
    extra = 1
    fields = ('order', 'title', 'duration_minutes', 'key_takeaways', 'content')
    ordering = ('order',)


@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'duration_weeks', 'total_modules_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'duration_weeks')
    search_fields = ('title', 'instructor', 'description', 'curriculum_overview')
    filter_horizontal = ('skills_covered',)
    inlines = [ProgramModuleInline]
    actions = ['activate_programs', 'deactivate_programs']

    def total_modules_count(self, obj):
        return obj.modules.count()
    total_modules_count.short_description = 'Modules'

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
    list_display = ('candidate', 'program', 'status', 'progress_display', 'certificate_id', 'enrolled_at', 'completed_at')
    list_filter = ('status', 'program')
    search_fields = (
        'candidate__user__first_name',
        'candidate__user__last_name',
        'candidate__user__email',
        'certificate_id',
        'program__title'
    )
    readonly_fields = ('certificate_id', 'enrolled_at', 'completed_at')
    inlines = [ModuleProgressInline]

    def progress_display(self, obj):
        return f"{obj.progress_percentage}% ({obj.completed_modules_count}/{obj.total_modules_count})"
    progress_display.short_description = 'Progress'


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
