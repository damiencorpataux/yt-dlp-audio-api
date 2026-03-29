from difflib import SequenceMatcher
import re

PROVIDER_WEIGHT = {
    "bandcamp": 1.0,      # high quality, official
    "soundcloud": 0.9,    # good but noisy
    "youtube": 0.8,       # many reuploads
}

def rank(query, results):
    results = dedupe(results)
    results = rank_results(query, results)
    return results

def normalize(text: str):
    text = text.lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", "", text)  # remove (live), [remix]
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text.strip()

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
