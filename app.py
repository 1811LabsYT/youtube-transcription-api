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


async def transcribe_audio(audio_file, language):
    try:
        deepgram = Deepgram(DEEPGRAM_API_KEY)

        with open(audio_file, 'rb') as audio:
            is_language_autodetect = not language or language == 'autodetect'

            source = {'buffer': audio, 'mimetype': 'audio/mp3'}
            options = {
                'model': 'nova-2',
                'smart_format': True,
                'diarize': True,
                'punctuate': True,
                'paragraphs': True,
            }
            if is_language_autodetect:
                options['detect_language'] = True
            else:
                options['language'] = language

            response = await deepgram.transcription.prerecorded(source, options)

        transcript = response['results']['channels'][0]['alternatives'][0]['transcript']

        return {"diarization": response, "transcript": transcript}
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
            language = next(iter(info['subtitles']))
            subtitle_url = info['subtitles'][language][0]['url']
        elif 'automatic_captions' in info and 'en' in info['automatic_captions']:
            language = next(iter(info['automatic_captions']))
            subtitle_url = info['automatic_captions'][language][0]['url']
        else:
            return None

        subtitle_data = ydl.urlopen(subtitle_url).read().decode('utf-8')
        return subtitle_data, language


def process_video_and_transcribe(video_url, note_id, language, callback_url=None):
    try:
        print(f'Getting transcription for {video_url}')

        audio_file, info = download_video(video_url)

        if audio_file and os.path.exists(audio_file):
            transcription = asyncio.run(transcribe_audio(audio_file, language))
            transcript = transcription['transcript']
            diarization = transcription['diarization']

            results = None
            detected_language = None

            # Check if Deepgram transcription is empty
            if not transcript.strip():
                print(f'Transcript not found from deepgram for {video_url}')

                # Fallback to yt-dlp transcription
                transcription, language = get_yt_dlp_transcript(info)

                if transcription:
                    results = json.loads(transcription)['events']
                    detected_language = language

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
                "diarization": diarization,
                "results": results,
                "language": detected_language
            }

            if callback_url:
                # Send the transcript to the callback URL with stringified diarization
                transcription_data["diarization"] = json.dumps(diarization)
                requests.post(callback_url, json=transcription_data)
            else:
                return transcription_data

        else:
            raise Exception("Failed to download audio")

    except Exception as e:
        print(e)
        error_data = {"note_id": note_id,
                      "transcript": "error", "error": str(e)}
        if callback_url:
            requests.post(callback_url, json=error_data)
        else:
            return error_data


@app.route('/', methods=['GET'])
def home():
    return 'Youtube Transcription API Running...'


@app.route('/transcribe', methods=['POST'])
def transcribe():
    data = request.json
    video_url = data.get('url')
    callback_url = data.get('callbackUrl')
    note_id = data.get('noteId')
    language = data.get('language')

    if not video_url:
        return jsonify({"error": "Missing 'url' in request body"}), 400

    if callback_url:
        # Start the background process
        threading.Thread(target=process_video_and_transcribe,
                         args=(video_url, note_id, language, callback_url)).start()
        return jsonify({"message": "Transcription process started. Results will be sent to the callback URL."}), 202
    else:
        # Process synchronously and return the result
        result = process_video_and_transcribe(video_url, note_id, language)
        return jsonify(result), 200


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
