from django.contrib import admin
from .models import CustomUser, Project, Application, Bookmark

admin.site.register(CustomUser)
admin.site.register(Project)
admin.site.register(Application)
admin.site.register(Bookmark)