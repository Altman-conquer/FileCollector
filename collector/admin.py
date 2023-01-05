from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import User, Folder, SmsCode

admin.site.register(User)

admin.site.register(Folder)

admin.site.register(SmsCode)