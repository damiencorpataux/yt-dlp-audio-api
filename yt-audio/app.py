from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import yt_dlp
import requests


# Helpers

def run_search(query: str):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"ytsearch10:{query}", download=False)

    return [
        {
            "id": e.get("id"),
            "title": e.get("title"),
            "duration": e.get("duration"),
            "url": f"https://youtube.com/watch?v={e.get('id')}",
            "description": e.get("description"),
            "channel": e.get("channel"),
            "thumbnail": e.get("thumbnails", [{}])[0].get("url"),
        }
        for e in result.get("entries", [])
    ]

def get_audio_info(url: str):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def resolve_filesize(info, stream_url):
    # 1. Best: exact filesize from yt-dlp
    if info.get("filesize"):
        return info["filesize"]

    # 2. Optional: approximate (you can disable this if you want strict correctness)
    if info.get("filesize_approx"):
        return info["filesize_approx"]

    # 3. Fallback: HEAD request
    try:
        r = requests.head(stream_url, allow_redirects=True, timeout=5)
        if "Content-Length" in r.headers:
            return int(r.headers["Content-Length"])
    except Exception:
        pass

    return None


# API

app = FastAPI()

@app.get("/")
async def index():
    return FileResponse('index.html')

@app.get("/search")
def search(q: str):
    return {"results": run_search(q)}

@app.get("/stream")
def stream(url: str):
    try:
        info = get_audio_info(url)
    except Exception as e:
        raise HTTPException(500, str(e))

    stream_url = info["url"]
    title = info.get("title", "audio")
    filesize = resolve_filesize(info, stream_url)

    r = requests.get(stream_url, stream=True)

    if r.status_code != 200:
        raise HTTPException(500, "Failed to fetch stream")

    def iter_stream():
        for chunk in r.iter_content(chunk_size=1024 * 64):
            if chunk:
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{title}"',
    }
    if filesize:
        headers["Content-Length"] = str(filesize)

    return StreamingResponse(
        iter_stream(),
        media_type="audio/mpeg",
        headers=headers
    )
