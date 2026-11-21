from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import TaskAttachment


@receiver(post_delete, sender=TaskAttachment)
def remove_attachment_file(sender, instance, **kwargs):
    storage, name = instance.file.storage, instance.file.name
    if name:
        transaction.on_commit(lambda: storage.delete(name), robust=True)
