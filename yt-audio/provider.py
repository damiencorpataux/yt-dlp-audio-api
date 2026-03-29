import yt_dlp
import requests
from bs4 import BeautifulSoup
import re

# Helpers

def search_ytdlp(query: str, provider="ytsearch10"):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(f"{provider}:{query}", download=False)

    return [strip_ytdlp_info(info) for info in result.get("entries", [])]

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

def youtube(query: str):
    return search_ytdlp(query, provider="ytsearch10")

def soundcloud(query: str):
    return search_ytdlp(query, provider="scsearch10")
