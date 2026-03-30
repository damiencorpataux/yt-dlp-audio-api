
from difflib import SequenceMatcher
import math
import re

BAD_WORDS = ["live", "remix", "cover", "edit", "radio edit"]
DURATION_OPTIMAL = 300  # 5 minutes
DURATION_SIGMA = 300    # spread (~5 min)
PROVIDER_WEIGHT = {
    "bandcamp": 1.0,    # high quality, official
    "soundcloud": 0.9,  # good but noisy
    "youtube": 0.8,     # many reuploads
}

def rank(results, query):
    """
    Return results ordered by score.
    """
    results = dedupe(results)
    return sorted(
        results,
        key=lambda r: score_result(query, r),
        reverse=True
    )

# Scoring

def score_result(query, result):
    title = result.title
    provider = result.provider
    duration = result.duration
    channel = result.channel

    score = 0

    # Text similarity
    t_score = title_score(query, title)
    score += t_score

    # Channel similarity
    score += channel_score(query, channel)

    # Provider weight
    score *= PROVIDER_WEIGHT.get(provider, 0.5)

    # Duration
    score += duration_score(duration, t_score, provider)

    return score

def title_score(query, title):
    score = 100 * similarity(normalize(query), normalize(title))
    score += -20 if any(word in title.lower() for word in BAD_WORDS) else 0
    return score

def channel_score(query, channel):
    # Boost up to +30 if channel matches query well
    # score = 30 * similarity(normalize(query), (channel))
    score = 0
    # Bonus for official-looking channels
    c = channel.lower()
    if "official" in c:
        score += 10
    if "vevo" in c:
        score += 8
    if "topic" in c:  # YouTube auto-generated artist channel
        score += 6
    return score

def duration_score(duration, text_match_score, provider):
    if not duration:
        if provider == "bandcamp":
            return 8 * (text_match_score / 100)
        return 0

    diff = duration - DURATION_OPTIMAL
    gauss = math.exp(-(diff ** 2) / (2 * DURATION_SIGMA ** 2))

    base_score = (gauss * 35) - 20
    weight = (text_match_score / 100)

    return base_score * weight

# Helpers

def normalize(text: str):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", "", text)  # remove (live), [remix]
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()

def similarity(a: str, b: str):
    return SequenceMatcher(None, a, b).ratio()

def dedupe(results):
    seen = {}
    for r in results:
        key = normalize(r.title)
        if key not in seen or score_result(key, r) > score_result(key, seen[key]):
            seen[key] = r
    return list(seen.values())
