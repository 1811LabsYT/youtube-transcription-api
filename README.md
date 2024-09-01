# YouTube Transcription API

This project provides a Flask-based API that fetches transcripts for YouTube videos using the YouTube Transcription API. It allows users to retrieve transcripts, including translations, for a given YouTube video ID.

## Features

- Fetch transcripts for a YouTube video
- Get information about available transcripts (language, generation method, etc.)
- Retrieve translations of transcripts
- Automatically translate non-English transcripts to English

## Requirements

- Python 3.9+
- Flask==3.0.3
- yt-dlp
- gunicorn==20.1.0
- deepgram-sdk==2.\*

## Setup

1. Clone this repository:

   ```
   git clone https://github.com/1811LabsYT/youtube-transcription-api.git
   cd youtube-transcription-api
   ```

2. Create a virtual environment and activate it:

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the Flask application:

   ```
   python app.py
   ```

2. The API will be available at `http://localhost:5000`.

3. To get a transcript, make a GET request to the `/get-transcript` endpoint with the `video_id` parameter:
   ```
   http://localhost:5000/get-transcript?video_id=VIDEO_ID
   ```
   Replace `VIDEO_ID` with the actual YouTube video ID.

## API Endpoint

### GET /get-transcript

Retrieves transcript information for a given YouTube video.

Query Parameters:

- `url` (required): The YouTube Video Url.

Response:

- A string containing transcription text.

## Test it locally

Run the command in your terminal:

```
python app.py
```

The API will be available at `http://localhost:5001`.

## Error Handling

The API returns appropriate error messages and status codes for common issues, such as missing video IDs or API errors.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is open-source and available under the MIT License.
