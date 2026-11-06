#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端集成测试：验证 Agent 通过 MusicTagClient / CLI 驱动底层异步任务的完整闭环
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.music_tag_cli import MusicTagClient, analyze_music_anomalies

def test_agent_workflow():
    print("==================================================")
    print("🚀 开始 Agent Harness 工具与任务模式端到端测试")
    print("==================================================")

    # 1. 初始化客户端
    client = MusicTagClient(base_url="http://127.0.0.1:18002", username="admin", password="admin")
    token = client.login()
    print(f"[1] √ 登录成功，Token 前缀: {token[:16]}...")

    # 2. 模拟 Agent 阶段一：目录体检与异常特征识别
    target_dir = "/app/media/01_精选专辑"
    print(f"\n[2] Agent 正在扫描体检目录: {target_dir}")
    data = client.get_music_list(target_dir, page=1, page_size=20)
    items = data.get("items", [])
    assert len(items) > 0, "测试目录无歌曲"
    anomalies = analyze_music_anomalies(items)
    print(f"[√] 成功体检 {len(items)} 首歌，发现缺失歌词: {anomalies['missing_lyrics_count']} 首")

    # 3. 模拟 Agent 阶段二：多渠道在线检索与消歧决策
    test_song = items[0]
    song_filename = test_song["filename"]
    print(f"\n[3] Agent 正在为曲目 '{song_filename}' 检索在线权威元数据...")
    candidates = []
    for res_name in ["kugou", "qmusic", "netease", "migu"]:
        candidates = client.search_online("晴天", resource=res_name)
        if candidates:
            print(f"[√] 成功从数据源 '{res_name}' 检索到 {len(candidates)} 条候选。")
            break
    assert len(candidates) > 0, "在线检索无结果"

    # Agent 智能筛选首张录音室正规专辑《叶惠美》
    selected = None
    for cand in candidates:
        if cand.get("name") == "晴天" and cand.get("album") == "叶惠美":
            selected = cand
            break
    if not selected:
        selected = candidates[0]
    print(f"[√] Agent 消歧选定最佳候选: 《{selected.get('name')}》- {selected.get('artist')} (专辑: {selected.get('album')})")

    # 4. 模拟 Agent 阶段三：规划变更并提交异步批量任务
    print(f"\n[4] Agent 正在提交异步批量标签任务...")
    target_tags = [{
        "name": song_filename,
        "title": selected.get("name", "晴天"),
        "artist": selected.get("artist", "周杰伦"),
        "album": selected.get("album", "叶惠美"),
        "albumartist": "周杰伦",
        "tracknumber": "01",
        "discnumber": "1",
        "year": "2003",
        "genre": "Pop",
        "comment": "Curated-By-Agent-Harness"
    }]

    batch_res = client.submit_batch_tags(
        file_full_path=target_dir,
        select_data=target_tags,
        apply_to_all=False
    )
    batch_id = batch_res.get("batch")
    assert batch_id, f"任务提交失败: {batch_res}"
    print(f"[√] 异步任务提交成功，批次 ID (batch_id): {batch_id}")

    # 5. 模拟 Agent 阶段四：轮询监听任务完成
    print(f"\n[5] 等待底座 AsyncExecutor 写入磁盘并完成任务...")
    final_status = client.wait_for_batch(batch_id, poll_interval=0.5, max_wait=30.0)
    print(f"[√] 批次任务处理完毕: {final_status.get('finished')}/{final_status.get('total')} 完成, 状态: {final_status.get('is_done')}")
    assert final_status.get("failed") == 0, f"有任务失败: {final_status}"

    # 6. 验证磁盘写回与缓存生效
    print(f"\n[6] 刷新缓存并校验最终元数据落盘结果...")
    client.force_refresh_cache(target_dir)
    refreshed_data = client.get_music_list(target_dir, page=1, page_size=20)
    found_item = None
    for it in refreshed_data.get("items", []):
        if it["filename"] == song_filename:
            found_item = it
            break
    assert found_item, "未找到目标文件"
    assert found_item["title"] == "晴天", f"标题未更新: {found_item['title']}"
    assert found_item["album"] == "叶惠美", f"专辑未更新: {found_item['album']}"
    print(f"[√] 验证成功！当前曲目元数据已安全更新: 标题={found_item['title']}, 专辑={found_item['album']}, 年份={found_item['year']}")

    print("\n==================================================")
    print("🎉 全部测试通过！Agent Harness -> 异步任务模式验证无误！")
    print("==================================================")

if __name__ == "__main__":
    test_agent_workflow()
