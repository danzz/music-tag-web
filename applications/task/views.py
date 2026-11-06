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
from applications.task.filters import TaskFilters, TaskRecordFilters
from applications.task.models import TaskRecord, Task
from applications.task.serialziers import FileListSerializer, Id3Serializer, UpdateId3Serializer, \
    FetchId3ByTitleSerializer, FetchLlyricSerializer, BatchUpdateId3Serializer, TranslationLycSerializer, \
    TidyFolderSerializer, TaskSerializer, TaskRecordSerializer, UploadImageSerializer, RetryFailedSerializer, FolderMusicListSerializer, AgentPlanSerializer, AgentTestConnectionSerializer, GenerateCourseCoverSerializer, ApplyCourseCoverSerializer, TestComfyuiConnectionSerializer
from applications.task.services.music_ids import MusicIDS
from applications.task.services.music_resource import MusicResource
from applications.task.services.update_ids import update_music_info, update_music_info_async
from applications.task.services import folder_music_service
from applications.task.tasks import batch_auto_tag_task, tidy_folder_task, process_single_auto_tag_task
from applications.utils.translation import translation_lyc_text
from component.drf.viewsets import GenericViewSet


from django.views.decorators.csrf import csrf_exempt
from django.http import StreamingHttpResponse
from rest_framework.renderers import BaseRenderer

class ServerSentEventRenderer(BaseRenderer):
    media_type = 'text/event-stream'
    format = 'txt'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


@csrf_exempt
def events_view(request):
    """
    SSE (Server-Sent Events) 原生 Django 实时数据流推送
    绕过 DRF Content Negotiation，完全兼容任何浏览器 EventSource Accept 头
    """
    last_event_id = request.META.get('HTTP_LAST_EVENT_ID', 0)
    from applications.task.services.task_store import task_store
    response = StreamingHttpResponse(
        task_store.subscribe_events(last_event_id=last_event_id),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


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
        elif self.action == "agent_plan":
            return AgentPlanSerializer
        elif self.action == "agent_test_connection":
            return AgentTestConnectionSerializer
        elif self.action == "generate_course_cover":
            return GenerateCourseCoverSerializer
        elif self.action == "apply_course_cover":
            return ApplyCourseCoverSerializer
        elif self.action == "test_comfyui_connection":
            return TestComfyuiConnectionSerializer
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
                        node_info = {
                            "id": dir_index,
                            "name": dir_name,
                            "title": dir_name,
                            "path": os.path.normpath(entry.path.encode('utf-8', 'replace').decode()),
                            "icon": "icon-folder",
                            "is_dir": True,
                            "async": True,
                        }
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
        from applications.task.services.task_store import task_store
        active_states = task_store.get_active_path_states(file_path)
        task_map = {fn: info.get("state", "null") for fn, info in active_states.items()}
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
        from applications.task.services.task_store import task_store
        filenames = [item["filename"] for item in res_data.get("items", [])]
        task_map = task_store.get_active_path_states(file_path, filenames)
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
        # 带有文件修改时间戳版本号，允许浏览器长效缓存，极大减轻 NAS 机械硬盘并发请求压力
        response['Cache-Control'] = 'public, max-age=604800'
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
        from applications.task.services.task_store import task_store
        paths = [item.get('file_full_path') for item in music_id3_info if item.get('file_full_path')]
        has_active, count, samples = task_store.check_active_tasks(paths)
        if has_active:
            sample_str = "、".join(samples)
            return self.failure_response(msg=f"该歌曲（{sample_str}）当前正在后台处理中，请等待处理完成后再保存！")
        update_music_info(music_id3_info, False)
        for item in music_id3_info:
            folder_music_service.invalidate_cache(item.get('file_full_path', ''))
        return self.success_response()

    @action(methods=['POST'], detail=False)
    def batch_update_id3(self, request, *args, **kwargs):
        """批量更新音乐id3信息 (异步多线程并发版 - 基于内存/Redis临时任务中心)"""
        validate_data = self.is_validated_data(request.data)
        full_path = os.path.normpath(validate_data['file_full_path'])
        select_data = validate_data['select_data']
        music_info = validate_data['music_info']
        apply_to_all = validate_data.get('apply_to_all', False) or len(select_data) == 0
        music_id3_info = []
        allow_type = ["flac", "mp3", "ape", "wav", "aiff", "wv", "tta", "m4a", "ogg", "mpc",
                      "opus", "wma", "dsf", "dff"]
        timestamp = str(int(time.time() * 1000))

        if apply_to_all:
            try:
                entries = list(os.scandir(full_path))
                entries.sort(key=lambda e: e.name)
            except Exception:
                entries = []
            for idx, entry in enumerate(entries, 1):
                if entry.is_file():
                    each = entry.name
                    file_type = each.split(".")[-1].lower()
                    if file_type not in allow_type:
                        continue
                    item = dict(music_info)
                    item_path = os.path.normpath(entry.path)
                    item.update({
                        "file_full_path": item_path,
                        "filename": each,
                        "song_name": ".".join(each.split(".")[:-1]),
                        "sequence_index": idx
                    })
                    music_id3_info.append(item)
        else:
            for idx, data in enumerate(select_data, 1):
                if data.get('icon') == 'icon-folder':
                    file_full_path = os.path.normpath(f"{full_path}/{data.get('name')}")
                    try:
                        entries = list(os.scandir(file_full_path))
                        entries.sort(key=lambda e: e.name)
                    except Exception:
                        continue
                    for sub_idx, entry in enumerate(entries, 1):
                        each = entry.name
                        file_type = each.split(".")[-1].lower()
                        if file_type not in allow_type:
                            continue
                        item = dict(music_info)
                        item_path = os.path.normpath(f"{file_full_path}/{each}")
                        item.update({
                            "file_full_path": item_path,
                            "filename": each,
                            "song_name": ".".join(each.split(".")[:-1]),
                            "sequence_index": sub_idx
                        })
                        music_id3_info.append(item)
                else:
                    name = data.get('name') or data.get('filename', '')
                    item_path = os.path.normpath(f"{full_path}/{name}")
                    item = dict(music_info)
                    item.update({
                        "file_full_path": item_path,
                        "filename": name,
                        "song_name": ".".join(name.split(".")[:-1]),
                        "sequence_index": data.get("sequence_index", idx)
                    })
                    all_tag_keys = [
                        "tracknumber", "discnumber", "title", "artist", "album", "albumartist",
                        "year", "genre", "comment", "lyrics", "album_img", "clear_cover",
                        "is_save_lyrics_file", "is_save_album_cover", "language", "album_type"
                    ]
                    for k in all_tag_keys:
                        if k in data and data[k] is not None:
                            item[k] = data[k]
                    music_id3_info.append(item)

        target_paths = [item["file_full_path"] for item in music_id3_info]
        from applications.task.services.task_store import task_store
        has_active, count, samples = task_store.check_active_tasks(target_paths)
        if has_active:
            sample_str = "、".join(samples)
            if count > len(samples):
                sample_str += f" 等共 {count} 首"
            return self.failure_response(msg=f"检测到所选范围内有歌曲（{sample_str}）正在处理或排队中，请等待当前任务全部执行完毕后再提交！")

        task_store.init_batch(timestamp, music_id3_info, task_type="manual_update")
        update_music_info_async(timestamp, music_id3_info, False)
        return self.success_response(data={"batch": timestamp, "total": len(music_id3_info)})

    @action(methods=['POST'], detail=False)
    def batch_auto_update_id3(self, request, *args, **kwargs):
        """批量自动刮削音乐id3信息 (异步多线程并发版 - 基于内存/Redis临时任务中心)"""
        validate_data = self.is_validated_data(request.data)
        full_path = os.path.normpath(validate_data['file_full_path'])
        select_data = validate_data['select_data']
        music_info = validate_data['music_info']
        select_mode = music_info["select_mode"]
        source_list = music_info.get("source_list", [])
        timestamp = str(int(time.time() * 1000))
        allow_type = ["flac", "mp3", "ape", "wav", "aiff", "wv", "tta", "m4a", "ogg", "mpc",
                      "opus", "wma", "dsf", "dff"]

        task_items = []
        for each in select_data:
            name = each.get("name")
            if each.get("icon") == "icon-folder":
                folder_path = os.path.normpath(f"{full_path}/{name}")
                try:
                    entries = list(os.scandir(folder_path))
                except Exception:
                    continue
                for entry in entries:
                    if entry.is_file():
                        fname = entry.name
                        ftype = fname.split(".")[-1].lower()
                        if ftype in allow_type:
                            sname = ".".join(fname.split(".")[:-1])
                            task_items.append({
                                "file_full_path": os.path.normpath(entry.path),
                                "filename": fname,
                                "song_name": sname,
                                "artist": ""
                            })
            else:
                sname = ".".join(name.split(".")[:-1])
                task_items.append({
                    "file_full_path": os.path.normpath(f"{full_path}/{name}"),
                    "filename": name,
                    "song_name": sname,
                    "artist": ""
                })

        target_paths = [item["file_full_path"] for item in task_items]
        from applications.task.services.task_store import task_store
        has_active, count, samples = task_store.check_active_tasks(target_paths)
        if has_active:
            sample_str = "、".join(samples)
            if count > len(samples):
                sample_str += f" 等共 {count} 首"
            return self.failure_response(msg=f"检测到所选范围内有歌曲（{sample_str}）正在处理或排队中，请等待当前任务全部执行完毕后再提交！")

        task_store.init_batch(timestamp, task_items, task_type="auto_tag")
        total = batch_auto_tag_task(timestamp, task_items, source_list, select_mode)
        return self.success_response(data={"batch": timestamp, "total": total})

    @action(methods=['GET'], detail=False)
    def batch_progress(self, request, *args, **kwargs):
        """查询批次任务执行进度"""
        batch = request.query_params.get("batch")
        if not batch:
            return self.failure_response(msg="缺少 batch 参数")

        include_records = request.query_params.get("include_records", "false").lower() in ("true", "1")
        from applications.task.services.task_store import task_store
        progress = task_store.get_batch_progress(batch, include_records=include_records)
        if not progress:
            from applications.task.services.async_executor import executor
            progress = executor.get_progress(batch)
        if not progress:
            progress = {
                "batch_id": batch,
                "total": 0,
                "finished": 0,
                "success": 0,
                "failed": 0,
                "is_done": True,
                "percentage": 100.0
            }
        return self.success_response(data=progress)

    @action(methods=['POST'], detail=False)
    def retry_failed(self, request, *args, **kwargs):
        """重试指定批次或全部失败的任务"""
        validate_data = self.is_validated_data(request.data)
        batch = validate_data.get("batch")
        source_list = validate_data.get("source_list") or ["netease", "qmusic", "migu", "kugou"]
        select_mode = validate_data.get("select_mode") or "hard"

        from applications.task.services.task_store import task_store
        failed_res = task_store.get_task_records(page=1, page_size=1000, state="failed", batch=batch or "")
        failed_tasks = failed_res.get("items", [])
        if not failed_tasks:
            return self.success_response(msg="无失败项需要重试", data={"total": 0})

        new_batch = str(int(time.time() * 1000))
        task_store.init_batch(new_batch, failed_tasks, task_type="auto_tag")
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
        root_path = os.path.normpath(validate_data["root_path"])
        first_dir = validate_data["first_dir"]
        second_dir = validate_data.get("second_dir", "") or ""
        full_path = os.path.normpath(validate_data["file_full_path"])
        select_data = validate_data.get("select_data", [])
        apply_to_all = validate_data.get("apply_to_all", False)
        move_lrc = validate_data.get("move_lrc", True)
        conflict_action = validate_data.get("conflict_action", "skip")
        clean_empty_dir = validate_data.get("clean_empty_dir", False)

        allow_type = ["flac", "mp3", "ape", "wav", "aiff", "wv", "tta", "m4a", "ogg", "mpc",
                      "opus", "wma", "dsf", "dff"]
        task_items = []

        if apply_to_all:
            try:
                entries = list(os.scandir(full_path))
                entries.sort(key=lambda e: e.name)
            except Exception:
                entries = []
            for idx, entry in enumerate(entries, 1):
                if entry.is_file():
                    each = entry.name
                    file_type = each.split(".")[-1].lower()
                    if file_type not in allow_type:
                        continue
                    item_path = os.path.normpath(entry.path)
                    sname = ".".join(each.split(".")[:-1])
                    task_items.append({
                        "file_full_path": item_path,
                        "filename": each,
                        "song_name": sname,
                        "artist": "",
                        "sequence_index": idx
                    })
        else:
            for idx, data in enumerate(select_data, 1):
                name = data.get("filename") or data.get("name")
                if not name:
                    continue
                if data.get("icon") == "icon-folder":
                    folder_path = os.path.normpath(f"{full_path}/{name}")
                    try:
                        entries = list(os.scandir(folder_path))
                        entries.sort(key=lambda e: e.name)
                    except Exception:
                        continue
                    for sub_idx, sub_entry in enumerate(entries, 1):
                        if sub_entry.is_file():
                            each = sub_entry.name
                            file_type = each.split(".")[-1].lower()
                            if file_type not in allow_type:
                                continue
                            item_path = os.path.normpath(sub_entry.path)
                            sname = ".".join(each.split(".")[:-1])
                            task_items.append({
                                "file_full_path": item_path,
                                "filename": each,
                                "song_name": sname,
                                "artist": "",
                                "sequence_index": sub_idx
                            })
                else:
                    item_path = os.path.normpath(data.get("path") or f"{full_path}/{name}")
                    sname = ".".join(name.split(".")[:-1])
                    task_items.append({
                        "file_full_path": item_path,
                        "filename": name,
                        "song_name": sname,
                        "artist": data.get("artist", ""),
                        "sequence_index": idx
                    })

        if not task_items:
            return self.failure_response(msg="未找到需要整理的有效音频文件")

        target_paths = [item["file_full_path"] for item in task_items]
        from applications.task.services.task_store import task_store
        has_active, count, samples = task_store.check_active_tasks(target_paths)
        if has_active:
            sample_str = "、".join(samples)
            if count > len(samples):
                sample_str += f" 等共 {count} 首"
            return self.failure_response(msg=f"检测到所选范围内有歌曲（{sample_str}）正在处理或排队中，请等待当前任务全部执行完毕后再提交！")

        timestamp = str(int(time.time() * 1000))
        task_store.init_batch(timestamp, task_items, task_type="tidy_folder")
        tidy_config = {
            "root_path": root_path,
            "first_dir": first_dir,
            "second_dir": second_dir,
            "move_lrc": move_lrc,
            "conflict_action": conflict_action,
            "clean_empty_dir": clean_empty_dir
        }
        total = tidy_folder_task(timestamp, task_items, tidy_config)
        return self.success_response(data={"batch": timestamp, "total": total})

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
        return self.success_response()

    @action(methods=["get"], detail=False)
    def active_queue(self, request, *args, **kwargs):
        return self.success_response(data=[])

    @action(methods=['POST'], detail=False)
    def force_refresh_cache(self, request, *args, **kwargs):
        """强制清除元数据与封面缓存（内存、SQLite及跨多Worker广播同步）"""
        file_path = request.data.get('file_path', '')
        folder_music_service.force_clear_all_caches(file_path)
        return self.success_response(msg="缓存已强制清空")

    @action(methods=['POST'], detail=False)
    def agent_plan(self, request, *args, **kwargs):
        """Web 内置轻量 Agent 智能规划接口"""
        validate_data = self.is_validated_data(request.data)
        dir_path = os.path.normpath(validate_data['dir_path'])
        mode = validate_data.get('mode', 'auto')
        files = validate_data.get('files', [])
        system_prompt = validate_data.get('system_prompt', '').strip()
        user_prompt = validate_data.get('user_prompt', '').strip()
        ai_config = validate_data.get('ai_config', {}) or {}

        # 1. 本地规则引擎生成基础方案
        from scripts.music_tag_cli import MusicTagClient
        client = MusicTagClient(base_url="http://127.0.0.1:8001")
        plan_res = client.auto_plan(dir_path, plan_type=mode)

        # 如果指定了特定文件，做过滤
        if files:
            file_set = set(files)
            plan_res["plan"] = [p for p in plan_res.get("plan", []) if p.get("name") in file_set]
            plan_res["summary"]["needs_curation"] = len(plan_res["plan"])

        # 2. 如果配置了云端/本地大模型，调用大模型对方案进行语义精炼
        api_key = (ai_config.get('api_key') or ai_config.get('apiKey') or '').strip()
        base_url = (ai_config.get('base_url') or ai_config.get('baseUrl') or '').strip().rstrip('/') or 'https://api.openai.com/v1'
        model = (ai_config.get('model') or '').strip()

        if model and plan_res.get("plan"):
            try:
                import urllib.request
                import json
                import re

                llm_endpoint = f"{base_url}/chat/completions"
                sys_content = system_prompt or "你是一位专业的数字音频馆藏专家，负责对音频文件的标签、音轨号、专辑与作者信息进行消歧与清洗。"

                items_for_llm = []
                for p in plan_res["plan"]:
                    prop = p.get("proposed") or {}
                    items_for_llm.append({
                        "filename": p.get("name"),
                        "current_title": p.get("current", {}).get("title"),
                        "current_artist": p.get("current", {}).get("artist"),
                        "current_album": p.get("current", {}).get("album"),
                        "proposed_title": prop.get("title"),
                        "proposed_artist": prop.get("artist"),
                        "proposed_album": prop.get("album"),
                        "proposed_track": prop.get("tracknumber"),
                    })

                user_content = {
                    "dir_name": os.path.basename(dir_path),
                    "detected_mode": plan_res.get("mode", "music"),
                    "user_instruction": user_prompt or "请审查并润色上述方案，剔除残余广告，确保标题纯正优雅，输出修改后的建议。",
                    "items": items_for_llm
                }

                req_payload = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": sys_content + "\n请严格以 JSON 格式输出，返回一个数组，包含对象的键：filename, title, artist, album, tracknumber, reason。不要输出任何 Markdown 格式或额外解释文本。"},
                        {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)}
                    ],
                    "temperature": float(ai_config.get("temperature", 0.3)),
                }

                req_headers = {"Content-Type": "application/json"}
                if api_key:
                    req_headers["Authorization"] = f"Bearer {api_key}"

                req = urllib.request.Request(
                    llm_endpoint,
                    data=json.dumps(req_payload).encode('utf-8'),
                    headers=req_headers,
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=25) as resp:
                    resp_json = json.loads(resp.read().decode('utf-8'))
                    llm_text = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if "```" in llm_text:
                        match = re.search(r'```(?:json)?\s*(.*?)\s*```', llm_text, re.DOTALL)
                        if match:
                            llm_text = match.group(1).strip()

                    llm_items = json.loads(llm_text)
                    if isinstance(llm_items, list):
                        llm_map = {item.get("filename"): item for item in llm_items if item.get("filename")}
                        for p in plan_res["plan"]:
                            fn = p.get("name")
                            if fn in llm_map and p.get("proposed"):
                                refined = llm_map[fn]
                                if refined.get("title"):
                                    p["proposed"]["title"] = refined["title"]
                                if refined.get("artist"):
                                    p["proposed"]["artist"] = refined["artist"]
                                    p["proposed"]["albumartist"] = refined["artist"]
                                if refined.get("album"):
                                    p["proposed"]["album"] = refined["album"]
                                if refined.get("tracknumber"):
                                    p["proposed"]["tracknumber"] = str(refined["tracknumber"])
                                if refined.get("reason"):
                                    p["reason"] = f"[LLM 润色] {refined['reason']}"
                        plan_res["llm_status"] = "success"
            except Exception as e:
                plan_res["llm_status"] = f"warning: 大模型调用异常 ({str(e)})，已自动使用内置规则引擎方案"
        else:
            plan_res["llm_status"] = "local_rules"

        return self.success_response(data=plan_res)

    @action(methods=['POST'], detail=False)
    def agent_test_connection(self, request, *args, **kwargs):
        """测试 AI 大模型接口连通性与可用性"""
        validate_data = self.is_validated_data(request.data)
        base_url = (validate_data.get('base_url') or validate_data.get('baseUrl') or '').strip().rstrip('/')
        api_key = (validate_data.get('api_key') or validate_data.get('apiKey') or '').strip()
        model = (validate_data.get('model') or '').strip()

        if not base_url:
            base_url = 'https://api.openai.com/v1'

        if not model:
            return self.failure_response(msg="请填写模型名称 (Model Name)，例如：qwen3.8:27b-mlx、gpt-4o-mini 等")

        endpoint = f"{base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        test_payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Hello, respond with: OK"}
            ],
            "max_tokens": 15,
            "temperature": 0.1
        }

        import time
        import urllib.request
        import urllib.error
        import json

        t0 = time.time()
        try:
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(test_payload).encode('utf-8'),
                headers=headers,
                method="POST"
            )
            # 10 秒超时
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.getcode()
                raw_body = resp.read().decode('utf-8', errors='ignore')
                latency_ms = int((time.time() - t0) * 1000)

                resp_json = json.loads(raw_body)
                choices = resp_json.get("choices", [])
                reply = ""
                if choices and isinstance(choices, list):
                    reply = choices[0].get("message", {}).get("content", "").strip()

                return self.success_response(
                    msg=f"测试成功！连接正常，模型响应耗时 {latency_ms} ms",
                    data={
                        "latency_ms": latency_ms,
                        "model": model,
                        "status_code": status_code,
                        "reply": reply or "OK"
                    }
                )
        except urllib.error.HTTPError as e:
            latency_ms = int((time.time() - t0) * 1000)
            err_body = ""
            try:
                err_body = e.read().decode('utf-8', errors='ignore')
            except Exception:
                pass

            msg = f"HTTP 错误 {e.code}"
            if e.code == 401:
                msg = "认证失败 (401 Unauthorized)：API Key 无效或未提供正确凭证"
            elif e.code == 404:
                msg = f"未找到端点或模型 (404 Not Found)：请检查 Base URL 是否需包含 /v1，或模型「{model}」在服务端是否存在"
            elif e.code == 403:
                msg = "访问被拒绝 (403 Forbidden)：无权访问该接口或模型"
            elif e.code == 429:
                msg = "请求过多或配额不足 (429 Rate Limit / Quota Exceeded)"
            elif e.code >= 500:
                msg = f"服务端错误 ({e.code})：{err_body[:180] if err_body else '模型服务内部故障'}"
            else:
                if err_body:
                    msg += f"：{err_body[:150]}"

            return self.failure_response(msg=msg)
        except urllib.error.URLError as e:
            reason_str = str(e.reason)
            if "Connection refused" in reason_str or "111" in reason_str or "61" in reason_str:
                msg = f"连接被拒绝 (Connection Refused)：无法连接到 {base_url}。请确认服务已启动并监听外部网络；若在 Docker 中访问宿主机服务，可尝试将地址设为 http://host.docker.internal:端口"
            elif "timed out" in reason_str.lower() or "timeout" in reason_str.lower():
                msg = f"连接超时 (Timeout)：请求 {base_url} 超过 10 秒无响应，请检查 IP、端口及防火墙设置"
            elif "Name or service not known" in reason_str or "nodename nor servname provided" in reason_str:
                msg = f"无法解析地址 (DNS Error)：无法识别主机名或域名，请检查 Base URL 是否正确"
            else:
                msg = f"网络连接失败：{reason_str}"
            return self.failure_response(msg=msg)
        except Exception as e:
            return self.failure_response(msg=f"测试失败：{str(e)}")

    @action(methods=['POST'], detail=False)
    def test_comfyui_connection(self, request, *args, **kwargs):
        """测试 ComfyUI 服务连通性、设备与显存状态"""
        validate_data = self.is_validated_data(request.data)
        url = (validate_data.get('comfyui_url') or 'http://host.docker.internal:8188').strip().rstrip('/')

        import time
        import urllib.request
        import urllib.error
        import json

        endpoint = f"{url}/system_stats"
        t0 = time.time()
        try:
            req = urllib.request.Request(endpoint, headers={"User-Agent": "MusicTagWeb"}, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw_body = resp.read().decode('utf-8', errors='ignore')
                latency_ms = int((time.time() - t0) * 1000)
                stats = json.loads(raw_body)

                system_info = stats.get('system', {})
                devices = stats.get('devices', [])
                dev_str = ""
                if devices:
                    d = devices[0]
                    name = d.get('name', 'GPU')
                    vram_free = round(d.get('vram_free', 0) / (1024**3), 2)
                    vram_total = round(d.get('vram_total', 0) / (1024**3), 2)
                    dev_str = f"{name} (可用显存: {vram_free}G / 总显存: {vram_total}G)"
                else:
                    dev_str = system_info.get('os', '运行正常')

                return self.success_response(
                    msg=f"连接成功！ComfyUI 响应耗时 {latency_ms} ms。设备：{dev_str}",
                    data={
                        "latency_ms": latency_ms,
                        "device": dev_str,
                        "system": system_info
                    }
                )
        except urllib.error.HTTPError as e:
            return self.failure_response(msg=f"服务响应 HTTP {e.code}：{e.reason}")
        except urllib.error.URLError as e:
            reason_str = str(e.reason)
            if "Connection refused" in reason_str or "111" in reason_str or "61" in reason_str:
                msg = f"连接被拒绝 (Connection Refused)：服务未在该端口运行，或未配置允许外部访问。"
            elif "timed out" in reason_str.lower() or "timeout" in reason_str.lower():
                msg = f"连接超时 (Timeout)：无法连接到 {url}。若服务在 Windows 上运行，请检查 ComfyUI 是否添加了 --listen 0.0.0.0 参数，以及 Windows 防火墙是否放行了 8188 端口。"
            else:
                msg = f"网络连接失败：{reason_str}"
            return self.failure_response(msg=msg)
        except Exception as e:
            return self.failure_response(msg=f"测试失败：{str(e)}")

    @action(methods=['POST'], detail=False)
    def generate_course_cover(self, request, *args, **kwargs):
        """生成得到/音频课程专属封面预览"""
        validate_data = self.is_validated_data(request.data)
        folder_path = os.path.normpath(validate_data['folder_path'])
        title = validate_data['title'].strip()
        author = validate_data.get('author', '').strip()
        category = validate_data.get('category', '得到课程').strip()
        prompt = validate_data.get('prompt', '').strip()
        engine = validate_data.get('engine', 'comfyui')
        comfyui_url = validate_data.get('comfyui_url', 'http://host.docker.internal:8188').strip()
        style = validate_data.get('style', 'amber_dark')
        quality = validate_data.get('quality', 'fast')
        layout = validate_data.get('layout', 'dedao_clean')
        font_size = validate_data.get('font_size', 'auto')

        from applications.task.services.cover_generator import CourseCoverGenerator
        start_time = time.time()
        try:
            res = CourseCoverGenerator.generate_cover(
                title=title,
                author=author,
                category=category,
                prompt=prompt,
                engine=engine,
                comfyui_url=comfyui_url,
                style=style,
                quality=quality,
                layout=layout,
                font_size=font_size
            )
            cost_sec = round(time.time() - start_time, 2)
            return self.success_response(data={
                "image_base64": res["image_base64"],
                "source": res["source"],
                "cost_sec": cost_sec,
                "title": title,
                "author": author,
                "category": category
            })
        except Exception as e:
            return self.failure_response(msg=f"封面生成失败: {str(e)}")

    @action(methods=['POST'], detail=False)
    def apply_course_cover(self, request, *args, **kwargs):
        """保存封面到目录并内嵌音频标签"""
        validate_data = self.is_validated_data(request.data)
        folder_path = os.path.normpath(validate_data['folder_path'])
        image_base64 = validate_data['image_base64']
        embed_to_files = validate_data.get('embed_to_files', True)

        if not os.path.isdir(folder_path):
            return self.failure_response(msg="指定的课程目录不存在")

        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]
        image_bytes = base64.b64decode(image_base64)

        from applications.task.services.cover_generator import CourseCoverGenerator
        try:
            res = CourseCoverGenerator.save_and_embed_cover(
                folder_path=folder_path,
                image_bytes=image_bytes,
                embed_to_files=embed_to_files
            )
            return self.success_response(data=res, msg=f"封面已成功保存为 cover.jpg，并已内嵌写入 {res['embedded_files']} 首音频")
        except Exception as e:
            return self.failure_response(msg=f"保存或内嵌封面失败: {str(e)}")

    @action(methods=['GET'], detail=False, permission_classes=[AllowAny], authentication_classes=[], renderer_classes=[ServerSentEventRenderer])
    def events(self, request, *args, **kwargs):
        """
        SSE (Server-Sent Events) 实时数据流推送
        """
        return events_view(request)


class TaskModelViewSets(GenericViewSet):
    """任务执行记录与状态视图集（基于内存/Redis的临时过程数据中心）"""

    def list(self, request, *args, **kwargs):
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        state = request.query_params.get("state", "")
        batch = request.query_params.get("batch", "")
        search = request.query_params.get("search", "")

        from applications.task.services.task_store import task_store
        res_data = task_store.get_task_records(page=page, page_size=page_size, state=state, batch=batch, search=search)
        return self.success_response(data=res_data)

    @action(methods=['GET'], detail=False)
    def stats(self, request, *args, **kwargs):
        """获取当前任务统计数量与最近批次列表"""
        from applications.task.services.task_store import task_store
        data = task_store.get_stats()
        return self.success_response(data=data)

    @action(methods=['POST'], detail=False)
    def clear(self, request, *args, **kwargs):
        """清空任务记录（可按批次或状态清空）"""
        batch = request.data.get("batch")
        state = request.data.get("state")
        from applications.task.services.task_store import task_store
        task_store.clear_tasks(batch, state)
        return self.success_response(msg="临时任务记录已成功清理")

    @action(methods=['POST'], detail=False)
    def retry_single(self, request, *args, **kwargs):
        """重试单条失败任务"""
        record_id = request.data.get("id")
        if not record_id:
            return self.failure_response(msg="缺少任务ID")
        from applications.task.services.task_store import task_store
        record_data = task_store.retry_single(record_id)
        if not record_data:
            return self.failure_response(msg="任务不存在或已过期")

        from applications.task.services.async_executor import executor
        from applications.task.tasks import process_single_auto_tag_task
        source_list = ["netease", "qmusic", "migu", "kugou"]
        executor.executor.submit(process_single_auto_tag_task, record_data, source_list=source_list, select_mode="hard")
        return self.success_response(msg="已重新提交任务")

    @action(methods=['POST'], detail=False)
    def resume_pending(self, request, *args, **kwargs):
        """恢复执行被中断或仍在排队中的未完成任务"""
        batch = request.data.get("batch", "")
        from applications.task.services.task_store import task_store
        pending = task_store.get_pending_tasks(batch=batch, limit=2000)
        if not pending:
            return self.success_response(msg="暂无排队中的任务", data={"total": 0})

        from applications.task.services.async_executor import executor
        from applications.task.services.update_ids import process_single_manual_save
        from applications.task.tasks import process_single_auto_tag_task

        count = 0
        manual_items = []
        auto_items = []
        for p in pending:
            item_data = {
                "task_id": p["id"],
                "file_full_path": p["full_path"],
                "filename": os.path.basename(p["full_path"]),
                "song_name": p["song_name"],
                "artist": p["artist_name"]
            }
            if p.get("tag_source") == "auto_tag":
                auto_items.append(item_data)
            else:
                manual_items.append(item_data)

        first_batch = pending[0].get("batch_id") or str(int(time.time() * 1000))
        if manual_items:
            executor.submit_batch(first_batch, manual_items, process_single_manual_save, task_type="manual_update")
            count += len(manual_items)

        if auto_items:
            executor.submit_batch(first_batch, auto_items, process_single_auto_tag_task, source_list=["netease", "qmusic", "migu", "kugou"], select_mode="hard", task_type="auto_tag")
            count += len(auto_items)

        return self.success_response(msg=f"已成功继续执行 {count} 个未完成任务", data={"total": count, "batch": first_batch})
