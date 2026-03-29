from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import yt_dlp
from bs4 import BeautifulSoup
import requests
import re
import asyncio

# Search

async def run_search(query: str):
    providers = {
        "bandcamp": search_bandcamp,
        "soundcloud": search_soundcloud,
        "youtube": search_youtube,
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
        except Exception:
            data = []

        results.extend([
            {**item, "provider": name}
            for item in data
        ])

    # Ranking
    results = dedupe(results)
    results = rank_results(query, results)

    return results

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
    return search_ytdlp(query, provider="ytsearch10")

def search_soundcloud(query: str):
    return search_ytdlp(query, provider="scsearch10")

def search_ytdlp(query: str, provider="ytsearch10"):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"{provider}:{query}", download=False)

    return [strip_ytdlp_info(info) for info in result.get("entries", [])]

# Search ranking

PROVIDER_WEIGHT = {
    "bandcamp": 1.0,      # high quality, official
    "soundcloud": 0.9,    # good but noisy
    "youtube": 0.8,       # many reuploads
}

def normalize(text: str):
    text = text.lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", "", text)  # remove (live), [remix]
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()

from difflib import SequenceMatcher
def similarity(a: str, b: str):
    return SequenceMatcher(None, a, b).ratio()

def text_score(query, title):
    return similarity(normalize(query), normalize(title)) * 100

BAD_WORDS = ["live", "remix", "cover", "edit", "radio edit"]
def penalty(title):
    t = title.lower()
    return -20 if any(word in t for word in BAD_WORDS) else 0

def bonus(title):
    t = title.lower()
    if "official" in t:
        return +10
    if "topic" in t:  # YouTube auto-generated
        return +8
    return 0

def score_result(query, result):
    title = result.get("title", "")
    provider = result.get("provider", "")

    score = 0
    score += text_score(query, title)            # Text similarity
    score *= PROVIDER_WEIGHT.get(provider, 0.5)  # Provider weight
    score += bonus(title)                        # Heuristics
    score += penalty(title)

    return score

def rank_results(query, results):
    return sorted(
        results,
        key=lambda r: score_result(query, r),
        reverse=True
    )

def dedupe(results):
    seen = {}
    for r in results:
        key = normalize(r["title"])
        if key not in seen or score_result(key, r) > score_result(key, seen[key]):
            seen[key] = r
    return list(seen.values())

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
def index():
    return FileResponse('index.html')

@app.get("/search")
async def search(q: str):
    return {"results": await run_search(q)}

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