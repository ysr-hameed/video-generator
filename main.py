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
    "#FF073A", "#FF2400", "#FF4500", "#FF6347", "#FF6B6B", "#FF7F50", "#FF8C00",
    "#FFD700", "#FFE135", "#ADFF2F", "#7FFF00", "#00FF00", "#39FF14", "#00FF41",
    "#00FF7F", "#00FFFF", "#00BFFF", "#1E90FF", "#4169E1", "#0000FF", "#8A2BE2",
    "#FF00FF", "#FF1493", "#FF69B4", "#DC143C", "#9B59B6", "#8E44AD",
    "#3498DB", "#2980B9", "#1ABC9C", "#16A085", "#2ECC71", "#27AE60",
]

TTS_VOICE = "en-US-JennyNeural"

BG_COLORS = [
    (10, 10, 20), (15, 15, 25), (8, 8, 18), (12, 12, 22), (20, 15, 25),
]

ANIMATIONS = [
    "slide_up", "slide_down", "slide_left", "slide_right",
    "bounce", "wave", "pulse", "elastic",
    "fade_in", "pop", "float", "drop"
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
    if anim == "slide_up":
        return 0, int(60 * (1 - word_progress))
    elif anim == "slide_down":
        return 0, int(-60 * (1 - word_progress))
    elif anim == "slide_left":
        return int(100 * (1 - word_progress)), 0
    elif anim == "slide_right":
        return int(-100 * (1 - word_progress)), 0
    elif anim == "bounce":
        return 0, int(-30 * abs(math.sin(word_progress * math.pi)))
    elif anim == "wave":
        return 0, int(-25 * math.sin(word_progress * math.pi * 2 + word_idx * 0.5))
    elif anim == "pulse":
        return 0, int(-10 * math.sin(word_progress * math.pi * 3))
    elif anim == "elastic":
        e = 1 - math.pow(2, -10 * word_progress) * math.cos(word_progress * math.pi * 3)
        return 0, int(-40 * (1 - e))
    elif anim == "float":
        return 0, int(-20 * math.sin(word_progress * math.pi * 2))
    elif anim == "drop":
        if word_progress < 0.3:
            return 0, int(-100 * (1 - word_progress / 0.3))
        else:
            bounce = int(15 * math.sin((word_progress - 0.3) * math.pi * 5))
            return 0, bounce
    return 0, 0

def draw_frame(words, frame_time, scene_start, scene_duration, output_path, colors, bg, anim_type):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    
    font = get_font(48)
    progress = (frame_time - scene_start) / scene_duration
    progress = max(0, min(1, progress))
    
    word_count = len(words)
    words_per_moment = int(word_count * progress)
    if words_per_moment == 0 and progress > 0:
        words_per_moment = 1
    visible_words = words[:words_per_moment]
    
    max_width = WIDTH - 150
    lines = wrap_words(visible_words, font, max_width, draw)
    
    line_h = 65
    total_h = len(lines) * line_h
    start_y = (HEIGHT - total_h) // 2
    
    for line_idx, line in enumerate(lines):
        line_w = sum(draw.textbbox((0, 0), w, font=font)[2] for w in line)
        line_w += (len(line) - 1) * 12
        x = (WIDTH - line_w) // 2
        y = start_y + line_idx * line_h
        
        for w_idx, word in enumerate(line):
            global_idx = sum(len(lines[i]) for i in range(line_idx)) + w_idx
            word_progress = 1.0 if global_idx < words_per_moment - 1 else (progress * word_count - global_idx)
            word_progress = max(0, min(1, word_progress * 2))
            
            ox, oy = get_word_animation_offset(anim_type, word_progress, global_idx)
            
            color = colors[global_idx % len(colors)]
            rgb = hex_to_rgb(color)
            draw.text((x + ox, y + oy), word, fill=rgb, font=font)
            x += draw.textbbox((0, 0), word, font=font)[2] + 12
    
    for _ in range(25):
        px = random.randint(0, WIDTH)
        py = random.randint(0, HEIGHT)
        r = random.randint(2, 4)
        color = random.choice(colors)
        draw.ellipse([px, py, px+r*2, py+r*2], fill=hex_to_rgb(color))
    
    img.save(output_path, "PNG")

def main():
    audio_dir = os.path.join(SCRIPT_DIR, "audio")
    frames_dir = os.path.join(SCRIPT_DIR, "frames")
    output_dir = os.path.join(SCRIPT_DIR, "output")
    scenes_dir = os.path.join(SCRIPT_DIR, "scenes")
    source_vtt = os.path.join(SCRIPT_DIR, "source.vtt")
    
    for folder in [audio_dir, frames_dir, output_dir, scenes_dir]:
        os.makedirs(folder, exist_ok=True)
        for file in os.listdir(folder):
            path = os.path.join(folder, file)
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
    
    print("Reading source subtitles...")
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
        
        num_frames = int(scene_duration * FPS)
        print(f"  Generating {num_frames} frames with {anim} animation...")
        
        for frame_num in range(num_frames):
            frame_time = frame_num / FPS
            frame_path = os.path.join(scene_frames_dir, f"frame_{frame_num:05d}.png")
            draw_frame(sub["words"], frame_time, 0, scene_duration, 
                      frame_path, colors, bg, anim)
        
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
    main()
