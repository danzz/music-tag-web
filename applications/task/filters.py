import django_filters
from django.db import models
from applications.task.models import TaskRecord, Task


class TaskFilters(django_filters.FilterSet):
    state = django_filters.CharFilter(lookup_expr="iexact")


class TaskRecordFilters(django_filters.FilterSet):
    state = django_filters.CharFilter(lookup_expr="iexact")
    batch = django_filters.CharFilter(lookup_expr="iexact")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = TaskRecord
        fields = ["state", "batch"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            models.Q(song_name__icontains=value) |
            models.Q(full_path__icontains=value) |
            models.Q(extra__icontains=value)
        )
