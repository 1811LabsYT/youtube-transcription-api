from flask import Flask, request, jsonify
import yt_dlp
import os
from deepgram import Deepgram
import asyncio
import requests

app = Flask(__name__)

# Make sure to set this environment variable
# DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')
DEEPGRAM_API_KEY = "25dfe638f80278d7bb1683907998959efdf801db"


def get_cookies():
    # cookie_file = 'cookies.txt'
    # if not os.path.exists(cookie_file):
    #     raise FileNotFoundError(
    #         f"Cookie file '{cookie_file}' not found. Please create it with your YouTube cookies.")
    # return cookie_file
    url = "https://wyccrwewjrdertucxipz.supabase.co/rest/v1/youtube-cookies"

    payload = {}
    headers = {
        'apikey': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind5Y2Nyd2V3anJkZXJ0dWN4aXB6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTM2MDgwMDIsImV4cCI6MjAyOTE4NDAwMn0.FLEZyScF0zvEwG6vgE3Qo1vO6PIvADqtWIVzXswz2Uo',
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind5Y2Nyd2V3anJkZXJ0dWN4aXB6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MTM2MDgwMDIsImV4cCI6MjAyOTE4NDAwMn0.FLEZyScF0zvEwG6vgE3Qo1vO6PIvADqtWIVzXswz2Uo'
    }

    response = requests.request("GET", url, headers=headers, data=payload)

    return response.text


async def transcribe_audio(audio_file):
    deepgram = Deepgram(DEEPGRAM_API_KEY)

    with open(audio_file, 'rb') as audio:
        source = {'buffer': audio, 'mimetype': 'audio/mp3'}
        response = await deepgram.transcription.prerecorded(source, {'detect_language': True})

    return response


def download_video(url):
    cookie = get_cookies()
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': '%(title)s.%(ext)s',
        'cookiefile': cookie,
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
    callbackUrl = data.get('callbackUrl')

    if not video_url:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    async def process_transcription():
        try:
            audio_file = download_video(video_url)

            if audio_file and os.path.exists(audio_file):
                transcription = await transcribe_audio(audio_file)
                transcript = transcription['results']['channels'][0]['alternatives'][0]['transcript']

                # Send the transcript to the callback URL
                requests.post(callbackUrl, json={"transcript": transcript})

                # Delete the audio file
                os.remove(audio_file)
            else:
                requests.post(callbackUrl, json={
                              "error": "Failed to download audio"})
        except Exception as e:
            requests.post(callbackUrl, json={"error": str(e)})

    # Trigger the background task
    asyncio.create_task(process_transcription())

    return jsonify({"message": "Transcription process started."}), 202


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
