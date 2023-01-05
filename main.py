#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'FileCollector.settings')
    try:
        from django.core.management import execute_from_command_line

    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    sys.argv = [os.path.join(os.getcwd(), 'main.py'), 'runserver', '8000']
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    print('注：该项目若通过main.py运行，将会自动启动Django服务器，端口为8000')
    # get the desktop path
    print(os.path.join(os.path.expanduser("~"), 'Desktop'))
    main()
