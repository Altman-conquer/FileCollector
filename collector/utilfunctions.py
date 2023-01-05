import os
from tkinter.filedialog import Open, Directory


def join_path(a: str, b: str):
    if a.endswith('/'):
        a = a[:-1]
    if b.startswith('/'):
        b = b[1:]
    if a == '':
        return b
    elif b == '':
        return a
    else:
        return a + '/' + b


def create_dir(path):
    """
    创建文件夹，注意不要传入文件名在路径末尾
    :param path:
    :return:
    """
    if not os.path.exists(path):
        os.makedirs(path)
    return path


def ask_filenames(**options):
    """
    支持多选，返回一个文件路径字符串列表，如果取消的话返回一个空列表
    :param options:
    :param title: 标题
    :return:
    """
    options["multiple"] = 1
    return Open(**options).show()


def ask_directory(**options):
    """
    返回一个目录路径字符串
    :param options:
    :param title: 标题
    :return:
    """
    return Directory(**options).show()


if __name__ == '__main__':
    pass
