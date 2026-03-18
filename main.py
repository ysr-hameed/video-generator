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
WORDS_PER_SCENE = 6

JOKER_THEMES = [
    {"bg": (10, 10, 15), "text": "#FFFFFF", "accent1": "#00FF00", "accent2": "#BD00FF"},
    {"bg": (8, 8, 12), "text": "#F0F0F0", "accent1": "#00FF41", "accent2": "#9D00FF"},
    {"bg": (15, 15, 20), "text": "#E8E8E8", "accent1": "#39FF14", "accent2": "#8B00FF"},
    {"bg": (20, 20, 25), "text": "#FFFFFF", "accent1": "#7FFF00", "accent2": "#9400D3"},
]

ANIMATIONS = ["slide_up", "zoom_in", "bounce", "fade_in", "slide_left"]

def get_audio_duration(audio_file):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", audio_file],
        capture_output=True, text=True
    )
    return float(json.loads(result.stdout).get("format", {}).get("duration", 0))

def wrap_words_to_lines(words, font, max_width, draw):
    lines = []
    current_line = []
    current_width = 0
    WORD_SPACING = 12
    
    for word in words:
        word_width = draw.textbbox((0, 0), word, font=font)[2] + WORD_SPACING
        if current_width + word_width <= max_width:
            current_line.append(word)
            current_width += word_width
        else:
            if current_line:
                lines.append(current_line)
            current_line = [word]
            current_width = word_width
    
    if current_line:
        lines.append(current_line)
    
    return lines

def create_scene_frame(words, bg, accent1, accent2, main_text, frame_num, total_frames, output_path):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 44)
    except:
        font = ImageFont.load_default()
    
    max_width = WIDTH - 100
    lines = wrap_words_to_lines(words, font, max_width, draw)
    
    line_height = 60
    total_height = len(lines) * line_height
    start_y = (HEIGHT - total_height) // 2
    
    scene_progress = frame_num / total_frames if total_frames > 0 else 1
    reveal_end = 0.3
    hold_end = 0.8
    
    WORD_SPACING = 12
    current_y = start_y
    
    for line_idx, line_words in enumerate(lines):
        line_text = " ".join(line_words)
        line_bbox = draw.textbbox((0, 0), line_text, font=font)
        line_width = line_bbox[2] + (len(line_words) - 1) * WORD_SPACING
        x = (WIDTH - line_width) // 2
        
        for word_idx, word in enumerate(line_words):
            global_idx = sum(len(lines[i]) for i in range(line_idx)) + word_idx
            
            word_delay = global_idx * 0.15
            if scene_progress <= word_delay:
                word_progress = 0
            else:
                time_for_word = reveal_end - word_delay
                if time_for_word > 0:
                    word_progress = min(1, (scene_progress - word_delay) / time_for_word)
                else:
                    word_progress = 1
            
            anim_type = ANIMATIONS[global_idx % len(ANIMATIONS)]
            
            if anim_type == "slide_up":
                offset_y = int(50 * (1 - word_progress))
                offset_x = 0
            elif anim_type == "zoom_in":
                offset_y = int(40 * (1 - word_progress * 0.8))
                offset_x = 0
            elif anim_type == "bounce":
                bounce = int(20 * abs(math.sin(word_progress * math.pi)))
                offset_y = -bounce
                offset_x = 0
            elif anim_type == "slide_left":
                offset_x = int(80 * (1 - word_progress))
                offset_y = 0
            else:
                offset_y = 0
                offset_x = 0
            
            color_idx = global_idx % 3
            if color_idx == 0:
                color = accent1
            elif color_idx == 1:
                color = accent2
            else:
                color = main_text
            
            draw.text((x + offset_x, current_y + offset_y), word.upper(), fill=color, font=font)
            
            word_bbox = draw.textbbox((0, 0), word, font=font)
            x += word_bbox[2] + WORD_SPACING
        
        current_y += line_height
    
    for _ in range(25):
        px = random.randint(0, WIDTH)
        py = random.randint(0, HEIGHT)
        r = random.randint(1, 4)
        color = random.choice([accent1, accent2])
        rgb = tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        draw.ellipse([px, py, px+r*2, py+r*2], fill=rgb)
    
    img.save(output_path, "PNG")

async def generate_audio(text, output_file):
    communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
    await communicate.save(output_file)

def main():
    audio_dir = os.path.join(SCRIPT_DIR, "audio")
    frames_dir = os.path.join(SCRIPT_DIR, "frames")
    output_dir = os.path.join(SCRIPT_DIR, "output")
    
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    print("Reading script...")
    with open(os.path.join(SCRIPT_DIR, "script.txt"), "r") as f:
        script_text = f.read().strip()
    
    print("Generating TTS audio...")
    audio_path = os.path.join(audio_dir, "script.mp3")
    asyncio.run(generate_audio(script_text, audio_path))
    
    audio_duration = get_audio_duration(audio_path)
    print(f"Audio duration: {audio_duration:.2f}s")
    
    lines = script_text.split('\n')
    all_words = []
    
    for line in lines:
        line = line.strip()
        if line:
            words = line.split()
            all_words.extend(words)
    
    print(f"Total words: {len(all_words)}")
    
    scenes = []
    for i in range(0, len(all_words), WORDS_PER_SCENE):
        chunk = all_words[i:i + WORDS_PER_SCENE]
        if chunk:
            scenes.append(chunk)
    
    print(f"Scenes: {len(scenes)}")
    
    total_scenes = len(scenes)
    time_per_scene = audio_duration / total_scenes
    frames_per_scene = max(int(time_per_scene * FPS), FPS * 6)
    
    print(f"Frames per scene: {frames_per_scene}")
    
    frame = 0
    for scene_idx, scene_words in enumerate(scenes):
        theme = JOKER_THEMES[scene_idx % len(JOKER_THEMES)]
        
        for f in range(frames_per_scene):
            create_scene_frame(
                scene_words,
                theme["bg"],
                theme["accent1"],
                theme["accent2"],
                theme["text"],
                f,
                frames_per_scene,
                os.path.join(frames_dir, f"frame_{frame:05d}.png")
            )
            frame += 1
        
        print(f"Scene {scene_idx + 1}/{total_scenes}: {' '.join(scene_words)}")
    
    print(f"Total frames: {frame}")
    
    print("Creating video...")
    result = subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS), "-i", os.path.join(frames_dir, "frame_%05d.png"),
        "-i", audio_path, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        os.path.join(output_dir, "video.mp4")
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr[-500:]}")
    else:
        print(f"Done! Video: {os.path.join(output_dir, 'video.mp4')}")

if __name__ == "__main__":
    main()
