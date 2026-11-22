"""Local IDE entry point: migrate, check, then start one loopback server."""
import argparse
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

BASE_DIR = Path(__file__).resolve().parent
PORT = 8022


def main():
    parser = argparse.ArgumentParser(description="Локальный запуск приложения")
    parser.add_argument("--check", action="store_true", help="Подготовить базу и проверить конфигурацию без запуска сервера")
    parser.add_argument("--port", type=int, default=PORT, help="Локальный порт приложения")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Порт должен быть от 1024 до 65535")
    os.chdir(BASE_DIR)
    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        host = unquote(urlsplit(database_url).hostname or "localhost")
        if host not in {"localhost", "127.0.0.1", "::1"} and not host.startswith("/"):
            raise SystemExit("Локальный запуск требует локальную DATABASE_URL. Удалите переменную для SQLite или укажите PostgreSQL на этом компьютере.")
    erp_url = os.getenv("ERP_BASE_URL", "")
    if erp_url and urlsplit(erp_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Для локального запуска укажите локальный адрес сервиса 1С.")
    os.environ["DEBUG"] = "1"
    os.environ["ALLOWED_HOSTS"] = "127.0.0.1,localhost"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from django.core.management import call_command
    django.setup()
    call_command("migrate", interactive=False, verbosity=0)
    call_command("check", verbosity=0)
    if args.check:
        print("Локальная конфигурация проверена: http://127.0.0.1:" + str(args.port))
        return
    call_command("runserver", "127.0.0.1:" + str(args.port), use_reloader=False)


if __name__ == "__main__":
    main()
