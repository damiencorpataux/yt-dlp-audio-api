import provider
import ranking

from fastapi import FastAPI, Request, Header, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from typing import List
import yt_dlp
import requests
import asyncio
import subprocess
from functools import lru_cache
import os

# API Auth

def auth(x_api_key: str = Header(None)):
    if os.getenv("PROFILE", "").lower() != "secure":
        return  # only active when PROFILE=secure
    if not x_api_key in get_allowed_keys():
        raise HTTPException(status_code=401, detail="Unauthorized")

@lru_cache
def get_allowed_keys():
    try:
        with open("../yt-audio-data/authorized_keys", "r") as f:
            return {line.strip().split(" ")[0] for line in f}
    except FileNotFoundError as e:
        print(f"ERROR authenticating: {e}")
        return []

# API Helpers

def get_audio_info(url: str):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    # Select thumbnail
    for i in range(-4,1):
        try:
            thumbnail = (info.get("thumbnails"))[i].get("url")
            break
        except:
            pass
        thumbnail = None

    return provider.AudioItem(
        url=info.get("url"),
        title=info.get("title"),
        duration=info.get("duration"),
        channel=info.get("channel"),
        thumbnail=thumbnail,
        description=info.get("description"),
        acodec=info.get("acodec"),
        provider=None
    )

# API Routes

async def run_search(query: str):
    providers = {
        "bandcamp": provider.bandcamp,
        "soundcloud": provider.soundcloud,
        "youtube": provider.youtube,
    }

    loop = asyncio.get_running_loop()
    tasks = {
        name: loop.run_in_executor(None, func, query)
        for name, func in providers.items()
    }

    results = []
    for name, task in tasks.items():
        try:
            data = await task
        except Exception as e:
            print(f"ERROR searching '{name}': {e}")
            data = []

        results.extend([
            item.model_copy(update={"provider": name})
            for item in data
        ])

    # Ranking
    results = ranking.rank(results, query)

    return results

app = FastAPI(
    title="YT Audio API",
    summary="A minimalistic audio REST API to yt-dlp"
)

@app.get("/")
def index():
    """
    Web UI.
    """
    return FileResponse('index.html')

@app.get("/search",
         response_model=List[provider.AudioItem],
         dependencies=[Depends(auth)])
async def search(q: str):
    """
    Perform search on configured providers (Bandcamp, Soundcloud, YouTube).
    """
    try:
        return await run_search(q)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/info",
         response_model=provider.AudioItem,
         dependencies=[Depends(auth)])
def info(url: str):
    try:
        return get_audio_info(url)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/stream",
         response_class=StreamingResponse,
         dependencies=[Depends(auth)],
         deprecated=True)
def stream(request: Request, url: str):
    """
    Stream audio proxy, with support of headers `Range` and `Content-Length`.
    Deprecated: use direct stream of key `url` from route `/info`.
    """
    try:
        info = get_audio_info(url)
    except Exception as e:
        raise HTTPException(500, str(e))

    stream_url = info.url
    title = info.title

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
        media_type=r.headers.get("Content-Type", "application/octet-stream"),
    )

@app.get("/stream/mp3",
         response_class=StreamingResponse,
         dependencies=[Depends(auth)])
def stream_mp3(request: Request, url: str):
    """
    Stream audio transcoded to mp3, without support of headers `Range` and `Content-Length`.
    """
    try:
        info = get_audio_info(url)
    except Exception as e:
        raise HTTPException(500, str(e))

    stream_url = info.url
    title = info.title

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

@app.get("/update",
         response_class=StreamingResponse,
         dependencies=[Depends(auth)])
def update():
    """
    Upgrade `yt-dlp`. Quick hack.
    """
    process = subprocess.Popen(["pip", "install", "--upgrade", "yt-dlp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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

    return StreamingResponse(
        iter_stream(),
        media_type="text/plain",
        status_code=200,
    )
