import datetime
import ftplib
import json
import os
import random
import time
import zipfile
import threading

from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, redirect
from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.sms.v20210111 import sms_client, models

from FileCollector.settings import VALID_TIME, ACTIVE_TIME, HOME_PATH, TENCENT_SECRET_ID, TENCENT_SECRET_KEY, \
    ROOT_USER_PHONE, ROOT_USER_NAME, ROOT_USER_PASSWORD, UPLOAD_MAX_SIZE, ZIP_FILE_PATH
from .ftp import FTP, Traverser
from .models import SmsCode, User, Folder, FeedBack, UploadRecord
from .utilfunctions import join_path

FTP.default_path = HOME_PATH



def content(request, path):
    print(path)
    if len(path) == 0:
        path = request.session.get('ftp_path', HOME_PATH)
    else:
        path = join_path(HOME_PATH, path)
    while len(path) > len(HOME_PATH):
        if Traverser.is_exist(path):
            break
        path = path[:path.rfind('/')]
    request.session['ftp_path'] = path
    return main(request)


def info(request):
    return render(request, 'collector/InfoPage.html', {
        'info': '网站服务器已迁移，请使用<a class="link-primary" href="http://file.zhandj.com">http://file.zhandj.com</a> 访问该网站，谢谢！'})


def login(request):
    if request.method == 'POST':
        request.session['login_success'] = False
        if check_not_null(request, ['phone_number', 'password']):
            try:
                user = User.objects.get(phone=request.POST['phone_number'], password=request.POST['password'])
                request.session['username'] = user.username
                request.session['phone'] = user.phone
                request.session['password'] = user.password
                request.session['login_success'] = True
                if check_not_null(request, ['check_remember']):
                    request.session['auto_login'] = True
                else:
                    request.session['auto_login'] = False
                update_active(request)
                request.session['login_success'] = True
                print('登录成功')
                return redirect('collector:main')
            except User.DoesNotExist:
                pass
        return render(request, 'collector/login.html',
                      {'error': True, 'phone_number': request.POST.get('phone_number', ''),
                       'password': request.POST.get('password', ''), 'error_info': '用户名或密码错误'})
    else:
        if request.session.get('auto_login', False) is True:
            try:
                User.objects.get(phone=request.session['phone'], password=request.session['password'])
                update_active(request)
                print('自动登录成功')
                return redirect('collector:main')
            except User.DoesNotExist as e:
                print(e)
                pass
            except KeyError as e:
                print(e)
                pass
            print('自动登录失败')
        return render(request, 'collector/login.html')


def register(request):
    if request.method == 'POST':
        if User.objects.filter(phone=request.POST['phone_number']).count() != 0:
            return JsonResponse({'status': 'false', 'message': '该手机号已被注册'})
        elif not check_not_null(request, ['phone_number', 'password', 'verification_code']):
            return JsonResponse({'status': 'false', 'message': '请将注册信息填写完整'})
        else:
            tmp = check_sms(request.POST['phone_number'], request.POST['verification_code'])
            if tmp is True:
                User.objects.create(username=request.POST['user_name'],
                                    phone=request.POST['phone_number'],
                                    password=request.POST['password'])
                return JsonResponse({'status': 'true'})
            else:
                return JsonResponse({'status': 'false', 'message': tmp})
    else:
        return render(request, 'collector/register.html')


def forget_password(request):
    if request.method == 'POST':
        if not check_not_null(request, ['phone_number', 'verification_code', 'password']):
            return JsonResponse({'status': 'false', 'message': '请将信息填写完整'})
        else:
            tmp = check_sms(request.POST['phone_number'], request.POST['verification_code'])
            if tmp is True:
                User.objects.filter(phone=request.POST['phone_number']).update(password=request.POST['password'])
                return JsonResponse({'status': 'true'})
            else:
                return JsonResponse({'status': 'false', 'message': tmp})
    else:
        return render(request, 'collector/forgetpassword.html')


def main(request, error_info=None):
    FTP.default_path = HOME_PATH
    clear_zip_files()
    try:
        if is_active(request) and request.session.get('login_success', False) is True:
            update_active(request)
            temp = request.session.get('ftp_path', None)
            if temp is None or temp.startswith(FTP.default_path) is False:
                request.session['ftp_path'] = FTP.default_path
            try:
                ftp = FTP(request.session['ftp_path']).connect()
            except ftplib.error_perm as e:
                print('ftp连接失败')
                print(e)
                request.session['ftp_path'] = FTP.default_path
                ftp = FTP(request.session['ftp_path']).connect()
            path = ftp.pwd_list()
            while '' in path:
                path.remove('')
            # result = {'HOME': len(path)}
            # for k, v in enumerate(path):
            #     result[v] = len(path) - k - 1
            result = ['HOME'] + path

            return render(request, 'collector/main.html', {'user': User.objects.get(phone=request.session['phone']),
                                                           'folders': ftp.dirs(), 'path': result,
                                                           'error_info': error_info})
    except Exception as e:
        request.session['ftp_path'] = FTP.default_path
        print(e)
    return redirect('collector:login')


def set_public(request, file_name):
    if file_name is not None and file_name != '':
        try:
            Folder.objects.filter(path=join_path(request.session['ftp_path'], file_name)).update(priority=1)
        except Exception as e:
            return redirect('collector:main', error_info=str(e))
    return redirect('collector:main')


def set_private(request, file_name):
    if file_name is not None and file_name != '':
        try:
            Folder.objects.filter(path=join_path(request.session['ftp_path'], file_name)).update(priority=0)
        except Exception as e:
            return redirect('collector:main', error_info=str(e))
    return redirect('collector:main')


def logout(request):
    request.session['login_success'] = False
    request.session['auto_login'] = False
    deactive(request)
    return redirect('collector:login')


def enter_folder(request):
    """
    进入文件夹
    :param request:
    :return:
    """
    if check_not_null(request, ['folder_name']):
        try:
            new_path = join_path(request.session['ftp_path'], request.POST['folder_name'])

            # check if the path is valid
            if os.path.exists(new_path):
                request.session['ftp_path'] = new_path
        except Exception as e:
            print(e)
    return redirect('collector:content', path=request.session.get('ftp_path', HOME_PATH)[len(HOME_PATH):])


def prev_folder(request, level=1):
    """
    返回上 level 级文件夹
    :param level:
    :param request:
    :return:
    """
    cur_path = request.session['ftp_path']
    if cur_path[-1] == '/':
        cur_path = cur_path[:-1]
    for i in range(level):
        cur_path = cur_path[:cur_path.rfind('/')]
    if len(cur_path) <= len(FTP.default_path):
        cur_path = FTP.default_path
    request.session['ftp_path'] = cur_path
    return redirect('collector:content', path=request.session.get('ftp_path', HOME_PATH)[len(HOME_PATH):])


def download_check(request):
    try:
        info = []
        if check_not_null(request, ['file_name']):
            ftp = FTP(request.session['ftp_path']).connect()
            user = User.objects.get(phone=request.session['phone'])
            file_path = join_path(ftp.pwd(), request.POST['file_name'])
            if ftp.download_able(user, join_path(ftp.pwd(), request.POST['file_name'])):
                return JsonResponse({'can_be_download': True, 'file_path': file_path,
                                     'file_name': request.POST['file_name'], 'file_size': os.path.getsize(file_path)})
            else:
                info.append(request.POST['file_name'])
        elif check_not_null(request, ['file_name[]']):
            ftp = FTP(request.session['ftp_path']).connect()
            user = User.objects.get(phone=request.session['phone'])
            for i in request.POST.getlist('file_name[]'):
                if not ftp.download_able(user, join_path(ftp.pwd(), i)):
                    info.append(i)
            if len(info) == 0:
                # zip files
                zip_file_name = f'merged_{str(time.time() * 1000 + random.randint(0, 999))}.zip'
                zip_file = join_path(ZIP_FILE_PATH, zip_file_name)
                files = list(map(lambda x: join_path(ftp.pwd(), x), request.POST.getlist('file_name[]')))
                with zipfile.ZipFile(zip_file, 'w') as zip:
                    for i in files:
                        zip.write(i, i[i.rfind('/') + 1:])
                return JsonResponse({'can_be_download': True, 'file_path': zip_file, 'file_name': zip_file_name,
                                     'file_size': os.path.getsize(zip_file)})
        if len(info) == 0:
            return JsonResponse({'can_be_download': False, 'error_info': '请选择文件后再下载'})
        else:
            return JsonResponse({'can_be_download': False, 'error_info': '文件:"' + '","'.join(info) + '"没有权限下载'})
    except Exception as e:
        print(e)
    return JsonResponse({'can_be_download': False, 'error_info': '服务器错误'})


def download(request):
    """
    下载文件
    :param request:
    :return:
    """
    if check_not_null(request, ['file_path']):
        response = StreamingHttpResponse(open(request.POST['file_path'], 'rb'))
        response['content_type'] = "application/octet-stream"
        # response['Content-Length'] = os.path.getsize(request.POST['file_path'])
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(request.POST['file_path'])
        return response
    else:
        print('下载文件为空')
        response = StreamingHttpResponse(None)
        return response


def upload(request):
    """
    上传文件
    :param request:
    :return:
    """
    if request.method == 'POST' and len(request.FILES) > 0:
        try:
            if Folder.objects.filter(user=User.objects.get(phone=request.session['phone']),
                                     path=join_path(request.session['ftp_path'],
                                                    request.FILES['file'].name)).count() == 0:
                Folder.objects.create(user=User.objects.get(phone=request.session['phone']),
                                      path=join_path(request.session['ftp_path'], request.FILES['file'].name))
            if request.FILES['file'].size > UPLOAD_MAX_SIZE:
                return JsonResponse(
                    {'success': False, 'info': '文件大小超过限制,最大为' + str(UPLOAD_MAX_SIZE / 1024 / 1024) + 'M'})
            # record = async_upload_request()
            # thread = threading.Thread(target=async_upload,
            #                           args=(record, request.session['ftp_path'], request.FILES['file']))
            # thread.start()
            FTP(request.session['ftp_path']).connect().upload(request.FILES['file'])
            print('上传成功')
            return JsonResponse({'success': True, 'upload_id': 0})
        except Exception as e:
            print('上传失败', e)
            return JsonResponse({'success': False, 'info': str(e)})
    print('上传失败')
    return JsonResponse({'success': False, 'info': '上传失败'})


def async_upload_request():
    record = UploadRecord.objects.create()
    return record


def async_upload(record: UploadRecord, ftp_path, file):
    try:
        FTP(ftp_path).connect().upload(file)
        record.state = 1
    except Exception as e:
        record.state = 2
        print(e)

    record.save()


def create_folder(request):
    """
    创建文件夹
    :param request:
    :return:
    """
    try:
        if User.objects.get(phone=request.session['phone']).priority == 0:
            return JsonResponse({'success': False, 'info': '权限不足'})
        folder_name = FTP(request.session['ftp_path']).connect().create_folder()
        Folder.objects.create(user=User.objects.get(phone=request.session['phone']),
                              path=join_path(request.session['ftp_path'], folder_name),
                              priority=0)
        return JsonResponse({'success': True})
    except Exception as e:
        print(e)
        return JsonResponse({'success': False, 'info': '创建文件夹失败' + str(e)})


def rename(request):
    """
    重命名文件或文件夹
    :param request:
    :return:
    """

    if check_not_null(request, ['old_name', 'new_name']):
        if '/' in request.POST['new_name']:
            return JsonResponse({'success': False, 'info': '文件名中不能包含 "/"'})
        try:
            ftp = FTP(request.session['ftp_path']).connect()
            prev_path = join_path(request.session['ftp_path'], request.POST['old_name'])
            new_prev_path = join_path(request.session['ftp_path'], request.POST['new_name'])
            if ftp.is_dir(prev_path):
                data = get_all_data(ftp.traverser, prev_path)
            else:
                data = []
            if ftp.rename(request.POST['old_name'], request.POST['new_name'],
                          User.objects.get(phone=request.session['phone'])) is True:
                data.append(prev_path)
                for i in data:
                    new_path = join_path(new_prev_path, i[len(prev_path):])
                    Folder.objects.filter(path=i).update(path=new_path)
                return JsonResponse({'success': True})
        except Exception as e:
            print(e)
            return JsonResponse({'success': False, 'info': str(e)})
    print('重命名失败')
    return JsonResponse({'success': False, 'info': '重命名失败，请确认是否有权限操作'})


def user_rename(request):
    """
    重命名用户名
    :param request:
    :return:
    """
    if check_not_null(request, ['new_user_name']):
        try:
            User.objects.filter(phone=request.session['phone']).update(username=request.POST['new_user_name'])
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'info': str(e)})
    return JsonResponse({'success': False, 'info': '新名字不能为空'})


def delete(request):
    """
    删除文件或文件夹
    :param request:
    :return:
    """
    if check_not_null(request, ['name']):
        try:
            ftp = FTP(request.session['ftp_path']).connect()
            prev_path = join_path(request.session['ftp_path'], request.POST['name'])
            if ftp.is_dir(request.POST['name']):
                data = get_all_data(ftp.traverser, prev_path)
                data.append(prev_path)
            else:
                data = [prev_path]

            if ftp.delete(prev_path, User.objects.get(phone=request.session['phone'])):
                for i in data:
                    Folder.objects.filter(path=i).delete()
                return JsonResponse({'success': True})
        except Exception as e:
            print(e)
    print('删除失败')
    return JsonResponse({'success': False, 'info': '删除失败，请确认是否有权限操作'})


def force_delete(request):
    """
    删除文件或文件夹
    :param request:
    :return:
    """
    print('force_delete')
    print(request.POST)
    if check_not_null(request, ['name']):
        try:
            prev_path = join_path(request.session['ftp_path'], request.POST['name'])
            Folder.objects.filter(path=prev_path).delete()
            ftp = FTP(request.session['ftp_path']).connect()
            try:
                ftp.traverser.delete(prev_path)
            except Exception as e:
                pass
            print('取消上传成功')
            return JsonResponse({'success': True})
        except Exception as e:
            print(e)
    print('取消上传失败')
    return JsonResponse({'success': False, 'info': '取消上传失败'})


def feedback(request):
    if check_not_null(request, ['feedback']):
        try:
            FeedBack.objects.create(user=User.objects.get(phone=request.session['phone']),
                                    content=request.POST['feedback'])
        except Exception as e:
            print(e)
    return JsonResponse({'success': True})


def get_time_delta(data_time):
    """
    获取数据时间与当前时间的时间差，在时区转换为UTC+0:00后使用
    :param data_time:
    :return:
    """
    if type(data_time) == int:
        return datetime.datetime.utcnow().timestamp() - data_time
    return datetime.datetime.utcnow().timestamp() - data_time.timestamp()


def update_active(request):
    request.session['active_time'] = int(datetime.datetime.utcnow().timestamp())


def deactive(request):
    request.session['active_time'] = 0


def is_active(request):
    """
    检查用户是否活跃
    :param request:
    :return:
    """
    if request.session.get('active_time', None) is not None:
        if get_time_delta(request.session['active_time']) < ACTIVE_TIME:
            return True
    return False


def check_not_null(request, a: list):
    """
    检查request中被a包含的所有元素是否为空
    :param request:
    :param a:
    :return:
    """
    for i in a:
        if request.POST.get(i, '') == '':
            print(i + ' is null')
            return False
    return True


def send_sms(request):
    if not check_not_null(request, ['phone_number']):
        return JsonResponse({'success': False, 'message': '手机号不能为空'})
    else:
        phone_number = str(request.POST['phone_number'])
    try:
        time = SmsCode.objects.get(phone=phone_number).time
        # print(datetime.datetime.now().timestamp() - time)
        if datetime.datetime.now().timestamp() - time <= VALID_TIME:
            return JsonResponse(
                {'code': '404', 'message': ("验证码发送过于频繁, 间隔必须长于%d分钟" % (VALID_TIME / 60))})
    except SmsCode.DoesNotExist:
        pass
    try:
        # 实例化一个认证对象，入参需要传入腾讯云账户secretId，secretKey,此处还需注意密钥对的保密
        # 密钥可前往https://console.cloud.tencent.com/cam/capi网站进行获取
        cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        # 实例化一个http选项，可选的，没有特殊需求可以跳过
        httpProfile = HttpProfile()
        httpProfile.endpoint = "sms.tencentcloudapi.com"

        # 实例化一个client选项，可选的，没有特殊需求可以跳过
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        # 实例化要请求产品的client对象,clientProfile是可选的
        client = sms_client.SmsClient(cred, "ap-guangzhou", clientProfile)

        # 实例化一个请求对象,每个接口都会对应一个request对象
        req = models.SendSmsRequest()
        code = str(random.randint(10000, 99999))
        params = {
            "PhoneNumberSet": [phone_number],
            "SmsSdkAppId": "1400624629",
            "SignName": "爱在今春",
            "TemplateId": "1419481",
            "TemplateParamSet": [code, "10"]
        }
        req.from_json_string(json.dumps(params))

        # 返回的resp是一个SendSmsResponse的实例，与请求对象对应
        resp = client.SendSms(req)
        # 输出json格式的字符串回包
        print(resp.to_json_string())
        if resp.SendStatusSet[0].Code == 'Ok':
            save_sms(phone_number, code)
        return JsonResponse({'code': resp.SendStatusSet[0].Code, 'message': resp.to_json_string()})
    except TencentCloudSDKException as err:
        print(err)
        return JsonResponse({'code': '404', 'message': '发送失败' + str(err)})


def save_sms(phone: str, code: str):
    """
    保存验证码
    :param phone:
    :param code:
    :return: None
    """
    SmsCode(phone=phone, code=code, time=datetime.datetime.now().timestamp()).save()


def check_sms(phone: str, code: str):
    """
    检查验证码是否正确
    :param phone:
    :param code:
    :return:
    """
    try:
        result = get_time_delta(SmsCode.objects.get(phone=phone, code=code).time)
        if result > VALID_TIME:
            return '验证码已过期'
        return True
    except SmsCode.DoesNotExist:
        print('验证码不存在')
        return '验证码错误'


def initialize_folders():
    """
    初始化文件夹
    Warning: this operation will clear all the data in the Folder and remove root_user !!!!
    :return:
    """
    print('initializing folders...')
    # clear all folders
    Folder.objects.all().delete()

    # delete root_user and create it if exist
    User.objects.filter(username=ROOT_USER_PHONE).delete()
    root_user = User.objects.create(username=ROOT_USER_NAME,
                                    password=ROOT_USER_PASSWORD,
                                    phone=ROOT_USER_PHONE,
                                    priority=1)
    data = get_all_data(Traverser(HOME_PATH))
    for i in data:
        Folder.objects.create(path=i, user=root_user, priority=0)
    print('initialization finished')
    return True


def get_all_data(traverser, prev_path=None, filter=None, first=True):
    """
    递归获取所有文件夹
    filter: 传入None则不过滤，传入'file'则只返回文件，传入'dir'则只返回文件夹
    :return:
    """

    if prev_path is None:
        prev_path = traverser.pwd()
    tmp = traverser.pwd()
    traverser.path = prev_path

    data = traverser.nlst()
    result = []
    filtered_data = []

    for i in data:
        try:
            traverser.cwd(i)
            result.extend(get_all_data(traverser, join_path(prev_path, i), filter, False))
            traverser.cwd('..')
            if filter == 'dir':
                filtered_data.append(join_path(prev_path, i))
        except ValueError:
            if filter == 'file':
                filtered_data.append(join_path(prev_path, i))
            pass
        if filter is None:
            filtered_data.append(join_path(prev_path, i))
    result.extend(filtered_data)

    if first:
        traverser.path = tmp

    return result


def clear_zip_files():
    """
    清除所有zip文件
    :return:
    """
    try:
        for i in os.listdir(ZIP_FILE_PATH):
            if i.endswith('.zip') and i.startswith('merged_') and (
                    time.time() - os.path.getmtime(join_path(ZIP_FILE_PATH, i)) > 360000):
                os.remove(join_path(ZIP_FILE_PATH, i))
    except Exception as e:
        print(str(e))
    return True
