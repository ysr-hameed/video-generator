import os
import json
import math
import random
import subprocess
import asyncio
import edge_tts
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

WIDTH = 1280
HEIGHT = 720
FPS = 15
MIN_WORDS_PER_SCENE = 5
MAX_WORDS_PER_SCENE = 9
PARTICLE_COUNT = 30

NEON_COLORS = [
    "#FF073A", "#FF2400", "#FF4500", "#FF6347", "#FF6B6B", "#FF7F50", "#FF8C00", "#FFA500",
    "#FFD700", "#FFE135", "#ADFF2F", "#7FFF00", "#00FF00", "#39FF14", "#00FF41", "#00FA9A",
    "#00FF7F", "#00FFFF", "#00BFFF", "#1E90FF", "#4169E1", "#0000FF", "#8A2BE2", "#9400D3",
    "#FF00FF", "#FF1493", "#FF69B4", "#FFB6C1", "#FFC0CB", "#DC143C", "#FF4444", "#FF6B6B",
    "#9B59B6", "#8E44AD", "#6C3483", "#5B2C6F", "#4A235A", "#2ECC71", "#27AE60", "#1ABC9C",
    "#16A085", "#3498DB", "#2980B9", "#1F618D", "#34495E", "#2C3E50", "#F39C12", "#D35400",
    "#E74C3C", "#C0392B", "#E91E63", "#9C27B0", "#673AB7", "#3F51B5", "#2196F3", "#00BCD4",
    "#009688", "#4CAF50", "#8BC34A", "#CDDC39", "#FFEB3B", "#FFC107", "#FF9800", "#FF5722",
]

DARK_BG_COLORS = [
    (5, 5, 10), (8, 8, 15), (10, 10, 18), (12, 12, 20), (15, 15, 25),
    (18, 18, 30), (20, 20, 35), (10, 8, 15), (15, 10, 20), (8, 12, 10),
    (20, 15, 10), (15, 20, 15), (25, 20, 15), (12, 15, 20), (18, 12, 25),
]

ANIMATIONS = [
    "slide_up", "slide_down", "slide_left", "slide_right",
    "zoom_in", "zoom_out", "bounce", "fade_in", "fade_out",
    "shake", "typewriter", "wave", "pulse", "elastic",
    "slide_arc", "pop_in", "squeeze_in", "float_up", "drop_in",
    "glide_left", "glide_right", "expand_center", "reveal_letter"
]

def format_vtt_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

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
    WORD_SPACING = 18
    
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

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_scene_frame(words, bg, colors, frame_num, total_frames, output_path, anim_type):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
    except:
        font = ImageFont.load_default()
    
    max_width = WIDTH - 300
    lines = wrap_words_to_lines(words, font, max_width, draw)
    
    line_height = 75
    total_height = len(lines) * line_height
    start_y = (HEIGHT - total_height) // 2
    
    scene_progress = frame_num / total_frames if total_frames > 0 else 1
    reveal_end = 0.08
    
    WORD_SPACING = 45
    current_y = start_y
    
    def get_text_width(text):
        return font.getlength(text)
    
    for line_idx, line_words in enumerate(lines):
        line_width = sum(get_text_width(w) for w in line_words) + (len(line_words) - 1) * WORD_SPACING
        x = (WIDTH - line_width) // 2
        
        for word_idx, word in enumerate(line_words):
            global_idx = sum(len(lines[i]) for i in range(line_idx)) + word_idx
            
            word_delay = global_idx * 0.03
            if scene_progress <= word_delay:
                word_progress = 0
            elif scene_progress < word_delay + reveal_end:
                word_progress = (scene_progress - word_delay) / reveal_end
            else:
                word_progress = 1
            
            word_progress = max(0, min(1, word_progress))
            
            offset_x, offset_y = 0, 0
            scale = 1.0
            
            if anim_type == "slide_up":
                offset_y = int(150 * (1 - word_progress))
            elif anim_type == "slide_down":
                offset_y = int(-150 * (1 - word_progress))
            elif anim_type == "zoom_in":
                scale = 0.3 + 0.7 * word_progress
                offset_y = int(100 * (1 - word_progress))
            elif anim_type == "zoom_out":
                scale = 1.7 - 0.7 * word_progress
                offset_y = int(-60 * (1 - word_progress))
            elif anim_type == "bounce":
                bounce = int(40 * abs(math.sin(word_progress * math.pi)))
                offset_y = -bounce
            elif anim_type == "slide_left":
                offset_x = int(200 * (1 - word_progress))
            elif anim_type == "slide_right":
                offset_x = int(-200 * (1 - word_progress))
            elif anim_type == "fade_in":
                pass
            elif anim_type == "fade_out":
                pass
            elif anim_type == "shake":
                if word_progress < 1:
                    shake = int(40 * math.sin(word_progress * math.pi * 8) * (1 - word_progress))
                    offset_x = shake
            elif anim_type == "typewriter":
                visible_chars = int(len(word) * word_progress)
                word = word[:visible_chars] if visible_chars > 0 else ""
                if not word:
                    x += get_text_width(" ") + WORD_SPACING
                    continue
            elif anim_type == "wave":
                wave = int(50 * math.sin(word_progress * math.pi * 3 + global_idx))
                offset_y = -wave
            elif anim_type == "pulse":
                scale = 1.0 + 0.3 * math.sin(word_progress * math.pi)
            elif anim_type == "flip":
                scale = math.cos(word_progress * math.pi)
                if scale < 0:
                    scale = 0
            elif anim_type == "spiral":
                rotation = word_progress * math.pi * 3
                offset_x = int(80 * math.cos(rotation))
                offset_y = int(80 * math.sin(rotation))
            elif anim_type == "elastic":
                if word_progress < 1:
                    elastic = 1 - math.pow(2, -12 * word_progress) * math.cos(word_progress * math.pi * 4)
                    offset_y = int(-80 * (1 - elastic))
            elif anim_type == "flash":
                pass
            elif anim_type == "glow_pulse":
                pass
            elif anim_type == "blur_reveal":
                pass
            elif anim_type == "slide_arc":
                arc_x = int(120 * math.sin(word_progress * math.pi))
                arc_y = int(80 * (1 - word_progress))
                offset_x = arc_x
                offset_y = -arc_y
            
            color = colors[global_idx % len(colors)]
            
            if word:
                if scale != 1.0 and scale > 0:
                    temp_img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
                    temp_draw = ImageDraw.Draw(temp_img)
                    
                    try:
                        sized_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(52 * scale))
                    except:
                        sized_font = font
                    
                    temp_draw.text((x, current_y + offset_y), word.upper(), fill=(*hex_to_rgb(color), 255), font=sized_font)
                    img.paste(temp_img, mask=temp_img)
                else:
                    draw.text((x + offset_x, current_y + offset_y), word.upper(), fill=hex_to_rgb(color), font=font)
            
            x += get_text_width(word if word else " ") + WORD_SPACING
        
        current_y += line_height
    
    for _ in range(PARTICLE_COUNT):
        px = random.randint(0, WIDTH)
        py = random.randint(0, HEIGHT)
        r = random.randint(1, 4)
        color = random.choice(colors)
        rgb = hex_to_rgb(color)
        draw.ellipse([px, py, px+r*2, py+r*2], fill=rgb)
    
    img.save(output_path, "PNG")

def create_scene_frame_sync(words, word_data, bg, colors, frame_time, scene_start, frame_num, total_frames, output_path, anim_type, is_title=False, is_list=False):
    img = Image.new("RGB", (WIDTH, HEIGHT), bg)
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
    except:
        font = ImageFont.load_default()
    
    def get_text_width(text):
        return font.getlength(text)
    
    if not words:
        for _ in range(PARTICLE_COUNT):
            px = random.randint(0, WIDTH)
            py = random.randint(0, HEIGHT)
            r = random.randint(1, 4)
            color = random.choice(colors)
            rgb = hex_to_rgb(color)
            draw.ellipse([px, py, px+r*2, py+r*2], fill=rgb)
        img.save(output_path, "PNG")
        return
    
    max_width = WIDTH - 200
    lines = wrap_words_to_lines(words, font, max_width, draw)
    
    line_height = 75
    total_height = len(lines) * line_height
    start_y = (HEIGHT - total_height) // 2
    
    WORD_SPACING = 30
    
    word_positions = []
    current_y = start_y
    
    for line_words in lines:
        line_width = sum(get_text_width(w) for w in line_words) + (len(line_words) - 1) * WORD_SPACING
        line_x = (WIDTH - line_width) // 2
        
        line_positions = []
        x = line_x
        for word in line_words:
            line_positions.append((x, current_y))
            x += get_text_width(word) + WORD_SPACING
        
        word_positions.append(line_positions)
        current_y += line_height
    
    for line_idx, line_words in enumerate(lines):
        for word_idx, word in enumerate(line_words):
            base_x, base_y = word_positions[line_idx][word_idx]
            
            data_idx = sum(len(lines[i]) for i in range(line_idx)) + word_idx
            
            if data_idx < len(word_data) and word_data:
                wd = word_data[data_idx]
                word_speak_start = wd["offset"]
                word_duration = wd["duration"]
            else:
                word_speak_start = scene_start + data_idx * 0.4
                word_duration = 0.4
            
            anim_duration = max(word_duration * 0.6, 0.25)
            word_end_time = word_speak_start + anim_duration
            
            if frame_time < word_speak_start:
                continue
            
            word_progress = 1.0
            if frame_time < word_end_time:
                word_progress = (frame_time - word_speak_start) / anim_duration
            
            word_progress = max(0, min(1, word_progress))
            
            offset_x, offset_y = 0, 0
            scale = 1.0
            
            if anim_type == "slide_up":
                offset_y = int(60 * (1 - word_progress))
            elif anim_type == "slide_down":
                offset_y = int(-60 * (1 - word_progress))
            elif anim_type == "zoom_in":
                scale = 0.6 + 0.4 * word_progress
            elif anim_type == "bounce":
                bounce = int(15 * abs(math.sin(word_progress * math.pi)))
                offset_y = -bounce
            elif anim_type == "slide_left":
                offset_x = int(80 * (1 - word_progress))
            elif anim_type == "fade_in":
                pass
            elif anim_type == "wave":
                wave = int(20 * math.sin(word_progress * math.pi * 2 + word_idx))
                offset_y = -wave
            elif anim_type == "pop_in":
                if word_progress < 0.5:
                    scale = word_progress * 2
                else:
                    scale = 1.0
            elif anim_type == "float_up":
                offset_y = int(-40 * (1 - word_progress))
            elif anim_type == "glide_left":
                offset_x = int(100 * (1 - word_progress))
            else:
                pass
            
            color = colors[word_idx % len(colors)]
            display_word = word.upper() if is_title else word
            
            if scale != 1.0 and scale > 0:
                try:
                    sized_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(52 * scale))
                except:
                    sized_font = font
                
                temp_img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
                temp_draw = ImageDraw.Draw(temp_img)
                temp_draw.text((base_x + offset_x, base_y + offset_y), display_word, fill=(*hex_to_rgb(color), 255), font=sized_font)
                img.paste(temp_img, mask=temp_img)
            else:
                draw.text((base_x + offset_x, base_y + offset_y), display_word, fill=hex_to_rgb(color), font=font)
    
    for _ in range(PARTICLE_COUNT):
        px = random.randint(0, WIDTH)
        py = random.randint(0, HEIGHT)
        r = random.randint(1, 4)
        color = random.choice(colors)
        rgb = hex_to_rgb(color)
        draw.ellipse([px, py, px+r*2, py+r*2], fill=rgb)
    
    img.save(output_path, "PNG")

async def generate_audio_with_timings(text, output_file, rate="-15%"):
    word_timings = []
    
    async def get_sentence_boundaries():
        boundaries = []
        communicate = edge_tts.Communicate(text, "en-US-GuyNeural", rate=rate, volume="+50%")
        async for chunk in communicate.stream():
            if chunk["type"] == "SentenceBoundary":
                boundaries.append({
                    "text": chunk["text"],
                    "offset": chunk["offset"] / 10_000_000
                })
        return boundaries
    
    async def save_audio():
        communicate = edge_tts.Communicate(text, "en-US-GuyNeural", rate=rate, volume="+50%")
        await communicate.save(output_file)
    
    boundaries, _ = await asyncio.gather(get_sentence_boundaries(), save_audio())
    
    return boundaries, text

def estimate_word_timings(sentence_boundaries, full_text):
    words = full_text.split()
    word_timings = []
    
    if not sentence_boundaries:
        total_duration = 2.0
        for i, word in enumerate(words):
            word_timings.append({
                "word": word,
                "offset": i * (total_duration / len(words)),
                "duration": total_duration / len(words)
            })
        return word_timings
    
    total_duration = sentence_boundaries[-1]["offset"] + 0.5
    words_per_sentence = []
    
    for i, boundary in enumerate(sentence_boundaries):
        sentence_words = boundary["text"].split()
        words_per_sentence.append(sentence_words)
    
    total_words = sum(len(s) for s in words_per_sentence)
    
    if total_words == 0:
        return word_timings
    
    avg_time_per_word = total_duration / total_words
    
    word_idx = 0
    for sent_idx, sentence in enumerate(words_per_sentence):
        sent_start = sentence_boundaries[sent_idx]["offset"]
        
        for i, word in enumerate(sentence):
            word_start = sent_start + i * avg_time_per_word
            word_timings.append({
                "word": word,
                "offset": word_start,
                "duration": avg_time_per_word
            })
    
    return word_timings

def parse_markdown_script(text):
    lines = text.split('\n')
    segments = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if line.startswith('# '):
            segments.append({
                "type": "header1",
                "text": line[2:].strip(),
                "words": line[2:].split()
            })
        elif line.startswith('## '):
            segments.append({
                "type": "header2",
                "text": line[3:].strip(),
                "words": line[3:].split()
            })
        elif line.startswith('- ') or line.startswith('* '):
            content = line[2:].strip()
            segments.append({
                "type": "list",
                "text": content,
                "words": content.split()
            })
        elif line.startswith('1. ') or line.startswith('2. ') or line.startswith('3. '):
            content = line[3:].strip()
            segments.append({
                "type": "list",
                "text": content,
                "words": content.split()
            })
        else:
            segments.append({
                "type": "content",
                "text": line,
                "words": line.split()
            })
    
    return segments

def main():
    audio_dir = os.path.join(SCRIPT_DIR, "audio")
    frames_dir = os.path.join(SCRIPT_DIR, "frames")
    output_dir = os.path.join(SCRIPT_DIR, "output")
    
    os.makedirs(audio_dir, exist_ok=True)
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    
    print("Cleaning folders...")
    for folder in [audio_dir, frames_dir, output_dir]:
        for file in os.listdir(folder):
            file_path = os.path.join(folder, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    
    print("Reading script...")
    with open(os.path.join(SCRIPT_DIR, "script.txt"), "r") as f:
        script_text = f.read().strip()
    
    segments = parse_markdown_script(script_text)
    print(f"Script segments: {len(segments)}")
    
    all_words_from_segments = []
    for seg in segments:
        all_words_from_segments.extend(seg["words"])
    print(f"Total words in script: {len(all_words_from_segments)}")
    
    tts_text = ' '.join([seg["text"] for seg in segments])
    
    print("Generating TTS audio with word timings...")
    audio_path = os.path.join(audio_dir, "script.mp3")
    boundaries, full_text = asyncio.run(generate_audio_with_timings(tts_text, audio_path, rate="-15%"))
    
    audio_duration = get_audio_duration(audio_path)
    print(f"Audio duration: {audio_duration:.2f}s")
    
    word_timings = estimate_word_timings(boundaries, tts_text)
    print(f"Word timings from TTS: {len(word_timings)}")
    
    scenes = []
    
    word_idx = 0
    while word_idx < len(word_timings):
        words_in_scene = []
        timings_in_scene = []
        
        scene_start_time = word_timings[word_idx]["offset"]
        
        target_words = random.randint(MIN_WORDS_PER_SCENE, MAX_WORDS_PER_SCENE)
        target_words = min(target_words, len(word_timings) - word_idx)
        
        for i in range(target_words):
            if word_idx + i < len(word_timings):
                words_in_scene.append(word_timings[word_idx + i]["word"])
                timings_in_scene.append(word_timings[word_idx + i])
        
        scene_end_time = timings_in_scene[-1]["offset"] + timings_in_scene[-1]["duration"]
        scene_duration = scene_end_time - scene_start_time
        
        min_scene_duration = 2.5
        if scene_duration < min_scene_duration:
            scene_end_time = scene_start_time + min_scene_duration
        
        bg_color = random.choice(DARK_BG_COLORS)
        num_colors = random.randint(2, 3)
        scene_colors = random.sample(NEON_COLORS, num_colors)
        scene_anim = random.choice(ANIMATIONS)
        
        is_header = len(words_in_scene) <= 5 and word_idx == 0
        
        scenes.append({
            "words": words_in_scene,
            "word_data": timings_in_scene,
            "start_time": scene_start_time,
            "end_time": scene_end_time,
            "text": " ".join(words_in_scene),
            "bg": bg_color,
            "colors": scene_colors,
            "anim": scene_anim,
            "is_title": is_header,
            "is_list": False,
        })
        
        word_idx += target_words
    
    print(f"Scenes created: {len(scenes)}")
    
    print(f"Scenes: {len(scenes)}")
    
    print("Creating VTT subtitle file...")
    vtt_path = os.path.join(audio_dir, "subtitles.vtt")
    with open(vtt_path, "w") as f:
        f.write("WEBVTT\n\n")
        for idx, scene in enumerate(scenes):
            start = format_vtt_time(scene["start_time"])
            end = format_vtt_time(scene["end_time"])
            text = scene["text"].upper() if scene["is_title"] else scene["text"]
            f.write(f"{idx+1}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")
    
    print("Generating frames...")
    
    total_frames = int(audio_duration * FPS)
    print(f"Total frames: {total_frames} (audio: {audio_duration:.2f}s)")
    
    current_scene_idx = 0
    
    for frame_num in range(total_frames):
        frame_time = frame_num / FPS
        
        while current_scene_idx < len(scenes) - 1 and frame_time >= scenes[current_scene_idx + 1]["start_time"]:
            current_scene_idx += 1
        
        scene = scenes[current_scene_idx]
        scene_start = scene["start_time"]
        
        words_to_show = []
        words_data = []
        
        for w_idx, wd in enumerate(scene["word_data"]):
            if frame_time >= wd["offset"]:
                words_to_show.append(scene["words"][w_idx])
                words_data.append(wd)
        
        if frame_num % 300 == 0:
            print(f"Frame {frame_num}/{total_frames} - Scene {current_scene_idx} - Words: {len(words_to_show)}")
        
        create_scene_frame_sync(
            words_to_show,
            words_data,
            scene["bg"],
            scene["colors"],
            frame_time,
            scene_start,
            frame_num,
            total_frames,
            os.path.join(frames_dir, f"frame_{frame_num:05d}.png"),
            scene["anim"],
            scene.get("is_title", False),
            scene.get("is_list", False)
        )
    
    print(f"Total frames: {total_frames}")
    
    print("Creating video...")
    result = subprocess.run([
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%05d.png"),
        "-i", audio_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-map", "0:v",
        "-map", "1:a",
        os.path.join(output_dir, "video.mp4")
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr[-500:]}")
    else:
        print(f"Done! Video: {os.path.join(output_dir, 'video.mp4')}")
        print(f"Subtitles: {vtt_path}")

if __name__ == "__main__":
    main()
