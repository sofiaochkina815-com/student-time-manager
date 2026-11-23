"""Проверка отслеживаемых исходников в отдельном окружении и пустой базе."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
import venv


def verify(report_path):
    root = Path(__file__).resolve().parents[1]
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    sources = {}
    with tempfile.TemporaryDirectory(prefix="student-time-install-") as directory:
        target = Path(directory)
        for name in filter(None, names):
            original = root/name
            if original.is_symlink():
                raise RuntimeError("Символические ссылки в комплекте требуют отдельной проверки.")
            destination = target/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, destination)
            sources[name] = hashlib.sha256(original.read_bytes()).hexdigest()
        venv.EnvBuilder(with_pip=True).create(target/".venv")
        python = target/".venv"/("Scripts/python.exe" if os.name == "nt" else "bin/python")
        env = {key:value for key,value in os.environ.items() if key not in
            {"DATABASE_URL", "SECRET_KEY", "DEBUG", "ALLOWED_HOSTS", "DJANGO_SETTINGS_MODULE", "PYTHONPATH", "PYTHONHOME"}}
        env.update(DEBUG="1", ALLOWED_HOSTS="127.0.0.1,localhost,testserver")
        with (target/"verification.log").open("w+") as log:
            def run(*args):
                result = subprocess.run([str(python), *args], cwd=target, env=env, stdout=log, stderr=log, timeout=180)
                if result.returncode:
                    log.seek(0)
                    raise RuntimeError(log.read()[-6000:])
            run("-m", "pip", "install", "-r", "requirements.txt")
            run("-m", "pip", "check")
            run("run_local.py", "--check")
            run("main.py", "makemigrations", "--check", "--dry-run")
            run("main.py", "test", "planner", "--verbosity", "1")
            run("main.py", "shell", "-c", "from django.contrib.auth import get_user_model; from planner.demo import seed_demo; from django.test import Client; u=get_user_model().objects.create_user('installation-demo'); seed_demo(u); c=Client(); c.force_login(u); paths=['/tasks/','/references/','/week/','/analytics/','/research/','/goals/','/sessions/','/profile/']; assert all(c.get(p).status_code==200 for p in paths); r=c.get('/reports/study.pdf'); assert r.status_code==200 and r.content.startswith(b'%PDF-'); print('Business smoke OK')")
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            server = subprocess.Popen([str(python), str(target/"run_local.py"), "--port", str(port)], cwd=root.parent, env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic()+30
                while True:
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                            assert response.status == 200
                        break
                    except (URLError, TimeoutError):
                        if server.poll() is not None or time.monotonic() >= deadline:
                            raise RuntimeError("Чистый локальный сервер не запустился.")
                        time.sleep(.2)
                with urlopen(f"http://127.0.0.1:{port}/static/planner/app.css", timeout=2) as response:
                    assert response.status == 200 and b"{" in response.read()
            finally:
                server.terminate()
                try: server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill(); server.wait(timeout=5)
            log.seek(0)
            transcript = log.read()
        versions = subprocess.check_output([str(python), "-m", "pip", "freeze"], cwd=target, env=env, text=True).splitlines()
    result = {"schema_version": 1, "status": "passed", "source_sha256": sources,
        "python": sys.version, "dependencies": versions,
        "checks": ["isolated_venv_install", "pip_check", "empty_database_migrations", "migration_consistency", "full_test_suite", "demo_and_authenticated_pages", "study_pdf", "loopback_http_from_other_cwd", "css_http"],
        "test_output": transcript[transcript.find("Found "):][-2200:],
        "limitations": ["SQLite does not prove PostgreSQL row-lock behavior", "HTTP and Django clients do not replace visual browser acceptance"]}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(f"Чистая локальная установка проверена: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("reports/local-install-v1.json"))
    verify(parser.parse_args().report.resolve())
