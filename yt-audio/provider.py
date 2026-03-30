import yt_dlp
import requests
from bs4 import BeautifulSoup
import re

# Data model

from pydantic import BaseModel, HttpUrl
from typing import Optional

class AudioItem(BaseModel):
    url: str  # HttpUrl
    title: str
    duration: Optional[float]
    channel: Optional[str]
    thumbnail: Optional[str]
    description: Optional[str]
    acodec: Optional[str]
    provider: Optional[str]

# Helpers

def search_ytdlp(query: str, provider="ytsearch10"):
    """
    Perform a search using yt-dlp.
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"{provider}:{query}", download=False)

    return result.get("entries", [])

# Providers

def bandcamp(query):
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
                results.append(AudioItem(
                    url=url,
                    title=title,
                    duration=None,
                    channel=artist,
                    thumbnail=thumbnail,
                    description=description,
                    acodec=None,
                    provider=None,
                ))
        except Exception as e:
            print(f"Failed to parse Bandcamp result: {track}")

    return results

def soundcloud(query: str):
    return [
        AudioItem(
            url=info.get("url"),
            title=info.get("title"),
            duration=info.get("duration"),
            channel=info.get("uploader") or info.get("channel"),
            thumbnail=(info.get("thumbnails") or [{}])[0].get("url"),
            description=info.get("description"),
            acodec=info.get("acodec"),
            provider=None,
        )
        for info in search_ytdlp(query, provider="scsearch10")
    ]

def youtube(query: str):
    return [
        AudioItem(
            url=info.get("url"),
            title=info.get("title"),
            duration=info.get("duration"),
            channel=info.get("channel"),
            thumbnail=(info.get("thumbnails") or [{}])[0].get("url"),
            description=info.get("description"),
            acodec=info.get("acodec"),
            provider=None,
        )
        for info in search_ytdlp(query, provider="ytsearch10")
    ]