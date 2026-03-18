import os
import json
import math
import random
import subprocess
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1280
HEIGHT = 720

BACKGROUNDS = [
    ((30, 30, 60), "#FFD700"), ((60, 40, 80), "#00FFFF"), ((20, 50, 70), "#FF69B4"),
    ((50, 30, 50), "#ADFF2F"), ((40, 60, 40), "#FF4500"), ((70, 50, 30), "#9370DB"),
    ((25, 45, 65), "#00CED1"), ((55, 35, 55), "#FF6347"), ((35, 55, 45), "#7FFFD4"),
    ((65, 45, 35), "#FFD700"), ((45, 25, 75), "#00FFFF"), ((60, 60, 30), "#FF69B4"),
    ((50, 50, 50), "#ADFF2F"), ((40, 40, 80), "#FF4500"), ((70, 30, 50), "#9370DB"),
    ((25, 35, 55), "#00CED1"), ((55, 45, 65), "#FF6347"), ((65, 35, 45), "#FFD700"),
    ((45, 55, 25), "#00FFFF"), ((60, 30, 40), "#FF69B4"), ((40, 50, 50), "#ADFF2F"),
    ((70, 40, 60), "#FF4500"), ((30, 60, 30), "#9370DB"), ((50, 40, 70), "#00CED1"),
    ((35, 30, 70), "#FF69B4"), ((55, 55, 30), "#00FFFF"), ((25, 55, 45), "#FFD700"),
]

WORD_ANIMATIONS = ["slide_up", "slide_down", "zoom_in", "fade", "bounce", "scale", "wave", "fly_left", "fly_right", "pulse"]

async def generate_audio(text, output_file):
    communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
    await communicate.save(output_file)

def get_audio_duration(audio_file):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", audio_file],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))

def create_word_frame(words_data, bg_color, accent_color, frame_num, total_frames, output_path):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg_color)
    draw = ImageDraw.Draw(img)
    
    for _ in range(25):
        x = random.randint(0, WIDTH)
        y = random.randint(0, HEIGHT)
        r = random.randint(2, 6)
        draw.ellipse([x, y, x+r, y+r], fill=accent_color, outline=accent_color)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        reg_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except:
        font = ImageFont.load_default()
        reg_font = font
    
    words = [w.upper() for w in words_data]
    
    total_width = sum(draw.textbbox((0, 0), w, font=font)[2] for w in words)
    total_width += len(words) * 15
    
    start_x = (WIDTH - total_width) // 2
    y_base = HEIGHT // 2 - 20
    
    for idx, word in enumerate(words):
        word_anim = WORD_ANIMATIONS[idx % len(WORD_ANIMATIONS)]
        x = start_x + sum(draw.textbbox((0, 0), words[i], font=font)[2] + 15 for i in range(idx))
        y = y_base
        
        progress = frame_num / total_frames if total_frames > 0 else 1
        speed = 3
        
        if word_anim == "slide_up":
            offset = int(60 * (1 - progress))
            y -= offset
            word_font = font
        elif word_anim == "slide_down":
            offset = int(60 * (1 - progress))
            y += offset
            word_font = font
        elif word_anim == "zoom_in":
            scale = 0.5 + 0.5 * min(1, progress * speed)
            try:
                word_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(32 * scale))
            except:
                word_font = font
        elif word_anim == "bounce":
            bounce = int(15 * abs(math.sin(progress * math.pi * speed)))
            y -= bounce
            word_font = font
        elif word_anim == "scale":
            scale = 0.7 + 0.3 * math.sin(progress * math.pi * speed)
            try:
                word_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(32 * scale))
            except:
                word_font = font
        elif word_anim == "wave":
            wave = int(8 * math.sin(progress * math.pi * 2 + idx * 0.5))
            y += wave
            word_font = reg_font
        elif word_anim == "fly_left":
            offset = int(100 * (1 - progress))
            x -= offset
            word_font = font
        elif word_anim == "fly_right":
            offset = int(100 * (1 - progress))
            x += offset
            word_font = font
        elif word_anim == "pulse":
            pulse = int(5 * math.sin(frame_num * 0.2))
            y -= pulse
            word_font = font
        else:
            word_font = font
        
        color = random.choice(["#FFFFFF", "#FFD700", "#00FFFF", "#FF69B4", "#ADFF2F", "#FF4500", "#9370DB"])
        draw.text((x, y), word, fill=color, font=word_font)
    
    img.save(output_path, "PNG")

def main():
    print("Reading script...")
    with open("/root/vid/script.txt", "r") as f:
        script_text = f.read()
    
    print("Generating TTS audio...")
    asyncio.run(generate_audio(script_text, "/root/vid/audio/script.mp3"))
    
    audio_duration = get_audio_duration("/root/vid/audio/script.mp3")
    print(f"Audio duration: {audio_duration:.2f}s")
    
    words = script_text.split()
    words_per_scene = random.randint(5, 8)
    scenes = []
    for i in range(0, len(words), words_per_scene):
        scene_words = " ".join(words[i:i+words_per_scene])
        if scene_words.strip():
            scenes.append(scene_words)
    
    print(f"Scenes: {len(scenes)}")
    
    FPS = 15
    audio_per_scene = audio_duration / len(scenes)
    frames_per_scene = int(audio_per_scene * FPS)
    
    frame = 0
    for scene_idx, scene_text in enumerate(scenes):
        bg = random.choice(BACKGROUNDS)
        scene_words = scene_text.split()
        
        for f in range(frames_per_scene):
            create_word_frame(scene_words, bg[0], bg[1], f, frames_per_scene, f"/root/vid/frames/frame_{frame:05d}.png")
            frame += 1
        
        if scene_idx % 10 == 0:
            print(f"Scene {scene_idx + 1}/{len(scenes)}")
    
    print("Creating video...")
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS), "-i", "/root/vid/frames/frame_%05d.png",
        "-i", "/root/vid/audio/script.mp3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-shortest", "/root/vid/output/video.mp4"
    ], capture_output=True)
    
    print(f"Done! Video: /root/vid/output/video.mp4")
    print(f"Duration: {audio_duration:.2f}s, FPS: {FPS}, Scenes: {len(scenes)}")

if __name__ == "__main__":
    main()