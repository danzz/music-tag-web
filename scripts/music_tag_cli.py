#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Music Tag Web - Agent Harness CLI & Client SDK
专为外部 Agent Harness (如 Antigravity, Claude Code, Cursor, OpenHands 等) 打造的高性能交互桥梁。
支持通过高性能并发预规划 (auto-plan) 与标准异步任务模式 (task mode) 秒级完成巡检与打标。
"""

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


class MusicTagClient:
    """Music Tag Web API 客户端封装 (支持长连接与并发操作)"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 300,
    ):
        self.base_url = (
            base_url
            or os.environ.get("MUSIC_TAG_BASE_URL")
            or "http://127.0.0.1:18002"
        ).rstrip("/")
        self.username = username or os.environ.get("MUSIC_TAG_USERNAME") or "admin"
        self.password = password or os.environ.get("MUSIC_TAG_PASSWORD") or "admin"
        self.token = token or os.environ.get("MUSIC_TAG_TOKEN")
        self.timeout = timeout
        # 安装全局 opener 支持 HTTP Keep-Alive 连接复用
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        urllib.request.install_opener(opener)

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        auth_required: bool = True,
    ) -> Dict[str, Any]:
        """发起 HTTP 请求并自动处理 JWT 鉴权"""
        if auth_required and not self.token:
            self.login()

        url = f"{self.base_url}{endpoint}"
        if params:
            query_str = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            url = f"{url}?{query_str}"

        headers = {
            "Content-Type": "application/json",
            "Connection": "keep-alive",
        }
        if self.token:
            headers["Authorization"] = f"JWT {self.token}"

        req_data = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(
            url, data=req_data, headers=headers, method=method.upper()
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_text = resp.read().decode("utf-8")
                return json.loads(resp_text)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("msg") or err_json.get("message") or err_body
            except Exception:
                msg = err_body
            raise RuntimeError(f"HTTP {e.code} Error from {endpoint}: {msg}")
        except Exception as e:
            raise RuntimeError(f"Network error calling {endpoint}: {str(e)}")

    def login(self) -> str:
        """登录并获取 JWT Token"""
        res = self._request(
            "POST",
            "/api/token/",
            {"username": self.username, "password": self.password},
            auth_required=False,
        )
        token = res.get("token") or res.get("data", {}).get("token")
        if not token:
            raise RuntimeError(f"登录失败，无法获取 Token: {res}")
        self.token = token
        return token

    # -------------------------------------------------------------------------
    # 数据查询与巡检能力 (Read-Only)
    # -------------------------------------------------------------------------

    def list_dir(self, file_path: str, only_dir: bool = False) -> List[Dict[str, Any]]:
        """浏览目录结构"""
        res = self._request(
            "POST",
            "/api/file_list/",
            {"file_path": file_path, "only_dir": only_dir},
        )
        return res.get("data", [])

    def get_music_list(
        self, file_path: str, page: int = 1, page_size: int = 500
    ) -> Dict[str, Any]:
        """获取指定目录下的音乐文件及其 ID3 标签与元数据"""
        res = self._request(
            "POST",
            "/api/folder_music_list/",
            {"file_path": file_path, "page": page, "page_size": page_size},
        )
        return res.get("data", {"items": [], "total": 0})

    def search_online(
        self,
        title: str,
        resource: str = "kugou",
        full_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """在线检索音乐元数据候选 (kugou / qmusic / netease / migu / smart_tag / acoustid)"""
        res = self._request(
            "POST",
            "/api/fetch_id3_by_title/",
            {
                "title": title,
                "resource": resource,
                "full_path": full_path or "",
            },
        )
        return res.get("data", [])

    def fetch_lyric(self, song_id: str, resource: str = "qmusic") -> str:
        """获取在线歌词"""
        res = self._request(
            "POST",
            "/api/fetch_lyric/",
            {"song_id": song_id, "resource": resource},
        )
        return res.get("data") or ""

    def get_task_status(
        self, batch_id: str, include_records: bool = False
    ) -> Dict[str, Any]:
        """查询异步批次任务执行进度"""
        res = self._request(
            "GET",
            "/api/batch_progress/",
            params={"batch": batch_id, "include_records": "true" if include_records else "false"},
        )
        return res.get("data", {})

    def get_task_records(
        self,
        batch: Optional[str] = None,
        state: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """查询任务记录列表"""
        res = self._request(
            "GET",
            "/api/record/",
            params={
                "batch": batch,
                "state": state,
                "page": page,
                "page_size": page_size,
                "search": search,
            },
        )
        return res.get("data", {"items": [], "total": 0})

    def get_stats(self) -> Dict[str, Any]:
        """获取任务统计"""
        res = self._request("GET", "/api/record/stats/")
        return res.get("data", {})

    # -------------------------------------------------------------------------
    # 异步任务提交能力 (Write - Task Mode)
    # -------------------------------------------------------------------------

    def submit_batch_tags(
        self,
        file_full_path: str,
        select_data: List[Dict[str, Any]],
        music_info: Optional[Dict[str, Any]] = None,
        apply_to_all: bool = False,
    ) -> Dict[str, Any]:
        """提交批量标签更新异步任务"""
        payload = {
            "file_full_path": file_full_path,
            "select_data": select_data,
            "music_info": music_info or {},
            "apply_to_all": apply_to_all,
        }
        res = self._request("POST", "/api/batch_update_id3/", payload)
        return res.get("data", {})

    def submit_auto_scrape(
        self,
        file_full_path: str,
        select_data: List[Dict[str, Any]],
        sources: Optional[List[str]] = None,
        select_mode: str = "hard",
    ) -> Dict[str, Any]:
        """提交多源自动刮削异步任务"""
        payload = {
            "file_full_path": file_full_path,
            "select_data": select_data,
            "music_info": {
                "source_list": sources or ["kugou", "qmusic", "netease", "migu"],
                "select_mode": select_mode,
            },
        }
        res = self._request("POST", "/api/batch_auto_update_id3/", payload)
        return res.get("data", {})

    def submit_tidy_folder(
        self,
        root_path: str,
        file_full_path: str,
        first_dir: str,
        second_dir: str = "",
        select_data: Optional[List[Dict[str, Any]]] = None,
        apply_to_all: bool = True,
        move_lrc: bool = True,
        conflict_action: str = "skip",
        clean_empty_dir: bool = False,
    ) -> Dict[str, Any]:
        """提交曲库文件夹归档整理异步任务"""
        payload = {
            "root_path": root_path,
            "file_full_path": file_full_path,
            "first_dir": first_dir,
            "second_dir": second_dir,
            "select_data": select_data or [],
            "apply_to_all": apply_to_all,
            "move_lrc": move_lrc,
            "conflict_action": conflict_action,
            "clean_empty_dir": clean_empty_dir,
        }
        res = self._request("POST", "/api/tidy_folder/", payload)
        return res.get("data", {})

    def wait_for_batch(
        self, batch_id: str, poll_interval: float = 0.5, max_wait: float = 60.0
    ) -> Dict[str, Any]:
        """轮询等待批次任务执行完成"""
        start = time.time()
        while time.time() - start < max_wait:
            status = self.get_task_status(batch_id, include_records=True)
            if status.get("is_done", False):
                return status
            time.sleep(poll_interval)
        raise TimeoutError(f"等待批次 {batch_id} 超时 ({max_wait}s)")

    def force_refresh_cache(self, file_path: str = "") -> bool:
        """强制清除缓存并重扫磁盘"""
        res = self._request("POST", "/api/force_refresh_cache/", {"file_path": file_path})
        return res.get("code") in ("200", 200, 0)

    # -------------------------------------------------------------------------
    # 极速批处理预规划与执行 (High Performance Auto-Plan)
    # -------------------------------------------------------------------------

    def auto_plan_course(
        self,
        dir_path: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        得到课程与有声书专属离线极速预规划：
        1. 解析目录名提取讲师/作者与课程/专辑名
        2. 剥离标题与文件名中的各种广告杂质
        3. 自动提取或补全音轨号并格式化补零
        4. 检测目录内本地封面 (cover.jpg/png) 并内嵌
        5. 清空 ID3 中被污染的 comment 描述，统一流派为 Audiobook
        """
        folder_name = os.path.basename(os.path.normpath(dir_path))
        course_meta = parse_course_folder_name(folder_name)
        artist = course_meta.get("artist") or "得到讲师"
        album = course_meta.get("album") or folder_name
        albumartist = course_meta.get("albumartist") or artist

        # 检查目录下是否有本地封面文件
        cover_path = ""
        for c_name in ("cover.jpg", "cover.jpeg", "cover.png", "folder.jpg", "folder.png"):
            try:
                chk_url = f"{self.base_url}/api/music_cover/?file_path={urllib.parse.quote(dir_path)}&file_name={urllib.parse.quote(c_name)}"
                req = urllib.request.Request(chk_url, method="HEAD")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        cover_path = f"{dir_path}/{c_name}"
                        break
            except Exception:
                pass
            if not cover_path and os.path.isfile(os.path.join(dir_path, c_name)):
                cover_path = f"{dir_path}/{c_name}"
                break

        # 自然排序文件列表
        items_sorted = sorted(items, key=lambda x: natural_sort_key(x.get("filename", "")))
        total_files = len(items_sorted)

        plan_list = []
        for idx, it in enumerate(items_sorted, 1):
            fn = it.get("filename", "")
            parsed = parse_course_audio_filename(fn, file_index=idx, total_files=total_files)
            clean_title = parsed["title"]
            track_num = parsed["tracknumber"]

            proposed = {
                "name": fn,
                "title": clean_title,
                "artist": artist,
                "album": album,
                "albumartist": albumartist,
                "tracknumber": str(track_num),
                "discnumber": "1",
                "genre": "Audiobook",
                "comment": "得到音频课程 (已净化)",
                "is_save_lyrics_file": False,
                "is_save_album_cover": False,
            }
            if cover_path:
                proposed["album_img"] = cover_path

            plan_list.append({
                "name": fn,
                "file_full_path": it.get("path"),
                "confidence": "high",
                "reason": f"从目录解析讲师【{artist}】与课程【{album}】，剥离引流广告，生成音轨号 {track_num}",
                "current": {
                    "title": it.get("title"),
                    "artist": it.get("artist"),
                    "album": it.get("album"),
                    "year": it.get("year"),
                    "tracknumber": it.get("tracknumber"),
                    "has_cover": it.get("has_cover"),
                    "has_lrc": it.get("has_lyrics") or it.get("has_lrc"),
                },
                "proposed": proposed,
            })

        return {
            "dir_path": dir_path,
            "mode": "course",
            "summary": {
                "total_in_dir": total_files,
                "needs_curation": total_files,
                "high_confidence": total_files,
                "medium_confidence": 0,
                "low_confidence": 0,
                "detected_artist": artist,
                "detected_album": album,
                "detected_cover": bool(cover_path),
            },
            "plan": plan_list,
        }

    def auto_plan(
        self,
        dir_path: str,
        sources: Optional[List[str]] = None,
        concurrency: int = 8,
        plan_type: str = "auto",
    ) -> Dict[str, Any]:
        """
        全并发一站式预规划：
        - 支持智能自动判断：得到课程 (course) 模式 vs 音乐歌曲 (music) 模式
        - 音乐模式：本地多线程并发多源检索与消歧打分、预取歌词封面
        - 课程模式：极速离线解析目录与文件、剥离广告、规范作者/专辑/音轨号
        """
        m_data = self.get_music_list(dir_path, page=1, page_size=1000)
        items = m_data.get("items", [])
        if not items:
            return {
                "dir_path": dir_path,
                "summary": {"total_in_dir": 0, "needs_curation": 0, "high_confidence": 0, "medium_confidence": 0, "low_confidence": 0},
                "plan": [],
            }

        folder_name = os.path.basename(os.path.normpath(dir_path))
        is_course = (plan_type == "course") or (
            plan_type == "auto" and is_course_folder(folder_name, items)
        )

        if is_course:
            return self.auto_plan_course(dir_path, items)

        # 筛选需要整理的曲目
        to_process = []
        for it in items:
            fn = it.get("filename", "")
            title = (it.get("title") or "").strip()
            artist = (it.get("artist") or "").strip()
            album = (it.get("album") or "").strip()
            has_cov = it.get("has_cover", False)
            has_lrc = it.get("has_lyrics", False) or it.get("has_lrc", False)

            is_dirty = any(re.search(pat, fn, re.IGNORECASE) for pat in DIRTY_PATTERNS)
            if (
                not artist
                or artist == "未知艺术家"
                or not album
                or album == "未知专辑"
                or not has_cov
                or not has_lrc
                or is_dirty
                or title == "Track01"
                or " - " in title
            ):
                to_process.append(it)

        def worker(item: Dict[str, Any]) -> Dict[str, Any]:
            fn = item.get("filename", "")
            parsed = extract_clean_title_and_artist(
                fn, item.get("title", ""), item.get("artist", "")
            )
            q_title = parsed["title"]
            q_artist = parsed["artist"]

            # 通用未知音轨
            if re.match(r"^Track\d+$", q_title, re.IGNORECASE) and not q_artist:
                return {
                    "name": fn,
                    "file_full_path": item.get("path"),
                    "confidence": "low",
                    "reason": "文件名为通用测试音轨且标签空白，安全保留原样",
                    "current": {
                        "title": item.get("title"),
                        "artist": item.get("artist"),
                        "album": item.get("album"),
                        "year": item.get("year"),
                        "has_cover": item.get("has_cover"),
                        "has_lrc": item.get("has_lyrics") or item.get("has_lrc"),
                    },
                    "proposed": None,
                    "candidates": [],
                }

            # 搜索候选
            candidates = []
            query_str = f"{q_artist} {q_title}".strip() if q_artist else q_title
            for src in sources:
                try:
                    cands = self.search_online(query_str, resource=src)
                    for c in cands:
                        c["_source"] = src
                    candidates.extend(cands)
                    if len(candidates) >= 5:
                        break
                except Exception:
                    continue

            # 打分消歧
            scored = []
            for c in candidates:
                sc = score_candidate(c, q_title, q_artist)
                if sc > 0:
                    scored.append((sc, c))
            scored.sort(key=lambda x: x[0], reverse=True)

            if not scored:
                return {
                    "name": fn,
                    "file_full_path": item.get("path"),
                    "confidence": "low",
                    "reason": f"未匹配到在线权威数据 (查询词: {query_str})",
                    "current": {
                        "title": item.get("title"),
                        "artist": item.get("artist"),
                        "album": item.get("album"),
                        "year": item.get("year"),
                        "has_cover": item.get("has_cover"),
                        "has_lrc": item.get("has_lyrics") or item.get("has_lrc"),
                    },
                    "proposed": None,
                    "candidates": [],
                }

            best_score, best_cand = scored[0]
            confidence = (
                "high" if best_score >= 14.0 else ("medium" if best_score >= 8.0 else "low")
            )
            reason = f"匹配至【{best_cand.get('_source')}】《{best_cand.get('name')}》- {best_cand.get('artist')}，收录于正规专辑《{best_cand.get('album')}》"

            # 并发抓取歌词
            lyric_text = ""
            if best_cand.get("id"):
                try:
                    lyric_text = self.fetch_lyric(
                        str(best_cand["id"]), resource=best_cand.get("_source", "qmusic")
                    )
                except Exception:
                    lyric_text = ""

            year_val = str(best_cand.get("year") or "").split("-")[0]

            proposed = {
                "name": fn,
                "title": best_cand.get("name") or q_title,
                "artist": best_cand.get("artist") or q_artist,
                "album": best_cand.get("album") or "未知专辑",
                "albumartist": best_cand.get("artist") or q_artist,
                "year": year_val,
                "genre": item.get("genre") or "Pop",
                "album_img": best_cand.get("album_img") or "",
                "lyrics": lyric_text,
                "is_save_lyrics_file": True,
                "is_save_album_cover": True,
                "comment": "Curated by AI Agent (auto-plan)",
            }

            return {
                "name": fn,
                "file_full_path": item.get("path"),
                "confidence": confidence,
                "reason": reason,
                "current": {
                    "title": item.get("title"),
                    "artist": item.get("artist"),
                    "album": item.get("album"),
                    "year": item.get("year"),
                    "has_cover": item.get("has_cover"),
                    "has_lrc": item.get("has_lyrics") or item.get("has_lrc"),
                },
                "proposed": proposed,
                "candidates_sample": [c for _, c in scored[:3]],
            }

        plan_list = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            plan_list = list(pool.map(worker, to_process))

        high_c = sum(1 for p in plan_list if p["confidence"] == "high")
        med_c = sum(1 for p in plan_list if p["confidence"] == "medium")
        low_c = sum(1 for p in plan_list if p["confidence"] == "low")

        return {
            "dir_path": dir_path,
            "summary": {
                "total_in_dir": len(items),
                "needs_curation": len(to_process),
                "high_confidence": high_c,
                "medium_confidence": med_c,
                "low_confidence": low_c,
            },
            "plan": plan_list,
        }

    def apply_plan(
        self,
        plan_data: Dict[str, Any],
        dir_path: Optional[str] = None,
        only_high_confidence: bool = False,
        wait: bool = True,
    ) -> Dict[str, Any]:
        """一键提交并应用预规划方案"""
        target_dir = dir_path or plan_data.get("dir_path")
        if not target_dir:
            raise ValueError("缺少目标目录 dir_path")

        plan_items = plan_data.get("plan", [])
        select_data = []
        for it in plan_items:
            if not it.get("proposed"):
                continue
            if only_high_confidence and it.get("confidence") != "high":
                continue
            select_data.append(it["proposed"])

        if not select_data:
            return {"batch": None, "total": 0, "message": "无需要执行的更新项"}

        res = self.submit_batch_tags(
            file_full_path=target_dir,
            select_data=select_data,
            apply_to_all=False,
        )
        batch_id = res.get("batch")
        if wait and batch_id:
            final_status = self.wait_for_batch(batch_id)
            self.force_refresh_cache(target_dir)
            return {
                "batch": batch_id,
                "total": len(select_data),
                "status": final_status,
            }
        return {"batch": batch_id, "total": len(select_data)}


# -----------------------------------------------------------------------------
# 启发式诊断与消歧打分工具函数
# -----------------------------------------------------------------------------

def natural_sort_key(text: str):
    """自然排序算法 (如 1, 2, 10 而非 1, 10, 2)"""
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]


COURSE_AD_PATTERNS = [
    r'【[^】]*(?:微信|公众号|关注|免费|更新|加V|QQ|课件|福利|认准|首发|自购|资源)[^】]*】',
    r'\[[^\]]*(?:微信|公众号|关注|免费|更新|加V|QQ|课件|福利|认准|首发|自购|资源)[^\]]*\]',
    r'\([^\)]*(?:微信|公众号|关注|免费|更新|加V|QQ|课件|福利|认准|首发|自购|资源)[^\)]*\)',
    r'（[^）]*(?:微信|公众号|关注|免费|更新|加V|QQ|课件|福利|认准|首发|自购|资源)[^）]*）',
    r'\b(?:www\.[a-zA-Z0-9_\-\.]+\.[a-zA-Z]{2,4})\b',
    r'(?:关注|认准|免费更新|更多资源请加|加微信|买课|更新公众号|微信)[：:\s]*[a-zA-Z0-9_\-]+',
]


def parse_course_folder_name(folder_name: str) -> Dict[str, str]:
    """
    智能解析得到课程目录名：
    - '32_万维钢·精英日课6' -> artist: '万维钢', album: '精英日课6'
    - '刘润·商业洞察力30讲' -> artist: '刘润', album: '商业洞察力30讲'
    - '薛兆丰的经济学课' -> artist: '薛兆丰', album: '经济学课'
    - '05.吴军-谷歌方法论' -> artist: '吴军', album: '谷歌方法论'
    - '[吴伯凡] 认知方法论' -> artist: '吴伯凡', album: '认知方法论'
    """
    s = re.sub(r'^\d+[\._\-\s]+', '', folder_name).strip()

    # 1. 常见模式：括号 [讲师] 课程名 / (讲师) 课程名
    m = re.match(r'^[\[\(【]([^\]\)】]+)[\]\)】]\s*(.*)$', s)
    if m:
        return {"artist": m.group(1).strip(), "album": m.group(2).strip(), "albumartist": m.group(1).strip()}

    # 2. 常见模式：中点 "·" 或 "•"
    if '·' in s or '•' in s:
        parts = re.split(r'[·•]', s, maxsplit=1)
        art, alb = parts[0].strip(), parts[1].strip()
        return {"artist": art, "album": alb, "albumartist": art}

    # 3. 常见模式：横杠 "-" 或下划线 "_"
    if ' - ' in s:
        parts = s.split(' - ', 1)
        art, alb = parts[0].strip(), parts[1].strip()
        return {"artist": art, "album": alb, "albumartist": art}
    elif '-' in s and not s.startswith('-'):
        parts = s.split('-', 1)
        art, alb = parts[0].strip(), parts[1].strip()
        return {"artist": art, "album": alb, "albumartist": art}
    elif '_' in s and not s.startswith('_'):
        parts = s.split('_', 1)
        art, alb = parts[0].strip(), parts[1].strip()
        return {"artist": art, "album": alb, "albumartist": art}

    # 4. 常见模式："xxx的yyy"
    m = re.match(r'^([\u4e00-\u9fa5]{2,4})的(.*)$', s)
    if m:
        art, alb = m.group(1).strip(), m.group(2).strip()
        return {"artist": art, "album": alb, "albumartist": art}

    return {"artist": "得到讲师", "album": s, "albumartist": "得到讲师"}


def parse_course_audio_filename(filename: str, file_index: int = 1, total_files: int = 1) -> Dict[str, Any]:
    """从课程音频文件名中剥离广告，提取音轨号与纯净标题"""
    base = filename.rsplit(".", 1)[0]
    clean_base = base
    for pat in COURSE_AD_PATTERNS:
        clean_base = re.sub(pat, '', clean_base, flags=re.IGNORECASE)

    clean_base = re.sub(
        r'\[(FLAC|MP3|APE|WAV|DSD|Hi-?Res|24bit|16bit|96kHz|128k|320k)[^\]]*\]', '', clean_base, flags=re.IGNORECASE
    )
    clean_base = clean_base.strip()

    track_num = None
    title_part = clean_base

    m1 = re.match(r'^第\s*(\d{1,4})\s*[讲期集回章节节课]?[丨|—\-_、\.\s：:]*(.*)$', clean_base)
    if m1:
        track_num = int(m1.group(1))
        title_part = m1.group(2).strip()

    if track_num is None:
        m2 = re.match(r'^(\d{1,4})[\._\-\s、丨|：:]+(.*)$', clean_base)
        if m2:
            track_num = int(m2.group(1))
            title_part = m2.group(2).strip()

    if track_num is None:
        m3 = re.match(r'^(\d{1,4})(.*)$', clean_base)
        if m3 and len(m3.group(2)) > 0:
            track_num = int(m3.group(1))
            title_part = m3.group(2).strip()

    if track_num is None:
        track_num = file_index

    track_str = f"{track_num:03d}" if total_files >= 100 else f"{track_num:02d}"
    clean_title = re.sub(r'^[丨|—\-_、\.\s：:]+', '', title_part).strip()
    if not clean_title:
        clean_title = clean_base

    return {"tracknumber": track_str, "title": clean_title}


def is_course_folder(folder_name: str, items: List[Dict[str, Any]]) -> bool:
    """智能启发式判断是否属于得到/有声书课程目录"""
    if '·' in folder_name or '•' in folder_name:
        return True
    course_keywords = ["课", "讲", "有声书", "专栏", "音频", "得到", "精英日课", "方法论", "通识", "商学院", "大课"]
    if any(kw in folder_name for kw in course_keywords):
        return True
    for it in items[:5]:
        fn = it.get("filename", "")
        if re.search(r'第\s*\d+\s*[讲期集节]', fn):
            return True
    return False


DIRTY_PATTERNS = [
    r"\[(FLAC|MP3|APE|WAV|DSD|Hi-?Res|24bit|16bit|96kHz|44\.1kHz|192kHz)[^\]]*\]",
    r"【(无损|首发|自购|压制|分轨|精选|高解析)[^】]*】",
    r"_(128|192|256|320)k\b",
    r"\b(www\.[a-zA-Z0-9_\-\.]+\.[a-zA-Z]{2,4})\b",
    r"^\d{1,4}\s*[\-\._\s]\s*",
]


def extract_clean_title_and_artist(
    filename: str, current_title: str = "", current_artist: str = ""
) -> Dict[str, str]:
    """从杂乱文件名与现有标签中解析干净的标题与艺术家"""
    base = filename.rsplit(".", 1)[0]
    clean_base = re.sub(
        r"\[(FLAC|MP3|APE|WAV|DSD|Hi-?Res|24bit|16bit|96kHz|44\.1kHz|192kHz|无损|高品质)[^\]]*\]",
        "",
        base,
        flags=re.IGNORECASE,
    )
    clean_base = re.sub(
        r"【(无损|首发|自购|压制|分轨|精选|高解析)[^】]*】", "", clean_base, flags=re.IGNORECASE
    )
    clean_base = re.sub(r"_(128|192|256|320)k\b", "", clean_base, flags=re.IGNORECASE)
    clean_base = re.sub(
        r"\b(www\.[a-zA-Z0-9_\-\.]+\.[a-zA-Z]{2,4})\b", "", clean_base, flags=re.IGNORECASE
    )
    clean_base = re.sub(r"^\d{1,4}\s*[\-\._\s]\s*", "", clean_base).strip()

    title = current_title.strip() if current_title else ""
    artist = current_artist.strip() if current_artist else ""

    if title:
        title = re.sub(r"\[[^\]]*\]|【[^】]*】", "", title).strip()

    if " - " in clean_base:
        parts = clean_base.split(" - ", 1)
        part1, part2 = parts[0].strip(), parts[1].strip()
        # 如果文件名清晰包含了 "歌手 - 歌名"
        if not artist or artist in ("未知艺术家", "未知", "TestArtist", "admin") or part1.lower() in clean_base.lower():
            artist = part1
        if not title or title in ("Track01", "未知标题", clean_base, base) or " - " in title:
            title = part2
    elif not title or title in ("Track01", "未知标题", "未知"):
        title = clean_base

    return {"title": title, "artist": artist, "clean_base": clean_base}


def score_candidate(cand: Dict[str, Any], query_title: str, query_artist: str) -> float:
    """智能候选消歧打分"""
    name = (cand.get("name") or "").strip().lower()
    artist = (cand.get("artist") or "").strip().lower()
    album = (cand.get("album") or "").strip().lower()
    q_title = query_title.strip().lower()
    q_artist = query_artist.strip().lower()

    score = 0.0
    if name == q_title:
        score += 10.0
    elif q_title in name or name in q_title:
        score += 5.0
    else:
        return 0.0

    if q_artist:
        if artist == q_artist:
            score += 10.0
        elif q_artist in artist or artist in q_artist:
            score += 6.0
        else:
            score -= 8.0

    is_live = any(kw in name or kw in album for kw in ["live", "现场", "演唱会"])
    if is_live and "live" not in q_title:
        score -= 8.0
    elif not is_live:
        score += 3.0

    is_compilation = any(
        kw in album for kw in ["精选", "合辑", "大全", "best", "hits", "热歌", "金曲"]
    )
    if is_compilation:
        score -= 2.0
    else:
        score += 3.0

    if cand.get("album_img"):
        score += 2.0

    return score


def analyze_music_anomalies(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """分析曲目列表中的异常特征 (供 Agent 快速感知)"""
    missing_title = []
    missing_artist = []
    missing_album = []
    missing_cover = []
    missing_lyrics = []
    dirty_names = []
    duplicate_map: Dict[str, List[Dict[str, Any]]] = {}

    for item in items:
        fn = item.get("filename", "")
        title = (item.get("title") or "").strip()
        artist = (item.get("artist") or "").strip()
        album = (item.get("album") or "").strip()

        if not title:
            missing_title.append(fn)
        if not artist or artist == "未知艺术家":
            missing_artist.append(fn)
        if not album or album == "未知专辑":
            missing_album.append(fn)
        if not item.get("has_cover"):
            missing_cover.append(fn)
        if not item.get("has_lyrics") and not item.get("has_lrc"):
            missing_lyrics.append(fn)

        for pat in DIRTY_PATTERNS:
            if re.search(pat, fn, re.IGNORECASE) or re.search(pat, title, re.IGNORECASE):
                dirty_names.append({"filename": fn, "title": title, "matched_pattern": pat})
                break

        key = f"{title.lower()}::{artist.lower()}"
        if title:
            duplicate_map.setdefault(key, []).append(
                {"filename": fn, "path": item.get("path"), "size": item.get("size")}
            )

    duplicates = [
        {"key": k, "files": v} for k, v in duplicate_map.items() if len(v) > 1
    ]

    return {
        "total_songs": len(items),
        "missing_title_count": len(missing_title),
        "missing_artist_count": len(missing_artist),
        "missing_album_count": len(missing_album),
        "missing_cover_count": len(missing_cover),
        "missing_lyrics_count": len(missing_lyrics),
        "dirty_names_sample": dirty_names[:10],
        "dirty_names_total": len(dirty_names),
        "duplicates_sample": duplicates[:5],
        "duplicates_total": len(duplicates),
    }


# -----------------------------------------------------------------------------
# CLI 命令行处理入口
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Music Tag Web CLI: 供 Agent Harness 调用的高性能工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--base-url", help="服务地址 (默认: $MUSIC_TAG_BASE_URL 或 http://127.0.0.1:18002)")
    parser.add_argument("--username", help="管理员用户名 (默认: admin)")
    parser.add_argument("--password", help="管理员密码 (默认: admin)")
    parser.add_argument("--token", help="JWT Token (若不提供则自动登录)")
    parser.add_argument("--json", action="store_true", help="以纯 JSON 格式输出")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # login
    subparsers.add_parser("login", help="登录并输出 JWT Token")

    # list-dir
    p_listdir = subparsers.add_parser("list-dir", help="浏览目录结构")
    p_listdir.add_argument("path", help="目录绝对路径，如 /app/media")
    p_listdir.add_argument("--only-dir", action="store_true", help="仅显示子文件夹")

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="深度体检指定文件夹中的曲目元数据与异常")
    p_inspect.add_argument("path", help="音乐目录路径，如 /app/media/01_精选专辑")
    p_inspect.add_argument("--page", type=int, default=1, help="页码")
    p_inspect.add_argument("--page-size", type=int, default=200, help="每页歌曲数量")

    # auto-plan (极速全并发预规划)
    p_plan = subparsers.add_parser("auto-plan", help="【极速】全并发生成目录内所有曲目的智能整理建议方案")
    p_plan.add_argument("path", help="音乐或课程目录路径")
    p_plan.add_argument("--type", choices=["auto", "music", "course"], default="auto", help="整理模式: auto (智能探测), music (音乐歌曲), course (得到课程/有声书)")
    p_plan.add_argument("--output", "-o", help="将建议方案保存至指定 JSON 文件")
    p_plan.add_argument("--sources", default="kugou,qmusic,netease,migu", help="检索源优先级")
    p_plan.add_argument("--concurrency", type=int, default=8, help="并发线程数")

    # apply-plan (一键应用预规划)
    p_apply = subparsers.add_parser("apply-plan", help="【极速】一键应用 auto-plan 方案并异步安全落盘")
    p_apply.add_argument("file", help="方案 JSON 文件路径 (传 '-' 从标准输入读取)")
    p_apply.add_argument("--dir", help="覆盖目标文件夹路径")
    p_apply.add_argument("--only-high", action="store_true", help="仅执行高置信度 (high) 修复项")
    p_apply.add_argument("--wait", action="store_true", default=True, help="阻塞等待任务完成并刷新缓存")

    # search
    p_search = subparsers.add_parser("search", help="在线检索音乐元数据候选")
    p_search.add_argument("title", help="歌曲名称或查询关键词")
    p_search.add_argument("--resource", default="kugou", help="源: kugou/qmusic/netease/migu/smart_tag/acoustid")
    p_search.add_argument("--path", help="关联的本地音乐文件绝对路径")

    # submit-tags
    p_submit_tags = subparsers.add_parser("submit-tags", help="提交批量标签更新异步任务")
    p_submit_tags.add_argument("--dir", required=True, help="目标文件夹完整路径")
    p_submit_tags.add_argument("--file", help="包含更新项的 JSON 文件路径 (若为空则从标准输入 stdin 读取)")
    p_submit_tags.add_argument("--wait", action="store_true", help="等待任务执行完成并输出最终结果")

    # submit-auto-tag
    p_auto_tag = subparsers.add_parser("submit-auto-tag", help="提交多源自动刮削异步任务")
    p_auto_tag.add_argument("--dir", required=True, help="目标文件夹路径")
    p_auto_tag.add_argument("--songs", nargs="*", help="指定文件名列表")
    p_auto_tag.add_argument("--sources", default="kugou,qmusic,netease,migu", help="数据源优先级")
    p_auto_tag.add_argument("--mode", choices=["hard", "simple"], default="hard", help="匹配严格度")
    p_auto_tag.add_argument("--wait", action="store_true", help="等待任务执行完成")

    # submit-tidy
    p_tidy = subparsers.add_parser("submit-tidy", help="提交按标签分类整理归档任务")
    p_tidy.add_argument("--root", required=True, help="整理后的根目录，如 /app/media")
    p_tidy.add_argument("--src-dir", required=True, help="待整理的源文件夹路径")
    p_tidy.add_argument("--first-dir", required=True, help="一级目录依据 (artist/album/genre/year/language)")
    p_tidy.add_argument("--second-dir", default="", help="二级目录依据 (可选)")
    p_tidy.add_argument("--conflict", choices=["skip", "overwrite"], default="skip", help="目标重名策略")
    p_tidy.add_argument("--move-lrc", action="store_true", default=True, help="同步移动同名 .lrc 歌词")
    p_tidy.add_argument("--clean-empty", action="store_true", help="整理完成后清理空源目录")
    p_tidy.add_argument("--wait", action="store_true", help="等待任务执行完成")

    # task-status
    p_status = subparsers.add_parser("task-status", help="查询异步批次任务执行进度")
    p_status.add_argument("batch", help="批次时间戳 ID")
    p_status.add_argument("--include-records", action="store_true", help="包含单曲明细")
    p_status.add_argument("--wait", action="store_true", help="阻塞轮询直到任务完成")

    # refresh-cache
    p_refresh = subparsers.add_parser("refresh-cache", help="强制刷新服务端与本地元数据缓存")
    p_refresh.add_argument("--path", default="", help="指定刷新的目录，留空刷新全部")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = MusicTagClient(
        base_url=args.base_url,
        username=args.username,
        password=args.password,
        token=args.token,
    )

    try:
        if args.command == "login":
            tok = client.login()
            out = {"token": tok, "base_url": client.base_url}
            print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else f"√ 登录成功: {tok}")

        elif args.command == "list-dir":
            data = client.list_dir(args.path, only_dir=args.only_dir)
            if args.json:
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                print(f"📁 目录内容: {args.path}")
                for entry in data:
                    print(f" - [{entry.get('icon', 'item')}] {entry.get('name')}")

        elif args.command == "inspect":
            data = client.get_music_list(args.path, page=args.page, page_size=args.page_size)
            items = data.get("items", [])
            anomalies = analyze_music_anomalies(items)
            result = {
                "folder_path": args.path,
                "total_in_folder": data.get("total", 0),
                "inspected_count": len(items),
                "anomalies": anomalies,
                "items": items,
            }
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
            else:
                print(f"📊 目录巡检报告: {args.path} (共 {data.get('total')} 首歌)")
                print(f"  • 缺失标题: {anomalies['missing_title_count']} 首")
                print(f"  • 缺失歌手: {anomalies['missing_artist_count']} 首")
                print(f"  • 缺失专辑: {anomalies['missing_album_count']} 首")
                print(f"  • 缺失封面: {anomalies['missing_cover_count']} 首")
                print(f"  • 缺失歌词: {anomalies['missing_lyrics_count']} 首")
                print(f"  • 脏污文件名/广告标记: {anomalies['dirty_names_total']} 首")
                print(f"  • 潜在重复曲目: {anomalies['duplicates_total']} 组")

        elif args.command == "auto-plan":
            t0 = time.time()
            sources_list = [s.strip() for s in args.sources.split(",") if s.strip()]
            plan_res = client.auto_plan(
                args.path,
                sources=sources_list,
                concurrency=args.concurrency,
                plan_type=args.type,
            )
            elapsed = time.time() - t0

            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(plan_res, f, indent=2, ensure_ascii=False)

            if args.json:
                print(json.dumps(plan_res, indent=2, ensure_ascii=False))
            else:
                summ = plan_res["summary"]
                mode_str = "得到课程/有声书" if plan_res.get("mode") == "course" else "音乐曲目"
                print(f"⚡ 【{mode_str}】预规划完成 (耗时: {elapsed:.2f}s)")
                if plan_res.get("mode") == "course":
                    print(f"  • 讲师 / 作者: {summ.get('detected_artist')}")
                    print(f"  • 课程 / 专辑: {summ.get('detected_album')}")
                    print(f"  • 本地封面: {'已检测并内嵌' if summ.get('detected_cover') else '未检测到 cover.jpg'}")
                    print(f"  • 总计节数: {summ['total_in_dir']} 讲 (广告已自动剥离净化，音轨已规整)")
                else:
                    print(f"  • 扫描总数: {summ['total_in_dir']} 首 | 需优化: {summ['needs_curation']} 首")
                    print(f"  • 高置信度匹配: {summ['high_confidence']} 首 (可以直接执行)")
                    print(f"  • 中等置信度: {summ['medium_confidence']} 首")
                    print(f"  • 低置信度/待确认: {summ['low_confidence']} 首")
                print("-" * 65)
                for item in plan_res["plan"]:
                    conf_tag = f"[{item['confidence'].upper()}]"
                    if item.get("proposed"):
                        prop = item["proposed"]
                        track_info = f"#{prop.get('tracknumber')} " if prop.get('tracknumber') else ""
                        print(f" {conf_tag:<8} {item['name']} -> {track_info}《{prop['title']}》- {prop['artist']} ({prop['album']})")
                    else:
                        print(f" {conf_tag:<8} {item['name']} -> (保持原样: {item['reason']})")
                if args.output:
                    print(f"\n√ 方案已写入: {args.output}")

        elif args.command == "apply-plan":
            if args.file == "-":
                plan_data = json.load(sys.stdin)
            else:
                with open(args.file, "r", encoding="utf-8") as f:
                    plan_data = json.load(f)

            res = client.apply_plan(
                plan_data,
                dir_path=args.dir,
                only_high_confidence=args.only_high,
                wait=args.wait,
            )
            print(json.dumps(res, indent=2, ensure_ascii=False) if args.json else f"√ 方案已成功执行完毕！Batch ID: {res.get('batch')}")

        elif args.command == "search":
            results = client.search_online(args.title, resource=args.resource, full_path=args.path)
            if args.json:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print(f"🔎 检索结果 [{args.resource}]: '{args.title}' (共 {len(results)} 条候选)")
                for idx, r in enumerate(results[:5], 1):
                    score = r.get("score", "-")
                    print(f"  {idx}. {r.get('name')} - {r.get('artist')} (专辑: {r.get('album')}) [得分: {score}]")

        elif args.command == "submit-tags":
            if args.file:
                with open(args.file, "r", encoding="utf-8") as f:
                    payload_data = json.load(f)
            else:
                payload_data = json.load(sys.stdin)

            if isinstance(payload_data, list):
                select_data = payload_data
                music_info = {}
            else:
                select_data = payload_data.get("select_data", [])
                music_info = payload_data.get("music_info", {})

            res = client.submit_batch_tags(
                file_full_path=args.dir,
                select_data=select_data,
                music_info=music_info,
            )
            batch_id = res.get("batch")
            if args.wait and batch_id:
                final_status = client.wait_for_batch(batch_id)
                client.force_refresh_cache(args.dir)
                out = {"batch": batch_id, "final_status": final_status}
            else:
                out = res

            print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else f"√ 批量任务已提交，Batch ID: {batch_id}")

        elif args.command == "submit-auto-tag":
            if args.songs:
                select_data = [{"name": s} for s in args.songs]
            else:
                m_data = client.get_music_list(args.dir, page=1, page_size=1000)
                select_data = [{"name": it["filename"]} for it in m_data.get("items", [])]

            sources_list = [s.strip() for s in args.sources.split(",") if s.strip()]
            res = client.submit_auto_scrape(
                file_full_path=args.dir,
                select_data=select_data,
                sources=sources_list,
                select_mode=args.mode,
            )
            batch_id = res.get("batch")
            if args.wait and batch_id:
                final_status = client.wait_for_batch(batch_id)
                client.force_refresh_cache(args.dir)
                out = {"batch": batch_id, "final_status": final_status}
            else:
                out = res

            print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else f"√ 自动刮削任务已提交，Batch ID: {batch_id}")

        elif args.command == "submit-tidy":
            res = client.submit_tidy_folder(
                root_path=args.root,
                file_full_path=args.src_dir,
                first_dir=args.first_dir,
                second_dir=args.second_dir,
                apply_to_all=True,
                move_lrc=args.move_lrc,
                conflict_action=args.conflict,
                clean_empty_dir=args.clean_empty,
            )
            batch_id = res.get("batch")
            if args.wait and batch_id:
                final_status = client.wait_for_batch(batch_id)
                client.force_refresh_cache(args.src_dir)
                out = {"batch": batch_id, "final_status": final_status}
            else:
                out = res

            print(json.dumps(out, indent=2, ensure_ascii=False) if args.json else f"√ 归档整理任务已提交，Batch ID: {batch_id}")

        elif args.command == "task-status":
            if args.wait:
                status = client.wait_for_batch(args.batch)
            else:
                status = client.get_task_status(args.batch, include_records=args.include_records)
            print(json.dumps(status, indent=2, ensure_ascii=False) if args.json else f"📊 批次进度 {args.batch}: 完成 {status.get('finished')}/{status.get('total')} ({status.get('percentage')}%)")

        elif args.command == "refresh-cache":
            ok = client.force_refresh_cache(args.path)
            print("√ 缓存刷新成功" if ok else "! 缓存刷新异常")

    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
        else:
            print(f"❌ 执行失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
