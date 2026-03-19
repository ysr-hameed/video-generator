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
    "glitch", "neon_flicker", "matrix_rain", "particle_burst",
    "circular_reveal", "spiral_in", "zoom_blur", "wave_distort",
    "scanline", "cyber_glitch", "hologram", "vhs_track",
    "neon_pulse", "laser_grid", "energy_wave", "chromatic_shift"
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
    idx_offset = word_idx * 0.3
    
    if anim == "glitch":
        offset_x = int(5 * math.sin(pp * 20 + word_idx)) if pp < 0.8 else 0
        offset_y = int(3 * math.cos(pp * 15)) if pp < 0.8 else 0
        return offset_x, offset_y
    
    elif anim == "neon_flicker":
        flicker = math.sin(pp * 30) * 5 if random.random() > 0.1 else 0
        return 0, flicker
    
    elif anim == "matrix_rain":
        trail = int(40 * (1 - pp)) * (word_idx % 3 + 1) // 3
        return 0, trail
    
    elif anim == "particle_burst":
        angle = (word_idx * 137.5) * math.pi / 180
        dist = 30 * pp * (1 - pp) * 4
        return int(math.cos(angle) * dist), int(math.sin(angle) * dist)
    
    elif anim == "circular_reveal":
        radius = 200 * pp
        angle = word_idx * 0.5 + pp * math.pi * 2
        return int(radius * math.cos(angle) * 0.1), int(radius * math.sin(angle) * 0.1)
    
    elif anim == "spiral_in":
        angle = pp * math.pi * 4 + word_idx * 0.8
        dist = 80 * (1 - pp)
        return int(math.cos(angle) * dist), int(math.sin(angle) * dist)
    
    elif anim == "zoom_blur":
        return 0, int(-10 * (1 + (1 - pp) * 2 - 1))
    
    elif anim == "wave_distort":
        return int(20 * math.sin(pp * math.pi * 3 + idx_offset)), int(-15 * math.sin(pp * math.pi * 2 + idx_offset))
    
    elif anim == "scanline":
        scan_y = int(HEIGHT * pp)
        offset = abs(word_idx * 10 - scan_y) if abs(word_idx * 10 - scan_y) < 30 else 30
        return 0, int((30 - offset) * math.sin(pp * math.pi))
    
    elif anim == "cyber_glitch":
        glitch = int(8 * math.sin(pp * 50)) if random.random() > 0.7 else 0
        shift = int(15 * (1 - pp)) if pp < 0.5 else 0
        return shift + glitch, glitch
    
    elif anim == "hologram":
        shimmer = int(5 * math.sin(pp * 20 + word_idx * 2))
        return shimmer, int(3 * math.sin(pp * 15))
    
    elif anim == "vhs_track":
        track_offset = int(2 * math.sin(pp * 10))
        jitter = int(3 * random.random() - 1.5) if pp < 0.9 else 0
        return track_offset + jitter, 0
    
    elif anim == "neon_pulse":
        pulse = int(10 * math.sin(pp * math.pi * 4))
        return 0, int(pulse - 5 * (1 - pp))
    
    elif anim == "laser_grid":
        grid_offset = int(50 * math.sin(pp * math.pi + word_idx * 0.2))
        return grid_offset, int(30 * math.cos(pp * math.pi))
    
    elif anim == "energy_wave":
        wave = int(40 * math.sin(pp * math.pi * 2 + word_idx * 0.4))
        return wave, int(-20 * math.cos(pp * math.pi))
    
    elif anim == "chromatic_shift":
        shift = int(8 * (1 - pp) * math.sin(pp * math.pi))
        return shift, 0
    
    return 0, 0

def draw_frame(words, frame_time, scene_start, scene_duration, output_path, colors, bg, anim_type):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    
    font = get_font(48)
    progress = (frame_time - scene_start) / scene_duration
    progress = max(0, min(1, progress))
    
    word_count = len(words)
    speed_factor = 1.5
    adjusted_progress = min(1.0, progress * speed_factor)
    words_per_moment = int(word_count * adjusted_progress)
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
            word_progress = 1.0 if global_idx < words_per_moment - 1 else (adjusted_progress * word_count - global_idx)
            word_progress = max(0, min(1, word_progress * 2))
            
            ox, oy = get_word_animation_offset(anim_type, word_progress, global_idx)
            
            color = colors[global_idx % len(colors)]
            rgb = hex_to_rgb(color)
            
            if anim_type in ["neon_flicker", "neon_pulse", "hologram", "energy_wave"]:
                glow_size = int(3 + 3 * math.sin(word_progress * math.pi))
                for gs in range(glow_size, 0, -1):
                    lighter = tuple(min(255, c + 30) for c in rgb)
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            if dx != 0 or dy != 0:
                                draw.text((x + ox + dx * gs, y + oy + dy * gs), word, fill=lighter, font=font)
            
            draw.text((x + ox, y + oy), word, fill=rgb, font=font)
            x += draw.textbbox((0, 0), word, font=font)[2] + 12
    
    base_particles = 20
    if anim_type in ["glitch", "cyber_glitch", "vhs_track"]:
        base_particles = 40
        for _ in range(15):
            px = random.randint(0, WIDTH)
            py = random.randint(0, HEIGHT)
            r = random.randint(1, 3)
            draw.rectangle([px, py, px+r, py+random.randint(5, 20)], fill=hex_to_rgb(random.choice(colors)))
    elif anim_type in ["matrix_rain"]:
        for x in range(0, WIDTH, 30):
            y = int((frame_time * 100 + x) % HEIGHT)
            draw.text((x, y), random.choice(["0", "1", "1", "0"]), fill=(0, 255, 0), font=get_font(12))
    elif anim_type in ["laser_grid", "energy_wave"]:
        for i in range(0, WIDTH, 40):
            draw.line([(i, 0), (i, HEIGHT)], fill=(*hex_to_rgb(colors[0]), 50))
        for i in range(0, HEIGHT, 40):
            draw.line([(0, i), (WIDTH, i)], fill=(*hex_to_rgb(colors[0]), 50))
    elif anim_type in ["neon_flicker", "neon_pulse", "hologram"]:
        for _ in range(10):
            x1, y1 = random.randint(0, WIDTH), random.randint(0, HEIGHT)
            x2, y2 = random.randint(0, WIDTH), random.randint(0, HEIGHT)
            draw.line([(x1, y1), (x2, y2)], fill=hex_to_rgb(random.choice(colors)), width=2)
    
    for _ in range(base_particles):
        px = random.randint(0, WIDTH)
        py = random.randint(0, HEIGHT)
        r = random.randint(2, 5)
        color = random.choice(colors)
        alpha = int(100 + 100 * math.sin(progress * math.pi))
        draw.ellipse([px, py, px+r*2, py+r*2], fill=hex_to_rgb(color))
    
    if anim_type in ["scanline"]:
        for y in range(0, HEIGHT, 4):
            draw.line([(0, y), (WIDTH, y)], fill=(0, 0, 0, 30))
    
    img.save(output_path, "PNG")

def main():
    output_dir = os.path.join(SCRIPT_DIR, "output")
    scenes_dir = os.path.join(SCRIPT_DIR, "scenes")
    source_vtt = os.path.join(SCRIPT_DIR, "source.vtt")
    
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
