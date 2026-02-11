from uuid import uuid4
from django.db import models



class BaseModel(models.Model):
    created_datetime = models.DateTimeField(auto_now_add=True)
    modified_datetime = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(default=uuid4, editable=False)

    class Meta:
        abstract = True


class SafeQuerySet(models.QuerySet):
    def delete(self):
        # Soft-delete for a whole QuerySet
        return super().delete()


class SafeManager(models.Manager.from_queryset(SafeQuerySet)):
    def get_queryset(self):
        # Only fetch active records by default
        return super().get_queryset()


class SafeBaseModel(BaseModel):
    # Put is_active here if you want *only* safe-delete models to have it
    is_active = models.BooleanField(default=True)

    # Manager that hides soft-deleted objects
    objects = SafeManager()

    # Manager that returns everything, including soft-deleted
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if update_fields is not None:
            update_fields = set(update_fields) | {"modified_datetime"}
        super().save(force_insert, force_update, using, update_fields)

    def delete(self):
        return super().delete()


