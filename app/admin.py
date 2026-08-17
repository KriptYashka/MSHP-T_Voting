from django.contrib import admin

from .models import Nomination, Profile, Project, ProjectScreenshot, Vote, VotingState


class ProjectScreenshotInline(admin.TabularInline):
    model = ProjectScreenshot
    extra = 1


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'role', 'age', 'user')
    list_filter = ('role',)


@admin.register(Nomination)
class NominationAdmin(admin.ModelAdmin):
    list_display = ('title', 'created_at')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'created_at')
    inlines = [ProjectScreenshotInline]
    readonly_fields = ('created_at',)


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = (
        'voter', 'project', 'nomination',
        'score_technical', 'score_aesthetics', 'score_playability',
        'created_at',
    )
    list_filter = ('nomination',)


@admin.register(VotingState)
class VotingStateAdmin(admin.ModelAdmin):
    list_display = ('current_project', 'phase')
