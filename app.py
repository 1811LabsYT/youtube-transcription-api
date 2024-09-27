from flask import Flask, request, jsonify
import yt_dlp
import os
from deepgram import Deepgram
import asyncio
import threading
import requests
import json
import re

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
    try:
        deepgram = Deepgram(DEEPGRAM_API_KEY)

        with open(audio_file, 'rb') as audio:
            source = {'buffer': audio, 'mimetype': 'audio/mp3'}
            response = await deepgram.transcription.prerecorded(source, {'detect_language': True})

        results = response['results']
        transcript = results['channels'][0]['alternatives'][0]['transcript']

        return {"diarization": results, "transcript": transcript}
    except:
        return {"diarization": None, "transcript": ''}


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
        'cookiefile': cookie_file
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        audio_file = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
        return audio_file, info


def get_yt_dlp_transcript(info):
    cookie_file = get_cookies()
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['all'],
        'skip_download': True,
        'outtmpl': 'subtitles',
        'cookiefile': cookie_file
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        if 'subtitles' in info and info['subtitles']:
            subtitle_lang = next(iter(info['subtitles']))
            subtitle_url = info['subtitles'][subtitle_lang][0]['url']
        elif 'automatic_captions' in info and 'en' in info['automatic_captions']:
            subtitle_lang = next(iter(info['automatic_captions']))
            subtitle_url = info['automatic_captions'][subtitle_lang][0]['url']
        else:
            return None

        subtitle_data = ydl.urlopen(subtitle_url).read().decode('utf-8')
        return subtitle_data


def process_video_and_transcribe(video_url, callback_url, note_id):
    try:
        print(f'Getting transcription for {video_url}')

        audio_file, info = download_video(video_url)

        if audio_file and os.path.exists(audio_file):
            transcription = asyncio.run(transcribe_audio(audio_file))
            transcript = transcription['transcript']

            # Check if Deepgram transcription is empty
            if not transcript.strip():
                print(f'Transcript not found from deepgram for {video_url}')

                # Fallback to yt-dlp transcription
                transcription = get_yt_dlp_transcript(info)

                results = None
                if transcription:
                    results = json.loads(transcription)['events']

                    utf8_strings = []
                    for event in results:
                        segs = event.get('segs', [])
                        utf8_string = segs[0].get('utf8', '')
                        if utf8_string:
                            utf8_string = utf8_string.replace('\n', ' ')
                            utf8_string = re.sub(r'(\\"|")', '', utf8_string)
                            utf8_strings.append(utf8_string)

                    transcript = ' '.join(utf8_strings)
                else:
                    raise Exception(
                        "Both Deepgram and yt-dlp failed to provide transcription")

            # Delete the audio file
            os.remove(audio_file)

            transcription_data = {
                "note_id": note_id,
                "transcript": transcript,
                "diarization": transcription['diarization'],
                "results": results
            }
            # Send the transcript to the callback URL
            requests.post(callback_url, json=transcription_data)
        else:
            requests.post(callback_url, json={
                          "note_id": note_id, "error": "Failed to download audio"})
    except Exception as e:
        print(e)
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
