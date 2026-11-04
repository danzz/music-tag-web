import base64
import copy
import os
import time

from django.http import HttpResponse, Http404
from django.utils.decorators import method_decorator
from django.views.decorators.gzip import gzip_page
from rest_framework import mixins
from rest_framework.decorators import action

from rest_framework.permissions import AllowAny

from applications.task.constants import ALLOW_TYPE
from applications.task.filters import TaskFilters
from applications.task.models import TaskRecord, Task
from applications.task.serialziers import FileListSerializer, Id3Serializer, UpdateId3Serializer, \
    FetchId3ByTitleSerializer, FetchLlyricSerializer, BatchUpdateId3Serializer, TranslationLycSerializer, \
    TidyFolderSerializer, TaskSerializer, UploadImageSerializer, RetryFailedSerializer, FolderMusicListSerializer
from applications.task.services.music_ids import MusicIDS
from applications.task.services.music_resource import MusicResource
from applications.task.services.update_ids import update_music_info, update_music_info_async
from applications.task.services import folder_music_service
from applications.task.tasks import full_scan_folder, scan, clear_music, batch_auto_tag_task, tidy_folder_task, process_single_auto_tag_task
from applications.utils.translation import translation_lyc_text
from component.drf.viewsets import GenericViewSet
from django_vue_cli.celery_app import app as celery_app


@method_decorator(gzip_page, name="dispatch")
class TaskViewSets(GenericViewSet):
    def get_serializer_class(self):
        if self.action == "file_list":
            return FileListSerializer
        elif self.action == "folder_music_list":
            return FolderMusicListSerializer
        elif self.action == "music_id3":
            return Id3Serializer
        elif self.action == "update_id3":
            return UpdateId3Serializer
        elif self.action == "fetch_id3_by_title":
            return FetchId3ByTitleSerializer
        elif self.action == "fetch_lyric":
            return FetchLlyricSerializer
        elif self.action in ["batch_update_id3", "batch_auto_update_id3"]:
            return BatchUpdateId3Serializer
        elif self.action == "translation_lyc":
            return TranslationLycSerializer
        elif self.action == "tidy_folder":
            return TidyFolderSerializer
        elif self.action == "upload_image":
            return UploadImageSerializer
        elif self.action == "retry_failed":
            return RetryFailedSerializer
        return FileListSerializer

    @action(methods=['POST'], detail=False)
    def file_list(self, request, *args, **kwargs):
        """文件列表"""
        validate_data = self.is_validated_data(request.data)
        file_path = validate_data['file_path']
        sorted_fields = validate_data.get('sorted_fields', [])
        only_dir = validate_data.get('only_dir', False)
        file_path_list = [p for p in file_path.split('/') if p]
        try:
            data = list(os.scandir(file_path))
        except FileNotFoundError:
            return self.failure_response(msg="文件夹不存在")
        except PermissionError:
            return self.failure_response(msg="无权限访问该文件夹")

        if only_dir:
            dir_children = []
            dir_index = 1
            for entry in data:
                try:
                    if entry.is_dir():
                        dir_name = entry.name.encode('utf-8', 'replace').decode()
                        has_sub = False
                        try:
                            with os.scandir(entry.path) as sub_entries:
                                for sub in sub_entries:
                                    if sub.is_dir():
                                        has_sub = True
                                        break
                        except Exception:
                            pass

                        node_info = {
                            "id": dir_index,
                            "name": dir_name,
                            "title": dir_name,
                            "path": os.path.normpath(entry.path.encode('utf-8', 'replace').decode()),
                            "icon": "icon-folder",
                            "is_dir": True
                        }
                        if has_sub:
                            node_info["async"] = True
                        else:
                            node_info["children"] = []
                            node_info["async"] = False

                        dir_children.append(node_info)
                        dir_index += 1
                except Exception:
                    continue
            dir_children = sorted(dir_children, key=lambda x: x.get("name").encode('gbk', "ignore"), reverse=False)
            res_data = [
                {
                    "name": file_path_list[-1] if file_path_list else file_path,
                    "title": file_path_list[-1] if file_path_list else file_path,
                    "path": os.path.normpath(file_path),
                    "expanded": True,
                    "id": 0,
                    "children": dir_children,
                    "icon": "icon-folder",
                    "is_dir": True
                }
            ]
            return self.success_response(data=res_data)
        children_data = []
        frc_map = {}
        file_data = []
        full_path_list = []
        for entry in data:
            each = entry.name.encode('utf-8', 'replace').decode()
            file_data.append({
                "name": each,
                "path": entry.path.encode('utf-8', 'replace').decode(),
                "is_dir": entry.is_dir(),
                "update_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(entry.stat().st_mtime)),
                "size": entry.stat().st_size
            })
            full_path_list.append(f"{file_path}/{each}")
            file_type = each.split(".")[-1]
            file_name = ".".join(each.split(".")[:-1])
            if file_type in ["lrc", "txt"]:
                frc_map[file_name] = each
        task_map = dict(Task.objects.filter(parent_path=file_path).values_list("filename", "state"))
        for index, entry in enumerate(file_data, 1):
            each = entry.get("name")
            file_type = each.split(".")[-1]
            file_name = ".".join(each.split(".")[:-1])
            if entry.get("is_dir", None):
                children_data.append({
                    "id": index,
                    "name": each,
                    "title": each,
                    "icon": "icon-folder",
                    "state": "null",
                    "children": [],
                    "size": entry.get("size"),
                    "update_time": entry.get("update_time")
                })
                continue
            if file_type not in ALLOW_TYPE:
                continue
            if file_name in frc_map:
                icon = "icon-script-files"
            else:
                icon = "icon-script-file"
            children_data.append({
                "id": index,
                "name": each,
                "title": each,
                "icon": icon,
                "state": task_map.get(each, "null"),
                "size": entry.get("size"),
                "update_time": entry.get("update_time")
            })
        if "name" in sorted_fields:
            children_data = sorted(children_data, key=lambda x: x.get("name").encode('gbk', "ignore"), reverse=False)
        if "update_time" in sorted_fields:
            children_data = sorted(children_data, key=lambda x: x.get("update_time"), reverse=True)
        if "size" in sorted_fields:
            children_data = sorted(children_data, key=lambda x: x.get("size"), reverse=True)
        res_data = [
            {
                "name": file_path_list[-1],
                "title": file_path_list[-1],
                "expanded": True,
                "id": 0,
                "children": children_data,
                "icon": "icon-folder",
            }
        ]
        return self.success_response(data=res_data)

    @action(methods=['POST'], detail=False)
    def folder_music_list(self, request, *args, **kwargs):
        """获取文件夹内音乐详细信息列表 (带缓存与多线程并发读取)"""
        validate_data = self.is_validated_data(request.data)
        file_path = validate_data['file_path']
        page = validate_data.get('page', 1)
        page_size = validate_data.get('page_size', 128)
        search_word = validate_data.get('search_word', '')
        sorted_field = validate_data.get('sorted_field', '')
        sort_order = validate_data.get('sort_order', 'asc')
        res_data = folder_music_service.get_folder_music_list(
            file_path=file_path,
            page=page,
            page_size=page_size,
            search_word=search_word,
            sorted_field=sorted_field,
            sort_order=sort_order
        )
        norm_file_path = os.path.normpath(file_path)
        task_qs = Task.objects.filter(parent_path=norm_file_path).values("filename", "state", "extra")
        task_map = {t["filename"]: t for t in task_qs}
        for item in res_data.get("items", []):
            task_info = task_map.get(item["filename"])
            if task_info:
                item["state"] = task_info.get("state", "none")
                item["extra"] = task_info.get("extra", "")
            else:
                item["state"] = "none"
                item["extra"] = ""
        return self.success_response(data=res_data)

    @action(methods=['GET'], detail=False, permission_classes=[AllowAny], authentication_classes=[])
    def music_cover(self, request, *args, **kwargs):
        """获取单首音乐或文件夹的封面缩略图"""
        file_path = request.query_params.get('file_path', '')
        file_name = request.query_params.get('file_name', '')
        if not file_path or not file_name:
            return HttpResponse(status=400)
        img_bytes, mime = folder_music_service.get_music_cover_data(file_path, file_name)
        if not img_bytes:
            return HttpResponse(status=404)
        response = HttpResponse(img_bytes, content_type=mime)
        response['Cache-Control'] = 'no-cache, must-revalidate'
        return response

    @action(methods=['POST'], detail=False)
    def music_id3(self, request, *args, **kwargs):
        """获取音乐id3信息"""
        validate_data = self.is_validated_data(request.data)
        file_path = validate_data['file_path']
        file_name = validate_data['file_name']
        file_type = file_name.split(".")[-1]
        if file_type in ["lrc", "txt"]:
            return self.success_response()
        file_path = file_path.rstrip('/')
        sub_path = file_path.split('/')[-1]
        if sub_path == file_name:
            return self.success_response()
        try:
            res_data = MusicIDS(f"{file_path}/{file_name}").to_dict()
        except Exception as e:
            return self.failure_response(msg=str(e))
        return self.success_response(data=res_data)

    @action(methods=['POST'], detail=False)
    def update_id3(self, request, *args, **kwargs):
        """更新音乐id3信息"""
        validate_data = self.is_validated_data(request.data)
        music_id3_info = validate_data['music_id3_info']
        update_music_info(music_id3_info, False)
        for item in music_id3_info:
            folder_music_service.invalidate_cache(item.get('file_full_path', ''))
        return self.success_response()

    @action(methods=['POST'], detail=False)
    def batch_update_id3(self, request, *args, **kwargs):
        """批量更新音乐id3信息 (异步多线程并发版)"""
        validate_data = self.is_validated_data(request.data)
        full_path = os.path.normpath(validate_data['file_full_path'])
        select_data = validate_data['select_data']
        music_info = validate_data['music_info']
        apply_to_all = validate_data.get('apply_to_all', False) or len(select_data) == 0
        music_id3_info = []
        allow_type = ["flac", "mp3", "ape", "wav", "aiff", "wv", "tta", "m4a", "ogg", "mpc",
                      "opus", "wma", "dsf", "dff"]
        timestamp = str(int(time.time() * 1000))
        bulk_records = []

        if apply_to_all:
            try:
                entries = list(os.scandir(full_path))
            except Exception:
                entries = []
            for entry in entries:
                if entry.is_file():
                    each = entry.name
                    file_type = each.split(".")[-1].lower()
                    if file_type not in allow_type:
                        continue
                    item = copy.deepcopy(music_info)
                    item_path = os.path.normpath(entry.path)
                    item.update({
                        "file_full_path": item_path,
                        "filename": each
                    })
                    song_name = ".".join(each.split(".")[:-1])
                    record = TaskRecord(
                        batch=timestamp,
                        song_name=song_name,
                        full_path=item_path,
                        icon="icon-music",
                        state="wait"
                    )
                    bulk_records.append(record)
                    music_id3_info.append(item)
        else:
            for data in select_data:
                if data.get('icon') == 'icon-folder':
                    file_full_path = os.path.normpath(f"{full_path}/{data.get('name')}")
                    try:
                        entries = list(os.scandir(file_full_path))
                    except Exception:
                        continue
                    for index, entry in enumerate(entries, 1):
                        each = entry.name
                        file_type = each.split(".")[-1].lower()
                        if file_type not in allow_type:
                            continue
                        item = copy.deepcopy(music_info)
                        item_path = os.path.normpath(f"{file_full_path}/{each}")
                        item.update({
                            "file_full_path": item_path,
                            "filename": each
                        })
                        song_name = ".".join(each.split(".")[:-1])
                        record = TaskRecord(
                            batch=timestamp,
                            song_name=song_name,
                            full_path=item_path,
                            icon="icon-music",
                            state="wait"
                        )
                        bulk_records.append(record)
                        music_id3_info.append(item)
                else:
                    item_path = os.path.normpath(f"{full_path}/{data.get('name')}")
                    item = copy.deepcopy(music_info)
                    name = data.get('name', '')
                    item.update({
                        "file_full_path": item_path,
                        "filename": name
                    })
                    song_name = ".".join(name.split(".")[:-1])
                    record = TaskRecord(
                        batch=timestamp,
                        song_name=song_name,
                        full_path=item_path,
                        icon="icon-music",
                        state="wait"
                    )
                    bulk_records.append(record)
                    music_id3_info.append(item)

        if bulk_records:
            TaskRecord.objects.bulk_create(bulk_records, batch_size=500)
            created_records = TaskRecord.objects.filter(batch=timestamp).exclude(icon="icon-folder")
            record_map = {os.path.normpath(r.full_path): r.id for r in created_records}
            for m in music_id3_info:
                m["task_id"] = record_map.get(os.path.normpath(m["file_full_path"]))

        update_music_info_async(timestamp, music_id3_info, False)
        return self.success_response(data={"batch": timestamp, "total": len(music_id3_info)})

    @action(methods=['POST'], detail=False)
    def batch_auto_update_id3(self, request, *args, **kwargs):
        """批量自动刮削音乐id3信息 (异步多线程并发版)"""
        validate_data = self.is_validated_data(request.data)
        full_path = validate_data['file_full_path']
        select_data = validate_data['select_data']
        music_info = validate_data['music_info']
        select_mode = music_info["select_mode"]
        source_list = music_info.get("source_list", [])
        timestamp = str(int(time.time() * 1000))
        bulk_set = []
        for each in select_data:
            name = each.get("name")
            song_name = ".".join(name.split(".")[:-1])
            bulk_set.append(TaskRecord(**{
                "song_name": song_name,
                "full_path": f"{full_path}/{name}",
                "icon": each.get("icon"),
                "batch": timestamp
            }))
        TaskRecord.objects.bulk_create(bulk_set, batch_size=500)
        total = batch_auto_tag_task(timestamp, source_list, select_mode)
        return self.success_response(data={"batch": timestamp, "total": total})

    @action(methods=['GET'], detail=False)
    def batch_progress(self, request, *args, **kwargs):
        """查询批次任务执行进度"""
        batch = request.query_params.get("batch")
        if not batch:
            return self.failure_response(msg="缺少 batch 参数")

        from applications.task.services.async_executor import executor
        progress = executor.get_progress(batch)
        if not progress:
            total = TaskRecord.objects.filter(batch=batch).exclude(icon="icon-folder").count()
            finished = TaskRecord.objects.filter(batch=batch, state__in=["success", "failed"]).count()
            success = TaskRecord.objects.filter(batch=batch, state="success").count()
            failed = TaskRecord.objects.filter(batch=batch, state="failed").count()
            is_done = (finished >= total) if total > 0 else True
            progress = {
                "batch_id": batch,
                "total": total,
                "finished": finished,
                "success": success,
                "failed": failed,
                "is_done": is_done,
                "percentage": round((finished / total * 100), 1) if total > 0 else 100.0
            }

        include_records = request.query_params.get("include_records", "false").lower() == "true"
        if include_records:
            records = TaskRecord.objects.filter(batch=batch).values("id", "full_path", "song_name", "state", "extra")
            record_map = {}
            for r in records:
                fp = r["full_path"]
                fn = os.path.basename(fp)
                record_map[fn] = {
                    "id": r["id"],
                    "state": r["state"],
                    "extra": r["extra"],
                    "filename": fn,
                    "full_path": fp
                }
            progress["records"] = record_map

        return self.success_response(data=progress)

    @action(methods=['POST'], detail=False)
    def retry_failed(self, request, *args, **kwargs):
        """重试指定批次或全部失败的任务"""
        validate_data = self.is_validated_data(request.data)
        batch = validate_data.get("batch")
        source_list = validate_data.get("source_list") or ["netease", "qmusic", "migu", "kugou"]
        select_mode = validate_data.get("select_mode") or "hard"

        query = TaskRecord.objects.filter(state="failed").exclude(icon="icon-folder")
        if batch:
            query = query.filter(batch=batch)
        failed_tasks = list(query)
        if not failed_tasks:
            return self.success_response(msg="无失败项需要重试", data={"total": 0})

        new_batch = str(int(time.time() * 1000))
        for t in failed_tasks:
            t.batch = new_batch
            t.state = "wait"
            t.extra = ""
            t.save()

        from applications.task.services.async_executor import executor
        executor.submit_batch(new_batch, failed_tasks, process_single_auto_tag_task, source_list=source_list, select_mode=select_mode, task_type="auto_tag")
        return self.success_response(data={"batch": new_batch, "total": len(failed_tasks)})


    @action(methods=['POST'], detail=False)
    def fetch_lyric(self, request, *args, **kwargs):
        validate_data = self.is_validated_data(request.data)
        resource = validate_data["resource"]
        song_id = validate_data["song_id"]
        try:
            lyric = MusicResource(resource).fetch_lyric(song_id) or ""
        except Exception as e:
            lyric = f"未找到歌词 {e}"
        return self.success_response(data=lyric)

    @action(methods=['POST'], detail=False)
    def fetch_id3_by_title(self, request, *args, **kwargs):
        validate_data = self.is_validated_data(request.data)
        resource = validate_data["resource"]
        full_path = validate_data.get("full_path", "")
        title = validate_data["title"]

        if resource == "acoustid":
            title = full_path
        elif resource == "smart_tag":
            title = {"title": title, "full_path": full_path}
        songs = MusicResource(resource).fetch_id3_by_title(title)
        return self.success_response(data=songs)

    @action(methods=['POST'], detail=False)
    def translation_lyc(self, request, *args, **kwargs):
        validate_data = self.is_validated_data(request.data)
        lyc = validate_data["lyc"]
        clean_lyc_list = []
        raw_lyc_list = []
        for line in lyc.split("\n"):
            if not line:
                continue
            clean_line = line.split("]")[-1]
            clean_line = clean_line.strip()
            if not clean_line:
                continue
            raw_lyc_list.append(line)
            clean_lyc_list.append(clean_line)
        clean_lyc_str = "\n".join(clean_lyc_list)
        results = translation_lyc_text(clean_lyc_str)
        new_lyc = []
        results_list = results.split("\n")
        for index, result in enumerate(results_list):
            if not result:
                new_lyc.append(raw_lyc_list[index])
            else:
                try:
                    src = clean_lyc_list[index]
                    raw_src = raw_lyc_list[index]
                except Exception as e:
                    continue
                if src.replace(" ", "") == result.replace(" ", ""):
                    new_lyc.append(raw_src)
                else:
                    new_lyc.append(f"{raw_src}\n「{result}」\n")
        return self.success_response(data="\n".join(new_lyc))

    @action(methods=['POST'], detail=False)
    def tidy_folder(self, request, *args, **kwargs):
        validate_data = self.is_validated_data(request.data)
        root_path = validate_data["root_path"]
        first_dir = validate_data["first_dir"]
        full_path = validate_data["file_full_path"]
        select_data = validate_data["select_data"]
        second_dir = validate_data.get("second_dir", "")
        music_id3_info = []
        for data in select_data:
            if data.get('icon') == 'icon-folder':
                file_full_path = f"{full_path}/{data.get('name')}"
                data = os.scandir(file_full_path)
                for index, entry in enumerate(data, 1):
                    each = entry.name
                    file_type = each.split(".")[-1]
                    if file_type not in ALLOW_TYPE:
                        continue
                    music_id3_info.append(f"{file_full_path}/{each}")
            else:
                music_id3_info.append(f"{full_path}/{data.get('name')}")
        tidy_folder_task(music_id3_info, {"root_path": root_path, "first_dir": first_dir, "second_dir": second_dir})
        return self.success_response()

    @action(methods=['POST'], detail=False)
    def upload_image(self, request, *args, **kwargs):
        upload_file = request.FILES.get('upload_file')
        if not upload_file:
            return self.failure_response(msg="未接收到上传文件")

        content_type = getattr(upload_file, 'content_type', '') or ''
        if not content_type or not content_type.startswith('image/'):
            fn = getattr(upload_file, 'name', '').lower()
            if fn.endswith('.png'):
                content_type = 'image/png'
            elif fn.endswith('.webp'):
                content_type = 'image/webp'
            elif fn.endswith('.gif'):
                content_type = 'image/gif'
            else:
                content_type = 'image/jpeg'

        bs64_img = base64.b64encode(upload_file.read()).decode('utf-8')
        data_url = f"data:{content_type};base64,{bs64_img}"
        return self.success_response(data=data_url)

    @action(methods=["get"], detail=False)
    def clear_celery(self, request, *args, **kwargs):
        active_tasks = celery_app.control.inspect().active()
        try:
            active_tasks_data = list(active_tasks.values())[0]
        except Exception:
            return self.success_response()
        for task in active_tasks_data:
            celery_app.control.revoke(task["id"], terminate=True)
        celery_app.control.purge()
        return self.success_response()

    @action(methods=["get"], detail=False)
    def active_queue(self, request, *args, **kwargs):
        active_tasks = celery_app.control.inspect().active()
        try:
            active_tasks_data = list(active_tasks.values())[0]
        except Exception:
            return self.success_response()
        return self.success_response(data=active_tasks_data)

    @action(methods=['GET'], detail=False)
    def task1(self, request, *args, **kwargs):
        scan.delay()
        return self.success_response()

    @action(methods=['GET'], detail=False)
    def task2(self, request, *args, **kwargs):
        clear_music()
        return self.success_response()

    @action(methods=['GET'], detail=False)
    def full_scan_folder(self, request, *args, **kwargs):
        full_scan_folder.delay()
        return self.success_response()


class TaskModelViewSets(mixins.ListModelMixin,
                        GenericViewSet):
    queryset = Task.objects.order_by("-id")
    serializer_class = TaskSerializer
    filterset_class = TaskFilters
