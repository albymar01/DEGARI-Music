# -*- coding: utf-8 -*-
import os, json, time, re, logging, tempfile, sys, argparse, random
from pathlib import Path
from typing import Dict, Any, List, Optional
from slugify import slugify            # pip install python-slugify
from unidecode import unidecode        # pip install unidecode
from lyricsgenius import Genius        # pip install lyricsgenius

# ========== CONFIG ==========
JSON_PATH = r"C:\Users\Utente\Desktop\DEGARI-Music\Creazione dei prototipi\descr_music.json"

TOKEN = os.getenv("GENIUS_TOKEN")
if not TOKEN:
    sys.exit("ERRORE: GENIUS_TOKEN non impostato (cmd:  setx GENIUS_TOKEN <il_tuo_token>  e riapri il terminale)")

BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache_lyrics"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SEED = [
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

EXCLUDED_TERMS = ["(Remix)", "(Live)", "(Demo)"]

genius = Genius(
    TOKEN,
    skip_non_songs=True,
    excluded_terms=EXCLUDED_TERMS,
    remove_section_headers=True,
    timeout=15,
    retries=0,          # gestiamo noi i retry
    sleep_time=0.0,     # gestiamo noi il backoff
    verbose=False,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

# ========== UTILS ==========
BRACKET_RE     = re.compile(r"\[.*?\]")
JUNK_LINES_RE  = re.compile(r"(?im)^\s*(you might also like|embed|translation[s]?:?|more on genius).*$")
MULTISPACE_RE  = re.compile(r"\s+")

def clean_lyrics(lyrics: str) -> str:
    if not lyrics:
        return ""
    t = JUNK_LINES_RE.sub(" ", lyrics)
    t = BRACKET_RE.sub(" ", t)
    t = unidecode(t)
    t = MULTISPACE_RE.sub(" ", t).strip()
    return t

def load_json(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def atomic_save_json(path: str, data: Any) -> None:
    # scrittura atomica per evitare file corrotti
    d = Path(path).parent
    d.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=d, encoding="utf-8") as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, path)

def coerce_str(x) -> str:
    # evita Ellipsis e None
    if x is Ellipsis or x is None:
        return ""
    return str(x)

def strip_ellipsis(obj):
    # rimuove ricorsivamente Ellipsis da dizionari/liste
    if obj is Ellipsis:
        return ""
    if isinstance(obj, dict):
        return {k: strip_ellipsis(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_ellipsis(v) for v in obj]
    return obj

def safe_year_from_fields(song_dict: Dict[str, Any]) -> str:
    date = song_dict.get("release_date") or song_dict.get("release_date_for_display") or ""
    date = coerce_str(date)
    if len(date) >= 4 and date[:4].isdigit():
        return date[:4]
    return ""

def make_id(artist: str, title: str, genre: str, year: str = "", genius_id: Optional[int] = None) -> str:
    base = f"{genre}_{slugify(artist)[:10]}_{slugify(title)[:16]}"
    year = coerce_str(year)
    if year:
        base += f"_{year}"
    if genius_id:
        base += f"_{genius_id}"
    return base

def cache_path_for(song_id: int) -> Path:
    return CACHE_DIR / f"{song_id}.json"

def get_lyrics_with_cache(song_id: Optional[int], url: Optional[str] = None) -> Optional[str]:
    cp = cache_path_for(song_id) if song_id else None
    if cp and cp.exists():
        try:
            return json.loads(cp.read_text("utf-8")).get("lyrics")
        except Exception:
            pass

    delay = 0.6
    for attempt in range(5):
        try:
            text = None
            if song_id:
                text = genius.lyrics(song_id=song_id)
            elif url:
                text = genius.lyrics(url=url)
            text = clean_lyrics(text)
            if text:
                if cp:
                    cp.write_text(json.dumps({"lyrics": text}, ensure_ascii=False), encoding="utf-8")
                return text
            return None
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate limit" in msg or "timed out" in msg or "timeout" in msg:
                sleep_for = delay * (2 ** attempt) + random.uniform(0, 0.6)
                logging.warning("Rate limit (tentativo %s), sleep %.1fs", attempt + 1, sleep_for)
                time.sleep(sleep_for)
                continue
            logging.warning("Errore lyrics song_id=%s: %s", song_id, e)
            time.sleep(0.5 + 0.2 * attempt)
    return None

def mk_item_from(song_dict: Dict[str, Any], genre: str) -> Dict[str, Any]:
    if not isinstance(song_dict, dict):
        raise ValueError("song_dict non è un dict valido")

    # alcuni to_dict() ritornano {'song': {...}}
    if "song" in song_dict and isinstance(song_dict["song"], dict):
        song_dict = song_dict["song"]

    title  = coerce_str(song_dict.get("title") or song_dict.get("title_with_featured") or "")
    artist = coerce_str((song_dict.get("primary_artist") or {}).get("name") or song_dict.get("artist", "") or "")
    year   = safe_year_from_fields(song_dict)
    gid    = song_dict.get("id")
    url    = song_dict.get("url")
    lyrics = get_lyrics_with_cache(gid, url=url)

    return {
        "ID": make_id(artist, title, genre, year=year, genius_id=gid),
        "genius_id": gid,
        "source": "genius",
        "source_url": coerce_str(url),
        "title": title,
        "artist": artist,
        "album": coerce_str((song_dict.get("album") or {}).get("name") or "Single"),
        "year": year,
        "lyrics": lyrics or "",
        "tags": [genre],
        "moods": [],
        "instruments": [],
        "subgenres": [genre],
        "contexts": []
    }

def search_artist_with_backoff(genius_client: Genius, artist: str, max_songs: int, sort: str = "popularity", attempts: int = 5):
    delay = 0.6
    last_exc = None
    for i in range(attempts):
        try:
            return genius_client.search_artist(artist, max_songs=max_songs, sort=sort)
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            if "429" in msg or "rate limit" in msg or "timed out" in msg or "timeout" in msg:
                sleep_for = delay * (2 ** i) + random.uniform(0, 0.5)
                logging.warning("search_artist('%s') tentativo %d fallito, attendo %.1fs", artist, i+1, sleep_for)
                time.sleep(sleep_for)
                continue
            time.sleep(0.5 + 0.2 * i)
    raise last_exc

# ========== MAIN ==========
def main():
    ap = argparse.ArgumentParser(description="DEGARI Music – crawler lyrics (Genius)")
    ap.add_argument("--max-per-artist", type=int, default=3, help="max brani per artista")
    ap.add_argument("--seed", type=str, nargs="*", help='coppie "Artista:genere" (override seed)')
    ap.add_argument("--json-path", type=str, default=JSON_PATH, help="path al descr_music.json")
    args = ap.parse_args()

    # SEED: CLI o default
    if args.seed:
        pairs = []
        for s in args.seed:
            if ":" in s:
                a, g = s.split(":", 1)
                pairs.append((a.strip(), g.strip()))
        seed = pairs
    else:
        seed = DEFAULT_SEED

    data = load_json(args.json_path)
    data = strip_ellipsis(data)  # sanifica eventuali vecchi Ellipsis nel file già esistente
    seen_ids   = {d.get("ID") for d in data if isinstance(d, dict)}
    seen_gids  = {d.get("genius_id") for d in data if isinstance(d, dict) and d.get("genius_id")}

    added = 0
    for artist, genre in seed:
        print(f"\n== {artist} ({genre}) ==")
        try:
            a = search_artist_with_backoff(genius, artist, max_songs=args.max_per_artist, sort="popularity")
        except Exception as e:
            print("  ! errore artista:", artist, e)
            continue

        songs = (a.songs or [])[: args.max_per_artist]
        for s in songs:
            try:
                s_dict = s.to_dict() if hasattr(s, "to_dict") else getattr(s, "__dict__", {})
                s_dict = strip_ellipsis(s_dict)  # <-- sanifica subito
                gid = s_dict.get("id")

                if gid and gid in seen_gids:
                    print("  - dup(gid):", gid)
                    continue

                item = mk_item_from(s_dict, genre)
                item = strip_ellipsis(item)  # ulteriore safety

                if item["ID"] in seen_ids:
                    print("  - dup(ID):", item["ID"])
                    continue

                data.append(item)
                seen_ids.add(item["ID"])
                if gid:
                    seen_gids.add(gid)
                print("  + add:", item["ID"])
                added += 1
            except Exception as e:
                print("  ! errore song:", getattr(s, "title", "?"), e)

            time.sleep(0.1)  # minima gentilezza

    data = strip_ellipsis(data)  # safety finale
    atomic_save_json(args.json_path, data)
    print(f"\nAggiornato: {args.json_path} -> Totale brani: {len(data)} (aggiunti {added})")

if __name__ == "__main__":
    main()
