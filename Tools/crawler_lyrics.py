# -*- coding: utf-8 -*-
"""
crawler_lyrics.py
=================

Script UNICO che:
- Legge i prototipi testuali (.txt) con filename stile: genre_artist_title_year_*.txt
- Carica profili "typical" e "rigid" per genere
- (Opzionale) carica un JSON stile descr_music_GENIUS.json con testi integrali
- (Opzionale) recupera testi mancanti via lyricsgenius (GENIUS_TOKEN)
- Costruisce un "piano esteso" per ogni canzone con:
    * meta (titolo/artista/anno/genere)
    * seed_excerpt (piccolo estratto dal .txt)
    * plan (tempo/struttura/strumentazione/lyrical_focus)
    * features (rigid selezionate + typical campionate)
    * genius_* (id/url/album/tags) se presenti
    * lyrics (TESTO INTEGRALE) se presente o recuperabile
- Output:
    * per-song (default): 1 JSON per canzone, nome: <prototipo>__extended.json
    * single-json: un unico file con una lista di record
- Opzioni utili:
    * --clean     : svuota la cartella output prima di scrivere
    * --fetch-missing-lyrics : tenta recupero testi mancanti da Genius
    * --out-mode per-song|single-json

Dipendenze opzionali (solo se usi --fetch-missing-lyrics):
    pip install lyricsgenius python-slugify unidecode

Autore: adattato e commentato per integrazione unica con funzionalità del crawler.
"""

import argparse
import json
import os
import random
import re
import sys
import time
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

# =======================
# RNG deterministico
# =======================
RND = random.Random(42)

# =======================
# Generi supportati
# =======================
GENRES = {"country", "metal", "pop", "rap", "reggae", "rnb", "rock", "trap"}

# =======================
# Utility base di normalizzazione
# =======================
def norm_txt(s: str) -> str:
    s = s or ""
    s = s.lower()
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def parse_prototype_filename(name: str) -> Dict[str, Any]:
    """
    Prova a parsare nomi tipo: genre_artist_title_year_*.txt
    Restituisce dict con chiavi: genre/artist/title/year (tutte stringhe o None)
    """
    base = Path(name).stem
    m = re.match(r"^(?P<genre>[a-z]+)_(?P<artist>[^_]+)_(?P<title>[^_]+)_(?P<year>\d{4})", base, re.IGNORECASE)
    out = {"genre": None, "artist": None, "title": None, "year": None}
    if m:
        out.update({k: m.group(k) for k in ("genre", "artist", "title", "year")})
    return out

# =======================
# Caricamento descr_music_GENIUS.json (o simile)
# =======================
def load_genius(path: Path) -> Tuple[List[dict], Dict[Tuple[str, str], dict]]:
    """
    Carica una lista di record tipo:
      {
        "ID": "...",
        "genius_id": 123,
        "source_url": "...",
        "title": "...",
        "artist": "...",
        "album": "...",
        "year": "2020",
        "lyrics": "TESTO INTEGRALE ...",
        "tags": [...],
        ...
      }

    Crea un indice su (title_norm, artist_norm) -> record
    """
    if not path or not path.exists():
        return [], {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = []
    index = {}
    for r in data:
        title = norm_txt(str(r.get("title", "")))
        artist = norm_txt(str(r.get("artist", "")))
        if title and artist:
            index[(title, artist)] = r
    return data, index

# =======================
# Lettura KV dai profili typical/rigid
# =======================
def parse_kv_text(text: str) -> Dict[str, float]:
    """
    Supporta:
      key: 0.8
      key = 0.8
      key 0.8

    ignora commenti (# ...) e righe vuote.
    Se una riga contiene parole senza numero, assegna 1.0 a ciascuna.
    """
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.replace("\t", " ")
        m = re.match(r"^([A-Za-z0-9_\-\.]+)\s*[:=\s]\s*([0-9]+[\,\.]?[0-9]*)$", line)
        if m:
            key = m.group(1).lower()
            val = m.group(2).replace(",", ".")
            try:
                out[key] = float(val)
            except ValueError:
                pass
        else:
            toks = re.findall(r"[A-Za-z0-9_\-\.]+", line)
            for t in toks:
                out[t.lower()] = 1.0
    return out

def load_profile_dir(d: Path) -> Dict[str, Dict[str, float]]:
    profiles = {}
    if not d or not d.exists():
        return profiles
    for f in d.iterdir():
        if not f.is_file():
            continue
        g = f.stem.lower()
        if g not in GENRES:
            continue
        if f.suffix.lower() == ".json":
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                raw = {}
            feats = raw.get("features", raw)
            profiles[g] = {k.lower(): float(v) for k, v in feats.items() if _is_number(v)}
        else:
            feats = parse_kv_text(f.read_text(encoding="utf-8", errors="ignore"))
            profiles[g] = feats
    return profiles

def _is_number(x) -> bool:
    try:
        float(x)
        return True
    except Exception:
        return False

def sanity_check_features(typical: Dict[str, Dict[str, float]]) -> List[str]:
    warn = []
    for g, feats in typical.items():
        bad = [k for k, v in feats.items() if not (0.0 <= float(v) <= 1.0)]
        if bad:
            warn.append(f"[{g}] valori fuori [0,1] per: {', '.join(bad[:5])}" + (" ..." if len(bad) > 5 else ""))
        if len([v for v in feats.values() if v >= 0.7]) > 20:
            warn.append(f"[{g}] molte feature >=0.7: valuta se stringere le priorità.")
    return warn

# =======================
# Scelta feature typical/rigid
# =======================
def choose_features(typical: Dict[str, float], rigid: Dict[str, float]) -> Tuple[List[str], List[str]]:
    """
    Restituisce (enforced, selected):
    - enforced: tutte le rigid > 0
    - selected: sottoinsieme probabilistico delle typical in base ai pesi
    """
    enforced = sorted(k for k, v in rigid.items() if v > 0)
    selected = []
    for k, w in typical.items():
        if w >= 0.9:
            selected.append(k)
        elif 0.7 <= w < 0.9:
            if RND.random() < 0.85:
                selected.append(k)
        elif 0.5 <= w < 0.7:
            if RND.random() < w:
                selected.append(k)
        else:
            if RND.random() < (w * 0.5):
                selected.append(k)
    selected = [s for s in sorted(set(selected)) if s not in enforced]
    return enforced, selected

# =======================
# Default range BPM per genere
# =======================
def default_tempo_range(genre: str) -> Tuple[int, int]:
    g = genre.lower()
    return {
        "pop": (90, 120),
        "rap": (80, 100),
        "trap": (130, 160),
        "rock": (100, 150),
        "metal": (120, 200),
        "rnb": (70, 105),
        "reggae": (70, 90),
        "country": (70, 110),
    }.get(g, (90, 120))

# =======================
# Strumentazione suggerita
# =======================
def instrumentation_from_features(genre: str, feats: List[str], enforced: List[str]) -> List[str]:
    g = genre.lower()
    inst = []
    if g in {"rap", "trap"}:
        if any(f in feats for f in ["trap_808", "hi_hat_rolls", "808"]):
            inst += ["808 sub-bass", "hi-hat rolls", "snare/clap on 3"]
        if any(f in feats for f in ["boom_bap_drums", "vinyl", "sample", "scratch"]):
            inst += ["sample-based drums", "swing groove", "vinyl/noise texture"]
        if "autotune" in feats:
            inst += ["melodic hook con autotune"]
        if "spoken_or_rap_vocals" in enforced:
            inst += ["rap vocal principale"]
    elif g == "pop":
        inst += ["drums", "electric bass", "synth/pad", "lead synth or guitar"]
    elif g == "rock":
        inst += ["drums", "electric bass", "rhythm guitars", "lead guitar"]
    elif g == "metal":
        inst += ["high gain guitars", "double-kick drums", "bass", "harsh/clean vocals"]
    elif g == "rnb":
        inst += ["smooth drums", "electric piano", "bass", "vocal stacks/harmonies"]
    elif g == "reggae":
        inst += ["skank guitar on offbeat", "deep bass", "rimshot/snare on 3", "organ bubble"]
    elif g == "country":
        inst += ["acoustic guitar", "pedal steel", "fiddle", "light drums"]
    return sorted(set(inst))

# =======================
# Struttura brano (dipende da genere + tag Genius opzionali)
# =======================
def make_structure(genre: str, genius_tags: List[str]) -> List[Dict[str, Any]]:
    g = genre.lower()
    tags = set((genius_tags or []))
    high_rep = any(t in tags for t in ["high_repetition", "hook_repetition", "catchy_chorus"])
    if g in {"rap", "trap"}:
        base = [
            {"section": "Intro", "bars": 4},
            {"section": "Verse", "bars": 16},
            {"section": "Hook", "bars": 8},
            {"section": "Verse", "bars": 16},
            {"section": "Hook", "bars": 8},
        ]
        if high_rep:
            base.append({"section": "Hook (outro)", "bars": 8})
        return base
    if g in {"pop", "rnb"}:
        base = [
            {"section": "Intro", "bars": 4},
            {"section": "Verse 1", "bars": 16},
            {"section": "Pre-Chorus", "bars": 8},
            {"section": "Chorus", "bars": 8},
            {"section": "Verse 2", "bars": 16},
            {"section": "Pre-Chorus", "bars": 8},
            {"section": "Chorus", "bars": 8},
        ]
        if high_rep:
            base += [{"section": "Bridge", "bars": 8}, {"section": "Double Chorus", "bars": 16}]
        else:
            base += [{"section": "Bridge", "bars": 8}, {"section": "Chorus", "bars": 8}]
        return base
    if g in {"rock", "metal", "country", "reggae"}:
        base = [
            {"section": "Intro", "bars": 4},
            {"section": "Verse 1", "bars": 16},
            {"section": "Chorus", "bars": 8},
            {"section": "Verse 2", "bars": 16},
            {"section": "Chorus", "bars": 8},
            {"section": "Bridge/Solo", "bars": 8},
            {"section": "Chorus", "bars": 8},
        ]
        if high_rep:
            base.append({"section": "Chorus (outro)", "bars": 8})
        return base
    return [{"section": "Intro", "bars": 4}, {"section": "Verse", "bars": 16}, {"section": "Chorus", "bars": 8}]

# =======================
# Focus testuale
# =======================
def lyrical_focus_from_typical(typical: Dict[str, float]) -> List[str]:
    keys = [k for k in typical.keys() if re.search(r"(flow|rhyme|punchline|story|wordplay|melody|hook|attitude|harmony)", k)]
    keys = sorted(keys, key=lambda k: typical.get(k, 0.0), reverse=True)
    return keys[:5]

# =======================
# Recupero lyrics via Genius (opzionale)
# =======================
def get_lyrics_via_genius(song_id: Optional[int], url: Optional[str] = None, cache_dir: Optional[Path] = None) -> Optional[str]:
    """
    Tenta di prendere i testi via lyricsgenius con backoff leggero.
    Richiede GENIUS_TOKEN nell'ambiente e la libreria 'lyricsgenius'.
    """
    token = os.getenv("GENIUS_TOKEN")
    if not token:
        return None

    try:
        from lyricsgenius import Genius  # import lazy
    except Exception:
        return None

    genius = Genius(
        token,
        skip_non_songs=True,
        excluded_terms=["(Remix)", "(Live)", "(Demo)"],
        remove_section_headers=True,
        timeout=15,
        retries=0,
        sleep_time=0.0,
        verbose=False,
    )

    cache_dir = cache_dir or (Path(__file__).resolve().parent / "cache_lyrics")
    cache_dir.mkdir(parents=True, exist_ok=True)

    def cp(song_id_: Optional[int]) -> Path:
        return cache_dir / f"{song_id_}.json" if song_id_ else cache_dir / f"url_{slugify_safe(url or '')}.json"

    # cache first
    cpath = cp(song_id)
    if cpath.exists():
        try:
            return json.loads(cpath.read_text("utf-8")).get("lyrics")
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
                cpath.write_text(json.dumps({"lyrics": text}, ensure_ascii=False), encoding="utf-8")
                return text
            return None
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "rate limit" in msg or "timed out" in msg or "timeout" in msg:
                sleep_for = delay * (2 ** attempt) + random.uniform(0, 0.6)
                time.sleep(sleep_for)
                continue
            time.sleep(0.5 + 0.2 * attempt)
    return None

# Helpers per cleaning testo (come nel crawler)
BRACKET_RE = re.compile(r"\[.*?\]")
JUNK_LINES_RE = re.compile(r"(?im)^\s*(you might also like|embed|translation[s]?:?|more on genius).*$")
MULTISPACE_RE = re.compile(r"\s+")

def clean_lyrics(lyrics: Optional[str]) -> str:
    if not lyrics:
        return ""
    t = JUNK_LINES_RE.sub(" ", lyrics)
    t = BRACKET_RE.sub(" ", t)
    # niente unidecode di default, preserviamo eventuali accenti
    t = MULTISPACE_RE.sub(" ", t).strip()
    return t

def slugify_safe(s: str) -> str:
    try:
        from slugify import slugify
        return slugify(s)
    except Exception:
        return re.sub(r"[^\w]+", "-", s.strip().lower()).strip("-")

# =======================
# Estensione di UNA canzone
# =======================
def extend_one(
    seed_text: str,
    meta: Dict[str, Any],
    typical_g: Dict[str, float],
    rigid_g: Dict[str, float],
    genius_idx: Dict[Tuple[str, str], dict],
    fetch_missing_lyrics: bool = False,
) -> Dict[str, Any]:
    """
    Crea il piano esteso e prova ad arricchire con metadati/lyrics da Genius.
    """
    genre = (meta.get("genre") or "").lower()
    artist_raw = meta.get("artist", "") or ""
    title_raw = meta.get("title", "") or ""
    artist = norm_txt(artist_raw)
    title = norm_txt(title_raw)

    genius_rec = genius_idx.get((title, artist), {}) if genius_idx else {}
    genius_tags = genius_rec.get("tags", []) if isinstance(genius_rec.get("tags"), list) else []
    genius_id = genius_rec.get("genius_id") or genius_rec.get("id")
    genius_url = genius_rec.get("source_url") or genius_rec.get("url") or ""
    album = genius_rec.get("album") or (genius_rec.get("album") or {}).get("name", "")
    year = meta.get("year") or genius_rec.get("year") or ""

    # features
    enforced, selected = choose_features(typical_g or {}, rigid_g or {})
    tempo_min, tempo_max = default_tempo_range(genre)
    tempo = int(RND.uniform(tempo_min, tempo_max))
    structure = make_structure(genre, genius_tags)
    instrumentation = instrumentation_from_features(genre, selected, enforced)
    lyr_focus = lyrical_focus_from_typical(typical_g or {})

    # testi integrali: preferisci quelli già presenti nel JSON "genius".
    lyrics_full = genius_rec.get("lyrics") or ""
    if not lyrics_full and fetch_missing_lyrics:
        lyrics_full = get_lyrics_via_genius(genius_id, genius_url)

    return {
        "source_file": meta.get("source_file"),
        "title": title_raw,
        "artist": artist_raw,
        "year": year,
        "genre": genre,
        "seed_excerpt": (seed_text or "")[:240],
        "plan": {
            "tempo_bpm": tempo,
            "structure": structure,
            "instrumentation": instrumentation,
            "repetition_bias": any(t in genius_tags for t in ["high_repetition", "hook_repetition", "catchy_chorus"]),
            "lyrical_focus": lyr_focus,
        },
        "features": {
            "enforced_rigid": enforced,
            "selected_typical": selected,
        },
        # Dati da Genius se presenti
        "genius": {
            "genius_id": genius_id,
            "source_url": genius_url,
            "album": album or "Single",
            "raw_tags": genius_tags,
        },
        # TESTO INTEGRALE
        "lyrics": lyrics_full or "",
    }

# =======================
# Core MAIN
# =======================
def main():
    ap = argparse.ArgumentParser(description="Generatore piani estesi + testi (script unico)")
    ap.add_argument("--input", required=True, help="Cartella con i prototipi (.txt) con filename tipo genre_artist_title_year_*.txt")
    ap.add_argument("--typical", required=True, help="Cartella profili typical per genere")
    ap.add_argument("--rigid", required=True, help="Cartella profili rigid per genere")
    ap.add_argument("--genius", required=False, help="Path a descr_music_GENIUS.json (o simile) con lyrics integrali")
    ap.add_argument("--out", required=True, help="Output: cartella (per-song) oppure file .json (single-json)")
    ap.add_argument("--out-mode", choices=["per-song", "single-json"], default="per-song", help="Formato output")
    ap.add_argument("--n_per_song", type=int, default=1, help="Numero varianti per canzone (default 1)")
    ap.add_argument("--clean", action="store_true", help="Svuota la cartella di output prima di scrivere (solo per-song)")
    ap.add_argument("--fetch-missing-lyrics", action="store_true", help="Recupera testi mancanti da Genius se GENIUS_TOKEN presente")
    args = ap.parse_args()

    inp = Path(args.input)
    outp = Path(args.out)

    # gestione output
    if args.out_mode == "per-song":
        if args.clean and outp.exists():
            # cancella tutto l'output precedente
            for f in outp.glob("*"):
                if f.is_file():
                    try:
                        f.unlink()
                    except Exception:
                        pass
                elif f.is_dir():
                    # non dovrebbe servire, ma per sicurezza
                    try:
                        for ff in f.rglob("*"):
                            try:
                                ff.unlink()
                            except Exception:
                                pass
                        f.rmdir()
                    except Exception:
                        pass
        outp.mkdir(parents=True, exist_ok=True)
    else:
        # single-json: assicura che la cartella esista
        outp.parent.mkdir(parents=True, exist_ok=True)

    # carica profili
    typical = load_profile_dir(Path(args.typical))
    rigid = load_profile_dir(Path(args.rigid))
    warnings = sanity_check_features(typical)
    if warnings and args.out_mode == "per-song":
        (outp / "_warnings.txt").write_text("\n".join(warnings), encoding="utf-8")

    # carica genius json
    genius_list, genius_idx = load_genius(Path(args.genius)) if args.genius else ([], {})

    all_records = []  # per modalità single-json
    log_lines = []

    # logging gentile
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    # iter prototipi
    for f in sorted(inp.glob("*.txt")):
        meta = parse_prototype_filename(f.name)
        if not meta.get("genre"):
            continue
        genre = meta["genre"].lower()
        if genre not in GENRES:
            continue
        meta["source_file"] = str(f)
        try:
            seed = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            seed = ""
        typ_g = typical.get(genre, {})
        rig_g = rigid.get(genre, {})

        # una sola variante (default). Se >1, rispettalo comunque.
        for i in range(max(1, args.n_per_song)):
            rec = extend_one(seed, meta, typ_g, rig_g, genius_idx, fetch_missing_lyrics=args.fetch_missing_lyrics)
            if args.out_mode == "per-song":
                out_name = f"{Path(f).stem}__extended.json" if args.n_per_song == 1 else f"{Path(f).stem}__extended_{i+1}.json"
                (outp / out_name).write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            else:
                all_records.append(rec)
        log_lines.append(f"[OK] {f.name} -> {max(1, args.n_per_song)} piani")

    # salvataggi finali
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if args.out_mode == "per-song":
        (outp / "_log.txt").write_text(f"Run {ts}\n" + "\n".join(log_lines), encoding="utf-8")
        print(f"Creati piani in: {outp}")
    else:
        outp.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Creato file unico: {outp} (brani: {len(all_records)})")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.stderr.write(f"ERRORE: {e}\n")
        sys.exit(1)
