from django.urls import path, re_path, reverse

import collector.views as views

app_name = 'collector'
urlpatterns = [
    path('', views.login, name='login'),
    path('register/', views.register, name='register'),
    path('register/send_sms/', views.send_sms, name='register_send_sms'),
    path('forget/', views.forget_password, name='forget'),
    path('forget/send_sms', views.send_sms, name='forget_send_sms'),
    path('main/', views.main, name='main'),
    path('main/logout', views.logout, name='logout'),
    path('main/download', views.download, name='download'),
    path('main/downloadcheck', views.download_check, name='download_check'),
    path('main/upload/', views.upload, name='upload'),
    path('main/enter', views.enter_folder, name='enter'),
    path('main/prev', views.prev_folder, name='prev'),
    path('main/prev/<int:level>', views.prev_folder, name='prev'),
    path('main/creater_folder', views.create_folder, name='create_folder'),
    path('main/rename', views.rename, name='rename'),
    path('main/userrename', views.user_rename, name='user_rename'),
    path('main/setpublic/<str:file_name>', views.set_public, name='set_public'),
    path('main/setprivate/<str:file_name>', views.set_private, name='set_private'),
    path('main/delete', views.delete, name='delete'),
    path('main/forcedelete', views.force_delete, name='forcedelete'),
    path('main/feedback', views.feedback, name='feedback'),

    # path('view', views.view, name='view_without_path'),
    re_path(r'^content/(?P<path>.*)', views.content, name='content'),
]
