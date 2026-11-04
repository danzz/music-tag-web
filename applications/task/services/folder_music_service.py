import os
import time
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from component import music_tag

ALLOW_TYPE = ["flac", "mp3", "ape", "wav", "aiff", "wv", "tta", "m4a", "ogg", "mpc", "opus", "wma", "dsf", "dff"]

# Cache: (path, mtime, size) -> dict of metadata
_metadata_cache = {}
# Cache: (full_path, mtime) -> (img_bytes, mime)
_cover_cache = {}


def invalidate_cache(full_path):
    """清除单个文件的元数据缓存和封面缓存"""
    full_path = os.path.normpath(full_path)
    keys_to_del = [k for k in _metadata_cache if k[0] == full_path]
    for k in keys_to_del:
        _metadata_cache.pop(k, None)
    cover_keys_to_del = [k for k in _cover_cache if k[0] == full_path]
    for k in cover_keys_to_del:
        _cover_cache.pop(k, None)


def extract_music_meta(entry_path, file_name, lrc_set):
    """提取单首歌曲的元数据，具备完善异常保护和外部封面检测"""
    entry_path = os.path.normpath(entry_path)
    try:
        stat = os.stat(entry_path)
        mtime = stat.st_mtime
        size = stat.st_size
    except Exception:
        mtime = 0
        size = 0

    cache_key = (entry_path, mtime, size)
    base_name = os.path.splitext(file_name)[0]
    has_lrc = base_name.lower() in lrc_set

    if cache_key in _metadata_cache:
        cached = _metadata_cache[cache_key].copy()
        cached["has_lrc"] = has_lrc
        return cached

    title = base_name
    artist = ""
    album = ""
    albumartist = ""
    genre = ""
    year = ""
    lyrics = ""
    has_cover = False

    try:
        f = music_tag.load_file(entry_path)
        t = f['title'].value
        if t:
            title = str(t).strip()
        art = f['artist'].value
        if art:
            artist = str(art).strip()
        alb = f['album'].value
        if alb:
            album = str(alb).strip()
        albart = f['albumartist'].value
        if albart:
            albumartist = str(albart).strip()
        g = f['genre'].value
        if g and str(g).strip().lower() != "未知":
            genre = str(g).strip()
        y = f['year'].value
        if y:
            y_str = str(y).strip()
            if y_str != "0":
                year = y_str
        lyr = f['lyrics'].value
        if lyr and str(lyr).strip():
            lyrics = str(lyr).strip()
        artwork = f['artwork'].values
        if artwork:
            has_cover = True
    except Exception:
        pass

    dir_path = os.path.dirname(entry_path)
    if not has_cover:
        for ext_cover in ["cover.jpg", "cover.png", "folder.jpg", "folder.png", f"{base_name}.jpg", f"{base_name}.png"]:
            if os.path.exists(os.path.join(dir_path, ext_cover)):
                has_cover = True
                break

    meta = {
        "id": file_name,
        "filename": file_name,
        "path": entry_path,
        "title": title,
        "artist": artist,
        "album": album,
        "albumartist": albumartist,
        "genre": genre,
        "year": year,
        "has_lyrics": bool(lyrics),
        "has_lrc": has_lrc,
        "has_cover": has_cover,
        "cover_url": f"/api/music_cover/?file_path={quote(dir_path)}&file_name={quote(file_name)}&v={int((mtime or 0) * 1000)}",
        "size": round(size / 1024 / 1024, 2),
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)) if mtime else "",
    }
    _metadata_cache[cache_key] = meta
    return meta


def get_folder_music_list(file_path, page=1, page_size=128, search_word="", sorted_field="", sort_order="asc"):
    """
    扫描目录返回该目录下的所有音乐文件详细标签信息（多线程并发读取 + 缓存加速）
    """
    file_path = os.path.normpath(file_path.rstrip("/"))
    if not os.path.exists(file_path):
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    try:
        entries = list(os.scandir(file_path))
    except Exception:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    lrc_set = set()
    audio_files = []

    for entry in entries:
        name = entry.name.encode('utf-8', 'replace').decode()
        if entry.is_dir():
            continue
        ext = name.split(".")[-1].lower()
        base_name = os.path.splitext(name)[0].lower()
        if ext == "lrc":
            lrc_set.add(base_name)
        elif ext in ALLOW_TYPE:
            audio_files.append((entry.path.encode('utf-8', 'replace').decode(), name))

    if not audio_files:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    # 多线程并发提取歌曲元数据
    items = []
    with ThreadPoolExecutor(max_workers=min(16, max(4, len(audio_files)))) as executor:
        futures = [
            executor.submit(extract_music_meta, full_path, file_name, lrc_set)
            for full_path, file_name in audio_files
        ]
        for f in futures:
            try:
                meta = f.result()
                if meta:
                    items.append(meta)
            except Exception:
                pass

    # 关键词过滤
    if search_word:
        kw = search_word.lower()
        items = [
            it for it in items
            if kw in it["filename"].lower() or kw in it["title"].lower() or kw in it["artist"].lower() or kw in it["album"].lower()
        ]

    # 排序
    reverse = (sort_order == "desc")
    if sorted_field:
        if sorted_field == "name" or sorted_field == "filename":
            items.sort(key=lambda x: x["filename"].lower(), reverse=reverse)
        elif sorted_field == "title":
            items.sort(key=lambda x: x["title"].lower(), reverse=reverse)
        elif sorted_field == "artist":
            items.sort(key=lambda x: x["artist"].lower(), reverse=reverse)
        elif sorted_field == "album":
            items.sort(key=lambda x: x["album"].lower(), reverse=reverse)
        elif sorted_field == "year":
            items.sort(key=lambda x: x["year"], reverse=reverse)
        elif sorted_field == "size":
            items.sort(key=lambda x: x["size"], reverse=reverse)
        elif sorted_field == "update_time":
            items.sort(key=lambda x: x["update_time"], reverse=reverse)
    else:
        # 默认按文件名自然升序排序
        items.sort(key=lambda x: x["filename"].lower())

    total = len(items)
    if page_size > 0:
        start = (page - 1) * page_size
        end = start + page_size
        page_items = items[start:end]
    else:
        page_items = items

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": page_items
    }


def get_music_cover_data(file_path, file_name):
    """
    读取单首歌曲或其目录的封面图片缩略图二进制数据（带缓存）
    """
    file_path = os.path.normpath(file_path.rstrip("/"))
    full_path = os.path.normpath(os.path.join(file_path, file_name))

    try:
        mtime = os.path.getmtime(full_path)
    except Exception:
        mtime = 0
    cache_key = (full_path, mtime)
    if cache_key in _cover_cache:
        return _cover_cache[cache_key]

    # 1. 尝试从音频文件内嵌封面读取
    if os.path.exists(full_path):
        try:
            f = music_tag.load_file(full_path)
            artwork = f['artwork'].values
            if artwork:
                art = artwork[0]
                if isinstance(art, bytes):
                    res = (art, "image/jpeg")
                else:
                    try:
                        thumb = art.raw_thumbnail([128, 128])
                        res = (thumb, getattr(art, 'mime', None) or "image/jpeg")
                    except Exception:
                        raw_data = getattr(art, 'raw', None) or (art if isinstance(art, bytes) else b"")
                        res = (raw_data, getattr(art, 'mime', None) or "image/jpeg")
                _cover_cache[cache_key] = res
                return res
        except Exception:
            pass

    # 2. 尝试从同目录下的外置封面文件读取
    base_name = os.path.splitext(file_name)[0]
    for ext_cover in ["cover.jpg", "cover.png", "folder.jpg", "folder.png", f"{base_name}.jpg", f"{base_name}.png"]:
        c_path = os.path.join(file_path, ext_cover)
        if os.path.exists(c_path):
            try:
                mime = "image/png" if ext_cover.endswith(".png") else "image/jpeg"
                with open(c_path, "rb") as img_f:
                    data = img_f.read()
                    res = (data, mime)
                    _cover_cache[cache_key] = res
                    return res
            except Exception:
                pass

    return None, None
