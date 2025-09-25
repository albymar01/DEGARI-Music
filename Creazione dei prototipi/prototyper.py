from pathlib import Path
import os
import json
import string
import re
from typing import Dict, Iterable, List, Tuple, Any, Optional

# Componenti NLP
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import treetaggerwrapper

# Config del progetto (file locale con path e campi da usare)
import prototyper_config as cfg

# =============================================================================
# Costanti e impostazioni base
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent  # Root progetto: .../DEGARI-Music

# Liste funzionali per filtrare token poco informativi (inglese)
PREPOSITIONS = ["of","to","from","in","on","at","by","for",
                "with","about","against","between","into",
                "through","during","before","after","above",
                "below","up","down","out","off","over","under"]
ARTICLES = ["the","a","an"]
CONJUNCTIONS = ["and","or","but","so","yet","for","nor","because",
                "although","though","while","if","when","where","that",
                "which","who","whom","whose","until","unless","since","as",
                "than","whether","either","neither","both","also","only"]
PUNCTUATION = list(string.punctuation) + ["...", "``"]  # Punteggiatura da scartare
CHARS_NOT_ALLOWED = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']  # Caratteri illegali per filename (Win)

# Range per lo score normalizzato dei prototipi
MIN_SCORE = 0.6
MAX_SCORE = 0.9
ENCODING = "utf-8"

TAGGER = None  # Inizializzato in main() se TreeTagger è disponibile

# =============================================================================
# Utility per path e I/O
# =============================================================================

def resolve_input_path() -> Path:
    # Risolve il path di input indicato in cfg.jsonDescrFile:
    # - se assoluto lo usa direttamente
    # - se relativo lo risolve rispetto alla root del progetto
    # Può puntare a un singolo file JSON o a una directory contenente JSON.
    raw = Path(cfg.jsonDescrFile)
    return raw if raw.is_absolute() else (PROJECT_ROOT / raw)

def resolve_output_dir() -> Path:
    # Risolve/crea la cartella di output indicata in cfg.outPath
    # - se assoluta la usa così com'è
    # - se relativa la risolve sotto la root del progetto
    p = Path(cfg.outPath)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    p.mkdir(parents=True, exist_ok=True)
    return p

def safe_slug(s: str) -> str:
    # Crea uno slug semplice: lowercase, alfanumerico con trattini singoli
    # Evita dipendenze esterne (es. slugify)
    s = (s or "").lower()
    s = re.sub(r"[^\w\s-]+", " ", s)
    s = re.sub(r"[\s_-]+", "-", s).strip("-")
    return s

def safe_filename(s: str) -> str:
    # Rimuove caratteri non consentiti nei filename su Windows
    if s is None:
        return ""
    for ch in CHARS_NOT_ALLOWED:
        s = s.replace(ch, "")
    return s

# =============================================================================
# Gestione TreeTagger / NLTK
# =============================================================================

def ensure_nltk():
    # Garantisce la disponibilità minima delle risorse NLTK:
    # - stopwords inglesi
    # - tokenizer 'punkt'
    try:
        _ = stopwords.words('english')
    except (LookupError, OSError):
        import nltk
        nltk.download('stopwords', quiet=True)
    try:
        import nltk
        nltk.data.find('tokenizers/punkt')
    except (LookupError, OSError):
        import nltk
        nltk.download('punkt', quiet=True)

def find_treetagger() -> Optional[str]:
    # Cerca automaticamente l'installazione di TreeTagger in questo ordine:
    # 1) variabili d'ambiente TAGDIR / TREETAGGER_HOME
    # 2) path desktop comuni
    # 3) sottocartella TreeTagger dentro il progetto
    # Accetta una dir che contenga 'bin' o 'lib'
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
        if p.exists() and (p.joinpath("bin").exists() or p.joinpath("lib").exists()):
            return str(p)
    return None

def make_tagger():
    # Istanzia un TreeTagger inglese.
    # Se non trova un'installazione valida, solleva RuntimeError con istruzioni.
    tagdir = find_treetagger()
    if not tagdir:
        raise RuntimeError(
            "TreeTagger non trovato. Imposta TAGDIR/TREETAGGER_HOME oppure installalo in:\n"
            r"- C:\Users\<utente>\Desktop\TreeTagger\n"
            f"- {PROJECT_ROOT / 'TreeTagger'}"
        )
    parfile = os.path.join(tagdir, "lib", "english-bnc.par")
    abbrev  = os.path.join(tagdir, "lib", "english-abbreviations")
    # Se i file specifici non esistono, lascia None: il wrapper userà i default.
    return treetaggerwrapper.TreeTagger(
        TAGLANG="en",
        TAGDIR=tagdir,
        TAGPARFILE=parfile if os.path.exists(parfile) else None,
        TAGABBREV=abbrev if os.path.exists(abbrev) else None,
    )

def get_tags(text: str):
    # Ritorna i tag TreeTagger per il testo, oppure lista vuota se il tagger non è pronto o fallisce.
    global TAGGER
    if TAGGER is None:
        return []
    try:
        return treetaggerwrapper.make_tags(TAGGER.tag_text(text))
    except Exception:
        return []

def getLemma(word: str) -> str:
    # Restituisce il lemma della parola via TreeTagger.
    # In fallback (assenza/errore) ritorna la parola lowercased.
    if not word:
        return ""
    try:
        tags = get_tags(word)
        if tags:
            lemma = tags[0].lemma or ""
            # TreeTagger talvolta usa "lemma:qualcosa": teniamo la parte prima di ':'
            return (str(lemma).split(":")[0]) or word.lower()
        return word.lower()
    except Exception:
        return word.lower()

def getTypeOfWord(word: str) -> str:
    # Restituisce il POS di TreeTagger (stringa semplificata), o "" se non disponibile.
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

# Utility POS (inglese) basate sui tag di TreeTagger
def isNumber(word):    return getTypeOfWord(word) in ("CD", "NUM")
def isVerb(word):      return getTypeOfWord(word).startswith("VB") if getTypeOfWord(word) else False   # VB, VBD, VBG, ...
def isAdjective(word): return getTypeOfWord(word).startswith("JJ") if getTypeOfWord(word) else False   # JJ, JJR, JJS
def isAdverb(word):    return getTypeOfWord(word).startswith("RB") if getTypeOfWord(word) else False   # RB, RBR, RBS

# =============================================================================
# Normalizzazione delle istanze (brani)
# =============================================================================

def to_text(value: Any) -> str:
    # Converte un valore in stringa:
    # - liste -> join con spazio
    # - None  -> stringa vuota
    # - altri -> str(value)
    if isinstance(value, list):
        return " ".join(map(str, value))
    return "" if value is None else str(value)

def normalize_instance(obj: Dict[str, Any]) -> Dict[str, Any]:
    # Uniforma un'istanza brano in un unico schema:
    # {
    #   "ID", "title", "artist", "album", "year",
    #   "lyrics", "tags", "moods", "instruments", "subgenres", "contexts"
    # }
    #
    # Supporta:
    # - schema "vecchio" (descr_music_GENIUS*.json)
    # - schema "nuovo" (file __extended*.json)
    # Caso 1) già nel formato "vecchio"
    if "ID" in obj and "lyrics" in obj:
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

    # Caso 2) schema "nuovo" (extended)
    title   = to_text(obj.get("title"))
    artist  = to_text(obj.get("artist"))
    album   = to_text((obj.get("genius") or {}).get("album") or "Single")
    year    = to_text(obj.get("year"))
    lyrics  = to_text(obj.get("lyrics"))

    genre   = to_text(obj.get("genre"))
    genius  = obj.get("genius") or {}
    gid     = genius.get("genius_id")
    gtags   = list(genius.get("raw_tags") or [])

    # Strumentazione dal piano se presente
    plan_instr = list((obj.get("plan") or {}).get("instrumentation") or [])

    # Subgeneri/contesti: se non forniti -> liste vuote (subgenres include il genre primario)
    subgenres = [genre] if genre else []
    contexts  = []

    # Costruzione ID: <genre>_<artist_slug_10>_<title_slug_16>[_<year>][_gid]
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
    # Generatore di istanze normalizzate a partire da:
    # - FILE JSON: oggetto singolo o lista di oggetti
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

    # - DIRECTORY: tutti i file *.json (flat, non ricorsivo)
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

# =============================================================================
# Generazione dei prototipi (feature words + score)
# =============================================================================

def writeWordInFile(file, word, value):
    # Scrive una riga "word: <spazi>value" con allineamento minimo
    spaces = max(1, 20 - len(word) + 1)
    file.write(f"{word}:{' ' * spaces}{value}\n")

def insertArtworkInDict(instance: Dict[str, Any],
                        dict_prototypes: Dict[str, Dict[str, int]],
                        remove_words: set):
    # Estrae i lemmi dai campi descrittivi dell'istanza e aggiorna il dizionario:
    # dict_prototypes[artwork_id][lemma] = frequenza grezza (conteggio)
    # Regola: associa il verbo (lemma) al sostantivo successivo come co-occorrenza leggera.
    # -----------------------------------------------------------------------------

    # Identificatore dell'artwork: usa cfg.instanceID se presente, altrimenti fallback dallo slug
    key_name = getattr(cfg, "instanceID", "ID")
    artwork_id = instance.get(key_name) if isinstance(instance, dict) else None
    if not artwork_id:
        title = instance.get("title", "") or ""
        artist = instance.get("artist", "") or ""
        year = instance.get("year", "") or ""
        artwork_id = safe_slug(f"{artist}_{title}_{year}") or "artwork"
    artwork = safe_filename(str(artwork_id))

    # Costruzione descrizione concatenando i campi elencati in cfg.instanceDescr (fallback default)
    try:
        descr_fields = list(cfg.instanceDescr)
    except Exception:
        descr_fields = ["title", "artist", "lyrics", "tags"]

    description = " " + " ".join(
        to_text(instance.get(d, "")) for d in descr_fields
    )

    # Tokenizzazione: preferisci NLTK, altrimenti split semplice
    try:
        word_tokens = word_tokenize(description)
    except Exception:
        word_tokens = description.split()

    verbo = None  # memorizza l'ultimo verbo lemmatizzato in attesa di agganciarlo a un sostantivo

    for word in word_tokens:
        word = word.lower().strip()
        if not word:
            continue

        # Filtra token: lunghezza >1, non stopword/funcword, non numeri, non avverbi
        if (len(word) > 1) and (word not in remove_words) and (not isNumber(word)) and (not isAdverb(word)):
            if isVerb(word):
                # Memorizza lemma del verbo per il prossimo sostantivo/parola utile
                verbo = getLemma(word)
            else:
                word_lemma = getLemma(word)

                if artwork not in dict_prototypes:
                    dict_prototypes[artwork] = {}

                dict_prototypes[artwork][word_lemma] = dict_prototypes[artwork].get(word_lemma, 0) + 1

                if verbo is not None:
                    # Aggiunge anche il verbo come feature "co-occorrenza" del sostantivo corrente
                    dict_prototypes[artwork][verbo] = dict_prototypes[artwork].get(verbo, 0) + 1
                    verbo = None

def main():
    # Inizializzazione componenti NLP
    ensure_nltk()
    global TAGGER
    try:
        TAGGER = make_tagger()
    except Exception as e:
        # Fallback: procede senza lemmatizzazione/pos avanzata
        TAGGER = None
        print(f"[WARN] TreeTagger non inizializzato: {e}. Il processo continuerà senza lemmatizzazione avanzata.")

    # Costruzione set di parole da rimuovere (stopword + liste funzionali)
    try:
        stop_words = set(stopwords.words('english'))
    except Exception:
        stop_words = set()
    remove_words = set(PREPOSITIONS + ARTICLES + CONJUNCTIONS + PUNCTUATION + list(stop_words))

    # Path input/output
    input_path = resolve_input_path()
    out_dir    = resolve_output_dir()

    # Costruzione prototipi (conteggi per artwork)
    dict_prototypes: Dict[str, Dict[str, int]] = {}
    n_items = 0
    for instance in iter_instances(input_path):
        try:
            insertArtworkInDict(instance, dict_prototypes, remove_words)
            n_items += 1
        except Exception as e:
            print(f"[WARN] errore durante l'elaborazione di un'istanza: {e}")

    # Scrittura file: uno per artwork (<artwork>.txt) con punteggi normalizzati in [MIN_SCORE, MAX_SCORE]
    written = 0
    for artwork, counts in dict_prototypes.items():
        totWords = sum(counts.values())
        if totWords == 0:
            continue

        # Calcolo freq min/max per normalizzare i punteggi
        minFreq, maxFreq = 1.0, 0.0
        for cnt in counts.values():
            freq = cnt / totWords
            if freq < minFreq: minFreq = freq
            if freq > maxFreq: maxFreq = freq

        rangeFreq = maxFreq - minFreq
        rangeScore = MAX_SCORE - MIN_SCORE

        # Filename sicuro (sostituisce apostrofi per evitare problemi)
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
