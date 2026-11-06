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


def prepare_artwork_image(raw_input, max_dim=2048, is_thumbnail=False):
    """
    规范化图片数据：
    - 支持 HTTP/HTTPS 远程下载
    - 支持 Base64 解码 (自动剥离 data:image/*;base64, 前缀)
    - 使用 Pillow 验证图片完整性，转换颜色通道 (RGBA->PNG, CMYK/其他->RGB JPEG)
    - 超大图片自动等比压缩尺寸 (避免嵌入超大图导致播放器崩溃或卡顿)
    - 返回 (clean_img_bytes, format_ext)
    """
    if not raw_input:
        return None, "jpg"

    img_content = None
    if isinstance(raw_input, str) and os.path.isfile(raw_input):
        try:
            with open(raw_input, "rb") as f_img:
                img_content = f_img.read()
        except Exception as e:
            raise ValueError(f"读取本地封面图片失败: {e}")
    elif isinstance(raw_input, str) and raw_input.startswith("http"):
        try:
            img_data = send().GET(raw_input)
            if img_data.status_code == 200:
                img_content = img_data.content
            else:
                raise ValueError(f"下载远程图片失败，HTTP状态码: {img_data.status_code}")
        except Exception as e:
            raise ValueError(f"下载网络图片出错: {e}")
    elif isinstance(raw_input, str):
        try:
            raw_b64 = raw_input
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            img_content = base64.b64decode(raw_b64)
        except Exception as e:
            raise ValueError(f"Base64图片解码失败: {e}")
    elif isinstance(raw_input, bytes):
        img_content = raw_input

    if not img_content:
        raise ValueError("图片数据为空")

    # 使用 Pillow 验证与规范化格式
    try:
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(img_content))
        target_ext = "jpg"
        target_fmt = "JPEG"
        if im.mode in ("RGBA", "LA", "P"):
            target_ext = "png"
            target_fmt = "PNG"
        elif im.mode != "RGB":
            im = im.convert("RGB")

        limit = 500 if is_thumbnail else max_dim
        if im.width > limit or im.height > limit:
            im.thumbnail((limit, limit), Image.BICUBIC)

        out_buf = io.BytesIO()
        if target_fmt == "JPEG":
            im.save(out_buf, format="JPEG", quality=92)
        else:
            im.save(out_buf, format="PNG")
        return out_buf.getvalue(), target_ext
    except Exception as e:
        raise ValueError(f"图片格式无效或损坏: {e}")


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

    # 3. 正则表达式替换或抽取
    regex_search = rule.get("regex_search", "")
    if regex_search:
        regex_replace = rule.get("regex_replace", "")
        try:
            if regex_replace and regex_replace in ("$1", "$2", "$3", r"\1", r"\2", r"\3"):
                grp_idx = int(regex_replace[-1])
                m = re.search(regex_search, value)
                if m and len(m.groups()) >= grp_idx:
                    value = m.group(grp_idx)
            else:
                py_replace = re.sub(r"\$(\d+)", r"\\\1", regex_replace)
                value = re.sub(regex_search, py_replace, value)
        except Exception:
            pass

    # 4. 去除首尾空白
    if rule.get("strip", True):
        value = value.strip()

    # 5. 格式化补零 (pad2: 01, pad3: 001, raw: 1)
    padding = rule.get("padding")
    if padding:
        try:
            m = re.search(r'\d+', value)
            if m:
                num = int(m.group(0))
                if padding == "pad2":
                    value = f"{num:02d}"
                elif padding == "pad3":
                    value = f"{num:03d}"
                elif padding == "raw":
                    value = str(num)
        except Exception:
            pass

    return value


def update_manual_task_state_safe(task_id, full_path, state, title, artist, extra="", meta=None):
    from applications.task.services.task_store import task_store
    task_store.update_item(full_path, state, extra=extra, title=title, artist=artist, task_id=task_id, meta=meta)


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
        from applications.task.services.folder_music_service import invalidate_cache, extract_music_meta
        invalidate_cache(full_path)
        if final_path != full_path:
            invalidate_cache(final_path)

        fn = os.path.basename(final_path)
        meta = extract_music_meta(final_path, fn, lrc_set=set())

        update_manual_task_state_safe(
            task_id,
            final_path,
            "success",
            meta.get("title") or title,
            meta.get("artist") or artist,
            extra="",
            meta=meta
        )
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
    if not var_dict.get("folder"):
        full_p = each.get("file_full_path") or getattr(f, "filename", "")
        if full_p:
            p_dir = os.path.basename(os.path.dirname(os.path.normpath(str(full_p))))
            var_dict["folder"] = p_dir
            var_dict["parent_folder"] = p_dir
            var_dict["dirname"] = p_dir
            var_dict["folder_name"] = p_dir
    seq_idx = each.get("sequence_index", 1)
    var_dict["seq"] = str(seq_idx)
    var_dict["sequence_index"] = str(seq_idx)
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
    if res_discnumber is not None:
        if str(res_discnumber).strip() == "":
            try:
                f["discnumber"] = 0
            except Exception:
                pass
        else:
            try:
                val_clean = str(res_discnumber).split("/")[0].strip()
                import re
                m = re.search(r'\d+', val_clean)
                if m:
                    f["discnumber"] = val_clean
                else:
                    f["discnumber"] = 0
            except Exception:
                f["discnumber"] = 0

    res_tracknumber = resolve_val("tracknumber")
    if res_tracknumber is not None:
        if str(res_tracknumber).strip() == "":
            try:
                f["tracknumber"] = 0
            except Exception:
                pass
        else:
            try:
                val_clean = str(res_tracknumber).split("/")[0].strip()
                import re
                m = re.search(r'\d+', val_clean)
                if m:
                    f["tracknumber"] = val_clean
                else:
                    f["tracknumber"] = 0
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
        clean_img_bytes, format_str = prepare_artwork_image(
            each["album_img"],
            max_dim=2048,
            is_thumbnail=is_raw_thumbnail
        )
        if clean_img_bytes:
            # 1. 写入音频文件内嵌标签
            try:
                f['artwork'] = clean_img_bytes
            except Exception as e:
                raise RuntimeError(f"音频内嵌封面写入失败: {e}")

            # 2. 如果开启了保存专辑封面文件
            if each.get("is_save_album_cover", False):
                try:
                    dir_name = os.path.dirname(each['file_full_path'])
                    raw_album = str(f.get('album', '') or each.get('album', '') or 'cover')
                    safe_album = re.sub(r'[\\/*?:"<>|]', '_', raw_album).strip() or "cover"
                    album_cover_path = os.path.join(dir_name, f"cover-{safe_album}.{format_str}")
                    with open(album_cover_path, "wb") as f_img:
                        f_img.write(clean_img_bytes)

                    std_cover_path = os.path.join(dir_name, f"cover.{format_str}")
                    with open(std_cover_path, "wb") as f_std:
                        f_std.write(clean_img_bytes)
                except Exception as e:
                    # 外部目录封面图片保存警告，不阻断音频标签内嵌保存
                    print(f"写入目录封面文件警告: {e}")
    else:
        if each.get("is_save_album_cover", False):
            try:
                artwork_vals = f['artwork'].values
                if artwork_vals:
                    art = artwork_vals[0]
                    raw_data = getattr(art, 'raw', None) or (art if isinstance(art, bytes) else None)
                    if raw_data:
                        dir_name = os.path.dirname(each['file_full_path'])
                        raw_album = str(f.get('album', '') or each.get('album', '') or 'cover')
                        safe_album = re.sub(r'[\\/*?:"<>|]', '_', raw_album).strip() or "cover"
                        format_str = getattr(art, 'format', 'jpg') or 'jpg'
                        album_cover_path = os.path.join(dir_name, f"cover-{safe_album}.{format_str}")
                        if not os.path.exists(album_cover_path):
                            with open(album_cover_path, "wb") as f_img:
                                f_img.write(raw_data)
            except Exception as e:
                print(f"导出封面到目录失败: {e}")
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
