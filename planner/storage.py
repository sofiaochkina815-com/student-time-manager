from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class DatabasePrivateStorage(Storage):
    """Private bytes persist with the database; no public file URLs."""
    def _open(self, name, mode="rb"):
        if mode != "rb":
            raise ValueError("Private storage is read-only through open().")
        from .models import PrivateFileBlob
        item = PrivateFileBlob.objects.filter(name=name).first()
        if item is None:
            raise FileNotFoundError(name)
        return ContentFile(bytes(item.content), name=name)

    def _save(self, name, content):
        from .models import PrivateFileBlob
        data = content.read(5 * 1024 * 1024 + 1)
        if not data or len(data) > 5 * 1024 * 1024:
            raise ValueError("File must contain at most 5 MiB.")
        PrivateFileBlob.objects.create(name=name, content=data, size=len(data))
        return name

    def exists(self, name):
        from .models import PrivateFileBlob
        return PrivateFileBlob.objects.filter(name=name).exists()

    def delete(self, name):
        from .models import PrivateFileBlob
        PrivateFileBlob.objects.filter(name=name).delete()

    def size(self, name):
        from .models import PrivateFileBlob
        item = PrivateFileBlob.objects.filter(name=name).values_list("size", flat=True).first()
        if item is None:
            raise FileNotFoundError(name)
        return item

    def url(self, name):
        raise NotImplementedError("Use the authenticated attachment download route.")
