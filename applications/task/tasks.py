import logging
import os
import re
import shutil
from collections import defaultdict

from applications.task.constants import ALLOW_TYPE
from applications.task.services.music_ids import MusicIDS
from applications.task.utils import match_song

logger = logging.getLogger(__name__)


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


FIELD_DEFAULT_NAMES = {
    'title': '未知标题',
    'artist': '未知艺术家',
    'album': '未知专辑',
    'albumartist': '未知专辑艺术家',
    'album_artist': '未知专辑艺术家',
    'album_type': '未知专辑类型',
    'genre': '未知风格',
    'language': '未知语言',
    'comment': '未知描述',
    'year': '未知年份',
    'tracknumber': '未知音轨号',
    'discnumber': '未知光盘号'
}


def sanitize_folder_name(name, default_name="未知"):
    if name is None:
        return default_name
    s = str(name).strip()
    if not s or s in ("0", "None"):
        return default_name
    # 替换 Windows / Linux / macOS 文件系统非法及路径分隔符: / \ : * ? " < > |
    s = re.sub(r'[\/\\:*?"<>|]', '_', s)
    # 去除首尾的句点和空格
    s = s.strip('. ')
    return s if s else default_name


def extract_tag_value(file_obj, field_key):
    if not field_key:
        return ""
    alias_map = {
        'albumartist': 'album_artist',
        'album_name': 'album',
        'tracknumber': 'track_number',
        'discnumber': 'disc_number'
    }
    attr_name = alias_map.get(field_key, field_key)
    val = getattr(file_obj, attr_name, None)
    if val is None or str(val).strip() == "" or str(val).strip() == "0":
        val = getattr(file_obj, field_key, None)
    default_label = FIELD_DEFAULT_NAMES.get(field_key, "未知")
    return sanitize_folder_name(val, default_label)


def process_single_tidy_task(task_item, tidy_config):
    """
    单首歌曲整理分类任务单元 (通过 AsyncExecutor 多线程并发执行)
    """
    task_id = task_item.get("id")
    full_path = task_item.get("file_full_path") or task_item.get("full_path") or ""
    song_name = task_item.get("song_name") or task_item.get("filename") or os.path.basename(full_path)
    artist_name = task_item.get("artist") or ""

    if not full_path or not os.path.exists(full_path):
        update_task_state_safe(task_id, full_path, "failed", song_name, artist_name, extra="源文件不存在")
        return False

    update_task_state_safe(task_id, full_path, "running", song_name, artist_name, extra="正在整理移动...")

    root_path = tidy_config.get("root_path")
    first_dir = tidy_config.get("first_dir")
    second_dir = tidy_config.get("second_dir")
    move_lrc = tidy_config.get("move_lrc", True)
    conflict_action = tidy_config.get("conflict_action", "skip")
    clean_empty_dir = tidy_config.get("clean_empty_dir", False)

    try:
        file_obj = MusicIDS(full_path)
        first_value = extract_tag_value(file_obj, first_dir)
        if second_dir:
            second_value = extract_tag_value(file_obj, second_dir)
            target_dir = os.path.join(root_path, first_value, second_value)
        else:
            target_dir = os.path.join(root_path, first_value)

        filename = os.path.basename(full_path)
        dst_file = os.path.normpath(os.path.join(target_dir, filename))
        src_file = os.path.normpath(full_path)

        # 1. 如果源文件与目标文件完全相同，则无需移动
        if src_file == dst_file:
            update_task_state_safe(task_id, full_path, "success", song_name, artist_name, extra="已在目标分类目录")
            return True

        # 2. 如果目标文件已存在
        if os.path.exists(dst_file):
            if conflict_action == "skip":
                update_task_state_safe(task_id, full_path, "success", song_name, artist_name, extra="目标已存在，已跳过")
                return True
            else:
                try:
                    os.remove(dst_file)
                except Exception as e:
                    logger.warning(f"Failed to remove existing dst_file {dst_file}: {e}")

        # 3. 创建目标文件夹并移动文件
        os.makedirs(target_dir, exist_ok=True)
        shutil.move(src_file, dst_file)

        # 4. 同步移动同名 .lrc 歌词文件
        if move_lrc:
            base_name, _ = os.path.splitext(filename)
            src_dir = os.path.dirname(src_file)
            src_lrc = os.path.join(src_dir, f"{base_name}.lrc")
            dst_lrc = os.path.join(target_dir, f"{base_name}.lrc")
            if os.path.exists(src_lrc) and os.path.normpath(src_lrc) != os.path.normpath(dst_lrc):
                if os.path.exists(dst_lrc):
                    if conflict_action == "overwrite":
                        try:
                            os.remove(dst_lrc)
                            shutil.move(src_lrc, dst_lrc)
                        except Exception:
                            pass
                else:
                    try:
                        shutil.move(src_lrc, dst_lrc)
                    except Exception:
                        pass

        # 5. 更新元数据缓存
        from applications.task.services.folder_music_service import invalidate_cache
        invalidate_cache(src_file)
        invalidate_cache(dst_file)

        # 6. 如果需要清理变为空的源文件夹
        if clean_empty_dir:
            src_dir = os.path.dirname(src_file)
            norm_root = os.path.normpath(root_path)
            norm_src = os.path.normpath(src_dir)
            if norm_src != norm_root and len(norm_src) > 5 and os.path.isdir(norm_src):
                try:
                    for hf in os.listdir(norm_src):
                        if hf.startswith('.'):
                            try:
                                os.remove(os.path.join(norm_src, hf))
                            except Exception:
                                pass
                    os.rmdir(norm_src)
                except OSError:
                    pass

        extra_info = f"已移动至: {first_value}" + (f"/{second_value}" if second_dir else "")
        update_task_state_safe(task_id, full_path, "success", song_name, artist_name, extra=extra_info)
        return True
    except Exception as e:
        logger.error(f"Error tidying file {full_path}: {e}", exc_info=True)
        update_task_state_safe(task_id, full_path, "failed", song_name, artist_name, extra=f"移动失败: {str(e)}")
        return False


def tidy_folder_task(batch_id, task_items, tidy_config):
    """
    整理文件夹任务（通过 AsyncExecutor 多线程并发异步执行）
    """
    from applications.task.services.async_executor import executor
    executor.submit_batch(batch_id, task_items, process_single_tidy_task, tidy_config=tidy_config, task_type="tidy_folder")
    return len(task_items)
