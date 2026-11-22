from urllib.parse import parse_qs, unquote, urlparse
from django.core.exceptions import ImproperlyConfigured


def postgres_database(value):
    try:
        parsed = urlparse(value)
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.path.strip("/"):
            raise ValueError
        port = parsed.port or 5432
        name = unquote(parsed.path.lstrip("/"))
        if "\x00" in name:
            raise ValueError
        query = parse_qs(parsed.query, keep_blank_values=True)
        if set(query) - {"sslmode", "connect_timeout", "channel_binding"} or any(len(v) != 1 for v in query.values()):
            raise ValueError
        options = {key: values[0] for key,values in query.items()}
        if "sslmode" in options and options["sslmode"] not in {"disable","allow","prefer","require","verify-ca","verify-full"}:
            raise ValueError
        if "channel_binding" in options and options["channel_binding"] not in {"disable","prefer","require"}:
            raise ValueError
        if "connect_timeout" in options:
            timeout = int(options["connect_timeout"])
            if not 1 <= timeout <= 60:
                raise ValueError
            options["connect_timeout"] = timeout
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("Некорректный DATABASE_URL PostgreSQL или неподдерживаемые параметры подключения.") from exc
    return {"ENGINE":"django.db.backends.postgresql", "NAME":name, "USER":unquote(parsed.username or ""), "PASSWORD":unquote(parsed.password or ""), "HOST":unquote(parsed.hostname or "localhost"), "PORT":port, "OPTIONS":options, "CONN_MAX_AGE":60, "CONN_HEALTH_CHECKS":True}
