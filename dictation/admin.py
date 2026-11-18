from django.contrib import admin

from .models import DictationSession, Submission

admin.site.register(DictationSession)
admin.site.register(Submission)
