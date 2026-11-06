import os
import io
import json
import time
import random
import base64
import urllib.request
import urllib.error
from PIL import Image, ImageDraw, ImageFont, ImageFilter

class CourseCoverGenerator:
    """
    得到/音频课程专属封面生成引擎
    支持：
    1. ComfyUI 驱动的 AI 插画背景生成（MOSS-Image / SD / Flux）
    2. 极速纯本地几何美学渐变引擎（无需GPU，0依赖，秒级生成）
    3. 专业级中文版式与排版引擎（标题折行、徽章、主讲人、半透明遮罩与微阴影）
    4. 一键写回 cover.jpg 及自动内嵌到目录下所有音频标签 (MP3/FLAC/M4A)
    """

    FONT_CANDIDATES = [
        "/app/data/fonts/default_font.ttc",
        "/app/data/fonts/default_font.ttf",
        "/tmp/test_font.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
    ]

    @classmethod
    def get_font(cls, size=36):
        """寻找可用中文字体"""
        # 1. 优先检查预设候选路径
        for path in cls.FONT_CANDIDATES:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    continue

        # 2. 检查 /app/data/fonts 目录下任意 ttf/otf/ttc
        fonts_dir = "/app/data/fonts"
        if os.path.isdir(fonts_dir):
            for fname in os.listdir(fonts_dir):
                if fname.lower().endswith((".ttf", ".otf", ".ttc")):
                    try:
                        return ImageFont.truetype(os.path.join(fonts_dir, fname), size)
                    except Exception:
                        continue

        # 3. 兜底默认字体
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    @classmethod
    def generate_gradient_background(cls, width=1024, height=1024, style="amber_dark"):
        """极速纯本地现代商业与美学渐变底图生成"""
        img = Image.new("RGB", (width, height), color=(26, 26, 36))
        draw = ImageDraw.Draw(img)

        # 渐变配色方案
        styles = {
            "amber_dark": [(20, 22, 34), (45, 30, 25), (180, 110, 45)],
            "deep_blue": [(15, 23, 42), (30, 58, 138), (56, 189, 248)],
            "emerald": [(6, 30, 25), (6, 78, 59), (52, 211, 153)],
            "crimson": [(35, 15, 20), (127, 29, 29), (248, 113, 113)],
            "purple": [(24, 18, 43), (76, 29, 149), (192, 132, 252)]
        }
        theme = styles.get(style, styles["amber_dark"])
        c_top, c_mid, c_accent = theme

        # 垂直平滑背景过渡
        for y in range(height):
            ratio = y / float(height)
            if ratio < 0.6:
                sub_ratio = ratio / 0.6
                r = int(c_top[0] * (1 - sub_ratio) + c_mid[0] * sub_ratio)
                g = int(c_top[1] * (1 - sub_ratio) + c_mid[1] * sub_ratio)
                b = int(c_top[2] * (1 - sub_ratio) + c_mid[2] * sub_ratio)
            else:
                sub_ratio = (ratio - 0.6) / 0.4
                r = int(c_mid[0] * (1 - sub_ratio) + c_top[0] * sub_ratio)
                g = int(c_mid[1] * (1 - sub_ratio) + c_top[1] * sub_ratio)
                b = int(c_mid[2] * (1 - sub_ratio) + c_top[2] * sub_ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        # 叠加现代几何光晕（柔和径向发光）
        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        # 中心偏上的光晕球
        cx, cy = int(width * 0.5), int(height * 0.45)
        radius = int(width * 0.45)
        overlay_draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(c_accent[0], c_accent[1], c_accent[2], 70)
        )
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=80))

        # 叠加微妙的几何装饰线条
        dec_draw = ImageDraw.Draw(overlay)
        dec_draw.rectangle([60, 60, width - 60, height - 60], outline=(255, 255, 255, 30), width=2)
        dec_draw.rectangle([70, 70, width - 70, height - 70], outline=(255, 255, 255, 15), width=1)

        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        return img

    @classmethod
    def call_comfyui_moss_image(cls, prompt_text, comfyui_url="http://host.docker.internal:8188", quality="fast", timeout=300):
        """调用本地 ComfyUI MOSS-Image 渲染背景插画（带任务中断与队列清洗）"""
        base_url = comfyui_url.rstrip('/')

        # 1. 立即清空 ComfyUI 队列、中断旧任务并释放 PyTorch 显存碎片（防止显存残留导致 Windows 共享内存回退）
        try:
            clear_req = urllib.request.Request(
                f"{base_url}/queue",
                data=json.dumps({"clear": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(clear_req, timeout=3)
            interrupt_req = urllib.request.Request(f"{base_url}/interrupt", data=b"", method="POST")
            urllib.request.urlopen(interrupt_req, timeout=3)
            free_req = urllib.request.Request(
                f"{base_url}/free",
                data=json.dumps({"unload_models": False, "free_memory": True}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(free_req, timeout=3)
            time.sleep(0.3)
        except Exception:
            pass

        positive_prompt = f"{prompt_text}, minimalist abstract modern book cover background, clean aesthetic, elegant lighting, smooth gradient, 3d render, masterpiece, 8k, no text, no watermark"
        negative_prompt = "text, letters, words, watermark, signature, ugly, deformed, blurry, low quality, realistic face, messy"

        # 针对 Apple Silicon MPS 性能调优：
        # fast 模式：768x768, 12步（~60-80秒秒级出图，再由 Pillow 矢量放大并排版至 1024x1024 纯净封面）
        # hd 模式：1024x1024, 16步（~160秒原生高精度）
        if quality == "hd":
            img_w, img_h, steps = 1024, 1024, 16
        else:
            img_w, img_h, steps = 768, 768, 12

        rand_seed = random.randint(1, 2147483647)
        file_prefix = f"MTW_Course_Cover_{int(time.time())}"

        # 智能检测目标 ComfyUI 服务已安装的模型，自动选择适配工作流
        available_unets = []
        try:
            info_req = urllib.request.Request(f"{base_url}/object_info/UNETLoader", headers={"User-Agent": "MusicTagWeb"})
            with urllib.request.urlopen(info_req, timeout=4) as info_resp:
                info_data = json.loads(info_resp.read().decode("utf-8"))
                available_unets = info_data.get("UNETLoader", {}).get("input", {}).get("required", {}).get("unet_name", [[]])[0]
        except Exception:
            pass

        if any("z_image_turbo" in str(u).lower() for u in available_unets):
            # A. Windows RTX 4080 SUPER 专属极速 DiT 工作流 (Z-Image-Turbo, 8步 AuraFlow, 强制 FP8 避免显存溢出到共享内存)
            prompt_payload = {
                "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "fp8_e4m3fn"}},
                "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2"}},
                "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
                "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"shift": 3.0, "model": ["1", 0]}},
                "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": positive_prompt}},
                "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
                "7": {"class_type": "EmptySD3LatentImage", "inputs": {"batch_size": 1, "height": 1024, "width": 1024}},
                "8": {"class_type": "KSampler", "inputs": {
                    "cfg": 1.0, "denoise": 1.0, "latent_image": ["7", 0], "model": ["4", 0],
                    "negative": ["6", 0], "positive": ["5", 0], "sampler_name": "res_multistep", "scheduler": "simple",
                    "seed": rand_seed, "steps": 8
                }},
                "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
                "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": file_prefix, "images": ["9", 0]}}
            }
            save_node_id = "10"
        else:
            # B. 本地 Mac MPS 适配工作流 (MOSS-Image / Flux 蒸馏)
            prompt_payload = {
                "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "moss_image_sft_int8_convrot.safetensors", "weight_dtype": "default"}},
                "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3.5_9b_w4a8_gptq.safetensors", "type": "moss_image"}},
                "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae_small.safetensors"}},
                "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": positive_prompt}},
                "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": negative_prompt}},
                "6": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1, "height": img_h, "width": img_w}},
                "7": {"class_type": "KSampler", "inputs": {
                    "cfg": 3.8, "denoise": 1.0, "latent_image": ["6", 0], "model": ["1", 0],
                    "negative": ["5", 0], "positive": ["4", 0], "sampler_name": "euler", "scheduler": "simple",
                    "seed": rand_seed, "steps": steps
                }},
                "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
                "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": file_prefix, "images": ["8", 0]}}
            }
            save_node_id = "9"

        # 2. 提交全新任务
        req_data = json.dumps({"prompt": prompt_payload}).encode("utf-8")
        req = urllib.request.Request(f"{base_url}/prompt", data=req_data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            submit_res = json.loads(resp.read().decode("utf-8"))
        prompt_id = submit_res.get("prompt_id")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI 返回异常: {submit_res}")

        # 3. 轮询直到生成完毕
        start_t = time.time()
        image_info = None
        while time.time() - start_t < timeout:
            time.sleep(1.5)
            try:
                h_req = urllib.request.Request(f"{base_url}/history/{prompt_id}")
                with urllib.request.urlopen(h_req, timeout=10) as h_resp:
                    history = json.loads(h_resp.read().decode("utf-8"))
                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        if save_node_id in outputs and "images" in outputs[save_node_id]:
                            images = outputs[save_node_id]["images"]
                            if images:
                                image_info = images[0]
                                break
            except Exception:
                pass

        if not image_info:
            raise TimeoutError(f"ComfyUI 生图超时 ({timeout}s)，请检查 ComfyUI 控制台状态")

        # 4. 下载生成的图片
        fname = image_info.get("filename")
        subfolder = image_info.get("subfolder", "")
        img_type = image_info.get("type", "output")
        view_url = f"{base_url}/view?filename={urllib.parse.quote(fname)}&subfolder={urllib.parse.quote(subfolder)}&type={img_type}"
        with urllib.request.urlopen(view_url, timeout=20) as img_resp:
            img_bytes = img_resp.read()
        return Image.open(io.BytesIO(img_bytes)).convert("RGB")

    @classmethod
    def overlay_course_typography(cls, bg_image, title, author="", category="得到课程", layout="dedao_clean", font_size="auto"):
        """
        在背景图上叠加“得到”级中文版式与排版
        layout:
          - 'dedao_clean': 得到官方极简专栏风（如《硅谷来信》：大号纯白粗标题 + 香槟金纯导师名，无多余徽章线条，极度纯粹）
          - 'badge_master': 大师课典藏徽标风（带顶部金边胶囊徽标、下划分割线、主讲人标签与底部英文水印）
        """
        width, height = bg_image.size
        # 统一规范为 1024x1024 正方形
        if (width, height) != (1024, 1024):
            bg_image = bg_image.resize((1024, 1024), Image.LANCZOS)
            width, height = 1024, 1024

        # 1. 遮罩暗化处理
        if layout == "dedao_clean":
            # 得到极简专栏风：仅在中下部文字阅读区做柔和径向暗化，不破坏顶部的主题几何图标（如信封、芯片）
            scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            scrim_draw = ImageDraw.Draw(scrim)
            cx, cy = width // 2, int(height * 0.56)
            rx, ry = int(width * 0.48), int(height * 0.30)
            scrim_draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(8, 12, 18, 185))
            scrim = scrim.filter(ImageFilter.GaussianBlur(radius=55))
            combined = Image.alpha_composite(bg_image.convert("RGBA"), scrim)
        else:
            # 典藏徽标风：全幅上下微渐变暗化
            scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            scrim_draw = ImageDraw.Draw(scrim)
            for y in range(240):
                alpha = int(90 * (1 - y / 240.0))
                scrim_draw.line([(0, y), (width, y)], fill=(10, 10, 15, alpha))
            for y in range(280, 820):
                rel = (y - 280) / 540.0
                alpha = int(140 * (1 - (2 * rel - 1) ** 2))
                scrim_draw.line([(0, y), (width, y)], fill=(12, 14, 20, alpha))
            for y in range(860, 1024):
                alpha = int(100 * ((y - 860) / 164.0))
                scrim_draw.line([(0, y), (width, y)], fill=(10, 10, 15, alpha))
            combined = Image.alpha_composite(bg_image.convert("RGBA"), scrim)

        # 2. 文字排版图层
        text_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)

        clean_title = title.strip()
        lines = []
        if len(clean_title) <= 10:
            lines.append(clean_title)
        else:
            current = ""
            for ch in clean_title:
                current += ch
                if len(current) >= 10 or (len(current) >= 7 and ch in "：:·— -，,"):
                    lines.append(current.strip())
                    current = ""
            if current:
                lines.append(current.strip())
        lines = lines[:3]

        if layout == "dedao_clean":
            # ================= 得到官方极简专栏风（还原参考图 100% 质感） =================
            max_line_len = max(len(l) for l in lines) if lines else 5

            custom_size = None
            if font_size and str(font_size).isdigit():
                val = int(font_size)
                if 40 <= val <= 220:
                    custom_size = val

            if custom_size:
                title_size = custom_size
                author_size = max(40, int(title_size * 0.42))
                stroke_w = 3 if title_size >= 120 else 2
                author_stroke = 1 if author_size < 60 else 2
            else:
                # 智能自适应字号：对标官方专栏巨幅视觉冲击力（短标题 150px，长标题 105~135px）
                if len(lines) == 1:
                    if max_line_len <= 5: # 如《硅谷来信2》
                        title_size = 150
                        author_size = 62
                        stroke_w = 3
                        author_stroke = 1
                    elif max_line_len <= 6:
                        title_size = 135
                        author_size = 58
                        stroke_w = 3
                        author_stroke = 1
                    elif max_line_len <= 7:
                        title_size = 122
                        author_size = 54
                        stroke_w = 3
                        author_stroke = 1
                    elif max_line_len <= 9:
                        title_size = 105
                        author_size = 50
                        stroke_w = 2
                        author_stroke = 1
                    else:
                        title_size = 92
                        author_size = 46
                        stroke_w = 2
                        author_stroke = 1
                else: # 2 ~ 3 行
                    if max_line_len <= 5:
                        title_size = 130
                        author_size = 56
                        stroke_w = 3
                        author_stroke = 1
                    elif max_line_len <= 7:
                        title_size = 112
                        author_size = 52
                        stroke_w = 2
                        author_stroke = 1
                    else:
                        title_size = 95
                        author_size = 46
                        stroke_w = 2
                        author_stroke = 1

            title_font = cls.get_font(title_size) or ImageFont.load_default()
            author_font = cls.get_font(author_size) or ImageFont.load_default()

            line_height = int(title_size * 1.18)
            total_title_h = len(lines) * line_height

            author_block_h = (44 + author_size) if author.strip() else 0
            total_content_h = total_title_h + author_block_h
            start_y = int(height * 0.53) - (total_content_h // 2)

            # A. 主标题：超大号粗体纯白无衬线（带微阴影与矢量描边加粗）
            for i, line in enumerate(lines):
                try:
                    l_bbox = draw.textbbox((0, 0), line, font=title_font, stroke_width=stroke_w)
                    lw = l_bbox[2] - l_bbox[0]
                except Exception:
                    lw = len(line) * int(title_size * 0.95)
                lx = (width - lw) // 2
                ly = start_y + i * line_height

                draw.text((lx + 2, ly + 4), line, font=title_font, fill=(0, 0, 0, 180), stroke_width=stroke_w, stroke_fill=(0, 0, 0, 180))
                draw.text((lx, ly), line, font=title_font, fill=(255, 255, 255, 255), stroke_width=stroke_w, stroke_fill=(255, 255, 255, 255))

            # B. 导师作者：纯粹姓名，香槟金色，居中紧随主标题其下
            if author.strip():
                clean_author = author.strip()
                try:
                    a_bbox = draw.textbbox((0, 0), clean_author, font=author_font, stroke_width=author_stroke)
                    aw = a_bbox[2] - a_bbox[0]
                except Exception:
                    aw = len(clean_author) * int(author_size * 0.9)
                ax = (width - aw) // 2
                ay = start_y + total_title_h + 38
                gold_color = (218, 185, 138, 255) # 得到官方经典香槟金
                draw.text((ax + 1, ay + 2), clean_author, font=author_font, fill=(0, 0, 0, 140), stroke_width=author_stroke, stroke_fill=(0, 0, 0, 140))
                draw.text((ax, ay), clean_author, font=author_font, fill=gold_color, stroke_width=author_stroke, stroke_fill=gold_color)

        else:
            # ================= 大师课典藏徽标风 =================
            badge_font = cls.get_font(26) or ImageFont.load_default()
            title_font = cls.get_font(68) or ImageFont.load_default()
            author_font = cls.get_font(36) or ImageFont.load_default()
            sub_font = cls.get_font(22) or ImageFont.load_default()

            # 胶囊徽标
            badge_text = f"✦  {category.strip() or '得到课程'}  ✦"
            try:
                bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
                bw = bbox[2] - bbox[0]
                bh = bbox[3] - bbox[1]
            except Exception:
                bw, bh = len(badge_text) * 16, 26
            badge_x = (width - bw) // 2
            badge_y = 110
            pad_x, pad_y = 24, 10
            capsule_box = [badge_x - pad_x, badge_y - pad_y, badge_x + bw + pad_x, badge_y + bh + pad_y]
            draw.rounded_rectangle(capsule_box, radius=18, fill=(20, 22, 28, 160), outline=(255, 200, 100, 120), width=1)
            draw.text((badge_x, badge_y), badge_text, font=badge_font, fill=(255, 215, 130, 240))

            # 标题
            line_height = 84
            total_title_h = len(lines) * line_height
            start_y = 440 - (total_title_h // 2)
            for i, line in enumerate(lines):
                try:
                    l_bbox = draw.textbbox((0, 0), line, font=title_font)
                    lw = l_bbox[2] - l_bbox[0]
                except Exception:
                    lw = len(line) * 60
                lx = (width - lw) // 2
                ly = start_y + i * line_height
                draw.text((lx + 2, ly + 3), line, font=title_font, fill=(0, 0, 0, 180))
                draw.text((lx, ly), line, font=title_font, fill=(255, 255, 255, 250))

            # 分割线
            div_y = start_y + total_title_h + 30
            div_w = 90
            draw.line([(width // 2 - div_w // 2, div_y), (width // 2 + div_w // 2, div_y)], fill=(255, 200, 100, 180), width=3)

            # 主讲人
            if author.strip():
                author_text = f"主 讲 人  ·  {author.strip()}"
                try:
                    a_bbox = draw.textbbox((0, 0), author_text, font=author_font)
                    aw = a_bbox[2] - a_bbox[0]
                except Exception:
                    aw = len(author_text) * 25
                ax = (width - aw) // 2
                ay = div_y + 36
                draw.text((ax + 1, ay + 2), author_text, font=author_font, fill=(0, 0, 0, 140))
                draw.text((ax, ay), author_text, font=author_font, fill=(235, 238, 245, 240))

            # 水印
            footer_text = "AUDIOBOOK MASTERCLASS COLLECTION  •  EXCLUSIVE EDITION"
            try:
                f_bbox = draw.textbbox((0, 0), footer_text, font=sub_font)
                fw = f_bbox[2] - f_bbox[0]
            except Exception:
                fw = len(footer_text) * 12
            fx = (width - fw) // 2
            fy = height - 90
            draw.text((fx, fy), footer_text, font=sub_font, fill=(255, 255, 255, 80))

        # 融合图层
        final_img = Image.alpha_composite(combined, text_layer).convert("RGB")
        return final_img

    @classmethod
    def generate_cover(cls, title, author="", category="得到课程", prompt="", engine="comfyui", comfyui_url="http://host.docker.internal:8188", style="amber_dark", quality="fast", layout="dedao_clean", font_size="auto"):
        """统一生成主入口"""
        bg_image = None
        source_note = "local_geometric"

        # 1. 尝试 ComfyUI 生成
        if engine == "comfyui":
            try:
                bg_prompt = prompt.strip() or f"minimalist abstract geometry illustration for knowledge course '{title}', modern art gallery aesthetic"
                bg_image = cls.call_comfyui_moss_image(bg_prompt, comfyui_url=comfyui_url, quality=quality, timeout=240)
                source_note = "comfyui_moss_image"
            except Exception as e:
                # 若失败，自动无缝降级为高颜值本地几何渐变引擎
                bg_image = cls.generate_gradient_background(style=style)
                source_note = f"comfyui_fallback_to_geometric: {str(e)}"
        else:
            bg_image = cls.generate_gradient_background(style=style)
            source_note = "local_geometric"

        # 2. 叠加得到风格高级排版
        final_cover = cls.overlay_course_typography(bg_image, title=title, author=author, category=category, layout=layout, font_size=font_size)

        # 3. 输出 base64 数据
        buffer = io.BytesIO()
        final_cover.save(buffer, format="JPEG", quality=95)
        img_bytes = buffer.getvalue()
        base64_str = "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode("utf-8")

        return {
            "image_base64": base64_str,
            "source": source_note,
            "image_bytes": img_bytes
        }

    @classmethod
    def save_and_embed_cover(cls, folder_path, image_bytes, embed_to_files=True):
        """保存 cover.jpg 并可选嵌入到当前目录下所有音频文件"""
        if not os.path.isdir(folder_path):
            raise FileNotFoundError(f"目录不存在: {folder_path}")

        # 1. 保存 cover.jpg 到目录
        cover_path = os.path.join(folder_path, "cover.jpg")
        with open(cover_path, "wb") as f:
            f.write(image_bytes)

        updated_count = 0
        if embed_to_files:
            # 2. 遍历目录中的音频文件并内嵌封面
            for fname in os.listdir(folder_path):
                fpath = os.path.join(folder_path, fname)
                if not os.path.isfile(fpath):
                    continue
                ext = os.path.splitext(fname)[1].lower()
                try:
                    if ext == ".mp3":
                        import mutagen.id3
                        from mutagen.id3 import ID3, APIC
                        try:
                            audio = ID3(fpath)
                        except Exception:
                            audio = ID3()
                        audio.delall('APIC')
                        audio.add(APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3, # 3 is front cover
                            desc='Cover',
                            data=image_bytes
                        ))
                        audio.save(fpath, v2_version=3)
                        updated_count += 1
                    elif ext == ".flac":
                        import mutagen.flac
                        from mutagen.flac import FLAC, Picture
                        audio = FLAC(fpath)
                        pic = Picture()
                        pic.data = image_bytes
                        pic.type = 3
                        pic.mime = "image/jpeg"
                        audio.clear_pictures()
                        audio.add_picture(pic)
                        audio.save()
                        updated_count += 1
                    elif ext in [".m4a", ".mp4"]:
                        import mutagen.mp4
                        from mutagen.mp4 import MP4, MP4Cover
                        audio = MP4(fpath)
                        audio["covr"] = [MP4Cover(image_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
                        audio.save()
                        updated_count += 1
                except Exception as e:
                    # 单曲写入跳过错误
                    pass

        return {
            "cover_path": cover_path,
            "embedded_files": updated_count
        }

