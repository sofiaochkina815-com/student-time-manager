# PostgreSQL

В режиме публикации DEBUG=0 обязателен DATABASE_URL PostgreSQL. TLS-параметры sslmode и channel_binding сохраняются; неизвестные и повторяющиеся параметры отклоняются. Пример без пароля: `postgresql://USER@HOST:5432/DB?sslmode=require&connect_timeout=5`. Настоящий URL хранится в переменных окружения.

Миграции: `.venv/bin/python main.py migrate --noinput`. Проверки: `.venv/bin/python main.py test planner`. В SQLite проверка реальной блокировки пропускается; на PostgreSQL два одновременных ввода по 1000 минут должны дать одну запись и один отказ по суточному лимиту.

Источник: https://docs.djangoproject.com/en/6.1/ref/databases/ . Факт локального испытания PostgreSQL не означает публикацию на хостинге.
