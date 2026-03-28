from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import yt_dlp
from bs4 import BeautifulSoup
import requests
import re

def run_search(query: str):
    try: bandcamp = search_bandcamp(query)
    except: bandcamp = []

    try: youtube = search_youtube(query)
    except: youtube = []

    # Add provider key
    return [
        *[{**result, **{"provider": "bandcamp"}} for result in bandcamp],
        *[{**result, **{"provider": "youtube"}} for result in youtube]
    ]

def search_bandcamp(query):
    url = f"https://bandcamp.com/search?item_type=t&q={query}"
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")

    results = []
    for track in soup.select("li.searchresult"):
        try:
            title = track.select_one(".heading a").text.strip()
            artist = re.sub("(\\n|\\s)+", " ", track.select_one(".subhead").text.strip())
            thumbnail = track.select_one(".art img").get("src")
            url = track.select_one(".itemurl a").get("href").split("?")[0]
            description = track.select_one(".tags")
            description = '' if not description else description.text.replace('\n', '').replace(' ', '')
            if "/track/" in url:
                results.append({
                    "url": url,
                    "title": title,
                    "channel": artist,
                    "thumbnail": thumbnail,
                    "description": description,
                    "duration": None
                })
        except Exception as e:
            print(f"Failed to parse Bandcamp result: {track}")

    return results

def search_youtube(query: str):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch10:{query}", download=False)

    return [strip_ytdlp_info(info) for info in result.get("entries", [])]

# Helpers

def get_audio_info(url: str, nostrip: bool = False):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info if nostrip else strip_ytdlp_info(info)

def strip_ytdlp_info(info):
    print(type(info), info)
    return {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "description": info.get("description"),
        "channel": info.get("channel"),
        "thumbnail": info.get("thumbnails", [{}])[0].get("url"),  # FIXME: A smart way to select sensible-sized thumnail ?
        "url": info.get("url"),
        "acodec": info.get("acodec")
    }

# API

app = FastAPI(
    title="YT Audio API",
    summary="A minimalistic audio REST API to yt-dlp"
)

@app.get("/")
async def index():
    return FileResponse('index.html')

@app.get("/search")
def search(q: str):
    return {"results": run_search(q)}

@app.get("/info")
def info(url: str, nostrip: bool = False):
    try:
        return get_audio_info(url, nostrip)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/stream")
def stream(request: Request, url: str):
    """
    Stream audio, with support of headers `Range` and `Content-Length`.
    Note: whenever possible, use direct stream of key `url` from route `/info`.
    """
    try:
        info = get_audio_info(url)
    except Exception as e:
        raise HTTPException(500, str(e))

    stream_url = info["url"]
    title = info.get("title", "audio")

    # Forward Range header if present
    headers = {}
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header

    r = requests.get(stream_url, headers=headers, stream=True)

    if r.status_code not in (200, 206):
        raise HTTPException(500, f"Upstream error: {r.status_code}")

    def iter_stream():
        for chunk in r.iter_content(chunk_size=1024 * 64):
            if chunk:
                yield chunk

    response_headers = {
        "Content-Disposition": f'attachment; filename="{title}"',
        "Accept-Ranges": "bytes",
    }

    # Forward critical headers from upstream
    for h in ["Content-Length", "Content-Range", "Content-Type"]:
        if h in r.headers:
            response_headers[h] = r.headers[h]

    return StreamingResponse(
        iter_stream(),
        status_code=r.status_code,  # 🔥 CRITICAL (200 vs 206)
        headers=response_headers,
        media_type=r.headers.get("Content-Type", "audio/mpeg"),
    )

import subprocess

@app.get("/stream/mp3")
def stream_mp3(request: Request, url: str):
    """
    Stream audio transcoded to mp3, without support of headers `Range` and `Content-Length`.
    """
    try:
        info = get_audio_info(url)
    except Exception as e:
        raise HTTPException(500, str(e))

    stream_url = info["url"]
    title = info.get("title", "audio")

    process = subprocess.Popen(
        [
            "ffmpeg",
            "-i", stream_url,
            "-vn",
            "-f", "mp3",
            "-acodec", "libmp3lame",
            "-ab", "192k",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=10**6,
    )

    def iter_stream():
        try:
            while True:
                chunk = process.stdout.read(1024 * 64)
                if not chunk:
                    break
                yield chunk
        finally:
            process.kill()

    headers = {
        "Content-Disposition": f'inline; filename="{title}.mp3"',
        "Content-Type": "audio/mpeg",
        # ❗ no Content-Length
        # ❗ no Content-Range
    }

    return StreamingResponse(
        iter_stream(),
        status_code=200,
        headers=headers,
        media_type="audio/mpeg",
    )