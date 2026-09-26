import os
import threading
from flask import Flask, render_template_string, request, jsonify
import yt_dlp

app = Flask(__name__)

# Real-time progress tracker dictionary
download_status = {
    "status": "idle",
    "percent": "0%",
    "speed": "0 KB/s",
    "eta": "Calculating...",
    "message": ""
}

def progress_hook(d):
    if d['status'] == 'downloading':
        download_status['status'] = 'downloading'
        download_status['percent'] = d.get('_percent_str', '0%').strip()
        download_status['speed'] = d.get('_speed_str', 'N/A').strip()
        download_status['eta'] = d.get('_eta_str', 'N/A').strip()
    elif d['status'] == 'finished':
        download_status['status'] = 'processing'
        download_status['percent'] = '100%'
        download_status['message'] = 'Processing & Merging via FFmpeg...'

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ur" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Aura Downloader — Pro Media Studio</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-base: #07090e;
            --surface: rgba(18, 24, 38, 0.85);
            --surface-border: rgba(255, 255, 255, 0.08);
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --accent: #a855f7;
            --success: #10b981;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Outfit', sans-serif; }

        body {
            background-color: var(--bg-base);
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(168, 85, 247, 0.12) 0%, transparent 40%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .app-card {
            width: 100%;
            max-width: 480px;
            background: var(--surface);
            backdrop-filter: blur(16px);
            border: 1px solid var(--surface-border);
            border-radius: 24px;
            padding: 32px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
        }

        .app-header { text-align: center; margin-bottom: 24px; }
        .logo-badge {
            display: inline-flex; align-items: center; justify-content: center;
            width: 56px; height: 56px;
            background: linear-gradient(135deg, var(--primary), var(--accent));
            border-radius: 16px; font-size: 24px; margin-bottom: 12px;
            box-shadow: 0 8px 20px rgba(99, 102, 241, 0.3);
        }
        .app-header h1 { font-size: 22px; font-weight: 700; color: #ffffff; }
        .app-header p { font-size: 13px; color: var(--text-muted); margin-top: 4px; }

        .step-section { display: none; }
        .step-section.active { display: block; }

        .input-group { margin-bottom: 20px; }
        .input-label { display: block; font-size: 13px; font-weight: 500; color: var(--text-muted); margin-bottom: 8px; }
        
        .text-input {
            width: 100%; padding: 14px 16px;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--surface-border); border-radius: 12px;
            color: #ffffff; font-size: 14px; outline: none; transition: all 0.25s ease;
        }
        .text-input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2); }

        .btn {
            width: 100%; padding: 14px; border: none; border-radius: 12px;
            font-size: 15px; font-weight: 600; cursor: pointer; transition: all 0.2s ease;
            display: flex; align-items: center; justify-content: center; gap: 8px;
        }
        .btn-primary { background: linear-gradient(135deg, var(--primary), var(--primary-hover)); color: white; box-shadow: 0 4px 16px rgba(99, 102, 241, 0.4); }
        .btn-success { background: linear-gradient(135deg, var(--success), #059669); color: white; box-shadow: 0 4px 16px rgba(16, 185, 129, 0.4); }
        .btn-secondary { background: rgba(255, 255, 255, 0.05); color: var(--text-muted); border: 1px solid var(--surface-border); margin-top: 8px; }

        .preview-card {
            background: rgba(15, 23, 42, 0.5); border: 1px solid var(--surface-border);
            border-radius: 14px; padding: 12px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px;
        }
        .thumbnail-wrapper { width: 80px; height: 60px; border-radius: 8px; overflow: hidden; background: #000; flex-shrink: 0; }
        .thumbnail-wrapper img { width: 100%; height: 100%; object-fit: cover; }
        .video-meta { overflow: hidden; }
        .video-title { font-size: 13px; font-weight: 600; color: #ffffff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; }
        .video-badge { display: inline-block; font-size: 11px; padding: 2px 8px; background: rgba(99, 102, 241, 0.15); color: #818cf8; border-radius: 6px; }

        .quality-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 20px; }
        .quality-card { background: rgba(15, 23, 42, 0.4); border: 1px solid var(--surface-border); border-radius: 10px; padding: 10px; text-align: center; cursor: pointer; transition: all 0.2s; }
        .quality-card input { display: none; }
        .quality-card .q-name { font-size: 13px; font-weight: 600; color: var(--text-main); }
        .quality-card.selected { background: rgba(99, 102, 241, 0.15); border-color: var(--primary); }
        .quality-card.selected .q-name { color: #818cf8; }

        /* Professional Progress Bar UI */
        .progress-wrapper {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--surface-border);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
        }
        .progress-bar-bg {
            width: 100%;
            height: 10px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 5px;
            overflow: hidden;
            margin: 16px 0 12px 0;
        }
        .progress-bar-fill {
            width: 0%;
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--accent));
            border-radius: 5px;
            transition: width 0.3s ease;
        }
        .progress-stats {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 8px;
        }
        .percent-text {
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 4px;
        }
    </style>
</head>
<body>

    <div class="app-card">
        <div class="app-header">
            <div class="logo-badge">📥</div>
            <h1>Aura Downloader</h1>
            <p>Professional Media Studio</p>
        </div>

        <!-- STEP 1 -->
        <div id="step1" class="step-section active">
            <div class="input-group">
                <label class="input-label">Video Link Yahan Paste Karein</label>
                <input type="text" id="urlInput" class="text-input" placeholder="https://youtube.com/watch?v=...">
            </div>
            <button type="button" class="btn btn-primary" onclick="fetchVideoInfo()">Analyze Link →</button>
        </div>

        <!-- STEP 2 -->
        <div id="step2" class="step-section">
            <div class="preview-card">
                <div class="thumbnail-wrapper"><img id="thumbnailImg" src="" alt="Thumbnail"></div>
                <div class="video-meta">
                    <div class="video-title" id="videoTitle">Loading details...</div>
                    <span class="video-badge">Ready</span>
                </div>
            </div>

            <label class="input-label">Download Quality Select Karein</label>
            <div class="quality-grid">
                <label class="quality-card" onclick="selectQuality(this)"><input type="radio" name="quality" value="mp3"><div class="q-name">🎵 MP3 Audio</div></label>
                <label class="quality-card" onclick="selectQuality(this)"><input type="radio" name="quality" value="360p"><div class="q-name">📱 360p</div></label>
                <label class="quality-card selected" onclick="selectQuality(this)"><input type="radio" name="quality" value="720p" checked><div class="q-name">💻 720p HD</div></label>
                <label class="quality-card" onclick="selectQuality(this)"><input type="radio" name="quality" value="1080p"><div class="q-name">🎬 1080p FHD</div></label>
                <label class="quality-card" onclick="selectQuality(this)"><input type="radio" name="quality" value="2k"><div class="q-name">📺 2K QHD</div></label>
                <label class="quality-card" onclick="selectQuality(this)"><input type="radio" name="quality" value="4k"><div class="q-name">🚀 4K UHD</div></label>
            </div>

            <button type="button" class="btn btn-success" onclick="startDownload()">📥 Start Download</button>
            <button type="button" class="btn btn-secondary" onclick="goBack()">← Enter Different Link</button>
        </div>

        <!-- STEP 3: Live Progress Studio -->
        <div id="step3" class="step-section">
            <div class="progress-wrapper">
                <div class="percent-text" id="percentDisplay">0%</div>
                <div style="font-size: 13px; color: var(--text-muted);" id="statusTitle">Initializing download...</div>
                
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="progressBar"></div>
                </div>

                <div class="progress-stats">
                    <span id="speedDisplay">Speed: 0 KB/s</span>
                    <span id="etaDisplay">ETA: --</span>
                </div>
            </div>
            
            <button type="button" class="btn btn-primary" id="resetBtn" style="display:none; margin-top:20px;" onclick="resetApp()">Download Another</button>
        </div>
    </div>

    <script>
        let currentUrl = "";

        function fetchVideoInfo() {
            let inputField = document.getElementById('urlInput');
            currentUrl = inputField.value.trim();
            
            if (!currentUrl) {
                alert('Kripya valid link dalein!');
                return;
            }

            document.getElementById('step1').classList.remove('active');
            document.getElementById('step2').classList.add('active');
            document.getElementById('videoTitle').innerText = "Media Video Ready";
            document.getElementById('thumbnailImg').src = "";

            fetch('/get_info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: currentUrl })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('videoTitle').innerText = data.title;
                    if (data.thumbnail) {
                        document.getElementById('thumbnailImg').src = data.thumbnail;
                    }
                }
            })
            .catch(err => {});
        }

        function goBack() {
            document.getElementById('step2').classList.remove('active');
            document.getElementById('step1').classList.add('active');
        }

        function selectQuality(element) {
            document.querySelectorAll('.quality-card').forEach(c => c.classList.remove('selected'));
            element.classList.add('selected');
            element.querySelector('input').checked = true;
        }

        async function startDownload() {
            document.getElementById('step2').classList.remove('active');
            document.getElementById('step3').classList.add('active');
            
            let selectedQuality = document.querySelector('input[name="quality"]:checked').value;
            let percentDisplay = document.getElementById('percentDisplay');
            let progressBar = document.getElementById('progressBar');
            let statusTitle = document.getElementById('statusTitle');
            let speedDisplay = document.getElementById('speedDisplay');
            let etaDisplay = document.getElementById('etaDisplay');
            
            document.getElementById('resetBtn').style.display = 'none';

            try {
                let response = await fetch('/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: currentUrl, quality: selectedQuality })
                });
                let data = await response.json();

                if (data.success) {
                    let checkInterval = setInterval(async () => {
                        let stRes = await fetch('/check_status');
                        let stData = await stRes.json();
                        
                        if (stData.status === 'downloading') {
                            let cleanPercent = stData.percent || '0%';
                            percentDisplay.innerText = cleanPercent;
                            let numVal = parseFloat(cleanPercent) || 0;
                            progressBar.style.width = numVal + '%';
                            
                            statusTitle.innerText = "Downloading media stream...";
                            speedDisplay.innerText = "Speed: " + stData.speed;
                            etaDisplay.innerText = "ETA: " + stData.eta;
                        } 
                        else if (stData.status === 'processing') {
                            percentDisplay.innerText = "100%";
                            progressBar.style.width = '100%';
                            statusTitle.innerHTML = "<b style='color: var(--accent);'>FFmpeg merging audio & video...</b>";
                            speedDisplay.innerText = "Processing...";
                            etaDisplay.innerText = "Almost done";
                        }
                        else if (stData.status === 'finished') {
                            clearInterval(checkInterval);
                            percentDisplay.innerText = "100%";
                            progressBar.style.width = '100%';
                            statusTitle.innerHTML = "<b style='color:var(--success);'>✨ File download mukammal ho gayi!</b>";
                            speedDisplay.innerText = "Saved to Downloads";
                            etaDisplay.innerText = "Complete";
                            document.getElementById('resetBtn').style.display = 'block';
                        } 
                        else if (stData.status === 'error') {
                            clearInterval(checkInterval);
                            statusTitle.innerHTML = "<b style='color:#ef4444;'>Error:</b> " + stData.message;
                            document.getElementById('resetBtn').style.display = 'block';
                        }
                    }, 800);
                } else {
                    statusTitle.innerHTML = "<b style='color:#ef4444;'>Error:</b> " + data.error;
                    document.getElementById('resetBtn').style.display = 'block';
                }
            } catch (err) {
                statusTitle.innerHTML = "<b style='color:#ef4444;'>Network Error! Server check karein.</b>";
                document.getElementById('resetBtn').style.display = 'block';
            }
        }

        function resetApp() {
            document.getElementById('urlInput').value = '';
            document.getElementById('percentDisplay').innerText = '0%';
            document.getElementById('progressBar').style.width = '0%';
            document.getElementById('step3').classList.remove('active');
            document.getElementById('step1').classList.add('active');
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_info', methods=['POST'])
def get_info():
    data = request.json
    url = data.get('url')
    try:
        ydl_opts = {
            'socket_timeout': 5,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'success': True,
                'title': info.get('title', 'Media Video'),
                'thumbnail': info.get('thumbnail', '')
            })
    except Exception as e:
        return jsonify({'success': True, 'title': 'Media Video', 'thumbnail': ''})

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    quality = data.get('quality', '720p')
    
    download_status['status'] = 'downloading'
    download_status['percent'] = '0%'
    download_status['speed'] = '0 KB/s'
    download_status['eta'] = 'Calculating...'
    download_status['message'] = ''
    
    def background_download():
        try:
            output_path = os.path.join(os.path.expanduser('~'), 'Downloads')
            os.makedirs(output_path, exist_ok=True)
            
            ydl_opts = {
                'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
                'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                'progress_hooks': [progress_hook],
            }
            
            if quality == "mp3":
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            elif quality == "360p":
                ydl_opts['format'] = 'best[height<=360]/best'
            elif quality == "720p":
                ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
            elif quality == "1080p":
                ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
            elif quality == "2k":
                ydl_opts['format'] = 'bestvideo[height<=1440]+bestaudio/best[height<=1440]/best'
            elif quality == "4k":
                ydl_opts['format'] = 'bestvideo[height<=2160]+bestaudio/bestvideo[height<=1440]+bestaudio/best'
            else:
                ydl_opts['format'] = 'bestvideo+bestaudio/best'
                
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(url, download=True)
                
            download_status['status'] = 'finished'
        except Exception as e:
            download_status['status'] = 'error'
            download_status['message'] = str(e)
            print("Background Download Error:", e)

    threading.Thread(target=background_download).start()
    return jsonify({'success': True})

@app.route('/check_status', methods=['GET'])
def check_status():
    return jsonify(download_status)

if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)