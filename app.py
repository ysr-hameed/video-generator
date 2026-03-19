from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import subprocess
import threading
import queue

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VTT = os.path.join(SCRIPT_DIR, "source.vtt")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

DEFAULT_VTT_CONTENT = """WEBVTT

#HEADING
What is an API

#PARAGRAPH
An API stands for Application Programming Interface. It allows software to communicate.

#HEADING
How APIs Work

#PARAGRAPH
When you use an app, it sends a request through an API to another service.

#HEADING
REST APIs

#PARAGRAPH
REST APIs use HTTP methods like GET, POST, PUT, and DELETE for operations.

#HEADING
API Security

#PARAGRAPH
Authentication and API keys help secure access to services and protect data.

#HEADING
JSON Format

#PARAGRAPH
JSON is the common data format for APIs, easy to read and widely used.

#HEADING
Popular APIs

#PARAGRAPH
Google Maps, Twitter, and Stripe APIs power many modern applications today."""

progress_queue = queue.Queue()
generation_done = False
current_progress = {'stage': '', 'current': 0, 'total': 0, 'scene': 0, 'total_scenes': 0}

def parse_vtt_content(content):
    subtitles = []
    try:
        lines = content.strip().split('\n')
        i = 0
        sub_num = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line or line == 'WEBVTT':
                i += 1
                continue
            if line.startswith('#'):
                sub_type = 'HEADING' if 'HEADING' in line.upper() else 'PARAGRAPH'
                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('#'):
                    text_lines.append(lines[i].strip())
                    i += 1
                text = ' '.join(text_lines)
                if text:
                    sub_num += 1
                    subtitles.append({
                        'num': sub_num,
                        'text': text,
                        'type': sub_type
                    })
            elif '-->' in line:
                sub_num += 1
                parts = line.split('-->')
                start = parts[0].strip()
                end = parts[1].strip()
                i += 1
                text_lines = []
                while i < len(lines):
                    next_line = lines[i].strip()
                    if not next_line:
                        i += 1
                        continue
                    if next_line.startswith('#') or next_line.isdigit():
                        break
                    text_lines.append(next_line)
                    i += 1
                text = ' '.join(text_lines)
                if text:
                    subtitles.append({
                        'num': sub_num,
                        'text': text,
                        'type': 'PARAGRAPH',
                        'time': f"{start} -> {end}"
                    })
            else:
                i += 1
    except Exception as e:
        return {'error': str(e)}
    return {'subtitles': subtitles}

def stream_output(process, queue, progress_info):
    for line in iter(process.stdout.readline, ''):
        if line:
            clean = line.strip()
            if clean and not clean.startswith('ffmpeg'):
                if 'Scene' in clean:
                    parts = clean.split(':')
                    if len(parts) > 0:
                        queue.put(f"[SCENE] {clean}\n")
                        progress_info['stage'] = f"Processing {parts[0]}"
                elif 'Generating TTS' in clean:
                    queue.put("[TTS] Generating audio...\n")
                    progress_info['stage'] = 'Generating TTS'
                elif 'TTS duration' in clean:
                    queue.put(f"[TTS] {clean}\n")
                elif 'Generating' in clean and 'frames' in clean:
                    queue.put(f"[FRAMES] {clean}\n")
                    progress_info['stage'] = 'Generating frames'
                elif 'Creating scene video' in clean:
                    queue.put("[FFMPEG] Creating scene video...\n")
                    progress_info['stage'] = 'Creating video'
                elif 'Scene video created' in clean:
                    queue.put("[FFMPEG] Scene complete\n")
                elif 'Combining all scenes' in clean:
                    queue.put("\n[FFMPEG] Combining all scenes into final video...\n")
                    progress_info['stage'] = 'Finalizing video'
                elif 'Final video' in clean or 'completed' in clean.lower():
                    queue.put(f"[DONE] {clean}\n")
                    progress_info['stage'] = 'Complete!'
                else:
                    queue.put(f"[INFO] {clean}\n")

def run_generation(vtt_path):
    global progress_queue, generation_done, current_progress
    
    current_progress = {'stage': 'Starting...', 'current': 0, 'total': 0, 'scene': 0, 'total_scenes': 0}
    
    try:
        progress_queue.put("[INFO] ==============================\n")
        progress_queue.put("[INFO] Starting video generation...\n")
        progress_queue.put("[INFO] ==============================\n")
        
        process = subprocess.Popen(
            ['python3', 'main.py', vtt_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=SCRIPT_DIR,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        
        import threading
        stream_thread = threading.Thread(target=stream_output, args=(process, progress_queue, current_progress))
        stream_thread.start()
        
        process.wait()
        stream_thread.join()
        
        if process.returncode == 0:
            current_progress['stage'] = 'Complete!'
            progress_queue.put('\n[DONE] =======================================\n')
            progress_queue.put('[DONE] Video generation completed successfully!\n')
            progress_queue.put('[DONE] =======================================\n')
        else:
            current_progress['stage'] = 'Failed'
            progress_queue.put("[ERROR] ===================================\n")
            progress_queue.put("[ERROR] Generation failed\n")
            progress_queue.put("[ERROR] ===================================\n")
            
    except Exception as e:
        progress_queue.put("[ERROR] " + str(e) + "\n")
        current_progress['stage'] = 'Error'
    
    progress_queue.put(None)
    generation_done = True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse_vtt', methods=['POST'])
def parse_vtt():
    data = request.json
    vtt_content = data.get('vtt_content', '')
    return jsonify(parse_vtt_content(vtt_content))

@app.route('/generate', methods=['POST'])
def generate():
    global progress_queue, generation_done
    
    data = request.json
    vtt_content = data.get('vtt_content', '')
    
    vtt_path = os.path.join(SCRIPT_DIR, 'source.vtt')
    with open(vtt_path, 'w') as f:
        f.write(vtt_content)
    
    progress_queue = queue.Queue()
    generation_done = False
    
    thread = threading.Thread(target=run_generation, args=(vtt_path,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/progress')
def progress():
    global progress_queue, generation_done
    
    messages = []
    while True:
        try:
            msg = progress_queue.get_nowait()
            if msg is None:
                break
            messages.append(msg)
        except queue.Empty:
            break
    
    log = ''.join(messages)
    
    scene_count = log.count('[SCENE]')
    tts_count = log.count('[TTS]')
    frames_count = log.count('[FRAMES]')
    ffmpeg_count = log.count('[FFMPEG]')
    total_items = max(1, scene_count * 4)
    current = scene_count + tts_count + frames_count + ffmpeg_count
    percent = min(100, int((current / total_items) * 100)) if total_items > 0 else 0
    
    return jsonify({
        'log': log,
        'done': generation_done,
        'success': generation_done and 'completed' in log.lower(),
        'stage': current_progress.get('stage', ''),
        'percent': percent,
        'scene': scene_count
    })

@app.route('/default_vtt')
def default_vtt():
    return jsonify({'content': DEFAULT_VTT_CONTENT})

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)