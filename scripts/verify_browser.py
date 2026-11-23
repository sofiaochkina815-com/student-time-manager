"""Реальный Chrome в изолированной копии приложения с вымышленными данными."""
import argparse
from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen
from playwright.sync_api import sync_playwright


def verify(app_python, output):
    root = Path(__file__).resolve().parents[1]
    app_python = Path(os.path.abspath(app_python))
    output.mkdir(parents=True, exist_ok=True)
    names = subprocess.check_output(['git','ls-files','-z'], cwd=root).decode().split('\0')
    password = secrets.token_urlsafe(24)
    env = {k:v for k,v in os.environ.items() if k not in {'DATABASE_URL','SECRET_KEY','DJANGO_SETTINGS_MODULE','PYTHONPATH','PYTHONHOME'}}
    env.update(DEBUG='1',ALLOWED_HOSTS='127.0.0.1,localhost,testserver')
    checks=[]; screenshots=[]; sources={}
    with tempfile.TemporaryDirectory(prefix='student-browser-') as directory:
        target=Path(directory)
        for name in filter(None,names):
            original=root/name
            if original.is_symlink():raise RuntimeError('Symlink in source kit')
            destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(original,destination);sources[name]=hashlib.sha256(original.read_bytes()).hexdigest()
        def run(*args,input=None):
            return subprocess.run([str(app_python),*args],cwd=target,env=env,input=input,text=True,
                capture_output=True,check=True,timeout=90).stdout
        run('main.py','migrate','--noinput')
        seed="""import json,sys; from django.contrib.auth import get_user_model; from planner.demo import seed_demo; u=get_user_model().objects.create_user('browser-demo',password=json.load(sys.stdin)['password']); seed_demo(u)"""
        run('main.py','shell','-c',seed,input=json.dumps({'password':password}))
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        url=f'http://127.0.0.1:{port}'
        with (target/'server.log').open('w') as log:
            server=subprocess.Popen([str(app_python),str(target/'main.py'),'runserver',f'127.0.0.1:{port}','--noreload'],cwd=target,env=env,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+20
                while True:
                    try:
                        with urlopen(url,timeout=2) as response:assert response.status==200
                        break
                    except (URLError,TimeoutError):
                        if server.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Local server failed')
                        time.sleep(.1)
                with sync_playwright() as p:
                    browser=p.chromium.launch(channel='chrome',headless=True)
                    context=browser.new_context(viewport={'width':1440,'height':1000},locale='ru-RU',timezone_id='Asia/Tbilisi',accept_downloads=True)
                    errors=[];page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
                    def visit(path):
                        response=page.goto(url+path);assert response.status==200,(path,response.status)
                    def shot(name):
                        page.screenshot(path=str(output/name),full_page=True);screenshots.append(name)
                    visit('/accounts/login/');page.locator('#id_username').fill('browser-demo');page.locator('#id_password').fill(password)
                    page.locator('main form button').click();page.wait_for_url(url+'/');checks.append('real_form_login')
                    visit('/tasks/new/');page.locator('#id_title').fill('Браузерная учебная задача')
                    page.locator('#id_due_date').fill(date.today().isoformat());page.locator('#id_priority').select_option('3')
                    page.locator('#id_planned_minutes').fill('40');page.get_by_role('button',name='Сохранить',exact=True).click();page.wait_for_url('**/tasks/')
                    item=page.locator('article').filter(has=page.get_by_role('heading',name='Браузерная учебная задача',exact=True))
                    edit=item.get_by_role('link',name='Изменить',exact=True).get_attribute('href')
                    task_id=re.search(r'/tasks/(\d+)/',edit).group(1);checks.append('task_created_from_form');shot('tasks-desktop.png')
                    visit(f'/tasks/{task_id}/time/');page.locator('#id_date').fill(date.today().isoformat());page.locator('#id_minutes').fill('7')
                    repeated=page.locator('main form').evaluate('(form)=>Object.fromEntries(new FormData(form))')
                    page.get_by_role('button',name='Сохранить время',exact=True).click();page.wait_for_url('**/tasks/');checks.append('manual_time_saved')
                    replay=context.request.post(url+f'/tasks/{task_id}/time/',form=repeated,headers={'Referer':url+f'/tasks/{task_id}/time/'})
                    assert replay.status==200
                    visit(f'/tasks/{task_id}/time/')
                    assert page.get_by_role('link',name='Исправить',exact=True).count()==1
                    checks.append('manual_time_retry_keeps_one_record')
                    visit('/sessions/new/');page.locator('#id_task').select_option(task_id)
                    previous=(datetime.now(ZoneInfo('Asia/Tbilisi'))-timedelta(days=1)).replace(hour=12,minute=0)
                    page.locator('#id_starts_at').fill(previous.strftime('%Y-%m-%dT%H:%M'));page.locator('#id_planned_minutes').fill('25')
                    page.get_by_role('button',name='Сохранить',exact=True).click();page.wait_for_url('**/sessions/')
                    page.get_by_role('link',name='Завершить',exact=True).click();page.locator('#id_minutes').fill('17')
                    page.get_by_role('button',name='Сохранить',exact=True).click();page.wait_for_url('**/sessions/')
                    visit('/sessions/?state=history');assert 'Записано: 17 мин' in page.locator('main').inner_text();checks.append('session_finished_into_time_ledger')
                    visit(f'/tasks/{task_id}/files/')
                    page.locator('input[type=file]').set_input_files({'name':'browser.txt','mimeType':'text/plain','buffer':'Вымышленный учебный материал'.encode()})
                    page.get_by_role('button',name='Сохранить файл',exact=True).click();page.wait_for_url('**/files/')
                    with page.expect_download() as result:page.get_by_role('link',name='Скачать',exact=True).click()
                    downloaded=target/'download.txt';result.value.save_as(downloaded)
                    assert downloaded.read_text()=='Вымышленный учебный материал';checks.append('private_file_roundtrip')
                    visit('/workload/')
                    workload=page.locator('article').filter(has=page.get_by_role('heading',name='Браузерная учебная задача',exact=True))
                    assert 'осталось 16 мин' in workload.inner_text()
                    shot('workload-desktop.png');checks.append('remaining_work_uses_all_actual_time')
                    visit('/tasks/')
                    item=page.locator('article').filter(has=page.get_by_role('heading',name='Браузерная учебная задача',exact=True))
                    old_state=item.locator('form').evaluate('(form)=>Object.fromEntries(new FormData(form))')
                    item.get_by_role('button',name='Завершить',exact=True).click();page.wait_for_url('**/tasks/')
                    visit('/tasks/?state=done')
                    item=page.locator('article').filter(has=page.get_by_role('heading',name='Браузерная учебная задача',exact=True))
                    item.get_by_role('button',name='Вернуть в план',exact=True).click();page.wait_for_url('**/tasks/')
                    stale=context.request.post(url+f'/tasks/{task_id}/toggle/',form=old_state,headers={'Referer':url+'/tasks/'})
                    assert stale.status==200 and 'Статус уже изменился' in stale.text()
                    visit('/tasks/')
                    page.get_by_role('link',name='История статусов задач',exact=True).click();page.wait_for_url('**/tasks/history/')
                    assert page.get_by_role('heading',name='Браузерная учебная задача',exact=True).count()==2
                    shot('history-desktop.png');checks.append('state_history_and_stale_form')
                    visit('/analytics/');shot('analytics-desktop.png')
                    with page.expect_download() as result:page.get_by_role('link',name='Отчёт PDF',exact=True).click()
                    pdf=output/'study-browser.pdf';result.value.save_as(pdf);assert pdf.read_bytes().startswith(b'%PDF-');checks.append('pdf_download')
                    visit('/calendar/');assert 'Браузерная учебная задача' in page.locator('main').inner_text();shot('calendar-desktop.png')
                    with page.expect_download() as result:page.get_by_role('link',name='Скачать месяц iCalendar',exact=True).click()
                    ics=output/'study-browser.ics';result.value.save_as(ics);assert b'BEGIN:VCALENDAR' in ics.read_bytes();checks.append('calendar_and_ics_download')
                    for path in ['/week/','/goals/','/groups/','/references/','/profile/','/research/']:visit(path)
                    checks.append('private_navigation')
                    page.set_viewport_size({'width':390,'height':844})
                    for path,name in [('/tasks/','tasks-mobile.png'),('/calendar/','calendar-mobile.png'),('/research/','research-mobile.png'),('/workload/','workload-mobile.png'),('/tasks/history/','history-mobile.png')]:
                        visit(path)
                        if path=='/research/':
                            assert page.locator('#id_after_end').input_value()==date.today().isoformat()
                            page.get_by_role('button',name='Сравнить',exact=True).click()
                            assert 'Изменение' in page.locator('main').inner_text()
                        shot(name)
                        dimensions=page.evaluate('({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})')
                        assert dimensions['scroll']<=dimensions['width']+1,(path,dimensions)
                    checks.append('mobile_390_layout');assert not errors,errors;checks.append('no_browser_page_errors')
                    run('main.py','shell','-c',f"from planner.models import TimeEntry; from django.db.models import Sum; assert TimeEntry.objects.filter(task_id={task_id}).aggregate(total=Sum('minutes'))['total']==24")
                    checks.append('backend_exact_24_minutes')
                    browser_version=browser.version;context.close();browser.close()
            finally:
                server.terminate()
                try:server.wait(timeout=10)
                except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
    report={'status':'passed','browser':'Chrome '+browser_version,'playwright':version('playwright'),
        'source_sha256':sources,'checks':checks,'screenshots':screenshots,'viewports':[[1440,1000],[390,844]],
        'limitations':['Simulated personal study account and one browser; not a complete accessibility or cross-browser audit.']}
    (output/'browser.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Chrome acceptance passed:',len(checks),'checks')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-python',default='.venv/bin/python')
    parser.add_argument('--output',type=Path,default=Path('reports/local-visual-v1'))
    args=parser.parse_args();verify(args.app_python,args.output.resolve())
