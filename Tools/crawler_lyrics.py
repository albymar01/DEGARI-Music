# -*- coding: utf-8 -*-
import os, json, time, re, logging
from slugify import slugify            # pip install python-slugify
from unidecode import unidecode        # pip install unidecode
from lyricsgenius import Genius        # pip install lyricsgenius

# ========== CONFIG ==========
JSON_PATH = r"C:\Users\sinog\Desktop\DEGARI-Music\Creazione dei prototipi\descr_music.json"
TOKEN = os.getenv("GENIUS_TOKEN")
assert TOKEN, "GENIUS_TOKEN non impostato (usa: setx GENIUS_TOKEN <il_tuo_token> e riapri il terminale)"

# Cartelle utili (facoltative)
BASE_DIR = os.path.dirname(__file__)
CACHE_DIR = os.path.join(BASE_DIR, "cache_lyrics")
os.makedirs(CACHE_DIR, exist_ok=True)

# Artista -> genere (puoi cambiare/estendere liberamente)
SEED = [
    ("Eminem", "rap"),
    ("Kendrick Lamar", "rap"),
    ("Travis Scott", "trap"),
    ("Future", "trap"),
    ("Metallica", "metal"),
    ("Judas Priest", "metal"),
    ("Nirvana", "rock"),
    ("AC/DC", "rock"),
    ("The Weeknd", "pop"),
    ("Lady Gaga", "pop"),
    ("Bob Marley", "reggae"),
    ("Inner Circle", "reggae"),
    ("Beyoncé", "rnb"),
    ("TLC", "rnb"),
    ("John Denver", "country"),
    ("Dolly Parton", "country"),
]

MAX_SONGS_PER_ARTIST = 1          # 3 per tenere il crawler veloce
EXCLUDED_TERMS = ["(Remix)", "(Live)", "(Demo)"]

# Parametri “aggressivi ma sicuri” per ridurre i tempi
genius = Genius(
    TOKEN,
    skip_non_songs=True,
    excluded_terms=EXCLUDED_TERMS,
    remove_section_headers=True,
    timeout=8,              # timeout breve
    retries=1,              # pochi retry
    sleep_time=0.2,         # pausa minima tra richieste
    verbose=False
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# ========== UTILS ==========
BRACKET_RE = re.compile(r"\[.*?\]")  # [Chorus], [Verse], ...

def clean_lyrics(lyrics: str) -> str:
    """Pulisce le lyrics da tag, bracket e caratteri strani."""
    if not lyrics:
        return ""
    t = lyrics.replace("You might also like", "")
    t = BRACKET_RE.sub(" ", t)
    t = unidecode(t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def safe_year(song) -> str:
    """Prova a estrarre l'anno anche quando .year non esiste."""
    try:
        comp = getattr(song, "release_date_components", None)
        if isinstance(comp, dict) and comp.get("year"):
            return str(comp["year"])
    except Exception:
        pass
    try:
        rd = getattr(song, "release_date", None)  # es. "2013-10-14"
        if rd and len(rd) >= 4 and rd[:4].isdigit():
            return rd[:4]
    except Exception:
        pass
    return ""

def make_id(artist, title, genre):
    return f"{genre}_{slugify(artist)[:10]}_{slugify(title)[:16]}"

def mk_item(song, genre):
    return {
        "ID": make_id(song.artist, song.title, genre),
        "title": song.title,
        "artist": song.artist,
        "album": song.album if getattr(song, "album", None) else "Single",
        "year": safe_year(song),
        "lyrics": clean_lyrics(getattr(song, "lyrics", "")),
        "tags": [genre],            # arricchirai poi con lyrics_features.py
        "moods": [],
        "instruments": [],
        "subgenres": [genre],
        "contexts": []
    }

# ========== MAIN ==========
if __name__ == "__main__":
    data = load_json(JSON_PATH)
    seen = {d.get("ID") for d in data if isinstance(d, dict)}

    for artist, genre in SEED:
        print(f"\n== {artist} ({genre}) ==")
        try:
            # prende rapidamente i brani più popolari
            a = genius.search_artist(artist, max_songs=MAX_SONGS_PER_ARTIST, sort="popularity")
        except Exception as e:
            print("  ! errore artista:", artist, e)
            continue

        for s in (a.songs or [])[:MAX_SONGS_PER_ARTIST]:
            try:
                # ottiene i testi completi del singolo brano
                s_full = genius.search_song(title=s.title, artist=artist)
                if not s_full or not getattr(s_full, "lyrics", None):
                    continue

                item = mk_item(s_full, genre)
                if item["ID"] in seen:
                    print("  - dup:", item["ID"])
                    continue

                data.append(item)
                seen.add(item["ID"])
                print("  + add:", item["ID"])

                time.sleep(0.8)  # gentile con il rate-limit
            except Exception as e:
                print("  ! errore song:", s.title, e)

    save_json(JSON_PATH, data)
    print("\nAggiornato:", JSON_PATH, "-> Totale brani:", len(data))
