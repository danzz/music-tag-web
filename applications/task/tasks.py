import os
import shutil
from collections import defaultdict

from applications.task.constants import ALLOW_TYPE
from applications.task.models import TaskRecord, Task
from applications.task.services.music_ids import MusicIDS
from applications.task.utils import match_song
from applications.utils.db_safety import db_write_safe


@db_write_safe
def update_task_state_safe(task_id, full_path, state, song_name, artist_name, extra=""):
    TaskRecord.objects.filter(id=task_id).update(state=state, extra=extra)
    parent_path = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    Task.objects.update_or_create(full_path=full_path, defaults={
        "state": state,
        "parent_path": parent_path,
        "filename": filename,
        "song_name": song_name,
        "artist_name": artist_name,
        "extra": extra,
    })


def process_single_auto_tag_task(task, source_list, select_mode):
    """
    单首歌曲自动刮削任务单元 (多线程并发执行)
    """
    is_match = False
    error_msg = ""
    for resource in source_list:
        try:
            is_match = match_song(resource, task.full_path, select_mode)
        except Exception as e:
            error_msg = f"{resource} 异常: {str(e)}"
            is_match = False
        if is_match:
            break

    if is_match:
        update_task_state_safe(task.id, task.full_path, "success", task.song_name, task.artist_name, extra="")
        return True
    else:
        fail_reason = error_msg if error_msg else "未匹配到合适的元数据"
        update_task_state_safe(task.id, task.full_path, "failed", task.song_name, task.artist_name, extra=fail_reason)
        return False


def batch_auto_tag_task(batch, source_list, select_mode):
    """
    自动刮削任务（多线程并发版）
    source_list: ["migu", "qmusic", "netease"]
    """
    folder_list = TaskRecord.objects.filter(batch=batch, icon="icon-folder").all()
    for folder in folder_list:
        try:
            data = os.scandir(folder.full_path)
            bulk_set = []
            for entry in data:
                each = entry.name
                file_type = each.split(".")[-1]
                file_name = ".".join(each.split(".")[:-1])
                if file_type not in ALLOW_TYPE:
                    continue
                bulk_set.append(TaskRecord(**{
                    "batch": batch,
                    "song_name": file_name,
                    "full_path": f"{folder.full_path}/{each}",
                    "icon": "icon-music",
                }))
            if bulk_set:
                TaskRecord.objects.bulk_create(bulk_set)
        except Exception as e:
            print(f"Error scanning folder {folder.full_path}: {e}")

    task_list = list(TaskRecord.objects.filter(batch=batch).exclude(icon="icon-folder").all())
    from applications.task.services.async_executor import executor
    executor.submit_batch(batch, task_list, process_single_auto_tag_task, source_list=source_list, select_mode=select_mode, task_type="auto_tag")
    return len(task_list)


def tidy_folder_task(music_path_list, tidy_config):
    """整理文件夹任务"""
    root_path = tidy_config.get("root_path")
    first_dir = tidy_config.get("first_dir")
    second_dir = tidy_config.get("second_dir")

    if second_dir:
        tidy_map = defaultdict(lambda: defaultdict(list))
        for music_path in music_path_list:
            file = MusicIDS(music_path)
            first_value = getattr(file, first_dir, "未知")
            second_value = getattr(file, second_dir, "未知")
            tidy_map[first_value][second_value].append(music_path)
        for first_value, second_map in tidy_map.items():
            first_path = os.path.join(root_path, first_value)
            if not os.path.exists(first_path):
                os.makedirs(first_path)
            for second_value, music_path_list in second_map.items():
                second_path = os.path.join(first_path, second_value)
                if not os.path.exists(second_path):
                    os.makedirs(second_path)
                for music_path in music_path_list:
                    shutil.move(music_path, second_path)
    else:
        tidy_map = defaultdict(list)
        for music_path in music_path_list:
            file = MusicIDS(music_path)
            first_value = getattr(file, first_dir, "未知")
            tidy_map[first_value].append(music_path)
        for first_value, music_path_list in tidy_map.items():
            first_path = os.path.join(root_path, first_value)
            if not os.path.exists(first_path):
                os.makedirs(first_path)
            for music_path in music_path_list:
                shutil.move(music_path, first_path)
