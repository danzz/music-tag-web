import json
import logging
import os
import queue
import threading
import time
from urllib.parse import quote
from django.conf import settings

logger = logging.getLogger(__name__)

TTL_SECONDS = 86400  # 24 小时自动过期清除过程数据


class BaseTaskStore:
    def init_batch(self, batch_id, items, task_type="manual_update"):
        raise NotImplementedError

    def check_active_tasks(self, file_paths):
        raise NotImplementedError

    def update_item(self, full_path, state, extra="", title="", artist="", task_id=None, meta=None):
        raise NotImplementedError

    def get_active_path_states(self, parent_path, filenames):
        raise NotImplementedError

    def get_batch_progress(self, batch_id, include_records=False):
        raise NotImplementedError

    def get_task_records(self, page=1, page_size=20, state="", batch="", search=""):
        raise NotImplementedError

    def get_stats(self):
        raise NotImplementedError

    def clear_tasks(self, batch=None, state=None):
        raise NotImplementedError

    def retry_single(self, record_id):
        raise NotImplementedError

    def get_pending_tasks(self, batch=None, limit=2000):
        raise NotImplementedError

    def publish_event(self, event_type, payload):
        raise NotImplementedError

    def subscribe_events(self, last_event_id=0):
        raise NotImplementedError


class PureMemoryTaskStore(BaseTaskStore):
    """
    纯 Python 堆内存任务中心（Zero-DB In-Memory Task Engine）：
    - 0 数据库依赖：彻底移除 SQLite / 文件存储，不创建任何 .db / -wal / -shm 文件
    - 文件级去重覆盖：以规范化绝对路径 (normpath) 为唯一 Key，重复修改覆盖旧状态，杜绝计数膨胀
    - 全内存结构：使用 Python 原生 dict/set/queue，纳秒至微秒级读写
    - 24 小时 TTL 自动修剪淘汰，重启随内存自动清空
    - 内存级 Pub/Sub：支持多客户端 SSE 即时流式分发
    """
    def __init__(self):
        self._lock = threading.RLock()
        self.batches = {}
        # file_tasks: norm_path -> task_dict (文件对象主存储，保证文件唯一)
        self.file_tasks = {}
        # tasks: task_id -> task_dict (按 ID 索引，指向 file_tasks 中的同一对象)
        self.tasks = {}
        self.path_to_task_id = {}
        self.path_map = {}
        self._id_counter = 1
        self._event_counter = 1
        self.subscribers = set()
        logger.info("Initialized PureMemoryTaskStore (Zero SQLite, Pure RAM, File Dedup).")

    def _prune_expired(self):
        cutoff = time.time() - TTL_SECONDS
        with self._lock:
            expired_fps = [
                fp for fp, task in self.file_tasks.items()
                if task.get("updated_at", 0) < cutoff
            ]
            for fp in expired_fps:
                task = self.file_tasks.pop(fp, None)
                if task:
                    tid = task.get("id")
                    self.tasks.pop(tid, None)
                    if self.path_to_task_id.get(fp) == tid:
                        self.path_to_task_id.pop(fp, None)
                    pp = task.get("parent_path")
                    fn = task.get("filename")
                    if pp in self.path_map and fn in self.path_map[pp]:
                        del self.path_map[pp][fn]
                        if not self.path_map[pp]:
                            del self.path_map[pp]

            expired_batches = [
                bid for bid, b in self.batches.items()
                if b.get("created_at", 0) < cutoff
            ]
            for bid in expired_batches:
                self.batches.pop(bid, None)

    def check_active_tasks(self, file_paths):
        """
        检查给定文件路径列表中是否有任务处于排队(wait)或执行中(running)状态。
        返回: (has_active: bool, active_count: int, sample_filenames: list[str])
        """
        if not file_paths:
            return False, 0, []
        self._prune_expired()
        active_filenames = []
        with self._lock:
            for raw_fp in file_paths:
                fp = os.path.normpath(raw_fp)
                task = self.file_tasks.get(fp)
                if task and task.get("state") in ("wait", "running"):
                    active_filenames.append(task.get("filename") or os.path.basename(fp))
        return len(active_filenames) > 0, len(active_filenames), active_filenames[:5]

    def init_batch(self, batch_id, items, task_type="manual_update"):
        self._prune_expired()
        now = time.time()
        total = len(items)
        bid = str(batch_id)

        with self._lock:
            self.batches[bid] = {
                "batch_id": bid,
                "total": total,
                "finished": 0,
                "success": 0,
                "failed": 0,
                "is_done": False if total > 0 else True,
                "task_type": task_type,
                "created_at": now
            }

            for item in items:
                raw_fp = item.get("file_full_path", "")
                fp = os.path.normpath(raw_fp)
                pp = os.path.normpath(os.path.dirname(fp))
                fn = os.path.basename(fp)
                sn = item.get("song_name") or (".".join(fn.split(".")[:-1]) if fn else "")
                art = item.get("artist") or ""

                if fp in self.file_tasks:
                    task_obj = self.file_tasks[fp]
                    task_obj["batch_id"] = bid
                    task_obj["parent_path"] = pp
                    task_obj["filename"] = fn
                    task_obj["state"] = "wait"
                    task_obj["extra"] = ""
                    task_obj["tag_source"] = task_type
                    task_obj["updated_at"] = now
                    if sn:
                        task_obj["song_name"] = sn
                    if art:
                        task_obj["artist_name"] = art
                    tid = task_obj["id"]
                else:
                    tid = self._id_counter
                    self._id_counter += 1
                    task_obj = {
                        "id": tid,
                        "batch_id": bid,
                        "full_path": fp,
                        "parent_path": pp,
                        "filename": fn,
                        "song_name": sn,
                        "artist_name": art,
                        "state": "wait",
                        "extra": "",
                        "tag_source": task_type,
                        "created_at": now,
                        "updated_at": now
                    }
                    self.file_tasks[fp] = task_obj
                    self.tasks[tid] = task_obj

                self.path_to_task_id[fp] = tid
                if pp not in self.path_map:
                    self.path_map[pp] = {}
                self.path_map[pp][fn] = tid

                item["task_id"] = tid

        self.publish_event("task_batch", {
            "batch_id": bid,
            "total": total,
            "finished": 0,
            "success": 0,
            "failed": 0,
            "percentage": 0.0,
            "is_done": False if total > 0 else True,
            "task_type": task_type
        })

    def update_item(self, full_path, state, extra="", title="", artist="", task_id=None, meta=None):
        now = time.time()
        fp = os.path.normpath(full_path)
        pp = os.path.normpath(os.path.dirname(fp))
        fn = os.path.basename(fp)

        batch_event = None
        song_name = ""
        batch_id = None

        with self._lock:
            task = None
            if fp in self.file_tasks:
                task = self.file_tasks[fp]
            elif task_id and int(task_id) in self.tasks:
                task = self.tasks[int(task_id)]
            elif fp in self.path_to_task_id:
                tid = self.path_to_task_id[fp]
                task = self.tasks.get(tid)

            effective_title = title or (meta.get("title") if isinstance(meta, dict) else "")
            effective_artist = artist or (meta.get("artist") if isinstance(meta, dict) else "")

            if task:
                tid = task["id"]
                batch_id = task.get("batch_id")
                song_name = effective_title or task.get("song_name") or fn
                task["state"] = state
                task["extra"] = extra
                task["updated_at"] = now
                if effective_title:
                    task["song_name"] = effective_title
                if effective_artist:
                    task["artist_name"] = effective_artist
            else:
                tid = self._id_counter
                self._id_counter += 1
                batch_id = "manual"
                song_name = effective_title or fn
                task = {
                    "id": tid,
                    "batch_id": "manual",
                    "full_path": fp,
                    "parent_path": pp,
                    "filename": fn,
                    "song_name": song_name,
                    "artist_name": effective_artist or "",
                    "state": state,
                    "extra": extra,
                    "tag_source": "manual_update",
                    "created_at": now,
                    "updated_at": now
                }
                self.file_tasks[fp] = task
                self.tasks[tid] = task
                self.path_to_task_id[fp] = tid
                if pp not in self.path_map:
                    self.path_map[pp] = {}
                self.path_map[pp][fn] = tid

            # 统计并更新批次进度
            if batch_id and batch_id != "manual" and batch_id in self.batches:
                b = self.batches[batch_id]
                batch_tasks = [t for t in self.file_tasks.values() if t.get("batch_id") == batch_id]
                tot = b["total"] or len(batch_tasks)
                fin = sum(1 for t in batch_tasks if t.get("state") in ("success", "failed"))
                suc = sum(1 for t in batch_tasks if t.get("state") == "success")
                fai = sum(1 for t in batch_tasks if t.get("state") == "failed")
                is_done = fin >= tot

                b["finished"] = fin
                b["success"] = suc
                b["failed"] = fai
                b["is_done"] = is_done
                pct = round((fin / tot * 100), 1) if tot > 0 else 100.0

                batch_event = {
                    "batch_id": batch_id,
                    "total": tot,
                    "finished": fin,
                    "success": suc,
                    "failed": fai,
                    "percentage": pct,
                    "is_done": is_done
                }

        if batch_event:
            self.publish_event("task_batch", batch_event)

        cover_url = f"/api/music_cover/?file_path={quote(pp)}&file_name={quote(fn)}&t={int(now * 1000)}"
        item_event = {
            "task_id": tid,
            "batch_id": batch_id,
            "full_path": fp,
            "parent_path": pp,
            "filename": fn,
            "song_name": song_name or fn,
            "state": state,
            "extra": extra,
            "cover_url": cover_url,
            "updated_at": now
        }
        if meta and isinstance(meta, dict):
            item_event["meta"] = {
                "title": meta.get("title", ""),
                "artist": meta.get("artist", ""),
                "album": meta.get("album", ""),
                "albumartist": meta.get("albumartist", ""),
                "genre": meta.get("genre", ""),
                "year": meta.get("year", ""),
                "has_lyrics": meta.get("has_lyrics", False),
                "has_cover": meta.get("has_cover", True),
                "cover_url": meta.get("cover_url") or cover_url,
                "filename": meta.get("filename", fn),
                "path": meta.get("path", fp)
            }
        self.publish_event("task_item", item_event)

    def get_active_path_states(self, parent_path, filenames=None):
        self._prune_expired()
        norm_parent = os.path.normpath(parent_path)
        cutoff = time.time() - TTL_SECONDS
        result = {}
        with self._lock:
            if filenames is not None:
                for fn in filenames:
                    fp = os.path.normpath(os.path.join(norm_parent, fn))
                    task = self.file_tasks.get(fp)
                    if task and task.get("updated_at", 0) >= cutoff:
                        result[fn] = {
                            "state": task.get("state", "none"),
                            "extra": task.get("extra", ""),
                            "song_name": task.get("song_name", fn)
                        }
            else:
                for fp, task in self.file_tasks.items():
                    if task.get("parent_path") == norm_parent and task.get("updated_at", 0) >= cutoff:
                        fn = task.get("filename")
                        if fn:
                            result[fn] = {
                                "state": task.get("state", "none"),
                                "extra": task.get("extra", ""),
                                "song_name": task.get("song_name", fn)
                            }
        return result

    def get_batch_progress(self, batch_id, include_records=False):
        bid = str(batch_id)
        with self._lock:
            if bid in self.batches:
                b = self.batches[bid]
                tot = b["total"]
                fin = b["finished"]
                pct = round((fin / tot * 100), 1) if tot > 0 else 100.0
                res = {
                    "batch_id": bid,
                    "total": tot,
                    "finished": fin,
                    "success": b["success"],
                    "failed": b["failed"],
                    "is_done": b["is_done"],
                    "percentage": pct,
                    "task_type": b.get("task_type", "manual_update")
                }
                if include_records:
                    rows = [t for t in self.file_tasks.values() if t.get("batch_id") == bid]
                    res["records"] = {t["filename"]: {"state": t["state"], "extra": t.get("extra", "")} for t in rows}
                return res
        return None

    def get_task_records(self, page=1, page_size=20, state="", batch="", search=""):
        self._prune_expired()
        cutoff = time.time() - TTL_SECONDS
        with self._lock:
            filtered = []
            for task in self.file_tasks.values():
                if task.get("updated_at", 0) < cutoff:
                    continue
                if state:
                    if state in ('running', 'active', 'wait_and_running'):
                        if task.get("state") not in ('running', 'wait'):
                            continue
                    elif task.get("state") != state:
                        continue
                if batch and task.get("batch_id") != str(batch):
                    continue
                if search:
                    s = search.lower()
                    if (s not in (task.get("song_name") or "").lower() and
                        s not in (task.get("filename") or "").lower() and
                        s not in (task.get("extra") or "").lower()):
                        continue
                filtered.append(task)

            filtered.sort(key=lambda x: x["id"], reverse=True)
            total_count = len(filtered)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            page_items = filtered[start_idx:end_idx]

            formatted = []
            for item in page_items:
                ts = item.get("updated_at") or item.get("created_at") or time.time()
                formatted.append({
                    "id": item["id"],
                    "batch": item["batch_id"],
                    "full_path": item["full_path"],
                    "parent_path": item["parent_path"],
                    "filename": item["filename"],
                    "song_name": item["song_name"],
                    "artist": item.get("artist_name", ""),
                    "state": item["state"],
                    "extra": item.get("extra", ""),
                    "tag_source": item.get("tag_source", "manual_update"),
                    "batch_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                })
            return {"items": formatted, "count": total_count}

    def get_stats(self):
        self._prune_expired()
        cutoff = time.time() - TTL_SECONDS
        with self._lock:
            total = 0
            success = 0
            failed = 0
            running = 0
            wait = 0
            batches_set = set()
            for task in self.file_tasks.values():
                if task.get("updated_at", 0) < cutoff:
                    continue
                total += 1
                st = task.get("state")
                if st == "success":
                    success += 1
                elif st == "failed":
                    failed += 1
                elif st == "running":
                    running += 1
                elif st == "wait":
                    wait += 1
                if task.get("batch_id") and task.get("batch_id") != "manual":
                    batches_set.add(task.get("batch_id"))

            recent_batches = sorted(list(batches_set), reverse=True)[:10]
            return {
                "total": total,
                "failed": failed,
                "success": success,
                "running": running,
                "wait": wait,
                "batches": recent_batches
            }

    def clear_tasks(self, batch=None, state=None):
        with self._lock:
            if not batch and not state:
                self.file_tasks.clear()
                self.tasks.clear()
                self.batches.clear()
                self.path_to_task_id.clear()
                self.path_map.clear()
                return True

            tids_to_remove = []
            for tid, t in list(self.tasks.items()):
                if batch and state:
                    if t.get("batch_id") == str(batch) and t.get("state") == state:
                        tids_to_remove.append(tid)
                elif batch:
                    if t.get("batch_id") == str(batch):
                        tids_to_remove.append(tid)
                elif state:
                    if t.get("state") == state:
                        tids_to_remove.append(tid)

            if batch and not state:
                self.batches.pop(str(batch), None)

            for tid in tids_to_remove:
                task = self.tasks.pop(tid, None)
                if task:
                    fp = task.get("full_path")
                    if fp:
                        self.file_tasks.pop(fp, None)
                        if self.path_to_task_id.get(fp) == tid:
                            self.path_to_task_id.pop(fp, None)
                    pp = task.get("parent_path")
                    fn = task.get("filename")
                    if pp in self.path_map and fn in self.path_map[pp]:
                        del self.path_map[pp][fn]
                        if not self.path_map[pp]:
                            del self.path_map[pp]
        return True

    def retry_single(self, record_id):
        with self._lock:
            task = self.tasks.get(int(record_id))
            if not task:
                return None
            task["state"] = "wait"
            task["extra"] = ""
            task["updated_at"] = time.time()
            return dict(task)

    def get_pending_tasks(self, batch=None, limit=2000):
        with self._lock:
            results = []
            for task in self.file_tasks.values():
                if task.get("state") == "wait":
                    if batch and task.get("batch_id") != str(batch):
                        continue
                    results.append(dict(task))
                    if len(results) >= limit:
                        break
            return results

    def publish_event(self, event_type, payload):
        with self._lock:
            eid = self._event_counter
            self._event_counter += 1
            subs = list(self.subscribers)

        msg = {"id": eid, "event": event_type, "data": json.dumps(payload)}
        for q in subs:
            try:
                q.put_nowait(msg)
            except Exception:
                pass

    def subscribe_events(self, last_event_id=0):
        q = queue.Queue(maxsize=1000)
        with self._lock:
            self.subscribers.add(q)

        # 首包立即建立连接
        yield "event: ping\ndata: {\"connected\": true}\n\n"
        last_ping = time.time()

        try:
            while True:
                try:
                    item = q.get(timeout=1.0)
                    eid = item.get("id")
                    etype = item.get("event")
                    p_str = item.get("data")
                    yield f"id: {eid}\nevent: {etype}\ndata: {p_str}\n\n"
                except queue.Empty:
                    pass

                now = time.time()
                if now - last_ping >= 15:
                    last_ping = now
                    yield "event: ping\ndata: {}\n\n"
        finally:
            with self._lock:
                self.subscribers.discard(q)


class RedisTaskStore(BaseTaskStore):
    """
    当环境配置了 Redis (REDIS_HOST) 时的原生 Redis 存储实现
    """
    def __init__(self, redis_client):
        self.r = redis_client
        logger.info("Initialized RedisTaskStore.")

    def _batch_key(self, batch_id):
        return f"mt:batch:{batch_id}"

    def _item_key(self, full_path):
        return f"mt:item:{os.path.normpath(full_path)}"

    def check_active_tasks(self, file_paths):
        if not file_paths:
            return False, 0, []
        active_filenames = []
        pipe = self.r.pipeline()
        for raw_fp in file_paths:
            fp = os.path.normpath(raw_fp)
            pipe.hget(self._item_key(fp), "state")
        states = pipe.execute()
        for raw_fp, st in zip(file_paths, states):
            st_str = st.decode() if isinstance(st, bytes) else (st or "")
            if st_str in ("wait", "running"):
                active_filenames.append(os.path.basename(raw_fp))
        return len(active_filenames) > 0, len(active_filenames), active_filenames[:5]

    def init_batch(self, batch_id, items, task_type="manual_update"):
        now = time.time()
        total = len(items)
        b_key = self._batch_key(batch_id)
        pipe = self.r.pipeline()
        pipe.hset(b_key, mapping={
            "batch_id": str(batch_id),
            "total": total,
            "finished": 0,
            "success": 0,
            "failed": 0,
            "is_done": 1 if total == 0 else 0,
            "task_type": task_type,
            "created_at": now
        })
        pipe.expire(b_key, TTL_SECONDS)

        for item in items:
            fp = os.path.normpath(item.get("file_full_path", ""))
            i_key = self._item_key(fp)
            fn = os.path.basename(fp)
            sn = item.get("song_name") or (".".join(fn.split(".")[:-1]) if fn else "")
            pipe.hset(i_key, mapping={
                "batch_id": str(batch_id),
                "full_path": fp,
                "parent_path": os.path.dirname(fp),
                "filename": fn,
                "song_name": sn,
                "artist_name": item.get("artist") or "",
                "state": "wait",
                "extra": "",
                "tag_source": task_type,
                "created_at": now,
                "updated_at": now
            })
            pipe.expire(i_key, TTL_SECONDS)
        pipe.execute()

        self.publish_event("task_batch", {
            "batch_id": str(batch_id),
            "total": total,
            "finished": 0,
            "success": 0,
            "failed": 0,
            "percentage": 0.0,
            "is_done": False if total > 0 else True,
            "task_type": task_type
        })

    def update_item(self, full_path, state, extra="", title="", artist="", task_id=None, meta=None):
        now = time.time()
        fp = os.path.normpath(full_path)
        i_key = self._item_key(fp)
        fn = os.path.basename(fp)
        parent_path = os.path.dirname(fp)

        raw = self.r.hgetall(i_key)
        batch_id = raw.get(b"batch_id", b"").decode() if raw else "manual"
        song_name = title or (raw.get(b"song_name", b"").decode() if raw else fn)

        pipe = self.r.pipeline()
        pipe.hset(i_key, mapping={
            "full_path": fp,
            "parent_path": parent_path,
            "filename": fn,
            "song_name": song_name,
            "artist_name": artist or (raw.get(b"artist_name", b"").decode() if raw else ""),
            "state": state,
            "extra": extra,
            "updated_at": now
        })
        pipe.expire(i_key, TTL_SECONDS)
        pipe.execute()

        # 更新批次进度
        if batch_id and batch_id != "manual":
            b_key = self._batch_key(batch_id)
            b_raw = self.r.hgetall(b_key)
            if b_raw:
                tot = int(b_raw.get(b"total", 0))
                fin = self.r.hincrby(b_key, "finished", 1)
                if state == "success":
                    suc = self.r.hincrby(b_key, "success", 1)
                    fai = int(b_raw.get(b"failed", 0))
                else:
                    suc = int(b_raw.get(b"success", 0))
                    fai = self.r.hincrby(b_key, "failed", 1)
                is_done = fin >= tot
                self.r.hset(b_key, "is_done", 1 if is_done else 0)
                pct = round((fin / tot * 100), 1) if tot > 0 else 100.0

                self.publish_event("task_batch", {
                    "batch_id": batch_id,
                    "total": tot,
                    "finished": fin,
                    "success": suc,
                    "failed": fai,
                    "percentage": pct,
                    "is_done": is_done
                })

        cover_url = f"/api/music_cover/?file_path={quote(parent_path)}&file_name={quote(fn)}&t={int(now * 1000)}"
        self.publish_event("task_item", {
            "full_path": fp,
            "parent_path": parent_path,
            "filename": fn,
            "song_name": song_name,
            "state": state,
            "extra": extra,
            "cover_url": cover_url,
            "updated_at": now
        })

    def get_active_path_states(self, parent_path, filenames=None):
        if not filenames:
            return {}
        norm_parent = os.path.normpath(parent_path)
        pipe = self.r.pipeline()
        for fn in filenames:
            fp = os.path.normpath(os.path.join(norm_parent, fn))
            pipe.hgetall(self._item_key(fp))
        records = pipe.execute()

        result = {}
        cutoff = time.time() - TTL_SECONDS
        for fn, raw in zip(filenames, records):
            if raw:
                updated_at = float(raw.get(b"updated_at", 0))
                if updated_at >= cutoff:
                    result[fn] = {
                        "state": raw.get(b"state", b"none").decode(),
                        "extra": raw.get(b"extra", b"").decode(),
                        "song_name": raw.get(b"song_name", b"").decode()
                    }
        return result

    def get_batch_progress(self, batch_id, include_records=False):
        b_key = self._batch_key(batch_id)
        raw = self.r.hgetall(b_key)
        if raw:
            tot = int(raw.get(b"total", 0))
            fin = int(raw.get(b"finished", 0))
            pct = round((fin / tot * 100), 1) if tot > 0 else 100.0
            res = {
                "batch_id": batch_id,
                "total": tot,
                "finished": fin,
                "success": int(raw.get(b"success", 0)),
                "failed": int(raw.get(b"failed", 0)),
                "is_done": bool(int(raw.get(b"is_done", 0))),
                "percentage": pct,
                "task_type": raw.get(b"task_type", b"manual_update").decode()
            }
            if include_records:
                res["records"] = {}
            return res
        return None

    def get_task_records(self, page=1, page_size=20, state="", batch="", search=""):
        return {"items": [], "count": 0}

    def get_stats(self):
        return {"total": 0, "failed": 0, "success": 0, "running": 0, "wait": 0, "batches": []}

    def clear_tasks(self, batch=None, state=None):
        return True

    def retry_single(self, record_id):
        return None

    def get_pending_tasks(self, batch=None, limit=2000):
        return []

    def publish_event(self, event_type, payload):
        try:
            self.r.publish("music_tag_events", json.dumps({"event_type": event_type, "payload": payload}))
        except Exception as e:
            logger.error(f"Failed to publish to redis: {e}")

    def subscribe_events(self, last_event_id=0):
        pubsub = self.r.pubsub()
        pubsub.subscribe("music_tag_events")
        yield "event: ping\ndata: {\"connected\": true}\n\n"
        last_ping = time.time()
        try:
            while True:
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    raw_data = json.loads(msg["data"].decode())
                    etype = raw_data.get("event_type", "task_item")
                    p_str = json.dumps(raw_data.get("payload", {}))
                    yield f"event: {etype}\ndata: {p_str}\n\n"

                now = time.time()
                if now - last_ping >= 15:
                    last_ping = now
                    yield "event: ping\ndata: {}\n\n"
        finally:
            pubsub.unsubscribe("music_tag_events")


def create_task_store():
    """工厂方法：优先使用纯 Python 堆内存任务中心，配置了 REDIS_HOST 则使用 Redis"""
    redis_host = os.getenv("REDIS_HOST") or getattr(settings, "REDIS_HOST", None)
    if redis_host and redis_host not in ["127.0.0.1", "localhost", "redis"]:
        try:
            import redis
            client = redis.Redis(host=redis_host, port=6379, db=2, socket_timeout=1.0)
            if client.ping():
                return RedisTaskStore(client)
        except Exception:
            pass

    return PureMemoryTaskStore()


# 单例导出
task_store = create_task_store()
