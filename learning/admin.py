from django.contrib import admin

from .models import (
    AppSetting,
    Badge,
    Challenge,
    Level,
    Streak,
    Text,
    UserBadge,
    UserLevelProgress,
    UserTextProgress,
    VocabularyEntry,
)


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "order", "text_pass_score", "required_texts", "required_average", "requires_exam")


@admin.register(Text)
class TextAdmin(admin.ModelAdmin):
    list_display = ("title", "level", "theme", "word_count", "accent", "origin")
    list_filter = ("level", "theme", "accent", "origin")
    search_fields = ("title", "content")


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ("icon", "code", "name", "description")


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "start_date", "end_date", "reward_xp", "text")


@admin.register(AppSetting)
class AppSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description")


admin.site.register(UserTextProgress)
admin.site.register(UserLevelProgress)
admin.site.register(VocabularyEntry)
admin.site.register(Streak)
admin.site.register(UserBadge)


