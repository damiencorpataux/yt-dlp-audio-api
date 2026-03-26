from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import yt_dlp
from bs4 import BeautifulSoup
import requests
import re

# Helpers

def run_search(query: str):
    try: bandcamp = search_bandcamp(query)
    except: bandcamp = []

    try: youtube = search_youtube(query)
    except: youtube = []

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

    return [
        strip_info(info)
        for info in result.get("entries", [])
    ]

def get_audio_info(url: str, nostrip: bool = True):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info if nostrip else strip_info(info)

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

def strip_info(info):
    return {
        # "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),
        "url": info.get("url"),
        "description": info.get("description"),
        "channel": info.get("channel"),
        "thumbnail": info.get("thumbnails", [{}])[0].get("url"),
    }


# API

app = FastAPI(
    title="YT Audio API",
    summary="A minimalistic API to yt-dlp (audio only)"
)

@app.get("/")
async def index():
    return FileResponse('index.html')

@app.get("/search")
def search(q: str):
    return {"results": run_search(q)}

@app.get("/info")
def info(url: str):
    try:
        return get_audio_info(url)
    except Exception as e:
        raise HTTPException(500, str(e))

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
