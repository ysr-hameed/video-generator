import os
import math
import random
import subprocess
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from multiprocessing import Pool, cpu_count

WIDTH = 1920
HEIGHT = 1080
FPS = 30
TTS_SPEED = 1.0
NUM_WORKERS = max(1, cpu_count() - 1)

def _render_frame(args):
    frame_num, scene_frames_dir, frame_data = args
    scene_duration, words, colors, bg, anim_type, bg_effect, sub_type, primary_color, use_glass, text_palette, current_heading = frame_data
    frame_time = frame_num / FPS
    frame_path = os.path.join(scene_frames_dir, f"frame_{frame_num:05d}.jpg")
    _draw_single_frame(frame_num, frame_time, scene_duration, frame_path, words, colors, bg, anim_type, bg_effect, sub_type, primary_color, use_glass, text_palette, current_heading)
    return frame_num

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

WIDTH = 1920
HEIGHT = 1080
FPS = 30
TTS_SPEED = 1.0

PRIMARY_COLORS = [
    "#4FC3F7", "#29B6F6", "#03A9F4", "#00BCD4", "#26C6DA",
    "#66BB6A", "#43A047", "#FFA726", "#FB8C00", "#EF5350",
    "#AB47BC", "#7E57C2", "#FF7043", "#EC407A", "#26A69A",
]

TEXT_PALETTES = [
    ["#FFFFFF", "#E0E0E0", "#C0C0C0"],
    ["#FFFFFF", "#4FC3F7", "#29B6F6"],
    ["#FFFFFF", "#66BB6A", "#43A047"],
    ["#FFFFFF", "#FFA726", "#FB8C00"],
    ["#FFFFFF", "#AB47BC", "#7E57C2"],
    ["#FFFFFF", "#EF5350", "#EC407A"],
    ["#FFFFFF", "#26C6DA", "#26A69A"],
    ["#E0E0E0", "#FFFFFF", "#BDBDBD"],
]

TTS_VOICE = "en-US-JennyNeural"

BG_COLORS = [
    (8, 8, 18), (10, 10, 22), (12, 10, 20), (9, 9, 20), (11, 11, 24),
]

BG_EFFECTS = ["minimal", "soft", "dots", "glow", "waves", "circles", "sparkle", "particle"]

WORD_ANIMATIONS = [
    "fade_in", "fade_up", "fade_down", "slide_left", "slide_right",
    "slide_up", "slide_down", "scale_in", "bounce_in", "elastic_in",
    "wave", "cascade", "typewriter", "blur_in", "glow_in",
    "stagger", "random_slide", "zoom_in", "pop_in", "shine_in"
]

def parse_time(time_str):
    time_str = time_str.strip()
    parts = time_str.split(':')
    if len(parts) == 3:
        h = int(parts[0])
        m = int(parts[1])
        s_ms = parts[2].split('.')
        s = int(s_ms[0])
        ms = int(s_ms[1]) if len(s_ms) > 1 else 0
        return h * 3600 + m * 60 + s + ms / 1000
    elif len(parts) == 2:
        m = int(parts[0])
        s_ms = parts[1].split('.')
        s = int(s_ms[0])
        ms = int(s_ms[1]) if len(s_ms) > 1 else 0
        return m * 60 + s + ms / 1000
    return 0

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_font(size):
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue
    return ImageFont.load_default()

def ease_out(t):
    return 1 - (1 - t) * (1 - t)

def ease_in_out(t):
    return t * t * (3 - 2 * t)

def wrap_words(words, font, max_width, draw):
    lines = []
    current_line = []
    for word in words:
        current_line.append(word)
        line_text = ' '.join(current_line)
        bbox = draw.textbbox((0, 0), line_text, font=font)
        if bbox[2] > max_width and len(current_line) > 1:
            current_line.pop()
            lines.append(current_line)
            current_line = [word]
    if current_line:
        lines.append(current_line)
    return lines if lines else [[]]

def parse_vtt(file_path):
    subtitles = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.strip().split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('#'):
                sub_type = 'HEADING' if 'HEADING' in line.upper() else 'PARAGRAPH'
                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('#'):
                    text_lines.append(lines[i].strip())
                    i += 1
                text = ' '.join(text_lines)
                if text:
                    subtitles.append({
                        'num': len(subtitles) + 1,
                        'text': text,
                        'type': sub_type,
                        'time': ''
                    })
            
            elif '-->' in line:
                parts = line.split('-->')
                start = parse_time(parts[0])
                end = parse_time(parts[1])
                duration = end - start
                i += 1
                text_lines = []
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        i += 1
                        continue
                    if next_line.startswith('#') or (next_line and next_line[0].isdigit() and '-->' not in next_line):
                        break
                    text_lines.append(next_line)
                    i += 1
                text = ' '.join(text_lines)
                if text:
                    subtitles.append({
                        'num': len(subtitles) + 1,
                        'text': text,
                        'type': 'PARAGRAPH',
                        'time': f"{parts[0].strip()} --> {parts[1].strip()}",
                        'start': start,
                        'end': end,
                        'duration': duration
                    })
            else:
                i += 1
        
        for sub in subtitles:
            words = sub['text'].split()
            sub['words'] = words
            
    except Exception as e:
        print(f"Error parsing VTT: {e}")
    
    return subtitles

def draw_background_effects(draw, colors, progress, effect, frame_num):
    c1 = hex_to_rgb(colors[0])
    t = progress
    
    if effect == "minimal":
        for i in range(8):
            x = int(WIDTH * (0.2 + 0.6 * (i / 7)) + 40 * math.sin(t * math.pi + i * 0.6))
            y = int(HEIGHT * 0.4 + 60 * math.cos(t * math.pi * 0.8 + i * 0.5))
            r = max(80, 150 + int(80 * abs(math.sin(t * math.pi * 0.5 + i * 0.2))))
            alpha = 6
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*c1, alpha))
    
    elif effect == "soft":
        for i in range(10):
            x = int(WIDTH * (0.15 + 0.7 * (i / 9)) + 50 * math.sin(t * math.pi * 0.7 + i * 0.4))
            y = int(HEIGHT * 0.3 + (HEIGHT * 0.4) * ((i * 31) % 5) / 5 + 40 * math.cos(t * math.pi * 0.6 + i * 0.3))
            r = max(100, 150 + int(80 * abs(math.sin(t * math.pi * 0.4 + i * 0.15))))
            alpha = 5
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*c1, alpha))
    
    elif effect == "dots":
        for i in range(35):
            x = int((i * 67 + frame_num * 3) % WIDTH)
            y = int((i * 43 + frame_num * 2) % HEIGHT)
            r = max(5, 15 + int(10 * abs(math.sin(t * math.pi * 2 + i * 0.3))))
            alpha = 10
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*c1, alpha))
    
    elif effect == "glow":
        for i in range(6):
            x = int(WIDTH * (0.25 + 0.5 * (i / 5)) + 30 * math.sin(t * math.pi + i * 0.5))
            y = int(HEIGHT * 0.4 + 50 * math.cos(t * math.pi * 0.7 + i * 0.4))
            r = max(100, 200 + int(100 * abs(math.sin(t * math.pi * 0.3 + i * 0.2))))
            alpha = 4
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*c1, alpha))
    
    elif effect == "waves":
        for w in range(8):
            y_base = int(HEIGHT * 0.25 + HEIGHT * 0.5 * (w / 7))
            for x in range(0, WIDTH, 100):
                y_offset = int(30 * math.sin((x / 120) + t * math.pi * 2 + w * 0.5))
                r = max(15, 40 + int(20 * abs(math.sin(t * math.pi + w * 0.3))))
                alpha = 6
                draw.ellipse([x - r, y_base + y_offset - r, x + r, y_base + y_offset + r], fill=(*c1, alpha))
    
    elif effect == "circles":
        cx, cy = WIDTH // 2, HEIGHT // 2
        for i in range(10):
            base_r = 100 + i * 90
            r = max(30, base_r + int(40 * math.sin(t * math.pi * 2 + i * 0.5)))
            alpha = int(4 + 3 * abs(math.sin(t * math.pi + i * 0.3)))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(*c1, alpha), width=3)
    
    elif effect == "sparkle":
        for i in range(45):
            x = int((i * 73 + int(t * 80)) % WIDTH)
            y = int((i * 47) % HEIGHT + 30 * math.sin(t * math.pi * 2 + i * 0.3))
            r = max(3, 10 + int(8 * abs(math.sin(t * math.pi * 3 + i * 0.4))))
            alpha = int(12 + 10 * abs(math.sin(t * math.pi * 2 + i * 0.5)))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*c1, alpha))
    
    elif effect == "particle":
        for i in range(30):
            angle = t * math.pi * 2 + i * 0.3
            dist = 150 + i * 30
            x = int(WIDTH // 2 + dist * math.cos(angle))
            y = int(HEIGHT // 2 + dist * math.sin(angle))
            r = max(8, 20 + int(12 * abs(math.sin(t * math.pi * 2 + i * 0.2))))
            alpha = 8
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*c1, alpha))

def draw_glass_bar(draw, colors, progress):
    c1 = hex_to_rgb(colors[0])
    
    bar_height = int(HEIGHT * 0.35)
    bar_y = (HEIGHT - bar_height) // 2
    
    overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    glow_intensity = 0.3 + 0.2 * math.sin(progress * math.pi)
    
    for i in range(5):
        offset = i * 3
        alpha = int(20 * glow_intensity * (1 - i * 0.15))
        overlay_draw.rectangle([offset, bar_y - offset, WIDTH - offset, bar_y + bar_height + offset], 
                              fill=(c1[0], c1[1], c1[2], alpha))
    
    overlay_draw.rectangle([0, bar_y, WIDTH, bar_y + bar_height], fill=(0, 0, 0, 100))
    
    for y in range(bar_y, bar_y + bar_height, 4):
        line_alpha = int(15 + 10 * math.sin((y / bar_height) * math.pi * 2 + progress * math.pi))
        overlay_draw.line([(0, y), (WIDTH, y)], fill=(255, 255, 255, line_alpha), width=1)
    
    img = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
    temp_img = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
    temp_draw = ImageDraw.Draw(temp_img)
    
    return overlay

def _draw_single_frame(frame_num, frame_time, scene_duration, output_path, words, colors, bg, anim_type, bg_effect, sub_type, primary_color, use_glass, text_palette, current_heading=None):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    
    progress = frame_time / scene_duration
    progress = max(0, min(1, progress))
    
    draw_background_effects(draw, colors, progress, bg_effect, frame_num)
    
    dark_overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    dark_draw = ImageDraw.Draw(dark_overlay)
    dark_draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(0, 0, 0, 100))
    img = Image.alpha_composite(img.convert('RGBA'), dark_overlay).convert('RGB')
    draw = ImageDraw.Draw(img)
    
    p_color = hex_to_rgb(primary_color)
    
    if use_glass:
        glass_overlay = draw_glass_bar(draw, colors, progress)
        img = Image.alpha_composite(img.convert('RGBA'), glass_overlay).convert('RGB')
        draw = ImageDraw.Draw(img)
    
    HEADING_END_X = 150
    HEADING_END_Y = 120
    HEADING_START_SIZE = 90
    HEADING_END_SIZE = 48
    
    if sub_type == 'HEADING':
        heading_progress = min(1.0, progress * 1.8)
        
        full_text = ' '.join(words)
        text_len = len(full_text)
        type_progress = min(1.0, heading_progress * 1.5)
        visible_count = int(text_len * type_progress)
        
        if heading_progress < 0.7:
            move_t = 0
        else:
            move_t = min(1.0, (heading_progress - 0.7) / 0.3)
        
        ease = ease_out(move_t)
        
        heading_font = get_font(HEADING_START_SIZE)
        temp_draw = ImageDraw.Draw(img)
        bbox = temp_draw.textbbox((0, 0), full_text, font=heading_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        start_x = WIDTH // 2 - text_width // 2
        start_y = HEIGHT // 2 - text_height // 2
        
        x = int(start_x + (HEADING_END_X - start_x) * ease)
        y = int(start_y + (HEADING_END_Y - start_y) * ease)
        font_size = int(HEADING_START_SIZE + (HEADING_END_SIZE - HEADING_START_SIZE) * ease)
        heading_font = get_font(font_size)
        
        if visible_count > 0:
            visible_text = full_text[:visible_count]
            draw.text((x + 3, y + 3), visible_text, fill=(0, 0, 0), font=heading_font)
            draw.text((x, y), visible_text, fill=p_color, font=heading_font)
    
    elif sub_type == 'PARAGRAPH' and len(words) > 0:
        if current_heading and current_heading.get("text"):
            h_color = hex_to_rgb(current_heading.get("color", "#FFFFFF"))
            h_font = get_font(HEADING_END_SIZE)
            h_x, h_y = HEADING_END_X, HEADING_END_Y
            draw.text((h_x + 3, h_y + 3), current_heading["text"], fill=(0, 0, 0), font=h_font)
            draw.text((h_x, h_y), current_heading["text"], fill=h_color, font=h_font)
        
        word_reveal = min(1.0, progress * 2.5)
        visible_count = max(1, int(len(words) * word_reveal))
        visible_words = words[:visible_count]
        font = get_font(64)
        lines = wrap_words(visible_words, font, WIDTH - 300, draw)
        line_h = 90
        total_h = len(lines) * line_h
        start_y = (HEIGHT - total_h) // 2
        for line_idx, line in enumerate(lines):
            line_w = sum(draw.textbbox((0, 0), w, font=font)[2] for w in line)
            line_w += (len(line) - 1) * 18
            x = (WIDTH - line_w) // 2
            y = start_y + line_idx * line_h
            for w_idx, word in enumerate(line):
                global_idx = sum(len(lines[i]) for i in range(line_idx)) + w_idx
                word_delay = global_idx * 0.08
                word_p = max(0, min(1, (word_reveal - word_delay) * 4))
                ease = ease_out(word_p)
                if anim_type == "fade_in":
                    ox, oy = 0, 0
                elif anim_type == "fade_up":
                    ox, oy = 0, int(-30 * (1 - ease))
                elif anim_type == "fade_down":
                    ox, oy = 0, int(30 * (1 - ease))
                elif anim_type == "slide_left":
                    ox, oy = int(-40 * (1 - ease)), 0
                elif anim_type == "slide_right":
                    ox, oy = int(40 * (1 - ease)), 0
                elif anim_type == "slide_up":
                    ox, oy = 0, int(-35 * (1 - ease))
                elif anim_type == "slide_down":
                    ox, oy = 0, int(35 * (1 - ease))
                elif anim_type == "scale_in":
                    ox, oy = 0, 0
                elif anim_type == "bounce_in":
                    bounce = 1 + 0.3 * math.sin(ease * math.pi)
                    ox, oy = 0, int(-20 * (1 - ease) * bounce)
                elif anim_type == "elastic_in":
                    elastic = ease * (2 - ease)
                    ox, oy = 0, int(-25 * (1 - elastic))
                elif anim_type == "wave":
                    ox = int(15 * math.sin(global_idx * 0.6 + ease * math.pi * 2))
                    oy = 0
                elif anim_type == "cascade":
                    ox = int(-20 * (1 - ease))
                    oy = int(-15 * (1 - ease))
                elif anim_type == "typewriter":
                    ox = int(-30 * (1 - ease))
                    oy = 0
                elif anim_type == "blur_in":
                    ox, oy = 0, 0
                elif anim_type == "glow_in":
                    ox, oy = 0, 0
                elif anim_type == "stagger":
                    stag_t = max(0, min(1, word_p - line_idx * 0.15 - w_idx * 0.08))
                    stag_ease = ease_out(stag_t)
                    ox, oy = 0, int(-20 * (1 - stag_ease))
                elif anim_type == "random_slide":
                    ox = int(random.choice([-25, 25, 0]) * (1 - ease))
                    oy = 0
                elif anim_type == "zoom_in":
                    ox, oy = 0, 0
                elif anim_type == "pop_in":
                    pop = ease * (2 - ease)
                    ox, oy = 0, int(-15 * (1 - pop))
                elif anim_type == "shine_in":
                    ox, oy = 0, 0
                else:
                    ox, oy = 0, 0
                rgb = hex_to_rgb(text_palette[(line_idx + w_idx) % len(text_palette)]) if text_palette else hex_to_rgb("#FFFFFF")
                draw.text((x + ox + 3, y + oy + 3), word, fill=(0, 0, 0), font=font)
                draw.text((x + ox, y + oy), word, fill=rgb, font=font)
                x += draw.textbbox((0, 0), word, font=font)[2] + 18
    
    img.save(output_path, "JPEG", quality=85)

def draw_frame(words, frame_time, scene_start, scene_duration, output_path, colors, bg, anim_type, bg_effect, sub_type='PARAGRAPH', frame_num=0, primary_color="#FFFFFF", use_glass=False, text_palette=None):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    
    progress = (frame_time - scene_start) / scene_duration
    progress = max(0, min(1, progress))
    
    draw_background_effects(draw, colors, progress, bg_effect, frame_num)
    
    dark_overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    dark_draw = ImageDraw.Draw(dark_overlay)
    dark_draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(0, 0, 0, 100))
    img = Image.alpha_composite(img.convert('RGBA'), dark_overlay).convert('RGB')
    draw = ImageDraw.Draw(img)
    
    p_color = hex_to_rgb(primary_color)
    
    if use_glass:
        glass_overlay = draw_glass_bar(draw, colors, progress)
        img = Image.alpha_composite(img.convert('RGBA'), glass_overlay).convert('RGB')
        draw = ImageDraw.Draw(img)
    
    if sub_type == 'HEADING':
        heading_progress = min(1.0, progress * 1.8)
        
        phase = heading_progress * 3
        
        if phase < 1:
            show_progress = phase
        elif phase < 2:
            show_progress = 1.0
        else:
            show_progress = max(0, 1.0 - (phase - 2))
        
        font_size = int(90 - 40 * min(1.0, show_progress * 1.2))
        heading_font = get_font(font_size)
        
        move_t = max(0, min(1, (heading_progress - 0.3) * 1.5))
        ease_move = ease_out(move_t)
        
        center_x = WIDTH // 2
        center_y = HEIGHT // 2
        
        target_x = 150
        target_y = 120
        
        x = int(center_x + (target_x - center_x) * ease_move)
        y = int(center_y + (target_y - center_y) * ease_move)
        
        visible_count = int(len(' '.join(words)) * min(1.0, heading_progress * 2))
        if visible_count > 0 and heading_progress > 0.1:
            visible_text = ' '.join(words)[:visible_count]
            
            bbox = draw.textbbox((0, 0), visible_text, font=heading_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            if move_t < 0.5:
                draw.text((x + 4, y + 4), visible_text, fill=(0, 0, 0), font=heading_font)
                draw.text((x, y), visible_text, fill=p_color, font=heading_font)
            else:
                draw.text((x + 4, y + 4), visible_text, fill=(0, 0, 0), font=heading_font)
                draw.text((x, y), visible_text, fill=p_color, font=heading_font)
                
                glow_alpha = int(40 * (1 - (move_t - 0.5) * 2))
                if glow_alpha > 0:
                    glow_draw = ImageDraw.Draw(img)
                    glow_draw.text((x - 1, y - 1), visible_text, fill=(p_color[0], p_color[1], p_color[2], glow_alpha), font=heading_font)
                    glow_draw.text((x + 1, y + 1), visible_text, fill=(p_color[0], p_color[1], p_color[2], glow_alpha), font=heading_font)
    
    elif sub_type == 'PARAGRAPH' and len(words) > 0:
        word_reveal = min(1.0, progress * 2.5)
        visible_count = max(1, int(len(words) * word_reveal))
        visible_words = words[:visible_count]
        
        font = get_font(64)
        lines = wrap_words(visible_words, font, WIDTH - 300, draw)
        
        line_h = 90
        total_h = len(lines) * line_h
        start_y = (HEIGHT - total_h) // 2
        
        for line_idx, line in enumerate(lines):
            line_w = sum(draw.textbbox((0, 0), w, font=font)[2] for w in line)
            line_w += (len(line) - 1) * 18
            x = (WIDTH - line_w) // 2
            y = start_y + line_idx * line_h
            
            for w_idx, word in enumerate(line):
                global_idx = sum(len(lines[i]) for i in range(line_idx)) + w_idx
                word_delay = global_idx * 0.08
                word_p = max(0, min(1, (word_reveal - word_delay) * 4))
                ease = ease_out(word_p)
                
                if anim_type == "fade_in":
                    ox, oy = 0, 0
                elif anim_type == "fade_up":
                    ox, oy = 0, int(-30 * (1 - ease))
                elif anim_type == "fade_down":
                    ox, oy = 0, int(30 * (1 - ease))
                elif anim_type == "slide_left":
                    ox, oy = int(-40 * (1 - ease)), 0
                elif anim_type == "slide_right":
                    ox, oy = int(40 * (1 - ease)), 0
                elif anim_type == "slide_up":
                    ox, oy = 0, int(-35 * (1 - ease))
                elif anim_type == "slide_down":
                    ox, oy = 0, int(35 * (1 - ease))
                elif anim_type == "scale_in":
                    ox, oy = 0, 0
                elif anim_type == "bounce_in":
                    bounce = 1 + 0.3 * math.sin(ease * math.pi)
                    ox, oy = 0, int(-20 * (1 - ease) * bounce)
                elif anim_type == "elastic_in":
                    elastic = ease * (2 - ease)
                    ox, oy = 0, int(-25 * (1 - elastic))
                elif anim_type == "wave":
                    ox = int(15 * math.sin(global_idx * 0.6 + ease * math.pi * 2))
                    oy = 0
                elif anim_type == "cascade":
                    ox = int(-20 * (1 - ease))
                    oy = int(-15 * (1 - ease))
                elif anim_type == "typewriter":
                    ox = int(-30 * (1 - ease))
                    oy = 0
                elif anim_type == "blur_in":
                    ox, oy = 0, 0
                elif anim_type == "glow_in":
                    ox, oy = 0, 0
                elif anim_type == "stagger":
                    stag_t = max(0, min(1, word_p - line_idx * 0.15 - w_idx * 0.08))
                    stag_ease = ease_out(stag_t)
                    ox, oy = 0, int(-20 * (1 - stag_ease))
                elif anim_type == "random_slide":
                    ox = int(random.choice([-25, 25, 0]) * (1 - ease))
                    oy = 0
                elif anim_type == "zoom_in":
                    ox, oy = 0, 0
                elif anim_type == "pop_in":
                    pop = ease * (2 - ease)
                    ox, oy = 0, int(-15 * (1 - pop))
                elif anim_type == "shine_in":
                    ox, oy = 0, 0
                else:
                    ox, oy = 0, 0
                
                if text_palette:
                    rgb = hex_to_rgb(text_palette[(line_idx + w_idx) % len(text_palette)])
                else:
                    rgb = hex_to_rgb("#FFFFFF")
                
                draw.text((x + ox + 3, y + oy + 3), word, fill=(0, 0, 0), font=font)
                draw.text((x + ox, y + oy), word, fill=rgb, font=font)
                x += draw.textbbox((0, 0), word, font=font)[2] + 18
    
    img.save(output_path, "PNG")

def get_audio_duration(audio_path):
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", audio_path
        ], capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except:
        return 3.0

async def generate_tts(text, output_file, speed=1.0):
    rate = f"+{int((speed - 1) * 100)}%" if speed >= 1 else f"{int((speed - 1) * 100)}%"
    comm = edge_tts.Communicate(text, TTS_VOICE, rate=rate)
    await comm.save(output_file)

def main(vtt_path=None):
    output_dir = os.path.join(SCRIPT_DIR, "output")
    scenes_dir = os.path.join(SCRIPT_DIR, "scenes")
    
    if vtt_path is None:
        source_vtt = os.path.join(SCRIPT_DIR, "source.vtt")
    else:
        source_vtt = vtt_path
    
    for folder in [output_dir, scenes_dir]:
        os.makedirs(folder, exist_ok=True)
    
    for file in os.listdir(scenes_dir):
        path = os.path.join(scenes_dir, file)
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            os.remove(path)
    
    print("Reading source subtitles...")
    print(f"Source: {source_vtt}")
    subtitles = parse_vtt(source_vtt)
    print(f"Found {len(subtitles)} subtitles")
    
    if not subtitles:
        print("No subtitles found!")
        return
    
    scene_videos = []
    current_heading = {"text": None, "color": None}
    
    print("\n=== Processing each scene ===\n")
    
    for i, sub in enumerate(subtitles):
        sub_type = sub.get('type', 'PARAGRAPH')
        print(f"Scene {i+1}: [{sub_type}] {sub['text'][:50]}...")
        
        tts_text = sub["text"] + "."
        scene_audio = os.path.join(scenes_dir, f"scene_{i:03d}.mp3")
        scene_frames_dir = os.path.join(scenes_dir, f"frames_{i:03d}")
        scene_video = os.path.join(scenes_dir, f"scene_{i:03d}.mp4")
        
        os.makedirs(scene_frames_dir, exist_ok=True)
        
        print(f"  Generating TTS...")
        asyncio.run(generate_tts(tts_text, scene_audio, TTS_SPEED))
        
        scene_duration = get_audio_duration(scene_audio)
        print(f"  Duration: {scene_duration:.2f}s")
        
        bg = random.choice(BG_COLORS)
        primary_color = random.choice(PRIMARY_COLORS)
        bg_effect = random.choice(BG_EFFECTS)
        anim_type = random.choice(WORD_ANIMATIONS)
        use_glass = random.random() < 0.3
        text_palette = random.choice(TEXT_PALETTES)
        
        if sub_type == 'HEADING':
            current_heading["text"] = sub["text"]
            current_heading["color"] = primary_color
        
        num_frames = int(scene_duration * FPS)
        print(f"  Frames: {num_frames} | Anim: {anim_type} | BG: {bg_effect} | Colors: {text_palette}")
        
        frame_data = (scene_duration, sub["words"], [primary_color], bg, anim_type, bg_effect, sub_type, primary_color, use_glass, text_palette, current_heading.copy())
        
        with Pool(NUM_WORKERS) as pool:
            tasks = [(fn, scene_frames_dir, frame_data) for fn in range(num_frames)]
            pool.map(_render_frame, tasks)
        
        print(f"  Creating scene video...")
        result = subprocess.run([
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", os.path.join(scene_frames_dir, "frame_%05d.jpg"),
            "-i", scene_audio,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-map", "0:v", "-map", "1:a",
            scene_video
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  Scene video created")
            scene_videos.append(scene_video)
        else:
            print(f"  Error: {result.stderr[-200:]}")
        print()
    
    print("=== Combining all scenes ===")
    
    concat_file = os.path.join(scenes_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for sv in scene_videos:
            f.write(f"file '{os.path.basename(sv)}'\n")
    
    final_video = os.path.join(output_dir, "video.mp4")
    result = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy", final_video
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"\n=== Done! ===")
        print(f"Video: {final_video}")
    else:
        print(f"Error creating final video: {result.stderr}")

def test_animations():
    output_dir = os.path.join(SCRIPT_DIR, "output")
    test_dir = os.path.join(SCRIPT_DIR, "test_animations")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)
    
    for file in os.listdir(test_dir):
        path = os.path.join(test_dir, file)
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        else:
            os.remove(path)
    
    print("=== Testing All Animations ===\n")
    
    test_words = ["One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight"]
    bg = (10, 10, 22)
    
    scene_videos = []
    
    all_tests = []
    for anim in WORD_ANIMATIONS:
        for bg_eff in BG_EFFECTS:
            all_tests.append((anim, bg_eff))
    
    random.shuffle(all_tests)
    
    test_count = 0
    for anim_type, bg_effect in all_tests[:32]:
        test_num = test_count + 1
        
        scene_audio = os.path.join(test_dir, f"scene_{test_num:03d}.mp3")
        scene_frames_dir = os.path.join(test_dir, f"frames_{test_num:03d}")
        scene_video = os.path.join(test_dir, f"scene_{test_num:03d}.mp4")
        
        os.makedirs(scene_frames_dir, exist_ok=True)
        
        label = f"Test {test_num}: {anim_type} + {bg_effect}"
        print(f"Generating: {label}")
        
        async def gen():
            await generate_tts(label, scene_audio)
        asyncio.run(gen())
        
        scene_duration = 4
        num_frames = int(scene_duration * FPS)
        primary_color = PRIMARY_COLORS[test_count % len(PRIMARY_COLORS)]
        text_palette = TEXT_PALETTES[test_count % len(TEXT_PALETTES)]
        
        frame_data = (scene_duration, test_words, [primary_color], bg, anim_type, bg_effect, "PARAGRAPH", primary_color, False, text_palette)
        
        with Pool(NUM_WORKERS) as pool:
            tasks = [(fn, scene_frames_dir, frame_data) for fn in range(num_frames)]
            pool.map(_render_frame, tasks)
        
        result = subprocess.run([
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", os.path.join(scene_frames_dir, "frame_%05d.jpg"),
            "-i", scene_audio,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-map", "0:v", "-map", "1:a",
            scene_video
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            scene_videos.append(scene_video)
            print(f"  Done: {len(scene_videos)} scenes")
        
        test_count += 1
    
    print("\n=== Creating test video ===")
    
    concat_file = os.path.join(test_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for sv in scene_videos:
            f.write(f"file '{os.path.basename(sv)}'\n")
    
    final_video = os.path.join(output_dir, "test_animations.mp4")
    result = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy", final_video
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"\n=== Test Video Created! ===")
        print(f"Video: {final_video}")
        print(f"Total: {len(scene_videos)} scenes ({len(WORD_ANIMATIONS)} animations x {len(BG_EFFECTS)} backgrounds)")
    else:
        print(f"Error: {result.stderr}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_animations()
    else:
        vtt_path = sys.argv[1] if len(sys.argv) > 1 else None
        main(vtt_path)
