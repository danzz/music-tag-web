import json
import os
import time
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
from component import music_tag
from applications.utils.db_safety import db_write_safe

ALLOW_TYPE = ["flac", "mp3", "ape", "wav", "aiff", "wv", "tta", "m4a", "ogg", "mpc", "opus", "wma", "dsf", "dff"]

# 针对群晖机械硬盘阵列与网络挂载，限制并发为 4，避免磁头来回剧烈寻道
DEFAULT_READ_WORKERS = int(os.getenv("READ_WORKERS", 4))

# L1 内存缓存: (path, mtime, size) -> dict of metadata
_metadata_cache = {}
# L1 封面缓存: (full_path, mtime) -> (img_bytes, mime)
_cover_cache = {}

_local_cache_ver = 0
CACHE_VERSION_FILE = "/tmp/music_tag_cache_version"


def bump_cache_version():
    """通知所有多进程 Worker 同步失效其本地内存缓存"""
    try:
        with open(CACHE_VERSION_FILE, "w") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def _check_cache_sync():
    """检查是否收到全局缓存失效广播"""
    global _local_cache_ver, _metadata_cache, _cover_cache
    try:
        if os.path.exists(CACHE_VERSION_FILE):
            mtime = os.path.getmtime(CACHE_VERSION_FILE)
            if mtime > _local_cache_ver:
                _metadata_cache.clear()
                _cover_cache.clear()
                _local_cache_ver = mtime
    except Exception:
        pass


def invalidate_cache(full_path):
    """清除单个文件的内存缓存与持久化 SQLite 缓存，并广播更新"""
    full_path = os.path.normpath(full_path)
    keys_to_del = [k for k in _metadata_cache if k[0] == full_path]
    for k in keys_to_del:
        _metadata_cache.pop(k, None)
    cover_keys_to_del = [k for k in _cover_cache if k[0] == full_path]
    for k in cover_keys_to_del:
        _cover_cache.pop(k, None)
    try:
        from applications.task.models import MusicMetaCache
        MusicMetaCache.objects.filter(path=full_path).delete()
    except Exception:
        pass
    bump_cache_version()


def force_clear_all_caches(target_path=None):
    """
    强制清空 L1 内存缓存与 L2 SQLite 缓存，并广播通知所有 Worker
    """
    global _metadata_cache, _cover_cache
    if target_path:
        norm_prefix = os.path.normpath(target_path)
        _metadata_cache = {k: v for k, v in _metadata_cache.items() if not k[0].startswith(norm_prefix)}
        _cover_cache = {k: v for k, v in _cover_cache.items() if not k[0].startswith(norm_prefix)}
        try:
            from applications.task.models import MusicMetaCache
            MusicMetaCache.objects.filter(path__startswith=norm_prefix).delete()
        except Exception:
            pass
    else:
        _metadata_cache.clear()
        _cover_cache.clear()
        try:
            from applications.task.models import MusicMetaCache
            MusicMetaCache.objects.all().delete()
        except Exception:
            pass
    bump_cache_version()


def batch_get_sqlite_meta_cache(file_list):
    """
    从 SQLite L2 缓存批量获取元数据
    file_list: list of dict, 每个元素包含 "full_path", "mtime", "size"
    返回: dict of {norm_path: meta_dict}
    """
    if not file_list:
        return {}
    hits = {}
    path_map = {f["full_path"]: (f["mtime"], f["size"]) for f in file_list}
    try:
        from applications.task.models import MusicMetaCache
        records = MusicMetaCache.objects.filter(path__in=list(path_map.keys()))
        for r in records:
            expected_mtime, expected_size = path_map.get(r.path, (None, None))
            if expected_mtime is not None and abs(r.mtime - expected_mtime) < 0.001 and r.size == expected_size:
                try:
                    hits[r.path] = json.loads(r.meta_json)
                except Exception:
                    pass
    except Exception:
        pass
    return hits


@db_write_safe
def batch_save_sqlite_meta_cache(meta_items):
    """
    将新解析出的元数据批量存入 SQLite L2 缓存表
    """
    if not meta_items:
        return
    try:
        from applications.task.models import MusicMetaCache
        for item in meta_items:
            path = item.get("path")
            mtime = item.get("_mtime", 0)
            size = item.get("_size", 0)
            if not path:
                continue
            save_item = item.copy()
            save_item.pop("_mtime", None)
            save_item.pop("_size", None)
            meta_json = json.dumps(save_item, ensure_ascii=False)
            MusicMetaCache.objects.update_or_create(
                path=path,
                defaults={
                    "mtime": mtime,
                    "size": size,
                    "meta_json": meta_json,
                }
            )
    except Exception:
        pass


def extract_music_meta(entry_path, file_name, lrc_set, dir_files_set=None, mtime=None, size=None):
    """提取单首歌曲的元数据，具备完善异常保护、内存封面匹配与缓存加速"""
    entry_path = os.path.normpath(entry_path)
    if mtime is None or size is None:
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

    # 命中 L1 内存缓存
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
    # 外部封面检测：优先通过内存集合检查，避免向网络文件系统发送大量 os.path.exists
    if not has_cover:
        ext_cover_candidates = ["cover.jpg", "cover.png", "folder.jpg", "folder.png", f"{base_name}.jpg", f"{base_name}.png"]
        if dir_files_set is not None:
            for ext_cover in ext_cover_candidates:
                if ext_cover.lower() in dir_files_set:
                    has_cover = True
                    break
        else:
            for ext_cover in ext_cover_candidates:
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
        "_mtime": mtime,
        "_size": size,
    }
    _metadata_cache[cache_key] = meta
    return meta


def resolve_music_items(file_list, lrc_set, dir_files_set):
    """
    高效两级缓存解析文件列表：
    1. 先查 L1 内存缓存
    2. 未命中查 L2 SQLite 缓存
    3. 仍未命中用受控并发 (默认 4 线程) 解析音频文件，并写回 L1 和 L2
    """
    if not file_list:
        return []

    items = []
    missing_l1 = []

    # 1. 检查 L1 内存缓存
    for f in file_list:
        cache_key = (f["full_path"], f["mtime"], f["size"])
        if cache_key in _metadata_cache:
            cached = _metadata_cache[cache_key].copy()
            cached["has_lrc"] = f["base_name"] in lrc_set
            items.append(cached)
        else:
            missing_l1.append(f)

    if not missing_l1:
        return items

    # 2. 检查 L2 SQLite 缓存
    sqlite_hits = batch_get_sqlite_meta_cache(missing_l1)
    still_missing = []

    for f in missing_l1:
        norm_p = f["full_path"]
        if norm_p in sqlite_hits:
            meta = sqlite_hits[norm_p].copy()
            meta["has_lrc"] = f["base_name"] in lrc_set
            # 填入 L1 内存
            _metadata_cache[(norm_p, f["mtime"], f["size"])] = meta
            items.append(meta)
        else:
            still_missing.append(f)

    if not still_missing:
        return items

    # 3. 真正需要物理读取音频头文件的项：使用限制为 4 的低并发线程池，保护机械硬盘
    newly_parsed = []
    max_workers = min(DEFAULT_READ_WORKERS, max(1, len(still_missing)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                extract_music_meta,
                f["full_path"],
                f["name"],
                lrc_set,
                dir_files_set,
                f["mtime"],
                f["size"]
            )
            for f in still_missing
        ]
        for fut in futures:
            try:
                meta = fut.result()
                if meta:
                    items.append(meta)
                    newly_parsed.append(meta)
            except Exception:
                pass

    # 批量写入 L2 SQLite 缓存
    if newly_parsed:
        batch_save_sqlite_meta_cache(newly_parsed)

    return items


def get_folder_music_list(file_path, page=1, page_size=128, search_word="", sorted_field="", sort_order="asc"):
    """
    扫描目录返回该目录下的音乐文件详细标签信息
    （针对群晖机械硬盘优化的按需分页 + L1内存/L2 SQLite双层持久化缓存 + 4并发收敛）
    """
    _check_cache_sync()
    file_path = os.path.normpath(file_path.rstrip("/"))
    if not os.path.exists(file_path):
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    try:
        entries = list(os.scandir(file_path))
    except Exception:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    dir_files_set = set()
    lrc_set = set()
    audio_files = []

    for entry in entries:
        try:
            name = entry.name.encode('utf-8', 'replace').decode()
            if entry.is_dir():
                continue
            dir_files_set.add(name.lower())
            ext = name.split(".")[-1].lower()
            base_name = os.path.splitext(name)[0].lower()
            if ext == "lrc":
                lrc_set.add(base_name)
            elif ext in ALLOW_TYPE:
                try:
                    st = entry.stat()
                    mtime = st.st_mtime
                    size = st.st_size
                except Exception:
                    mtime = 0
                    size = 0
                audio_files.append({
                    "full_path": os.path.normpath(entry.path),
                    "name": name,
                    "mtime": mtime,
                    "size": size,
                    "base_name": base_name,
                })
        except Exception:
            continue

    if not audio_files:
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

    can_lazy_paginate = (not search_word) and (sorted_field in ["", "name", "filename", "size", "update_time"])
    reverse = (sort_order == "desc")

    if can_lazy_paginate:
        # 1. 内存中按文件物理信息轻量排序
        if sorted_field in ["name", "filename"]:
            audio_files.sort(key=lambda x: x["name"].lower(), reverse=reverse)
        elif sorted_field == "size":
            audio_files.sort(key=lambda x: x["size"], reverse=reverse)
        elif sorted_field == "update_time":
            audio_files.sort(key=lambda x: x["mtime"], reverse=reverse)
        else:
            audio_files.sort(key=lambda x: x["name"].lower())

        total = len(audio_files)
        if page_size > 0:
            start = (page - 1) * page_size
            end = start + page_size
            target_files = audio_files[start:end]
        else:
            target_files = audio_files

        # 2. 仅对当前页的切片文件解析标签（结合 L1 内存 + L2 SQLite 双层缓存与 4 并发保护）
        page_items = resolve_music_items(target_files, lrc_set, dir_files_set)

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": page_items
        }

    # 用户指定了需要提取标签内容的搜索或排序
    items = resolve_music_items(audio_files, lrc_set, dir_files_set)

    # 关键词过滤
    if search_word:
        kw = search_word.lower()
        items = [
            it for it in items
            if kw in it["filename"].lower() or kw in it["title"].lower() or kw in it["artist"].lower() or kw in it["album"].lower()
        ]

    # 排序
    if sorted_field:
        if sorted_field in ["name", "filename"]:
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
    _check_cache_sync()
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
    candidate_covers = [
        "cover.jpg", "cover.jpeg", "cover.png", "Cover.jpg", "Cover.png",
        "folder.jpg", "folder.jpeg", "folder.png", "Folder.jpg", "Folder.png",
        f"{base_name}.jpg", f"{base_name}.jpeg", f"{base_name}.png"
    ]
    for ext_cover in candidate_covers:
        c_path = os.path.join(file_path, ext_cover)
        if os.path.exists(c_path):
            try:
                mime = "image/png" if ext_cover.lower().endswith(".png") else "image/jpeg"
                with open(c_path, "rb") as img_f:
                    data = img_f.read()
                    res = (data, mime)
                    _cover_cache[cache_key] = res
                    return res
            except Exception:
                pass

    return None, None
