from django.contrib import admin
from django.contrib.auth.models import User, Group
# Default User va Group'ni admindan olib tashlash
admin.site.unregister(User)
admin.site.unregister(Group)
