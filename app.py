from flask import Flask, render_template_string, request, jsonify, send_from_directory
import os
import subprocess
import threading
import queue

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VTT = os.path.join(SCRIPT_DIR, "source.vtt")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

progress_queue = queue.Queue()
generation_done = False

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Generator</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
            --primary: #6366f1;
            --secondary: #8b5cf6;
            --accent: #06b6d4;
            --success: #10b981;
            --bg-dark: #0f0f1a;
            --bg-card: #1a1a2e;
            --border: rgba(255,255,255,0.08);
            --text: #e2e8f0;
            --text-muted: #94a3b8;
        }
        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-dark);
            min-height: 100vh;
            color: var(--text);
            padding: 40px 20px;
        }
        .container { max-width: 900px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 40px; }
        .header h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent) 0%, var(--secondary) 50%, var(--primary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .header p { color: var(--text-muted); font-size: 1rem; }
        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 20px;
        }
        .card-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 16px;
        }
        .card-header i { color: var(--accent); font-size: 1.2rem; }
        .card-header h2 { font-size: 1.1rem; font-weight: 600; }
        .input-group { position: relative; }
        .input-group input {
            width: 100%;
            padding: 14px 16px 14px 44px;
            background: rgba(0,0,0,0.3);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text);
            font-size: 0.95rem;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s;
        }
        .input-group input:focus { border-color: var(--accent); }
        .input-group i {
            position: absolute;
            left: 16px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
        }
        .subtitles-preview {
            max-height: 300px;
            overflow-y: auto;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
            padding: 16px;
        }
        .subtitle-item {
            display: flex;
            gap: 16px;
            padding: 12px;
            border-bottom: 1px solid var(--border);
            align-items: flex-start;
        }
        .subtitle-item:last-child { border-bottom: none; }
        .subtitle-num {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: #fff;
            width: 28px;
            height: 28px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            font-weight: 600;
            flex-shrink: 0;
        }
        .subtitle-text { flex: 1; font-size: 0.9rem; line-height: 1.5; }
        .subtitle-time {
            font-size: 0.75rem;
            color: var(--accent);
            font-family: monospace;
            flex-shrink: 0;
        }
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 14px 28px;
            background: linear-gradient(135deg, var(--accent), var(--success));
            border: none;
            border-radius: 10px;
            color: #fff;
            font-size: 1rem;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            width: 100%;
        }
        .btn:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(6, 182, 212, 0.3);
        }
        .btn:disabled { opacity: 0.6; cursor: not-allowed; }
        .btn-download {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            display: none;
            margin-top: 15px;
        }
        .btn-download:hover { box-shadow: 0 8px 25px rgba(99, 102, 241, 0.3); }
        .progress-section { display: none; }
        .progress-section.active { display: block; }
        .progress-log {
            background: rgba(0,0,0,0.4);
            border-radius: 10px;
            padding: 16px;
            font-family: monospace;
            font-size: 0.85rem;
            max-height: 250px;
            overflow-y: auto;
            color: var(--success);
            line-height: 1.6;
        }
        .progress-log .info { color: var(--accent); }
        .progress-log .scene { color: var(--secondary); }
        .progress-log .error { color: #ef4444; }
        .progress-log .done { color: var(--success); }
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
            margin-bottom: 16px;
        }
        .status-badge.processing {
            background: rgba(139, 92, 246, 0.2);
            color: var(--secondary);
        }
        .status-badge.complete {
            background: rgba(16, 185, 129, 0.2);
            color: var(--success);
        }
        .status-badge .spinner {
            width: 14px;
            height: 14px;
            border: 2px solid currentColor;
            border-top-color: transparent;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-video"></i> Video Generator</h1>
            <p>Transform subtitles into stunning animated videos</p>
        </div>
        
        <div class="card">
            <div class="card-header">
                <i class="fas fa-file-alt"></i>
                <h2>Source File</h2>
            </div>
            <div class="input-group">
                <i class="fas fa-file-code"></i>
                <input type="text" id="vttPath" value="{{ default_vtt }}">
            </div>
        </div>
        
        <div class="card">
            <div class="card-header">
                <i class="fas fa-list-alt"></i>
                <h2>Subtitles Preview</h2>
            </div>
            <div class="subtitles-preview" id="subtitlesPreview">
                <p style="color: var(--text-muted); text-align: center; padding: 20px;">
                    <i class="fas fa-spinner fa-spin"></i> Loading subtitles...
                </p>
            </div>
        </div>
        
        <button class="btn" id="generateBtn" onclick="startGeneration()">
            <i class="fas fa-magic"></i> Generate Video
        </button>
        
        <div class="card progress-section" id="progressSection">
            <div class="card-header">
                <i class="fas fa-tasks"></i>
                <h2>Progress</h2>
            </div>
            <div class="status-badge processing" id="statusBadge">
                <div class="spinner"></div>
                <span id="statusText">Processing...</span>
            </div>
            <div class="progress-log" id="output"></div>
        </div>
        
        <button class="btn btn-download" id="downloadBtn" onclick="downloadVideo()">
            <i class="fas fa-download"></i> Download Video
        </button>
    </div>

    <script>
        let polling = false;
        
        async function loadSubtitles() {
            const vttPath = document.getElementById('vttPath').value;
            try {
                const resp = await fetch('/parse_vtt', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({vtt_path: vttPath})
                });
                const data = await resp.json();
                
                if (data.subtitles && data.subtitles.length > 0) {
                    let html = '';
                    data.subtitles.forEach((sub, i) => {
                        html += `
                            <div class="subtitle-item">
                                <div class="subtitle-num">${i + 1}</div>
                                <div class="subtitle-text">${sub.text}</div>
                                <div class="subtitle-time">${sub.time}</div>
                            </div>
                        `;
                    });
                    document.getElementById('subtitlesPreview').innerHTML = html;
                } else {
                    document.getElementById('subtitlesPreview').innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 20px;">No subtitles found</p>';
                }
            } catch(e) {
                document.getElementById('subtitlesPreview').innerHTML = '<p style="color: #ef4444; text-align: center; padding: 20px;">Error loading subtitles</p>';
            }
        }
        
        loadSubtitles();
        document.getElementById('vttPath').addEventListener('change', loadSubtitles);
        
        async function startGeneration() {
            const vttPath = document.getElementById('vttPath').value;
            const btn = document.getElementById('generateBtn');
            const progressSection = document.getElementById('progressSection');
            const downloadBtn = document.getElementById('downloadBtn');
            
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating...';
            progressSection.classList.add('active');
            downloadBtn.style.display = 'none';
            document.getElementById('output').innerHTML = '<span class="info">Initializing...</span>';
            
            await fetch('/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({vtt_path: vttPath})
            });
            
            polling = true;
            pollProgress();
        }
        
        async function pollProgress() {
            while (polling) {
                try {
                    const resp = await fetch('/progress');
                    const data = await resp.json();
                    
                    if (data.log) {
                        let html = data.log.replace(/Scene/g, '<span class="scene">Scene</span>')
                                          .replace(/Done/g, '<span class="done">Done</span>')
                                          .replace(/Error/g, '<span class="error">Error</span>')
                                          .replace(/Generating/g, '<span class="info">Generating</span>')
                                          .replace(/Creating/g, '<span class="info">Creating</span>');
                        document.getElementById('output').innerHTML = html;
                        document.getElementById('output').scrollTop = document.getElementById('output').scrollHeight;
                    }
                    
                    if (data.done) {
                        polling = false;
                        document.getElementById('generateBtn').disabled = false;
                        document.getElementById('generateBtn').innerHTML = '<i class="fas fa-magic"></i> Generate Video';
                        
                        const statusBadge = document.getElementById('statusBadge');
                        if (data.success) {
                            statusBadge.className = 'status-badge complete';
                            statusBadge.innerHTML = '<i class="fas fa-check-circle"></i><span>Complete!</span>';
                            document.getElementById('downloadBtn').style.display = 'flex';
                        } else {
                            statusBadge.className = 'status-badge';
                            statusBadge.innerHTML = '<i class="fas fa-exclamation-circle"></i><span>Failed</span>';
                            statusBadge.style.background = 'rgba(239, 68, 68, 0.2)';
                            statusBadge.style.color = '#ef4444';
                        }
                        break;
                    }
                } catch(e) {}
                await new Promise(r => setTimeout(r, 500));
            }
        }
        
        function downloadVideo() {
            window.open('/download/video.mp4', '_blank');
        }
    </script>
</body>
</html>
'''

def parse_vtt_file(vtt_path):
    subtitles = []
    try:
        with open(vtt_path, 'r') as f:
            content = f.read()
        
        lines = content.strip().split('\n')
        i = 0
        sub_num = 0
        while i < len(lines):
            line = lines[i].strip()
            if '-->' in line:
                sub_num += 1
                parts = line.split('-->')
                start = parts[0].strip()
                end = parts[1].strip()
                i += 1
                text_lines = []
                while i < len(lines) and lines[i].strip() and not lines[i].strip().isdigit():
                    text_lines.append(lines[i].strip())
                    i += 1
                text = ' '.join(text_lines)
                subtitles.append({
                    'num': sub_num,
                    'text': text,
                    'time': f"{start} -> {end}"
                })
            else:
                i += 1
    except Exception as e:
        return {'error': str(e)}
    return {'subtitles': subtitles}

def run_generation(vtt_path):
    global progress_queue, generation_done
    
    try:
        progress_queue.put("[INFO] Source: " + vtt_path + "\n")
        
        result = subprocess.run(
            ['python3', 'main.py', vtt_path],
            capture_output=True,
            text=True,
            cwd=SCRIPT_DIR,
            env={**os.environ, 'PYTHONUNBUFFERED': '1'}
        )
        
        if result.returncode == 0:
            output = result.stdout
            lines = output.split('\n')
            filtered = [l for l in lines if l.strip() and not l.startswith('ffmpeg')]
            progress_queue.put('\n'.join(filtered))
            progress_queue.put('\n[DONE] Video generation completed!')
        else:
            progress_queue.put("[ERROR] " + result.stderr[-500:])
            
    except Exception as e:
        progress_queue.put("[ERROR] " + str(e))
    
    progress_queue.put(None)
    generation_done = True

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE, default_vtt=DEFAULT_VTT)

@app.route('/parse_vtt', methods=['POST'])
def parse_vtt():
    data = request.json
    vtt_path = data.get('vtt_path', DEFAULT_VTT)
    return jsonify(parse_vtt_file(vtt_path))

@app.route('/generate', methods=['POST'])
def generate():
    global progress_queue, generation_done
    
    data = request.json
    vtt_path = data.get('vtt_path', DEFAULT_VTT)
    
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
    return jsonify({
        'log': log,
        'done': generation_done,
        'success': generation_done and 'completed' in log.lower()
    })

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)