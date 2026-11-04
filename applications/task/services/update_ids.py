import base64
import os
import re

from component import music_tag
from mutagen.flac import VCFLACDict
from mutagen.id3 import TXXX, ID3

from applications.task.models import Task
from applications.utils.constant_template import ConstantTemplate
from applications.utils.db_safety import db_write_safe
from applications.utils.send import send


def apply_field_transform(value, rule):
    """应用文本裁剪与转换规则 (切片、文本替换、正则替换、首尾去空)"""
    if not isinstance(value, str) or not rule:
        return value

    # 1. 字符切片 (去除前 N 个字符 / 去除后 M 个字符)
    try:
        trim_start = int(rule.get("trim_start", 0) or 0)
    except Exception:
        trim_start = 0
    try:
        trim_end = int(rule.get("trim_end", 0) or 0)
    except Exception:
        trim_end = 0

    if trim_start > 0:
        value = value[trim_start:]
    if trim_end > 0:
        if len(value) >= trim_end:
            value = value[:-trim_end]
        else:
            value = ""

    # 2. 文本替换
    replace_search = rule.get("replace_search", "")
    if replace_search:
        replace_with = rule.get("replace_with", "")
        value = value.replace(replace_search, replace_with)

    # 3. 正则表达式替换
    regex_search = rule.get("regex_search", "")
    if regex_search:
        regex_replace = rule.get("regex_replace", "")
        try:
            value = re.sub(regex_search, regex_replace, value)
        except Exception:
            pass

    # 4. 去除首尾空白
    if rule.get("strip", True):
        value = value.strip()

    return value


@db_write_safe
def update_manual_task_state_safe(task_id, full_path, state, title, artist, extra=""):
    full_path = os.path.normpath(full_path)
    parent_path = os.path.normpath(os.path.dirname(full_path))
    filename = os.path.basename(full_path)
    if task_id:
        from applications.task.models import TaskRecord
        TaskRecord.objects.filter(id=task_id).update(state=state, extra=extra)
    Task.objects.update_or_create(full_path=full_path, defaults={
        "state": state,
        "parent_path": parent_path,
        "filename": filename,
        "song_name": title or filename,
        "artist_name": artist or "",
        "extra": extra
    })


def process_single_manual_save(each, is_raw_thumbnail=False, **kwargs):
    """单首手动修改保存 (可供线程池并发调用)"""
    full_path = os.path.normpath(each.get("file_full_path"))
    task_id = each.get("task_id")
    title = each.get("title", "")
    artist = each.get("artist", "")
    try:
        update_manual_task_state_safe(task_id, full_path, "running", title, artist, extra="")
        f = music_tag.load_file(full_path)
        save_music(f, each, is_raw_thumbnail)
        final_path = os.path.normpath(each.get("file_full_path", full_path))
        update_manual_task_state_safe(task_id, final_path, "success", title, artist, extra="")
        from applications.task.services.folder_music_service import invalidate_cache
        invalidate_cache(full_path)
        if final_path != full_path:
            invalidate_cache(final_path)
        return True
    except Exception as e:
        update_manual_task_state_safe(task_id, full_path, "failed", title, artist, extra=f"保存失败: {str(e)}")
        return False


def update_music_info(music_id3_info, is_raw_thumbnail=False):
    for each in music_id3_info:
        process_single_manual_save(each, is_raw_thumbnail)


def update_music_info_async(batch, music_id3_info, is_raw_thumbnail=False):
    """多线程异步并发批量修改"""
    from applications.task.services.async_executor import executor
    executor.submit_batch(batch, music_id3_info, process_single_manual_save, is_raw_thumbnail=is_raw_thumbnail, task_type="manual_update")



def save_music(f, each, is_raw_thumbnail):
    from applications.task.services.music_ids import MusicIDS

    base_filename = ".".join(os.path.basename(f.filename).split(".")[:-1])
    file_ext = os.path.basename(f.filename).split(".")[-1]

    var_dict = MusicIDS(file=f).var_dict()
    transform_rules = each.get("transform_rules", {})

    def resolve_val(field_name):
        val = each.get(field_name, None)
        if val is None:
            return None
        val = str(val)
        if "${" in val:
            val = ConstantTemplate(val).resolve_data(var_dict)
        rule = transform_rules.get(field_name)
        if rule:
            val = apply_field_transform(val, rule)
        return val

    res_title = resolve_val("title")
    if res_title is not None and res_title != "":
        f["title"] = res_title

    res_artist = resolve_val("artist")
    if res_artist is not None and res_artist != "":
        artists = res_artist.split(",")
        f.set("artist", artists)

    res_album = resolve_val("album")
    if res_album is not None and res_album != "":
        f["album"] = res_album

    res_albumartist = resolve_val("albumartist")
    if res_albumartist is not None and res_albumartist != "":
        f["albumartist"] = res_albumartist

    res_discnumber = resolve_val("discnumber")
    if res_discnumber is not None and res_discnumber != "":
        try:
            f["discnumber"] = int(res_discnumber.split("/")[0].strip())
        except Exception:
            f["discnumber"] = 0

    res_tracknumber = resolve_val("tracknumber")
    if res_tracknumber is not None and res_tracknumber != "":
        try:
            f["tracknumber"] = int(res_tracknumber.split("/")[0].strip())
        except Exception:
            f["tracknumber"] = 0

    res_genre = resolve_val("genre")
    if res_genre is not None and res_genre != "":
        f["genre"] = res_genre

    res_year = resolve_val("year")
    if res_year is not None and res_year != "":
        f["year"] = res_year

    if each.get("lyrics", None):
        f["lyrics"] = each["lyrics"]
        if each.get("is_save_lyrics_file", False):
            lyrics_file_path = f"{os.path.dirname(each['file_full_path'])}/{base_filename}.lrc"
            with open(lyrics_file_path, "w", encoding="utf-8") as f_lyc:
                f_lyc.write(each["lyrics"])
    else:
        if each.get("lyrics") is not None:
            f.remove_tag("lyrics")
        if each.get("is_save_lyrics_file", False):
            lyrics_file_path = f"{os.path.dirname(each['file_full_path'])}/cover-{base_filename}.lrc"
            if not os.path.exists(lyrics_file_path):
                with open(lyrics_file_path, "w", encoding="utf-8") as f_lyc2:
                    f_lyc2.write(f["lyrics"].value)
    if each.get("comment", None):
        f["comment"] = each["comment"]

    if each.get("clear_cover", False):
        try:
            f.remove_tag("artwork")
        except Exception:
            pass
    elif each.get("album_img", None):
        try:
            img_content = None
            if each["album_img"].startswith("http"):
                img_data = send().GET(each["album_img"])
                if img_data.status_code == 200:
                    img_content = img_data.content
            else:
                raw_b64 = each["album_img"]
                if "," in raw_b64:
                    raw_b64 = raw_b64.split(",", 1)[1]
                img_content = base64.b64decode(raw_b64)
            if img_content:
                f['artwork'] = img_content
                if each.get("is_save_album_cover", False):
                    format_str = getattr(f['artwork'].value, 'format', 'jpg')
                    album_cover_path = f"{os.path.dirname(each['file_full_path'])}/cover-{f['album']}.{format_str}"
                    if os.path.exists(album_cover_path):
                        os.remove(album_cover_path)
                    with open(album_cover_path, "wb") as f_img:
                        f_img.write(img_content)
                    std_cover_path = f"{os.path.dirname(each['file_full_path'])}/cover.{format_str}"
                    try:
                        with open(std_cover_path, "wb") as f_std:
                            f_std.write(img_content)
                    except Exception:
                        pass
                if len(img_content) / 1024 / 1024 > 5:
                    f['artwork'] = f['artwork'].first.raw_thumbnail([2048, 2048])
                if is_raw_thumbnail:
                    f['artwork'] = f['artwork'].first.raw_thumbnail([2048, 2048])
        except Exception as e:
            print(e)
            pass
    else:
        if each.get("is_save_album_cover", False):
            format_str = getattr(f['artwork'].value, 'format', 'jpg')
            album_cover_path = f"{os.path.dirname(each['file_full_path'])}/cover-{f['album']}.{format_str}"
            if not os.path.exists(album_cover_path):
                with open(album_cover_path, "wb") as f_img:
                    f_img.write(f['artwork'].value.raw)
    if each.get("album_type", None):
        if isinstance(f.mfile.tags, VCFLACDict):
            f.mfile.tags["RELEASETYPE"] = each["album_type"]
        elif isinstance(f.mfile.tags, ID3):
            f.mfile.tags["MusicBrainz Album Type"] = TXXX(encoding=3,
                                                          desc="MusicBrainz Album Type",
                                                          text=each["album_type"])
        else:
            raise Exception("未知的音乐文件类型")
    if each.get("language", None):
        if isinstance(f.mfile.tags, VCFLACDict):
            f.mfile.tags["LANGUAGE"] = each["language"]
        elif isinstance(f.mfile.tags, ID3):
            f.mfile.tags["LANGUAGE"] = TXXX(encoding=3,
                                            desc="LANGUAGE",
                                            text=each["language"])
        else:
            f.mfile.tags["LANGUAGE"] = each["language"]
    f.save()
    # 重命名文件名称
    if each.get("filename", None):
        new_filename = resolve_val("filename")
        if new_filename:
            if not new_filename.endswith(f".{file_ext}"):
                new_filename = f"{new_filename}.{file_ext}"
            parent_path = os.path.dirname(each["file_full_path"])
            target_path = os.path.join(parent_path, new_filename)
            if each["file_full_path"] != target_path:
                os.rename(each["file_full_path"], target_path)
                from applications.task.services.folder_music_service import invalidate_cache
                invalidate_cache(each["file_full_path"])
                invalidate_cache(target_path)
                each["file_full_path"] = target_path
