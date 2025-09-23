# -*- coding: utf-8 -*-
"""
DEGARI-Music – Prototype Generator (dir o file JSON)
----------------------------------------------------
Legge descrizioni brani da:
  • una CARTELLA contenente JSON “per brano” (es. ...\extended\*.json), oppure
  • un FILE JSON unico con una lista di brani (schema GENIUS “vecchio”)

Per ogni brano costruisce il “prototipo” (bag-of-lemmas pesato) e salva un .txt
nella cartella di output (cfg.outPath).

Dipendenze:
  - nltk (stopwords, punkt)
  - treetaggerwrapper + TreeTagger installato (opzionale: il codice funziona
    anche se TreeTagger non è presente, ma senza lemmatizzazione)
"""

from pathlib import Path
import os
import json
import string
import re
from typing import Dict, Iterable, List, Tuple, Any, Optional

# NLP
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import treetaggerwrapper

# Config del progetto
import prototyper_config as cfg

# =========================
# Costanti & settaggi base
# =========================

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # .../DEGARI-Music

PREPOSITIONS = ["of","to","from","in","on","at","by","for",
                "with","about","against","between","into",
                "through","during","before","after","above",
                "below","up","down","out","off","over","under"]
ARTICLES = ["the","a","an"]
CONJUNCTIONS = ["and","or","but","so","yet","for","nor","because",
                "although","though","while","if","when","where","that",
                "which","who","whom","whose","until","unless","since","as",
                "than","whether","either","neither","both","also","only"]
PUNCTUATION = list(string.punctuation) + ["...", "``"]
CHARS_NOT_ALLOWED = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']

MIN_SCORE = 0.6
MAX_SCORE = 0.9
ENCODING = "utf-8"

TAGGER = None  # inizializzato in main() se disponibile

# =========================
# Utility percorso & I/O
# =========================

def resolve_input_path() -> Path:
    """
    Risolve il path indicato in cfg.jsonDescrFile.
    - Se assoluto: lo usa "as-is".
    - Se relativo: lo risolve rispetto alla root del progetto.
    Può essere sia un FILE che una CARTELLA.
    """
    raw = Path(cfg.jsonDescrFile)
    return raw if raw.is_absolute() else (PROJECT_ROOT / raw)

def resolve_output_dir() -> Path:
    """
    Risolve la cartella di output indicata in cfg.outPath.
    - Se assoluto: lo usa "as-is".
    - Se relativo: lo risolve rispetto alla root del progetto.
    """
    p = Path(cfg.outPath)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p

def safe_slug(s: str) -> str:
    """
    Slug semplice: minuscole, alfanumerico + trattino singolo.
    (evita dipendenze esterne per questa parte)
    """
    s = (s or "").lower()
    s = re.sub(r"[^\w\s-]+", " ", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s

def safe_filename(s: str) -> str:
    """
    Rimuove caratteri illegali in Windows.
    """
    if s is None:
        return ""
    for ch in CHARS_NOT_ALLOWED:
        s = s.replace(ch, "")
    return s

# =========================
# TreeTagger / NLTK
# =========================

def ensure_nltk():
    """Scarica risorse minime NLTK (se mancano)."""
    try:
        _ = stopwords.words('english')
    except (LookupError, OSError):
        import nltk
        nltk.download('stopwords', quiet=True)
    try:
        # controlla punkt
        import nltk
        nltk.data.find('tokenizers/punkt')
    except (LookupError, OSError):
        import nltk
        nltk.download('punkt', quiet=True)

def find_treetagger() -> Optional[str]:
    """
    Trova automaticamente l'installazione di TreeTagger.
    Ordine:
      1) Env: TAGDIR
      2) Env: TREETAGGER_HOME
      3) .../Desktop/TreeTagger (Utente/sinog)
      4) .../DEGARI-Music/TreeTagger
    """
    candidates = [
        os.getenv("TAGDIR"),
        os.getenv("TREETAGGER_HOME"),
        r"C:\Users\Utente\Desktop\TreeTagger",
        r"C:\Users\sinog\Desktop\TreeTagger",
        str(PROJECT_ROOT / "TreeTagger"),
    ]
    for c in candidates:
        if not c:
            continue
        p = Path(c)
        # accetta se esiste la cartella e sembra contenere bin o lib
        if p.exists() and (p.joinpath("bin").exists() or p.joinpath("lib").exists()):
            return str(p)
    return None

def make_tagger():
    """
    Crea e ritorna il tagger TreeTagger per l'inglese.
    Lancia RuntimeError se non trova un'installazione valida.
    """
    tagdir = find_treetagger()
    if not tagdir:
        raise RuntimeError(
            "TreeTagger non trovato. Imposta TAGDIR/TREETAGGER_HOME oppure installa TreeTagger in:\n"
            r"- C:\Users\<utente>\Desktop\TreeTagger\n"
            f"- {PROJECT_ROOT / 'TreeTagger'}"
        )
    parfile = os.path.join(tagdir, "lib", "english-bnc.par")
    abbrev  = os.path.join(tagdir, "lib", "english-abbreviations")
    # se i file par/abbrev non esistono, passiamo None (treetaggerwrapper sceglierà default)
    return treetaggerwrapper.TreeTagger(
        TAGLANG="en",
        TAGDIR=tagdir,
        TAGPARFILE=parfile if os.path.exists(parfile) else None,
        TAGABBREV=abbrev if os.path.exists(abbrev) else None,
    )

def get_tags(text: str):
    """
    Restituisce la lista di tag (oggetti Tag) per il testo dato.
    Se TAGGER non è inizializzato ritorna lista vuota.
    """
    global TAGGER
    if TAGGER is None:
        return []
    try:
        # TreeTagger accetta stringhe; make_tags gestisce l'output
        return treetaggerwrapper.make_tags(TAGGER.tag_text(text))
    except Exception:
        return []

def getLemma(word: str) -> str:
    """
    Ritorna il lemma di una parola usando TreeTagger, oppure la
    parola lowercased se TreeTagger non è disponibile o si verifica un errore.
    """
    if not word:
        return ""
    try:
        tags = get_tags(word)
        if tags:
            lemma = tags[0].lemma or ""
            # TreeTagger a volte ritorna "word:pos" o "lemma:..." - prendiamo la parte prima dei due punti
            return (str(lemma).split(":")[0]) or word.lower()
        return word.lower()
    except Exception:
        return word.lower()

def getTypeOfWord(word: str) -> str:
    """
    Ritorna il POS (simplificato) della parola, o stringa vuota se non disponibile.
    """
    if not word:
        return ""
    try:
        tags = get_tags(word)
        if tags:
            pos = tags[0].pos or ""
            return str(pos).split(":")[0]
        return ""
    except Exception:
        return ""

# POS (inglese)
def isNumber(word):    return getTypeOfWord(word) in ("CD", "NUM")
def isVerb(word):      return getTypeOfWord(word).startswith("VB") if getTypeOfWord(word) else False   # VB, VBD, VBG, ...
def isAdjective(word): return getTypeOfWord(word).startswith("JJ") if getTypeOfWord(word) else False   # JJ, JJR, JJS
def isAdverb(word):    return getTypeOfWord(word).startswith("RB") if getTypeOfWord(word) else False   # RB, RBR, RBS

# =========================
# Normalizzazione istanze
# =========================

def to_text(value: Any) -> str:
    """Converte liste in testo unico, altrimenti str()."""
    if isinstance(value, list):
        return " ".join(map(str, value))
    return "" if value is None else str(value)

def normalize_instance(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rende omogenea un'istanza brano in questo formato:
      {
        "ID": ...,
        "title": ..., "artist": ..., "album": ..., "year": ...,
        "lyrics": ..., "tags": [...], "moods": [...],
        "instruments": [...], "subgenres": [...], "contexts": [...]
      }

    Supporta:
      • Schema “vecchio” (descr_music_GENIUS*.json)
      • Schema “nuovo” (file __extended*.json)
    """
    # Caso 1: schema “vecchio” (ha già ID e campi richiesti)
    if "ID" in obj and "lyrics" in obj:
        # Garantisco che i campi attesi esistano, anche se vuoti
        return {
            "ID": to_text(obj.get("ID")),
            "title": to_text(obj.get("title")),
            "artist": to_text(obj.get("artist")),
            "album": to_text(obj.get("album")),
            "year": to_text(obj.get("year")),
            "lyrics": to_text(obj.get("lyrics")),
            "tags": list(obj.get("tags") or []),
            "moods": list(obj.get("moods") or []),
            "instruments": list(obj.get("instruments") or []),
            "subgenres": list(obj.get("subgenres") or []),
            "contexts": list(obj.get("contexts") or []),
        }

    # Caso 2: schema “nuovo” (file per brano da extended)
    # Campi principali
    title   = to_text(obj.get("title"))
    artist  = to_text(obj.get("artist"))
    album   = to_text((obj.get("genius") or {}).get("album") or "Single")
    year    = to_text(obj.get("year"))
    lyrics  = to_text(obj.get("lyrics"))

    genre   = to_text(obj.get("genre"))
    genius  = obj.get("genius") or {}
    gid     = genius.get("genius_id")
    gtags   = list(genius.get("raw_tags") or [])

    # Strumenti (se presenti nel piano)
    plan_instr = list((obj.get("plan") or {}).get("instrumentation") or [])

    # Subgeneri / contesti: non presenti -> liste vuote
    subgenres = [genre] if genre else []
    contexts  = []

    # ID: genere_artista_titolo_anno_(gid)
    slug_artist = safe_slug(artist)[:10] or "artist"
    slug_title  = safe_slug(title)[:16]  or "title"
    base_id = f"{genre or 'music'}_{slug_artist}_{slug_title}"
    if year:
        base_id += f"_{year}"
    if gid:
        base_id += f"_{gid}"

    return {
        "ID": base_id,
        "title": title,
        "artist": artist,
        "album": album,
        "year": year,
        "lyrics": lyrics,
        "tags": ([genre] if genre else []) + gtags,
        "moods": [],
        "instruments": plan_instr,
        "subgenres": subgenres,
        "contexts": contexts,
    }

def iter_instances(input_path: Path) -> Iterable[Dict[str, Any]]:
    """
    Ritorna un iterabile di istanze normalizzate.
    - Se input_path è FILE: carica json (obj o lista) e normalizza.
    - Se input_path è CARTELLA: legge tutti i *.json presenti (flat).
    """
    if input_path.is_file():
        data = json.loads(input_path.read_text(encoding=ENCODING))
        if isinstance(data, dict):
            yield normalize_instance(data)
        elif isinstance(data, list):
            for obj in data:
                if isinstance(obj, dict):
                    yield normalize_instance(obj)
        else:
            raise TypeError("Il JSON di input deve essere un oggetto o una lista di oggetti.")
        return

    if input_path.is_dir():
        for jf in sorted(input_path.glob("*.json")):
            try:
                text = jf.read_text(encoding=ENCODING)
                if not text.strip():
                    continue
                obj = json.loads(text)
                if isinstance(obj, dict):
                    yield normalize_instance(obj)
                elif isinstance(obj, list):
                    for o in obj:
                        if isinstance(o, dict):
                            yield normalize_instance(o)
            except Exception as e:
                print(f"[WARN] file JSON ignorato: {jf.name} -> {e}")
        return

    raise FileNotFoundError(f"Percorso input non trovato: {input_path}")

# =========================
# Generazione prototipi
# =========================

def writeWordInFile(file, word, value):
    spaces = max(1, 20 - len(word) + 1)
    file.write(f"{word}:{' ' * spaces}{value}\n")

def insertArtworkInDict(instance: Dict[str, Any],
                        dict_prototypes: Dict[str, Dict[str, int]],
                        remove_words: set):
    """
    Aggiorna il dizionario dei prototipi con i lemmi trovati nell'istanza.
    """
    # recupera identificatore artwork; se manca costruisco un fallback
    key_name = getattr(cfg, "instanceID", "ID")
    artwork_id = instance.get(key_name) if isinstance(instance, dict) else None
    if not artwork_id:
        # fallback: genere_artist_title_year
        title = instance.get("title", "") or ""
        artist = instance.get("artist", "") or ""
        year = instance.get("year", "") or ""
        artwork_id = safe_slug(f"{artist}_{title}_{year}") or "artwork"
    artwork = safe_filename(str(artwork_id))

    # Build della “description” concatenando i campi di interesse (cfg.instanceDescr)
    try:
        descr_fields = list(cfg.instanceDescr)
    except Exception:
        descr_fields = ["title", "artist", "lyrics", "tags"]

    description = " " + " ".join(
        to_text(instance.get(d, "")) for d in descr_fields
    )

    try:
        word_tokens = word_tokenize(description)
    except Exception:
        word_tokens = description.split()

    verbo = None

    for word in word_tokens:
        word = word.lower().strip()
        if not word:
            continue

        if (len(word) > 1) and (word not in remove_words) and (not isNumber(word)) and (not isAdverb(word)):
            if isVerb(word):
                # salvo il lemma del verbo in attesa di accoppiamento
                verbo = getLemma(word)
            else:
                word_lemma = getLemma(word)

                if artwork not in dict_prototypes:
                    dict_prototypes[artwork] = {}

                dict_prototypes[artwork][word_lemma] = dict_prototypes[artwork].get(word_lemma, 0) + 1

                if verbo is not None:
                    # attribuisco al sostantivo anche il verbo precedente (se presente)
                    dict_prototypes[artwork][verbo] = dict_prototypes[artwork].get(verbo, 0) + 1
                    verbo = None

def main():
    # NLTK & TreeTagger
    ensure_nltk()
    global TAGGER
    try:
        TAGGER = make_tagger()
    except Exception as e:
        # Fall back: il programma continua ma senza lemmatizzazione POS tramite TreeTagger
        TAGGER = None
        print(f"[WARN] TreeTagger non inizializzato: {e}. Il processo continuerà senza lemmatizzazione avanzata.")

    # Stopwords inglesi + liste funzionali
    try:
        stop_words = set(stopwords.words('english'))
    except Exception:
        stop_words = set()
    remove_words = set(PREPOSITIONS + ARTICLES + CONJUNCTIONS + PUNCTUATION + list(stop_words))

    # Path I/O
    input_path = resolve_input_path()
    out_dir    = resolve_output_dir()

    # Costruisci prototipi
    dict_prototypes: Dict[str, Dict[str, int]] = {}
    n_items = 0
    for instance in iter_instances(input_path):
        try:
            insertArtworkInDict(instance, dict_prototypes, remove_words)
            n_items += 1
        except Exception as e:
            print(f"[WARN] errore durante l'elaborazione di un'istanza: {e}")

    # Scrivi file (uno per artwork)
    written = 0
    for artwork, counts in dict_prototypes.items():
        totWords = sum(counts.values())
        if totWords == 0:
            continue

        # frequenze min/max
        minFreq, maxFreq = 1.0, 0.0
        for cnt in counts.values():
            freq = cnt / totWords
            if freq < minFreq: minFreq = freq
            if freq > maxFreq: maxFreq = freq

        rangeFreq = maxFreq - minFreq
        rangeScore = MAX_SCORE - MIN_SCORE

        safe_name = artwork.replace("'", "_")
        out_path = out_dir / f"{safe_name}.txt"

        with out_path.open("w", encoding=ENCODING) as f:
            for word, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
                freq = count / totWords
                if rangeFreq == 0:
                    score = MAX_SCORE
                else:
                    score = MIN_SCORE + (rangeScore * (freq - minFreq) / rangeFreq)
                writeWordInFile(f, word, round(score, 3))
        written += 1

    print(f"Processed items: {n_items}")
    print(f"File generated in {out_dir} (written {written} files)")

if __name__ == "__main__":
    main()
