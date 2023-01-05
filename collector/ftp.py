import datetime
import os
import shutil
import time

from FileCollector.settings import HOME_PATH, ROOT_USER_NAME, ROOT_USER_PHONE
from collector.models import Folder, User
from .utilfunctions import join_path


class FTPObj:
    file_name_max_len = 15
    user_name_max_len = 4

    def __init__(self, name: str, type: str, time: str, size: int, user_id: str, user_name: str, priority: int):
        self.name = name
        self.type = type
        self.time = time
        self.user_id = user_id
        self.user_name = user_name
        self.priority = priority
        if 0 < FTPObj.file_name_max_len < len(self.name):
            self.file_short_name = self.name[:FTPObj.file_name_max_len] + '...'
        else:
            self.file_short_name = self.name
        if 0 < FTPObj.user_name_max_len < len(self.user_name):
            self.user_short_name = self.user_name[:FTPObj.user_name_max_len] + '...'
        else:
            self.user_short_name = self.user_name

        # convert to suitable size format
        self.size_in_bytes = size
        if self.type == 'file':
            if size < 1024:
                self.size = f'{size} B'
            elif size < 1024 ** 2:
                self.size = f'{size / 1024:.1f} KB'
            elif size < 1024 ** 3:
                self.size = f'{size / 1024 ** 2:.1f} MB'
            else:
                self.size = f'{size / 1024 ** 3:.1f} GB'
        else:
            self.size = ''

    def __str__(self):
        return f'{self.name}   {self.type}   {self.time}   {self.size}'

    def __repr__(self):
        return self.__str__()


class FTPDownloadObj:
    def __init__(self, name: str, size: int, file_stream):
        self.name = name
        self.cur_size = 0
        self.total_size = size
        self.file = file_stream

    def update(self, s):
        self.file.write(s)
        self.cur_size += 8192

    def get_progress(self):
        if self.total_size == 0:
            return '0%'
        return f'{self.cur_size / self.total_size * 100:.2f}%'

    def __str__(self):
        return f'{self.name}   {self.cur_size}   {self.total_size}'

    def __repr__(self):
        return self.__str__()


class Traverser:
    def __init__(self, path):
        if path is None:
            raise ValueError('Traverser path cannot be None')
        elif not os.path.exists(path):
            raise ValueError('Traverser path does not exist')
        self.path = path

    def info(self):
        """
        获取当前目录下所有文件夹和文件
        :return:
        """
        dirs = []
        for i in os.listdir(self.path):
            full_path = join_path(self.path, i)
            dirs.append([i, time.ctime(os.path.getmtime(full_path)),
                         os.path.getsize(full_path),
                         os.path.isdir(full_path)])
        return dirs

    def cwd(self, path: str):
        """
        获取当前目录
        :return:
        """
        if not self.is_dir(path):
            raise ValueError('path is not a directory')
        if path == '..':
            self.path = self.path[:self.path.rfind('/')]
        elif path.startswith('/'):
            self.path = path
        else:
            self.path = join_path(self.path, path)

    def pwd(self):
        return self.path

    def is_dir(self, name: str = None):
        if name is None:
            return os.path.isdir(self.path)
        else:
            return os.path.isdir(join_path(self.path, name))

    def mkd(self, folder_name: str):
        os.mkdir(join_path(self.path, folder_name))

    def nlst(self):
        return os.listdir(self.path)

    def delete(self, path: str):
        try:
            shutil.rmtree(path)
        except:
            os.remove(path)

    def rename(self, old_name: str, new_name: str):
        os.rename(join_path(self.path, old_name), join_path(self.path, new_name))


class FTP:
    default_path = ''

    def __init__(self, path):
        self.path = HOME_PATH if path is None else path
        self.traverser = None

    def connect(self):
        self.traverser = Traverser(self.path)
        # self.ftp = ftplib.FTP()
        # self.ftp.set_pasv(False)
        # self.ftp.connect(self.host, self.port)
        # self.ftp.login(self.user, self.password)
        # self.cwd()
        return self

    @staticmethod
    def check_authority(self, user: User, file: Folder):
        if user.priority == 1:
            return True

        if file is None:
            if user.priority == 1:
                return True
            else:
                return False
        elif file.user.id == user.id:
            return True
        else:
            return False

    def add_to_database(self, file_path):
        try:
            Folder.objects.get(path=file_path)
        except Folder.DoesNotExist:
            obj = Folder(path=file_path, user=User.objects.get(phone=ROOT_USER_PHONE))
            obj.save()
            return obj

    def is_dir(self, name: str):
        return self.traverser.is_dir(name)

    def download_able(self, user: User, file_path):
        try:
            folder = Folder.objects.get(path=file_path)
            if folder.priority == 1:
                return True
        except Folder.DoesNotExist:
            folder = self.add_to_database(file_path)
        return FTP.check_authority(self, user, folder)

    def upload(self, file):
        """
        上传文件
        :param file:
        :return:
        """
        file_name = file.name
        file_path = join_path(self.path, file_name)
        with open(file_path, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        return True

    def cwd(self):
        self.traverser.cwd(self.path)

    def pwd(self):
        return self.traverser.pwd()

    def pwd_list(self):
        """
        获取当前目录路径(去除根目录)
        :return:
        """
        path = self.pwd()[len(FTP.default_path):]
        return path.split('/')

    def prev(self):
        if len(self.traverser.pwd()) == len(self.path):
            return False
        else:
            self.traverser.cwd('..')
            return True

    def next(self, dir_name):
        self.traverser.cwd(dir_name)
        return True

    def create_folder(self):
        folder_name = '新建文件夹'
        folders = self.traverser.nlst()
        if folder_name in folders:
            i = 1
            while True:
                if f'{folder_name}({i})' in folders:
                    i += 1
                else:
                    folder_name = f'{folder_name}({i})'
                    break
        self.traverser.mkd(folder_name)
        return folder_name

    def dirs(self, sort_by='type'):
        result = []
        data = self.traverser.info()
        for i in data:
            temp = {'type': 'dir' if i[-1] else 'file', 'size': int(i[-2]), 'name': i[0],
                    'time': datetime.datetime.strptime(i[1], '%a %b %d %H:%M:%S %Y').strftime(
                        '%Y-%m-%d %H:%M')}
            try:
                folder = Folder.objects.get(path=join_path(self.pwd(), temp['name']))
                temp['user_id'] = folder.user.id
                temp['user_name'] = folder.user.username
                temp['priority'] = folder.priority
            except Folder.DoesNotExist:
                temp['user_id'] = ''
                temp['user_name'] = ROOT_USER_NAME
                temp['priority'] = 0
            result.append(FTPObj(**temp))
        result.sort(key=lambda x: x.name)
        if sort_by == 'type':
            result.sort(key=lambda x: 0 if x.type == 'dir' else 1)
        return result

    def rename(self, old_name, new_name, user: User):
        try:
            file_path = join_path(self.pwd(), old_name)
            try:
                folder = Folder.objects.get(path=file_path)
            except Folder.DoesNotExist:
                folder = self.add_to_database(file_path)
            if FTP.check_authority(self, user, folder):
                self.traverser.rename(old_name, new_name)
                return True
            else:
                return '权限不足, 无法重命名'
        except Exception as e:
            print(e)
            return '重命名失败, 请检查文件名是否合法'

    def delete(self, file_path, user: User):
        try:
            try:
                folder = Folder.objects.get(path=file_path)
            except Folder.DoesNotExist:
                folder = self.add_to_database(file_path)
            if FTP.check_authority(self, user, folder):
                self.traverser.delete(file_path)
                return True
        except Exception as e:
            print(e)
        return False

    def close(self):
        pass
        # self.ftp.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == '__main__':
    pass
