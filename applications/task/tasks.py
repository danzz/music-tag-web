import os
import shutil
from collections import defaultdict

from applications.task.constants import ALLOW_TYPE
from applications.task.services.music_ids import MusicIDS
from applications.task.utils import match_song


def update_task_state_safe(task_id, full_path, state, song_name, artist_name, extra="", meta=None):
    from applications.task.services.task_store import task_store
    task_store.update_item(full_path, state, extra=extra, title=song_name, artist=artist_name, task_id=task_id, meta=meta)


def process_single_auto_tag_task(task, source_list, select_mode):
    """
    单首歌曲自动刮削任务单元 (多线程并发执行)
    """
    task_id = getattr(task, "id", None) or (task.get("id") if isinstance(task, dict) else None)
    full_path = getattr(task, "full_path", "") or (task.get("full_path") if isinstance(task, dict) else "")
    song_name = getattr(task, "song_name", "") or (task.get("song_name") if isinstance(task, dict) else "")
    artist_name = getattr(task, "artist_name", "") or (task.get("artist_name") if isinstance(task, dict) else "")

    update_task_state_safe(task_id, full_path, "running", song_name, artist_name, extra="")

    is_match = False
    error_msg = ""
    for resource in source_list:
        try:
            is_match = match_song(resource, full_path, select_mode)
        except Exception as e:
            error_msg = f"{resource} 异常: {str(e)}"
            is_match = False
        if is_match:
            break

    if is_match:
        from applications.task.services.folder_music_service import invalidate_cache, extract_music_meta
        invalidate_cache(full_path)
        fn = os.path.basename(full_path)
        meta = extract_music_meta(full_path, fn, lrc_set=set())
        update_task_state_safe(
            task_id,
            full_path,
            "success",
            meta.get("title") or song_name,
            meta.get("artist") or artist_name,
            extra="",
            meta=meta
        )
        return True
    else:
        fail_reason = error_msg if error_msg else "未匹配到合适的元数据"
        update_task_state_safe(task_id, full_path, "failed", song_name, artist_name, extra=fail_reason)
        return False


def batch_auto_tag_task(batch, task_items, source_list, select_mode):
    """
    自动刮削任务（多线程并发版）
    source_list: ["migu", "qmusic", "netease"]
    """
    from applications.task.services.async_executor import executor
    executor.submit_batch(batch, task_items, process_single_auto_tag_task, source_list=source_list, select_mode=select_mode, task_type="auto_tag")
    return len(task_items)


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
