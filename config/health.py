from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def live(request):
    return JsonResponse({"status":"alive"})


@require_safe
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        response = JsonResponse({"status":"unavailable"}, status=503)
    else:
        response = JsonResponse({"status":"ready"})
    response["Cache-Control"] = "no-store"
    return response
