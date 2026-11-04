import functools
import logging
import random
import threading
import time
from django.db import connection, close_old_connections, OperationalError

logger = logging.getLogger(__name__)

# 全局写锁，仅在 SQLite 引擎下生效，防止高并发下 database is locked
_sqlite_write_lock = threading.Lock()


def is_sqlite():
    """判断当前默认数据库是否为 SQLite"""
    try:
        return connection.vendor == 'sqlite'
    except Exception:
        return False


def setup_sqlite_pragma():
    """为 SQLite 连接配置 WAL 模式与忙等待超时"""
    if is_sqlite():
        try:
            with connection.cursor() as cursor:
                cursor.execute('PRAGMA journal_mode = WAL;')
                cursor.execute('PRAGMA synchronous = NORMAL;')
                cursor.execute('PRAGMA busy_timeout = 10000;')
        except Exception as e:
            logger.warning(f"Failed to configure SQLite PRAGMA: {e}")


def db_write_safe(func):
    """
    高并发数据库写入安全装饰器：
    1. 在子线程中自动关闭旧连接 (close_old_connections)
    2. SQLite 模式下加轻量级写锁互斥
    3. 支持遇到 database is locked 时自动退避重试 (最多5次)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        close_old_connections()
        max_retries = 5
        use_lock = is_sqlite()

        for attempt in range(max_retries):
            try:
                if use_lock:
                    with _sqlite_write_lock:
                        return func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    sleep_time = (0.05 * (2 ** attempt)) + random.uniform(0.01, 0.05)
                    logger.warning(f"Database locked, retrying in {sleep_time:.2f}s (attempt {attempt + 1}/{max_retries})...")
                    close_old_connections()
                    time.sleep(sleep_time)
                else:
                    raise
            except Exception:
                raise
            finally:
                close_old_connections()

    return wrapper

