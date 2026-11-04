#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import subprocess
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_ENV_DIR = os.path.join(BASE_DIR, "test_environment")
MEDIA_DIR = os.path.join(TEST_ENV_DIR, "media")
CONFIG_DIR = os.path.join(TEST_ENV_DIR, "config")


def run_cmd(cmd):
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def create_solid_color_img(path, color_name="blue", size="300x300"):
    cmd = f'ffmpeg -f lavfi -i "color=c={color_name}:s={size}" -frames:v 1 -update 1 "{path}" -y'
    run_cmd(cmd)


def main():
    print(f"[*] 正在初始化测试环境目录: {TEST_ENV_DIR}")
    if os.path.exists(MEDIA_DIR):
        shutil.rmtree(MEDIA_DIR)
    os.makedirs(MEDIA_DIR, exist_ok=True)
    os.makedirs(CONFIG_DIR, exist_ok=True)

    tmp_dir = "/tmp/music_tag_test_tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    # 准备不同颜色的临时封面
    colors = ["red", "blue", "green", "orange", "purple", "cyan", "gold"]
    cover_paths = {}
    for c in colors:
        c_path = os.path.join(tmp_dir, f"cover_{c}.jpg")
        create_solid_color_img(c_path, c)
        cover_paths[c] = c_path

    # ========================================================
    # 1. 01_精选专辑 (全标签、内嵌封面、外置封面、LRC联动测试)
    # ========================================================
    dir_01 = os.path.join(MEDIA_DIR, "01_精选专辑")
    os.makedirs(dir_01, exist_ok=True)
    print("  -> 生成 01_精选专辑 测试数据...")

    # 周杰伦 - 晴天 (MP3 + 内嵌封面 + 歌词 + 独立LRC文件)
    qingtian_mp3 = os.path.join(dir_01, "周杰伦 - 晴天.mp3")
    cmd = (
        f'ffmpeg -f lavfi -i "sine=frequency=440:duration=1.5" -i "{cover_paths["orange"]}" '
        f'-map 0:0 -map 1:0 -c:a libmp3lame -c:v mjpeg -id3v2_version 3 '
        f'-metadata title="晴天" -metadata artist="周杰伦" -metadata album="叶惠美" '
        f'-metadata album_artist="周杰伦" -metadata date="2003" -metadata genre="流行" '
        f'-metadata:s:v title="Album cover" -metadata:s:v comment="Cover (front)" '
        f'"{qingtian_mp3}" -y'
    )
    run_cmd(cmd)

    # 配套 LRC 歌词
    qingtian_lrc = os.path.join(dir_01, "周杰伦 - 晴天.lrc")
    with open(qingtian_lrc, "w", encoding="utf-8") as f:
        f.write("[00:00.00]周杰伦 - 晴天\n[00:02.00]词：周杰伦 曲：周杰伦\n[00:05.00]故事的小黄花 从出生那年就飘着\n")

    # 陈奕迅 - 富士山下 (MP3 + 内嵌蓝色封面)
    fuji_mp3 = os.path.join(dir_01, "陈奕迅 - 富士山下.mp3")
    cmd = (
        f'ffmpeg -f lavfi -i "sine=frequency=520:duration=1.5" -i "{cover_paths["blue"]}" '
        f'-map 0:0 -map 1:0 -c:a libmp3lame -c:v mjpeg -id3v2_version 3 '
        f'-metadata title="富士山下" -metadata artist="陈奕迅" -metadata album="What\'s Going On...?" '
        f'-metadata album_artist="陈奕迅" -metadata date="2006" -metadata genre="流行" '
        f'-metadata:s:v title="Album cover" -metadata:s:v comment="Cover (front)" '
        f'"{fuji_mp3}" -y'
    )
    run_cmd(cmd)

    # 王菲 - 红豆 (M4A / AAC 格式测试)
    hongdou_m4a = os.path.join(dir_01, "王菲 - 红豆.m4a")
    cmd = (
        f'ffmpeg -f lavfi -i "sine=frequency=660:duration=1.5" -i "{cover_paths["red"]}" '
        f'-map 0:0 -map 1:0 -c:a aac -c:v copy -disposition:v:0 attached_pic '
        f'-metadata title="红豆" -metadata artist="王菲" -metadata album="唱游" '
        f'-metadata album_artist="王菲" -metadata date="1998" -metadata genre="流行" '
        f'"{hongdou_m4a}" -y'
    )
    run_cmd(cmd)

    # 林俊杰 - 江南 (FLAC 无损格式测试)
    jiangnan_flac = os.path.join(dir_01, "林俊杰 - 江南.flac")
    cmd = (
        f'ffmpeg -f lavfi -i "sine=frequency=587:duration=1.5" -i "{cover_paths["green"]}" '
        f'-map 0:0 -map 1:0 -c:a flac -c:v copy -disposition:v:0 attached_pic '
        f'-metadata title="江南" -metadata artist="林俊杰" -metadata album="第二天堂" '
        f'-metadata album_artist="林俊杰" -metadata date="2004" -metadata genre="流行" '
        f'"{jiangnan_flac}" -y'
    )
    run_cmd(cmd)

    # 邓丽君 - 甜蜜蜜 (MP3 无内嵌封面，但目录包含 cover.jpg 外置封面)
    tianmimi_mp3 = os.path.join(dir_01, "邓丽君 - 甜蜜蜜.mp3")
    cmd = (
        f'ffmpeg -f lavfi -i "sine=frequency=880:duration=1.5" -c:a libmp3lame -id3v2_version 3 '
        f'-metadata title="甜蜜蜜" -metadata artist="邓丽君" -metadata album="甜蜜蜜" '
        f'-metadata album_artist="邓丽君" -metadata date="1979" -metadata genre="经典流行" '
        f'"{tianmimi_mp3}" -y'
    )
    run_cmd(cmd)

    # 同目录外置封面 cover.jpg (紫色)
    shutil.copy2(cover_paths["purple"], os.path.join(dir_01, "cover.jpg"))

    # ========================================================
    # 2. 02_待刮削与无标签 (测试在线搜索刮削、自动匹配、文件名解析)
    # ========================================================
    dir_02 = os.path.join(MEDIA_DIR, "02_待刮削与无标签")
    os.makedirs(dir_02, exist_ok=True)
    print("  -> 生成 02_待刮削与无标签 测试数据...")

    # 完全空白标签 Track01.mp3
    cmd = f'ffmpeg -f lavfi -i "sine=frequency=330:duration=1" -c:a libmp3lame "{os.path.join(dir_02, "Track01.mp3")}" -y'
    run_cmd(cmd)

    # 仅标题，缺失艺术家和专辑的海阔天空.mp3
    cmd = (
        f'ffmpeg -f lavfi -i "sine=frequency=440:duration=1" -c:a libmp3lame -id3v2_version 3 '
        f'-metadata title="海阔天空" '
        f'"{os.path.join(dir_02, "海阔天空.mp3")}" -y'
    )
    run_cmd(cmd)

    # 文件名为歌手-歌名，测试从文件名提取标签 Beyond - 光辉岁月.mp3
    cmd = (
        f'ffmpeg -f lavfi -i "sine=frequency=500:duration=1" -c:a libmp3lame '
        f'"{os.path.join(dir_02, "Beyond - 光辉岁月.mp3")}" -y'
    )
    run_cmd(cmd)

    # ========================================================
    # 3. 03_分页与大列表测试(40首) (测试每页条数、分页、紧凑字号、批量选择)
    # ========================================================
    dir_03 = os.path.join(MEDIA_DIR, "03_分页与大列表测试")
    os.makedirs(dir_03, exist_ok=True)
    print("  -> 生成 03_分页与大列表测试 测试数据(40首)...")

    for i in range(1, 41):
        color = colors[(i - 1) % len(colors)]
        filename = f"Song_{i:02d}.mp3"
        out_file = os.path.join(dir_03, filename)
        cmd = (
            f'ffmpeg -f lavfi -i "sine=frequency={300 + i * 15}:duration=0.5" -i "{cover_paths[color]}" '
            f'-map 0:0 -map 1:0 -c:a libmp3lame -c:v mjpeg -id3v2_version 3 '
            f'-metadata title="测试歌曲 {i:02d}" -metadata artist="测试艺术家 {(i % 5) + 1}" '
            f'-metadata album="测试合辑 {((i - 1) // 10) + 1}" -metadata date="{2000 + (i % 25)}" '
            f'-metadata:s:v title="Album cover" '
            f'"{out_file}" -y'
        )
        run_cmd(cmd)

    print("[√] 测试曲库生成完毕！")
    print(f"    - 媒体目录: {MEDIA_DIR}")
    print(f"    - 配置目录: {CONFIG_DIR}")


if __name__ == "__main__":
    main()
