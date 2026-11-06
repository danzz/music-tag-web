import os.path
import time

from rest_framework import serializers

from applications.task.models import TaskRecord, Task


class FileListSerializer(serializers.Serializer):
    file_path = serializers.CharField(required=True)
    sorted_fields = serializers.ListField(required=False, default=list)
    only_dir = serializers.BooleanField(required=False, default=False)


class Id3Serializer(serializers.Serializer):
    file_path = serializers.CharField(required=True)
    file_name = serializers.CharField(required=True)


class MusicId3Serializer(serializers.Serializer):
    title = serializers.CharField(required=True, allow_null=True, allow_blank=True)
    artist = serializers.CharField(required=True, allow_null=True, allow_blank=True)
    album = serializers.CharField(required=True, allow_null=True, allow_blank=True)
    album_type = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    language = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    albumartist = serializers.CharField(required=True, allow_null=True, allow_blank=True)
    discnumber = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    tracknumber = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    genre = serializers.CharField(required=True, allow_null=True, allow_blank=True)
    year = serializers.CharField(required=True, allow_null=True, allow_blank=True)
    lyrics = serializers.CharField(required=True, allow_null=True, allow_blank=True)
    is_save_lyrics_file = serializers.BooleanField(required=True)
    is_save_album_cover = serializers.BooleanField(required=True)
    comment = serializers.CharField(required=True, allow_null=True, allow_blank=True)
    album_img = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    filename = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    file_full_path = serializers.CharField(required=True)


class UpdateId3Serializer(serializers.Serializer):
    music_id3_info = MusicId3Serializer(many=True)


class BatchUpdateId3Serializer(serializers.Serializer):
    file_full_path = serializers.JSONField(required=True)
    music_info = serializers.JSONField(required=True)
    select_data = serializers.JSONField(required=True)
    apply_to_all = serializers.BooleanField(required=False, default=False)


class FetchId3ByTitleSerializer(serializers.Serializer):
    title = serializers.CharField(required=True)
    resource = serializers.CharField(required=True)
    full_path = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class FetchLlyricSerializer(serializers.Serializer):
    song_id = serializers.CharField(required=True)
    resource = serializers.CharField(required=True)


class TranslationLycSerializer(serializers.Serializer):
    lyc = serializers.CharField(required=True)


class TidyFolderSerializer(serializers.Serializer):
    root_path = serializers.CharField(required=True)
    first_dir = serializers.CharField(required=True)
    second_dir = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    file_full_path = serializers.CharField(required=True)
    select_data = serializers.JSONField(required=False, default=list)
    apply_to_all = serializers.BooleanField(required=False, default=False)
    move_lrc = serializers.BooleanField(required=False, default=True)
    conflict_action = serializers.CharField(required=False, default="skip")
    clean_empty_dir = serializers.BooleanField(required=False, default=False)


class AgentPlanSerializer(serializers.Serializer):
    dir_path = serializers.CharField(required=True)
    mode = serializers.CharField(required=False, default="auto")
    files = serializers.ListField(required=False, default=list)
    system_prompt = serializers.CharField(required=False, allow_blank=True, default="")
    user_prompt = serializers.CharField(required=False, allow_blank=True, default="")
    ai_config = serializers.DictField(required=False, default=dict)


class AgentTestConnectionSerializer(serializers.Serializer):
    base_url = serializers.CharField(required=False, allow_blank=True, default="")
    baseUrl = serializers.CharField(required=False, allow_blank=True, default="")
    api_key = serializers.CharField(required=False, allow_blank=True, default="")
    apiKey = serializers.CharField(required=False, allow_blank=True, default="")
    model = serializers.CharField(required=False, allow_blank=True, default="")
    temperature = serializers.FloatField(required=False, default=0.2)


class TestComfyuiConnectionSerializer(serializers.Serializer):
    comfyui_url = serializers.CharField(required=False, allow_blank=True, default="http://host.docker.internal:8188")


class GenerateCourseCoverSerializer(serializers.Serializer):
    folder_path = serializers.CharField(required=True)
    title = serializers.CharField(required=True)
    author = serializers.CharField(required=False, allow_blank=True, default="")
    category = serializers.CharField(required=False, allow_blank=True, default="得到课程")
    prompt = serializers.CharField(required=False, allow_blank=True, default="")
    engine = serializers.CharField(required=False, default="comfyui")
    comfyui_url = serializers.CharField(required=False, allow_blank=True, default="http://host.docker.internal:8188")
    style = serializers.CharField(required=False, default="amber_dark")
    quality = serializers.CharField(required=False, default="fast")
    layout = serializers.CharField(required=False, default="dedao_clean")
    font_size = serializers.CharField(required=False, default="auto")


class ApplyCourseCoverSerializer(serializers.Serializer):
    folder_path = serializers.CharField(required=True)
    image_base64 = serializers.CharField(required=True)
    embed_to_files = serializers.BooleanField(required=False, default=True)


class TaskSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = "__all__"

    def get_message(self, obj):
        reason = getattr(obj, "extra", "") or "未找到标签或修改失败！"
        return f"【{obj.song_name}】 {reason}"

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if os.path.exists(ret["full_path"]):
            ret["is_exists"] = True
        else:
            Task.objects.filter(id=ret["id"]).delete()
            ret["is_exists"] = False
        return ret


class TaskRecordSerializer(serializers.ModelSerializer):
    filename = serializers.SerializerMethodField()
    batch_time = serializers.SerializerMethodField()

    class Meta:
        model = TaskRecord
        fields = "__all__"

    def get_filename(self, obj):
        if obj.full_path:
            return os.path.basename(obj.full_path)
        return obj.song_name

    def get_batch_time(self, obj):
        if obj.created_at:
            return obj.created_at.strftime("%Y-%m-%d %H:%M:%S")
        try:
            ts = float(obj.batch) / 1000.0
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
        except Exception:
            return obj.batch


class UploadImageSerializer(serializers.Serializer):
    upload_file = serializers.ImageField(required=True)


class RetryFailedSerializer(serializers.Serializer):
    batch = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    source_list = serializers.ListField(required=False)
    select_mode = serializers.CharField(required=False, allow_null=True, allow_blank=True)


class FolderMusicListSerializer(serializers.Serializer):
    file_path = serializers.CharField(required=True)
    page = serializers.IntegerField(required=False, default=1)
    page_size = serializers.IntegerField(required=False, default=128)
    search_word = serializers.CharField(required=False, allow_null=True, allow_blank=True, default='')
    sorted_field = serializers.CharField(required=False, allow_null=True, allow_blank=True, default='')
    sort_order = serializers.CharField(required=False, allow_null=True, allow_blank=True, default='asc')


