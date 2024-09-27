from flask import Flask, request, jsonify
import yt_dlp
import os
from deepgram import Deepgram
import asyncio
import threading
import requests

app = Flask(__name__)

# Make sure to set this environment variable
DEEPGRAM_API_KEY = os.environ.get(
    'DEEPGRAM_API_KEY', '25dfe638f80278d7bb1683907998959efdf801db')


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


def process_video_and_transcribe(video_url, callback_url, note_id):
    try:
        audio_file = download_video(video_url)

        if audio_file and os.path.exists(audio_file):
            transcription = asyncio.run(transcribe_audio(audio_file))
            results = transcription['results']
            transcript = results['channels'][0]['alternatives'][0]['transcript']

            # Delete the audio file
            os.remove(audio_file)

            # Send the transcript to the callback URL
            requests.post(callback_url, json={
                          "note_id": note_id, "transcript": transcript, "diarization": results})
        else:
            requests.post(callback_url, json={
                          "note_id": note_id, "error": "Failed to download audio"})
    except Exception as e:
        requests.post(callback_url, json={"note_id": note_id, "error": str(e)})


@app.route('/', methods=['GET'])
def home():
    return 'Youtube Transcription API Running...'


@app.route('/transcribe', methods=['POST'])
def transcribe():
    data = request.json
    video_url = data.get('url')
    callback_url = data.get('callbackUrl')
    note_id = data.get('noteId')

    if not video_url or not callback_url:
        return jsonify({"error": "Missing 'url' or 'callbackUrl' in request body"}), 400

    # Start the background process
    threading.Thread(target=process_video_and_transcribe,
                     args=(video_url, callback_url, note_id)).start()

    return jsonify({"message": "Transcription process started. Results will be sent to the callback URL."}), 202


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
