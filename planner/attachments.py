import hashlib
from pathlib import Path
from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from .models import Task, TaskAttachment

MAX_FILE = 5*1024*1024
MAX_TOTAL = 50*1024*1024


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = TaskAttachment
        fields = ["file", "note"]

    def clean_file(self):
        upload = self.cleaned_data["file"]
        payload = upload.read(MAX_FILE+1);upload.seek(0)
        name = upload.name.replace("\\", "/").rsplit("/", 1)[-1].replace("\r", " ").replace("\n", " ")[:150]
        suffix = Path(name).suffix.lower()
        if not payload or len(payload) > MAX_FILE:
            raise forms.ValidationError("Файл должен быть непустым и не превышать 5 МиБ.")
        if suffix == ".pdf":
            if not payload.startswith(b"%PDF-"):
                raise forms.ValidationError("Содержимое не соответствует заголовку PDF.")
        elif suffix == ".txt":
            try:
                payload.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise forms.ValidationError("Текст должен иметь кодировку UTF-8.") from exc
            if b"\x00" in payload:
                raise forms.ValidationError("В текстовом файле обнаружены бинарные данные.")
        else:
            raise forms.ValidationError("Разрешены только PDF и TXT UTF-8.")
        self.instance.original_name = name
        self.instance.sha256 = hashlib.sha256(payload).hexdigest()
        self.instance.size = len(payload)
        self.instance.kind = suffix[1:]
        return upload


@receiver(post_delete, sender=TaskAttachment)
def remove_attachment_file(sender, instance, **kwargs):
    storage, name = instance.file.storage, instance.file.name
    if name:
        transaction.on_commit(lambda: storage.delete(name), robust=True)


@login_required
def attachment_list(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    instance = TaskAttachment(owner=request.user, task=task)
    form = AttachmentForm(request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None, instance=instance)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            used = TaskAttachment.objects.filter(owner=request.user).aggregate(total=Sum("size"))["total"] or 0
            if used+instance.size > MAX_TOTAL:
                form.add_error("file", "Общий объём личных файлов не должен превышать 50 МиБ.")
            elif TaskAttachment.objects.filter(owner=request.user, task=task, sha256=instance.sha256).exists():
                form.add_error("file", "Этот файл уже прикреплён к задаче.")
            else:
                try:
                    instance.save()
                except BaseException:
                    if instance.file.name and instance.file._committed:
                        instance.file.storage.delete(instance.file.name)
                    raise
                messages.success(request, "Файл сохранён в личных материалах задачи.")
                return redirect("attachment_list", pk=task.pk)
    return render(request, "planner/attachments.html", {"task": task, "form": form,
        "attachments": TaskAttachment.objects.filter(owner=request.user, task=task)})


@login_required
def attachment_download(request, pk):
    item = get_object_or_404(TaskAttachment, pk=pk, owner=request.user, task__owner=request.user)
    response = FileResponse(item.file.open("rb"), as_attachment=True, filename=item.original_name,
        content_type="application/pdf" if item.kind == "pdf" else "text/plain; charset=utf-8")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def attachment_delete(request, pk):
    item = get_object_or_404(TaskAttachment, pk=pk, owner=request.user, task__owner=request.user)
    task = item.task
    if request.method == "POST":
        item.delete()
        return redirect("attachment_list", pk=task.pk)
    return render(request, "planner/attachment_delete.html", {"item": item})
