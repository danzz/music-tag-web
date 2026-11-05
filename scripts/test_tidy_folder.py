import json
import os
import shutil
import time
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

def test_tidy_folder():
    print("[1] Logging in...")
    login_res = post("/api/token/", {"username": "admin", "password": "admin"})
    token = login_res.get("data", {}).get("token") or login_res.get("token")
    assert token, f"Login failed: {login_res}"
    print(f"[√] Logged in successfully. Token: {token[:16]}...")

    # Set up test media folder
    media_host_dir = os.path.abspath("test_environment/media")
    src_host_dir = os.path.join(media_host_dir, "test_tidy_src")
    target_host_dir = os.path.join(media_host_dir, "test_tidy_dst")
    
    # Clean previous test directories
    if os.path.exists(src_host_dir):
        shutil.rmtree(src_host_dir)
    if os.path.exists(target_host_dir):
        shutil.rmtree(target_host_dir)
    os.makedirs(src_host_dir, exist_ok=True)
    os.makedirs(target_host_dir, exist_ok=True)

    # Copy some existing test music into src_host_dir
    sample_src = os.path.join(media_host_dir, "01_精选专辑")
    sample_files = [f for f in os.listdir(sample_src) if f.endswith(".mp3") or f.endswith(".flac")]
    assert len(sample_files) >= 2, "Need at least 2 sample files"
    
    file1 = sample_files[0]
    file2 = sample_files[1]
    
    shutil.copy2(os.path.join(sample_src, file1), os.path.join(src_host_dir, file1))
    shutil.copy2(os.path.join(sample_src, file2), os.path.join(src_host_dir, file2))
    
    # Also create a dummy .lrc file for file1
    base1, _ = os.path.splitext(file1)
    lrc1_path = os.path.join(src_host_dir, f"{base1}.lrc")
    with open(lrc1_path, "w", encoding="utf-8") as f:
        f.write("[00:00.00] Test Lyric for Tidy\n")

    print(f"[2] Prepared test files in test_tidy_src: {file1} (with .lrc), {file2}")

    # Test 1: Tidy selected song (file1)
    print("\n[3] Testing tidying single selected song with move_lrc=True...")
    tidy_res1 = post("/api/tidy_folder/", {
        "file_full_path": "/app/media/test_tidy_src",
        "root_path": "/app/media/test_tidy_dst",
        "first_dir": "artist",
        "second_dir": "album",
        "apply_to_all": False,
        "select_data": [{"filename": file1}],
        "move_lrc": True,
        "conflict_action": "skip",
        "clean_empty_dir": False
    }, token=token)
    print(f"Tidy response: {tidy_res1}")
    assert tidy_res1.get("result") is True, f"Tidy failed: {tidy_res1}"
    batch_id1 = tidy_res1.get("data", {}).get("batch")
    assert batch_id1, "Missing batch_id"

    # Wait for batch task to complete
    for _ in range(20):
        time.sleep(0.5)
        prog = get(f"/api/batch_progress/?batch={batch_id1}&include_records=true", token=token)
        if prog.get("data", {}).get("is_done"):
            break
    print(f"Batch 1 progress: {prog.get('data')}")
    assert prog.get("data", {}).get("success") == 1

    # Verify file1 was moved from src and exists in dst along with .lrc
    assert not os.path.exists(os.path.join(src_host_dir, file1)), "file1 should have been moved out of src"
    assert not os.path.exists(lrc1_path), "lrc1 should have been moved out of src"

    # Search for file1 and lrc1 in target_host_dir
    found_file1 = False
    found_lrc1 = False
    for root, dirs, files in os.walk(target_host_dir):
        if file1 in files:
            found_file1 = True
        if f"{base1}.lrc" in files:
            found_lrc1 = True
    assert found_file1, f"file1 not found in target dir {target_host_dir}"
    assert found_lrc1, f"lrc1 not found in target dir {target_host_dir}"
    print("[√] file1 and associated .lrc moved successfully to organized folder structure!")

    # Test 2: Conflict handling (skip when target file already exists)
    print("\n[4] Testing conflict handling (skip when already exists)...")
    # Copy file1 again into src and tidy with skip
    shutil.copy2(os.path.join(sample_src, file1), os.path.join(src_host_dir, file1))
    tidy_res2 = post("/api/tidy_folder/", {
        "file_full_path": "/app/media/test_tidy_src",
        "root_path": "/app/media/test_tidy_dst",
        "first_dir": "artist",
        "second_dir": "album",
        "apply_to_all": False,
        "select_data": [{"filename": file1}],
        "move_lrc": True,
        "conflict_action": "skip",
        "clean_empty_dir": False
    }, token=token)
    batch_id2 = tidy_res2.get("data", {}).get("batch")
    for _ in range(20):
        time.sleep(0.5)
        prog = get(f"/api/batch_progress/?batch={batch_id2}&include_records=true", token=token)
        if prog.get("data", {}).get("is_done"):
            break
    print(f"Batch 2 (conflict skip) progress: {prog.get('data')}")
    assert prog.get("data", {}).get("success") == 1
    # file1 in src should still exist because it was skipped
    assert os.path.exists(os.path.join(src_host_dir, file1)), "file1 should remain in src because it was skipped"
    print("[√] Conflict skip verified: existing destination file preserved without crash!")

    # Remove the duplicate file1 in src
    os.remove(os.path.join(src_host_dir, file1))

    # Test 3: Tidy all remaining songs in folder with clean_empty_dir=True
    print("\n[5] Testing apply_to_all=True and clean_empty_dir=True...")
    tidy_res3 = post("/api/tidy_folder/", {
        "file_full_path": "/app/media/test_tidy_src",
        "root_path": "/app/media/test_tidy_dst",
        "first_dir": "artist",
        "second_dir": "",
        "apply_to_all": True,
        "select_data": [],
        "move_lrc": True,
        "conflict_action": "skip",
        "clean_empty_dir": True
    }, token=token)
    batch_id3 = tidy_res3.get("data", {}).get("batch")
    for _ in range(20):
        time.sleep(0.5)
        prog = get(f"/api/batch_progress/?batch={batch_id3}&include_records=true", token=token)
        if prog.get("data", {}).get("is_done"):
            break
    print(f"Batch 3 (all + clean empty dir) progress: {prog.get('data')}")
    assert prog.get("data", {}).get("success") == 1

    # Verify file2 moved to target
    found_file2 = False
    for root, dirs, files in os.walk(target_host_dir):
        if file2 in files:
            found_file2 = True
    assert found_file2, f"file2 not found in target dir {target_host_dir}"
    
    # Verify src_host_dir was deleted because it became empty
    assert not os.path.exists(src_host_dir), "src_host_dir should have been removed when empty"
    print("[√] apply_to_all and clean_empty_dir passed! Empty source directory removed.")

    # Test 4: Verify task center records have task_type="tidy_folder"
    print("\n[6] Checking Task Records in task center...")
    records = get(f"/api/record/?batch={batch_id3}", token=token)
    rec_items = records.get("data", {}).get("items", [])
    assert len(rec_items) >= 1
    rec = rec_items[0]
    print(f"Task record: tag_source={rec.get('tag_source')}, extra={rec.get('extra')}, state={rec.get('state')}")
    assert rec.get("tag_source") == "tidy_folder", f"Expected tag_source='tidy_folder', got {rec.get('tag_source')}"
    assert rec.get("state") == "success"
    print("[√] Task Center records reflect task_type='tidy_folder' correctly!")

    # Cleanup test destination folder
    if os.path.exists(target_host_dir):
        shutil.rmtree(target_host_dir)

    print("\n=======================================================")
    print("🎉 ALL TIDY FOLDER TESTS PASSED PERFECTLY!")
    print("=======================================================")

if __name__ == "__main__":
    test_tidy_folder()

