import os
import re
import threading
import uuid
from flask import Flask, render_template, request, jsonify, send_file, abort
import yt_dlp

app = Flask(__name__)
app.config['DOWNLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'downloads')
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Track download progress
download_progress = {}

def sanitize_filename(name):
    return re.sub(r'[^\w\s\-.]', '', name).strip()

def get_progress_hook(task_id):
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            eta = d.get('eta', 0)
            percent = (downloaded / total * 100) if total else 0
            download_progress[task_id] = {
                'status': 'downloading',
                'percent': round(percent, 1),
                'speed': format_size(speed) + '/s' if speed else 'N/A',
                'eta': format_time(eta) if eta else 'N/A',
                'downloaded': format_size(downloaded),
                'total': format_size(total)
            }
        elif d['status'] == 'finished':
            download_progress[task_id]['status'] = 'processing'
            download_progress[task_id]['percent'] = 99
    return hook

def format_size(bytes_val):
    if not bytes_val:
        return '0B'
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}TB"

def format_time(seconds):
    if not seconds:
        return '0s'
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds//60)}m {int(seconds%60)}s"
    return f"{int(seconds//3600)}h {int((seconds%3600)//60)}m"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get('formats', [])
        video_formats = []
        audio_formats = []
        seen_video = set()
        seen_audio = set()

        for f in formats:
            fid = f.get('format_id', '')
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            height = f.get('height')
            abr = f.get('abr')
            ext = f.get('ext', '')
            filesize = f.get('filesize') or f.get('filesize_approx')

            # Video formats (with video stream)
            if vcodec != 'none' and height:
                key = (height, ext)
                if key not in seen_video:
                    seen_video.add(key)
                    video_formats.append({
                        'format_id': fid,
                        'quality': f'{height}p',
                        'ext': ext,
                        'filesize': format_size(filesize) if filesize else 'Unknown',
                        'fps': f.get('fps', ''),
                        'vcodec': vcodec,
                        'has_audio': acodec != 'none',
                        'height': height
                    })

            # Audio-only formats
            elif acodec != 'none' and vcodec == 'none' and abr:
                key = (int(abr), ext)
                if key not in seen_audio:
                    seen_audio.add(key)
                    audio_formats.append({
                        'format_id': fid,
                        'quality': f'{int(abr)}kbps',
                        'ext': ext,
                        'filesize': format_size(filesize) if filesize else 'Unknown',
                        'acodec': acodec,
                        'abr': abr
                    })

        # Sort: video by height desc, audio by bitrate desc
        video_formats.sort(key=lambda x: x['height'], reverse=True)
        audio_formats.sort(key=lambda x: x['abr'], reverse=True)

        thumbnail = info.get('thumbnail', '')
        duration = info.get('duration', 0)

        return jsonify({
            'title': info.get('title', 'Unknown Title'),
            'thumbnail': thumbnail,
            'duration': format_time(duration),
            'channel': info.get('channel') or info.get('uploader', 'Unknown'),
            'view_count': f"{info.get('view_count', 0):,}" if info.get('view_count') else 'N/A',
            'upload_date': info.get('upload_date', ''),
            'video_formats': video_formats,
            'audio_formats': audio_formats,
        })

    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': f'Could not fetch video info: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', '')
    download_type = data.get('type', 'video')  # 'video' or 'audio'
    audio_format = data.get('audio_format', 'mp3')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    task_id = str(uuid.uuid4())
    download_progress[task_id] = {'status': 'starting', 'percent': 0}

    def do_download():
        try:
            out_path = app.config['DOWNLOAD_FOLDER']

            if download_type == 'audio':
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(out_path, f'{task_id}.%(ext)s'),
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': audio_format,
                        'preferredquality': '192',
                    }],
                    'progress_hooks': [get_progress_hook(task_id)],
                    'quiet': True,
                }
            else:
                # For video: if format has no audio, merge with best audio
                ydl_opts = {
                    'format': f'{format_id}+bestaudio/best' if format_id else 'bestvideo+bestaudio/best',
                    'outtmpl': os.path.join(out_path, f'{task_id}.%(ext)s'),
                    'merge_output_format': 'mp4',
                    'progress_hooks': [get_progress_hook(task_id)],
                    'quiet': True,
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                # Handle post-processed files
                if download_type == 'audio':
                    base = os.path.splitext(filename)[0]
                    filename = f"{base}.{audio_format}"
                elif ydl_opts.get('merge_output_format'):
                    base = os.path.splitext(filename)[0]
                    filename = f"{base}.mp4"

            title = sanitize_filename(info.get('title', 'video'))
            ext = os.path.splitext(filename)[1]
            final_name = f"{title}{ext}"

            download_progress[task_id] = {
                'status': 'done',
                'percent': 100,
                'filename': os.path.basename(filename),
                'display_name': final_name
            }

        except Exception as e:
            download_progress[task_id] = {
                'status': 'error',
                'error': str(e)
            }

    thread = threading.Thread(target=do_download)
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id})

@app.route('/api/progress/<task_id>')
def progress(task_id):
    prog = download_progress.get(task_id, {'status': 'not_found'})
    return jsonify(prog)

@app.route('/api/file/<task_id>')
def get_file(task_id):
    prog = download_progress.get(task_id, {})
    if prog.get('status') != 'done':
        abort(404)

    filename = prog.get('filename')
    display_name = prog.get('display_name', filename)
    filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        abort(404)

    return send_file(filepath, as_attachment=True, download_name=display_name)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
