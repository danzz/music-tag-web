import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)


class AsyncTaskExecutor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(AsyncTaskExecutor, cls).__new__(cls)
                    cls._instance._init_executor()
        return cls._instance

    def _init_executor(self):
        # 写入磁盘的专用工作线程池（默认固定 4 线程，避免机械硬盘磁头争抢寻道）
        write_workers = int(getattr(settings, "WRITE_WORKER_NUM", 4))
        self.executor = ThreadPoolExecutor(
            max_workers=write_workers,
            thread_name_prefix="music_tag_disk_worker"
        )
        self.batches = {}
        self.status_lock = threading.Lock()
        logger.info(f"Initialized AsyncTaskExecutor disk write pool with {write_workers} workers.")

    def init_batch(self, batch_id, total, task_type="auto_tag"):
        with self.status_lock:
            self.batches[str(batch_id)] = {
                "batch_id": str(batch_id),
                "total": total,
                "finished": 0,
                "success": 0,
                "failed": 0,
                "is_done": False if total > 0 else True,
                "task_type": task_type
            }

    def _task_done_callback(self, batch_id, success):
        batch_id_str = str(batch_id)
        with self.status_lock:
            if batch_id_str in self.batches:
                data = self.batches[batch_id_str]
                data["finished"] += 1
                if success:
                    data["success"] += 1
                else:
                    data["failed"] += 1
                if data["finished"] >= data["total"]:
                    data["is_done"] = True

    def submit_batch(self, batch_id, items, worker_func, *args, **kwargs):
        """
        提交一个批次任务到线程池异步并发执行。
        worker_func 应该返回 True 表示成功，False 表示失败。
        """
        total = len(items)
        task_type = kwargs.pop("task_type", "batch_task")
        self.init_batch(batch_id, total, task_type)

        def run_single(item):
            close_old_connections()
            success = False
            try:
                success = worker_func(item, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error executing worker_func for item {item}: {e}", exc_info=True)
                success = False
            finally:
                self._task_done_callback(batch_id, bool(success))
                close_old_connections()

        for item in items:
            self.executor.submit(run_single, item)

    def get_progress(self, batch_id):
        batch_id_str = str(batch_id)
        with self.status_lock:
            if batch_id_str in self.batches:
                info = dict(self.batches[batch_id_str])
                total = info["total"]
                finished = info["finished"]
                info["percentage"] = round((finished / total * 100), 1) if total > 0 else 100.0
                return info
        return None


# 单例导出
executor = AsyncTaskExecutor()

