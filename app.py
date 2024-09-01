from flask import Flask, request, jsonify
import yt_dlp
import os
from deepgram import Deepgram
import asyncio

app = Flask(__name__)

# Make sure to set this environment variable
# DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')
DEEPGRAM_API_KEY = "25dfe638f80278d7bb1683907998959efdf801db"


def get_cookies():
    cookie_file = 'cookies.txt'
    if not os.path.exists(cookie_file):
        raise FileNotFoundError(
            f"Cookie file '{cookie_file}' not found. Please create it with your YouTube cookies.")
    return cookie_file


async def transcribe_audio(audio_file):
    deepgram = Deepgram(DEEPGRAM_API_KEY)

    with open(audio_file, 'rb') as audio:
        source = {'buffer': audio, 'mimetype': 'audio/mp3'}
        response = await deepgram.transcription.prerecorded(source, {'detect_language': True})

    return response


def download_video(url):
    cookie_file = get_cookies()
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
        'cookiefile': cookie_file,
        'verbose': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        audio_file = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
        return audio_file


@app.route('/', methods=['GET'])
def home():
    return 'Youtube Transcription API Running...'


@app.route('/transcribe', methods=['POST'])
def transcribe():
    data = request.json
    video_url = data.get('url')

    if not video_url:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    try:
        audio_file = download_video(video_url)

        if audio_file and os.path.exists(audio_file):
            transcription = asyncio.run(transcribe_audio(audio_file))
            transcript = transcription['results']['channels'][0]['alternatives'][0]['transcript']

            # Delete the audio file
            os.remove(audio_file)

            return jsonify({"transcript": transcript})
        else:
            return jsonify({"error": "Failed to download audio"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
