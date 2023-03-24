from django.db import models

# Create your models here.
from django.db import models


class User(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=20, default='用户')
    password = models.CharField(max_length=20)
    phone = models.CharField(max_length=12, unique=True)
    priority = models.IntegerField(default=0)  # 0 普通用户, 1 管理员

    def __unicode__(self):
        return f'用户名:{self.username}, 密码:{self.password}: 手机号:{self.phone}: 权限:{self.priority}'


class Folder(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    path = models.CharField(max_length=255, unique=True)
    priority = models.IntegerField(default=0)  # 0 不能访问, 1 只能下载

    def __unicode__(self):
        return self.user.username + '的文件夹'

#
# class Group(models.Model):
#     id = models.AutoField(primary_key=True)
#     group_name = models.CharField(max_length=255)
#
#
# class UserGroup(models.Model):
#     group_id = models.ForeignKey(to=Group, on_delete=models.CASCADE, null=False)
#     user = models.ForeignKey(User, on_delete=models.CASCADE, null=False)
#
#
# class FolderGroup(models.Model):
#     group_id = models.ForeignKey(to=Group, on_delete=models.CASCADE, null=False)
#     folder = models.ForeignKey(Folder, on_delete=models.CASCADE, null=False)
#

class SmsCode(models.Model):
    phone = models.CharField(primary_key=True, max_length=32)
    code = models.CharField(null=False, max_length=6)
    time = models.BigIntegerField(default=0)

    def __unicode__(self):
        return f"phone = {self.phone}, code = {self.code}, time = {self.time}"


class FeedBack(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.CharField(max_length=1024)
    time = models.DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return f"用户{self.user.username}的反馈"


class UploadRecord(models.Model):
    id = models.AutoField(primary_key=True)
    state = models.IntegerField(default=0)  # 0 上传中, 1 上传成功, 2 上传失败
