import os
import json
import math
import random
import subprocess
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

WIDTH = 1280
HEIGHT = 720
FPS = 15
TTS_SPEED = 1.2

NEON_COLORS = [
    "#00FFFF", "#FF00FF", "#00FF00", "#FFFF00", "#FF0080", "#00FF80",
    "#8000FF", "#FF8000", "#0080FF", "#FF0088", "#80FF00", "#FF00B0",
    "#00B0FF", "#B0FF00", "#FF00B0", "#00FFB0", "#B000FF", "#FFB000",
]

TTS_VOICE = "en-US-JennyNeural"

BG_COLORS = [
    (20, 20, 35), (25, 25, 40), (30, 25, 35), (15, 20, 30), (25, 20, 35),
    (22, 22, 38), (18, 25, 35), (28, 22, 35),
]

ANIMATIONS = [
    "fade_up", "fade_down", "fade_in", "slide_left", "slide_right",
    "slide_up", "slide_down", "scale_in", "scale_out",
    "zoom_in", "zoom_out", "rotate_in", "spiral_in",
    "bounce_in", "elastic_in", "back_in", "circular_in",
    "flip_x", "flip_y", "roll_in", "blur_in",
    "wipe_left", "wipe_right", "wipe_up", "wipe_down",
    "mask_circle", "mask_square", "clip_left", "clip_right",
    "expand_out", "contract_in", "falling", "rising",
    "wave_left", "wave_right", "wave_up", "wave_down",
    "shimmer", "flash", "pop_in", "squeeze",
    "stretch_x", "stretch_y", "shear_left", "shear_right",
    "random_fade", "random_slide", "sequence_fade", "cascade",
    "stagger_up", "stagger_down", "alternating", "snake"
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

def parse_vtt(vtt_path):
    with open(vtt_path, 'r') as f:
        content = f.read()
    
    subtitles = []
    lines = content.strip().split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if '-->' in line:
            parts = line.split('-->')
            start = parse_time(parts[0].strip())
            end = parse_time(parts[1].strip())
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit():
                text_lines.append(lines[i].strip())
                i += 1
            text = ' '.join(text_lines)
            subtitles.append({
                "start": start, "end": end, "text": text, "words": text.split()
            })
        i += 1
    return subtitles

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def get_font(size):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()

def wrap_words(words, font, max_width, draw):
    lines, current_line, current_width = [], [], 0
    for word in words:
        word_w = draw.textbbox((0, 0), word, font=font)[2]
        test_w = current_width + word_w if not current_line else current_width + word_w + 12
        if test_w <= max_width:
            current_line.append(word)
            current_width = test_w
        else:
            if current_line:
                lines.append(current_line)
            current_line = [word]
            current_width = word_w
    if current_line:
        lines.append(current_line)
    return lines

async def generate_tts(text, output_file):
    comm = edge_tts.Communicate(text, TTS_VOICE)
    await comm.save(output_file)

def get_audio_duration(audio_file):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", audio_file],
        capture_output=True, text=True
    )
    return float(json.loads(result.stdout)["format"]["duration"])

def get_word_animation_offset(anim, word_progress, word_idx):
    pp = max(0, min(1, word_progress))
    delay = word_idx * 0.08
    delayed_pp = max(0, min(1, pp * 1.5 - delay))
    ease = delayed_pp * (2 - delayed_pp)
    
    if anim == "fade_up":
        return 0, int(-20 * (1 - ease))
    elif anim == "fade_down":
        return 0, int(20 * (1 - ease))
    elif anim == "fade_in":
        return 0, 0
    elif anim == "slide_left":
        return int(-30 * (1 - ease)), 0
    elif anim == "slide_right":
        return int(30 * (1 - ease)), 0
    elif anim == "slide_up":
        return 0, int(-25 * (1 - ease))
    elif anim == "slide_down":
        return 0, int(25 * (1 - ease))
    elif anim == "scale_in":
        return 0, 0
    elif anim == "scale_out":
        return 0, 0
    elif anim == "zoom_in":
        return 0, 0
    elif anim == "zoom_out":
        return 0, 0
    elif anim == "rotate_in":
        return 0, 0
    elif anim == "spiral_in":
        return 0, 0
    elif anim == "bounce_in":
        return 0, int(-10 * math.sin(delayed_pp * math.pi))
    elif anim == "elastic_in":
        return 0, int(-15 * (1 - ease))
    elif anim == "back_in":
        return 0, int(-15 * (1 - ease))
    elif anim == "circular_in":
        return 0, int(-10 * (1 - ease))
    elif anim == "flip_x":
        return 0, 0
    elif anim == "flip_y":
        return 0, 0
    elif anim == "roll_in":
        return int(20 * (1 - ease)), int(-15 * math.sin(delayed_pp * math.pi))
    elif anim == "blur_in":
        return 0, 0
    elif anim == "wipe_left":
        return int(-25 * (1 - ease)), 0
    elif anim == "wipe_right":
        return int(25 * (1 - ease)), 0
    elif anim == "wipe_up":
        return 0, int(-20 * (1 - ease))
    elif anim == "wipe_down":
        return 0, int(60 * (1 - ease))
    elif anim == "mask_circle":
        return 0, 0
    elif anim == "mask_square":
        return 0, 0
    elif anim == "clip_left":
        return int(-30 * (1 - ease)), 0
    elif anim == "clip_right":
        return int(30 * (1 - ease)), 0
    elif anim == "expand_out":
        return 0, 0
    elif anim == "contract_in":
        return 0, 0
    elif anim == "falling":
        return 0, int(-20 * (1 - ease))
    elif anim == "rising":
        return 0, int(20 * (1 - ease))
    elif anim == "wave_left":
        return int(-10 * math.sin(delayed_pp * math.pi)), 0
    elif anim == "wave_right":
        return int(10 * math.sin(delayed_pp * math.pi)), 0
    elif anim == "wave_up":
        return 0, int(-8 * math.sin(delayed_pp * math.pi))
    elif anim == "wave_down":
        return 0, int(8 * math.sin(delayed_pp * math.pi))
    elif anim == "shimmer":
        return int(2 * math.sin(delayed_pp * 20)), 0
    elif anim == "flash":
        return 0, 0
    elif anim == "pop_in":
        return 0, int(-8 * (1 - delayed_pp) * delayed_pp * 4)
    elif anim == "squeeze":
        return int(5 * (1 - delayed_pp)), 0
    elif anim == "stretch_x":
        return int(-8 * math.sin(delayed_pp * math.pi)), 0
    elif anim == "stretch_y":
        return 0, int(-8 * math.sin(delayed_pp * math.pi))
    elif anim == "shear_left":
        return int(-15 * delayed_pp * (1 - delayed_pp) * 4), 0
    elif anim == "shear_right":
        return int(15 * delayed_pp * (1 - delayed_pp) * 4), 0
    elif anim == "random_fade":
        return 0, int(-10 * (1 - ease))
    elif anim == "random_slide":
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        dx, dy = dirs[word_idx % 4]
        return int(dx * 20 * (1 - ease)), int(dy * 20 * (1 - ease))
    elif anim == "sequence_fade":
        return 0, int(-12 * (1 - ease))
    elif anim == "cascade":
        return 0, int(-10 * (1 - ease))
    elif anim == "stagger_up":
        return 0, int(-15 * (1 - ease))
    elif anim == "stagger_down":
        return 0, int(15 * (1 - ease))
    elif anim == "alternating":
        if word_idx % 2 == 0:
            return int(-15 * (1 - ease)), 0
        return int(15 * (1 - ease)), 0
    elif anim == "snake":
        wave = 8 * math.sin(delayed_pp * math.pi * 2 + word_idx * 0.3)
        return int(wave), 0
    
    return 0, 0

BG_EFFECTS = ["subtle", "blur", "gradient", "soft", "minimal"]

def draw_background_effects(draw, colors, progress, effect):
    bg_color = hex_to_rgb(colors[0])
    
    if effect == "subtle":
        alpha = int(3 + 2 * math.sin(progress * math.pi))
        for x in range(0, WIDTH, 100):
            draw.line([(x, 0), (x, HEIGHT)], fill=(*bg_color, alpha), width=1)
        for y in range(0, HEIGHT, 100):
            draw.line([(0, y), (WIDTH, y)], fill=(*bg_color, alpha), width=1)
    
    elif effect == "blur":
        for i in range(20):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            r = random.randint(30, 80)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*bg_color, 3))
    
    elif effect == "gradient":
        for y in range(0, HEIGHT, 20):
            alpha = int(2 + 3 * math.sin((y / HEIGHT) * math.pi + progress * math.pi))
            draw.line([(0, y), (WIDTH, y)], fill=(*bg_color, alpha))
    
    elif effect == "soft":
        for i in range(8):
            x = WIDTH // 8 * i + 40 + int(10 * math.sin(progress * math.pi * 2 + i))
            y = HEIGHT // 2 + int(20 * math.cos(progress * math.pi + i))
            r = 40 + int(15 * math.sin(progress * math.pi))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(*bg_color, 4))
    
    elif effect == "minimal":
        alpha = int(5 + 3 * math.sin(progress * math.pi))
        for x in range(0, WIDTH, 120):
            draw.line([(x, 0), (x, HEIGHT)], fill=(*bg_color, alpha), width=1)

def draw_frame(words, frame_time, scene_start, scene_duration, output_path, colors, bg, anim_type, bg_effect):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    
    progress = (frame_time - scene_start) / scene_duration
    progress = max(0, min(1, progress))
    
    draw_background_effects(draw, colors, progress, bg_effect)
    
    font = get_font(48)
    progress = (frame_time - scene_start) / scene_duration
    progress = max(0, min(1, progress))
    
    word_count = len(words)
    speed_factor = 2.5
    adjusted_progress = min(1.0, progress * speed_factor)
    words_per_moment = int(word_count * adjusted_progress)
    if words_per_moment == 0 and progress > 0:
        words_per_moment = 1
    
    all_lines = wrap_words(words, font, WIDTH - 150, draw)
    visible_count = min(words_per_moment, word_count)
    
    if visible_count > 0:
        visible_words = words[:visible_count]
        lines = wrap_words(visible_words, font, WIDTH - 150, draw)
    else:
        lines = []
    
    line_h = 60
    total_h = len(lines) * line_h
    start_y = (HEIGHT - total_h) // 2
    
    for line_idx, line in enumerate(lines):
        line_w = sum(draw.textbbox((0, 0), w, font=font)[2] for w in line)
        line_w += (len(line) - 1) * 12
        x = (WIDTH - line_w) // 2
        y = start_y + line_idx * line_h
        
        for w_idx, word in enumerate(line):
            global_idx = sum(len(lines[i]) for i in range(line_idx)) + w_idx
            word_delay = global_idx * 0.04
            word_progress = max(0, min(1, (adjusted_progress - word_delay) * 4))
            
            if global_idx >= words_per_moment:
                continue
            
            ox, oy = get_word_animation_offset(anim_type, word_progress, global_idx)
            
            color = colors[global_idx % len(colors)]
            rgb = hex_to_rgb(color)
            
            if anim_type in ["shimmer", "flash"]:
                lighter = tuple(min(255, c + 50) for c in rgb)
                draw.text((x + ox - 1, y + oy), word, fill=lighter, font=font)
                draw.text((x + ox + 1, y + oy), word, fill=lighter, font=font)
            
            draw.text((x + ox, y + oy), word, fill=rgb, font=font)
            x += draw.textbbox((0, 0), word, font=font)[2] + 12
    
    img.save(output_path, "PNG")

def main(vtt_path=None):
    output_dir = os.path.join(SCRIPT_DIR, "output")
    scenes_dir = os.path.join(SCRIPT_DIR, "scenes")
    if vtt_path is None:
        source_vtt = os.path.join(SCRIPT_DIR, "source.vtt")
    else:
        source_vtt = vtt_path
    
    for folder in [output_dir, scenes_dir]:
        os.makedirs(folder, exist_ok=True)
        for file in os.listdir(folder):
            path = os.path.join(folder, file)
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
    
    print("Reading source subtitles...")
    print(f"Source: {source_vtt}")
    subtitles = parse_vtt(source_vtt)
    print(f"Found {len(subtitles)} subtitles")
    
    scene_videos = []
    
    print("\n=== Processing each scene ===\n")
    
    for i, sub in enumerate(subtitles):
        print(f"Scene {i+1}: {sub['text'][:50]}...")
        
        tts_text = sub["text"] + "."
        scene_audio = os.path.join(scenes_dir, f"scene_{i:03d}.mp3")
        scene_frames_dir = os.path.join(scenes_dir, f"frames_{i:03d}")
        scene_video = os.path.join(scenes_dir, f"scene_{i:03d}.mp4")
        
        os.makedirs(scene_frames_dir, exist_ok=True)
        
        print(f"  Generating TTS...")
        asyncio.run(generate_tts(tts_text, scene_audio))
        
        scene_duration = get_audio_duration(scene_audio) / TTS_SPEED
        print(f"  TTS duration: {scene_duration:.2f}s")
        
        bg = random.choice(BG_COLORS)
        colors = random.sample(NEON_COLORS, 3)
        anim = random.choice(ANIMATIONS)
        bg_effect = random.choice(BG_EFFECTS)
        
        num_frames = int(scene_duration * FPS)
        print(f"  Generating {num_frames} frames with {anim} animation and {bg_effect} background...")
        
        for frame_num in range(num_frames):
            frame_time = frame_num / FPS
            frame_path = os.path.join(scene_frames_dir, f"frame_{frame_num:05d}.png")
            draw_frame(sub["words"], frame_time, 0, scene_duration, 
                      frame_path, colors, bg, anim, bg_effect)
        
        print(f"  Creating scene video...")
        result = subprocess.run([
            "ffmpeg", "-y", "-framerate", str(FPS),
            "-i", os.path.join(scene_frames_dir, "frame_%05d.png"),
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
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
        final_video
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"\n=== Done! ===")
        print(f"Video: {final_video}")
    else:
        print(f"Error: {result.stderr[-300:]}")

if __name__ == "__main__":
    import sys
    vtt_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(vtt_arg)
