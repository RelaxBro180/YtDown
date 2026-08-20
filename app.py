import os
import sys
import threading
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

FFMPEG_EXE = os.path.join(BASE_DIR, 'ffmpeg.exe')

def delayed_delete(path, delay=300.0):
    def _delete():
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            app.logger.error(f"Ошибка при удалении {path}: {e}")
            
    threading.Timer(delay, _delete).start()

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/download_media', methods=['POST'])
def download_media():
    data = request.json or {}
    url = data.get('url')
    media_type = data.get('type')

    if not url:
        return jsonify({'error': 'URL не предоставлен'}), 400
    if media_type not in ['audio', 'video']:
        return jsonify({'error': 'Неверный тип медиа'}), 400

    try:
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(id)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'overwrites': True,
            'ffmpeg_location': FFMPEG_EXE if os.path.exists(FFMPEG_EXE) else None,
            'extractor_args': {
                'youtube': {
                    'player_client': ['mweb', 'android', 'ios']
                }
            }
        }

        if media_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id')
            video_title = info.get('title', video_id)

            ext = 'mp3' if media_type == 'audio' else 'mp4'
            filename = os.path.join(DOWNLOAD_FOLDER, f"{video_id}.{ext}")

        if not os.path.exists(filename):
            return jsonify({'error': 'Ошибка обработки. Файл не найден после конвертации.'}), 500

        # Автоматическое удаление файла с диска через 5 минут
        delayed_delete(filename, delay=300.0)

        # Безопасное имя файла без спецсимволов для скачивания
        safe_title = "".join([c for c in video_title if c.isalpha() or c.isdigit() or c in ' ._-']).rstrip()
        download_name = f"{safe_title or video_id}.{ext}"

        return send_file(filename, as_attachment=True, download_name=download_name)

    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': f'Ошибка скачивания: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Сервер запущен! Перейди по адресу: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)