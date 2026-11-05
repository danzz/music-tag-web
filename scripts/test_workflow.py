import json
import time
import threading
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:18002"

def post(url, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"JWT {token}"
    req = urllib.request.Request(f"{BASE_URL}{url}", data=json.dumps(data or {}).encode('utf-8'), headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def get(url, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"JWT {token}"
    req = urllib.request.Request(f"{BASE_URL}{url}", headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))

def test_full_workflow():
    print("[1] Logging in...")
    login_res = post("/api/token/", {"username": "admin", "password": "admin"})
    token = login_res.get("data", {}).get("token") or login_res.get("token")
    assert token, f"Login failed: {login_res}"
    print(f"[√] Logged in successfully. Token: {token[:16]}...")

    print("\n[0] Resetting ephemeral records for clean test slate...")
    post("/api/record/clear/", {}, token=token)

    print("\n[2] Setting up SSE listener...")
    collected_events = []
    stop_event = threading.Event()

    def sse_worker():
        req = urllib.request.Request(f"{BASE_URL}/api/events/")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                buffer = ""
                while not stop_event.is_set():
                    line = resp.readline().decode('utf-8')
                    if not line:
                        break
                    buffer += line
                    if buffer.endswith("\n\n"):
                        # Parse SSE event
                        event_type = "message"
                        event_data = ""
                        for part in buffer.strip().split("\n"):
                            if part.startswith("event:"):
                                event_type = part[6:].strip()
                            elif part.startswith("data:"):
                                event_data = part[5:].strip()
                        collected_events.append({"type": event_type, "data": event_data})
                        buffer = ""
        except Exception as e:
            if not stop_event.is_set():
                print(f"SSE error: {e}")

    sse_thread = threading.Thread(target=sse_worker, daemon=True)
    sse_thread.start()
    time.sleep(1)

    print("\n[3] Checking folder music list for /app/media/01_精选专辑...")
    list_res = post("/api/folder_music_list/", {
        "file_path": "/app/media/01_精选专辑",
        "page": 1,
        "page_size": 20
    }, token=token)
    items = list_res.get("data", {}).get("items", [])
    print(f"Found {len(items)} songs. Checking initial state...")
    for it in items:
        print(f"  Song: {it['filename']} -> state: {it.get('state')}")
        assert it.get('state') == 'none', f"Expected state 'none' initially, got {it.get('state')}"
    print("[√] All songs correctly report 'none' initially (no stale permanent '已修改')!")

    print("\n[4] Submitting batch update for 3 songs...")
    target_songs = items[:3]
    select_data = [{"name": s["filename"], "icon": "icon-music"} for s in target_songs]
    music_info = {
        "artist": "TestArtist",
        "comment": "SSE-Ephemeral-Test"
    }
    batch_res = post("/api/batch_update_id3/", {
        "file_full_path": "/app/media/01_精选专辑",
        "select_data": select_data,
        "apply_to_all": False,
        "music_info": music_info
    }, token=token)
    print(f"Batch response: {batch_res}")
    batch_id = batch_res.get("data", {}).get("batch")
    assert batch_id, "Batch submission failed"

    print("\n[5] Waiting for tasks to process and SSE events to arrive...")
    time.sleep(4)

    print(f"Collected {len(collected_events)} SSE events:")
    task_items = [e for e in collected_events if e["type"] == "task_item"]
    task_batches = [e for e in collected_events if e["type"] == "task_batch"]
    pings = [e for e in collected_events if e["type"] == "ping"]
    print(f"  Pings: {len(pings)}")
    print(f"  Task items: {len(task_items)}")
    print(f"  Task batches: {len(task_batches)}")

    assert len(task_items) >= len(target_songs), f"Expected at least {len(target_songs)} task_item events, got {len(task_items)}"
    final_states = {}
    for ti in task_items:
        payload = json.loads(ti["data"])
        fn = payload.get('filename')
        st = payload.get('state')
        final_states[fn] = st
        print(f"  SSE item event: filename={fn}, state={st}, cover_url={payload.get('cover_url')}")
    
    # Verify each song reached 'success'
    for s in target_songs:
        fn = s["filename"]
        assert final_states.get(fn) == "success", f"Song {fn} did not reach success: {final_states.get(fn)}"

    print("\n[6] Checking folder music list again...")
    list_res2 = post("/api/folder_music_list/", {
        "file_path": "/app/media/01_精选专辑",
        "page": 1,
        "page_size": 20
    }, token=token)
    items2 = list_res2.get("data", {}).get("items", [])
    modified_filenames = [s["filename"] for s in target_songs]
    for it in items2:
        fn = it["filename"]
        st = it.get("state")
        print(f"  Song: {fn} -> state: {st}")
        if fn in modified_filenames:
            assert st == "success", f"Expected modified song {fn} to have state 'success', got {st}"
        else:
            assert st == "none", f"Expected untouched song {fn} to have state 'none', got {st}"
    print("[√] File list reflects active 24h task state accurately!")

    print("\n[7] Checking /api/record/stats/ and /api/record/...")
    stats = get("/api/record/stats/", token=token)
    print(f"Task Stats: {stats.get('data')}")
    assert stats.get('data', {}).get('total', 0) >= 3

    records = get("/api/record/?page=1&page_size=10", token=token)
    rec_items = records.get('data', {}).get('items', [])
    print(f"Task Records count: {len(rec_items)}")
    for r in rec_items:
        print(f"  Record: {r.get('filename')}, state={r.get('state')}, type={r.get('tag_source')}, time={r.get('batch_time')}")
    assert len(rec_items) >= 3

    print("\n[8] Testing deduplication: Submitting batch update for the SAME 3 songs a second time...")
    batch_res2 = post("/api/batch_update_id3/", {
        "file_full_path": "/app/media/01_精选专辑",
        "select_data": select_data,
        "apply_to_all": False,
        "music_info": music_info
    }, token=token)
    print(f"Second batch response: {batch_res2}")
    assert batch_res2.get("result") is True, f"Second batch submission failed: {batch_res2}"

    # Immediately check stats while second batch is running/done
    time.sleep(2)
    stats2 = get("/api/record/stats/", token=token)
    print(f"Stats after second submission on same 3 files: {stats2.get('data')}")
    # TOTAL MUST BE EXACTLY 3, NOT 6!
    assert stats2.get('data', {}).get('total') == 3, f"Expected total to remain 3 (deduplicated), but got {stats2.get('data', {}).get('total')}"
    print("[√] Deduplication passed! Total records count remained exactly 3 (did NOT double to 6)!")

    print("\n[9] Testing pre-submission interception when tasks are active...")
    # Launch concurrent requests on the same song to verify interception
    concurrent_results = []
    def worker_b():
        r = post("/api/batch_update_id3/", {
            "file_full_path": "/app/media/01_精选专辑",
            "select_data": [{"name": "周杰伦 - 晴天.mp3", "icon": "icon-music"}],
            "apply_to_all": False,
            "music_info": music_info
        }, token=token)
        concurrent_results.append(("batch", r))

    def worker_s():
        valid_info = {
            "file_full_path": "/app/media/01_精选专辑/周杰伦 - 晴天.mp3",
            "title": "晴天",
            "artist": "周杰伦",
            "album": "叶惠美",
            "albumartist": "周杰伦",
            "discnumber": "1",
            "tracknumber": "1",
            "genre": "Pop",
            "year": "2003",
            "lyrics": "",
            "is_save_lyrics_file": False,
            "is_save_album_cover": False,
            "comment": ""
        }
        r = post("/api/update_id3/", {"music_id3_info": [valid_info]}, token=token)
        concurrent_results.append(("single", r))

    tb = threading.Thread(target=worker_b)
    ts = threading.Thread(target=worker_s)
    tb.start()
    ts.start()
    tb.join()
    ts.join()

    print(f"Concurrent responses: {concurrent_results}")
    has_intercepted = any(
        (not r[1].get("result") and ("正在处理" in r[1].get("message", "") or "正在后台处理" in r[1].get("message", "")))
        for r in concurrent_results
    )
    assert has_intercepted, f"Expected at least one request to be intercepted, got: {concurrent_results}"
    print("[√] Pre-submission active task interception passed!")

    time.sleep(2)

    print("\n[10] Testing force_refresh_cache...")
    refresh_res = post("/api/force_refresh_cache/", {"file_path": "/app/media/01_精选专辑"}, token=token)
    print(f"Force refresh: {refresh_res}")
    assert refresh_res.get('result') is True

    stop_event.set()
    print("\n=======================================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")

if __name__ == "__main__":
    test_full_workflow()
