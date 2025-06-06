from django.contrib import admin
from .models import UserProfile, ScheduleTemplate, OperationalSchedule, Project

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'schedule_mode')
    search_fields = ('user__username', 'phone_number')
    list_filter = ('schedule_mode',)

@admin.register(ScheduleTemplate)
class ScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = ('user', 'week_type', 'day', 'activity', 'start_time', 'end_time')
    search_fields = ('user__username', 'activity')
    list_filter = ('week_type', 'day')

@admin.register(OperationalSchedule)
class OperationalScheduleAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'activity', 'start_time', 'end_time')
    search_fields = ('user__username', 'activity')
    list_filter = ('date',)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name',)
    filter_horizontal = ('users',)
