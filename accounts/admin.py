from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Interest, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Profil apprenant", {"fields": ("country", "birth_date", "native_language", "goal", "interests", "xp")}),
    )
    list_display = ("username", "email", "country", "goal", "xp", "is_staff")


admin.site.register(Interest)
