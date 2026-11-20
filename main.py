"""Запуск: python main.py [команда Django]."""
import os
import sys
from django.core.management import execute_from_command_line

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    args = sys.argv if len(sys.argv) > 1 else [sys.argv[0], "runserver", "127.0.0.1:8022"]
    execute_from_command_line(args)
