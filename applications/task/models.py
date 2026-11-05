from django.db import models


class Task(models.Model):
    song_name = models.CharField(max_length=255, default="")
    artist_name = models.CharField(max_length=255, default="")

    full_path = models.CharField(max_length=255)
    state = models.CharField(max_length=255, default="wait")
    parent_path = models.CharField(max_length=255, default="")
    filename = models.CharField(max_length=255, default="")
    extra = models.TextField(default="")
    created_at = models.DateTimeField(null=True, auto_now_add=True)


class TaskRecord(models.Model):
    song_name = models.CharField(max_length=255, default="")
    artist_name = models.CharField(max_length=255, default="")
    full_path = models.CharField(max_length=255, default="")
    tag_source = models.CharField(max_length=255, default="")
    icon = models.CharField(max_length=255, default="icon-folder")
    state = models.CharField(max_length=255, default="wait")
    extra = models.TextField(default="")
    created_at = models.DateTimeField(null=True, auto_now_add=True)
    batch = models.CharField(max_length=255, default="", db_index=True)


class MusicMetaCache(models.Model):
    path = models.CharField(max_length=512, unique=True, db_index=True)
    mtime = models.FloatField(default=0)
    size = models.BigIntegerField(default=0)
    meta_json = models.TextField(default="{}")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "task_music_meta_cache"
        verbose_name = "音频元数据缓存"
        verbose_name_plural = "音频元数据缓存"

    def __str__(self):
        return self.path
