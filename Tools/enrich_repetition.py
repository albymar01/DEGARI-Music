# enrich_repetition.py
# Aggiunge feature di ripetizione/chorus agli item in descr_music*.json (EN-only)
# - Calcola rep_ratio = 1 - (vocab_size / token_count)  in [0..1]
# - Estrae top n-gram (unigrammi/bigrammi/trigrammi)
# - Flag euristici: has_chorus_like, has_hook_like
# - Aggiunge/aggiorna "repetition" e arricchisce "tags" con:
#     catchy_chorus, hook_repetition, high_repetition (se rep_ratio >= soglia)
#
# NOTE:
# - Non scarta brani corti: elabora TUTTO (come richiesto)
# - Lingua: inglese; normalizza a-z, 0-9, apostrofo; rimuove tutto il resto
# - Riconosce (best-effort) etichette tra parentesi quadre tipo [Chorus], [Hook]
#   e le usa come "boost" per i flag (configurabile via --no-section-boost)

import argparse, json, re, os
from collections import Counter
from typing import List, Dict, Any, Tuple

# ----------------------------
# Utility per tokenizzazione
# ----------------------------

def ngrams(tokens: List[str], n: int) -> List[str]:
    """Costruisce lista di n-gram come stringhe unite da '_'."""
    if n <= 1:
        return tokens[:]
    return ["_".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

def normalize_text(text: str) -> List[str]:
    """
    Normalizza il testo:
    - minuscole
    - mantiene lettere a-z, cifre 0-9 e apostrofo
    - sostituisce il resto con spazio
    - rimuove token di lunghezza 1 (tranne cifre/apostrofi già filtrati)
    """
    t = (text or "").lower()
    t = re.sub(r"[^a-z0-9\s']", " ", t)
    toks = [w for w in t.split() if len(w) > 1]
    return toks

SECTION_TAG_RE = re.compile(r"\[(\s*chorus\s*|hook|refrain|bridge|verse|intro|outro|pre-?chorus)\]", re.IGNORECASE)

def extract_section_labels(raw_text: str) -> List[str]:
    """
    Estrae etichette di sezione tipo [Chorus], [Hook], [Verse], ecc.
    Restituisce lista normalizzata (minuscole, spazi normalizzati).
    """
    labels = []
    for m in SECTION_TAG_RE.finditer(raw_text or ""):
        label = re.sub(r"\s+", " ", m.group(1).strip().lower())
        labels.append(label)
    return labels

# ----------------------------
# Core scoring
# ----------------------------

def repetition_scores(
    text: str,
    n_top_terms: int = 5,
    section_boost: bool = True
) -> Dict[str, Any]:
    """
    Calcola indici di ripetizione e n-gram frequentissimi.
    - rep_ratio: 1 - (uniq/total)
    - has_chorus_like / has_hook_like: euristiche su bigram/trigram + (opz.) boost da [Chorus]/[Hook]
    """
    if not text or not text.strip():
        return {
            "rep_ratio": 0.0,
            "has_chorus_like": 0,
            "has_hook_like": 0,
            "top_terms": [],
            "top_bigrams": [],
            "top_trigrams": [],
            "section_labels": []
        }

    # 1) tokenizza “pulito” (inglese)
    toks = normalize_text(text)
    total = len(toks)
    if total == 0:
        return {
            "rep_ratio": 0.0,
            "has_chorus_like": 0,
            "has_hook_like": 0,
            "top_terms": [],
            "top_bigrams": [],
            "top_trigrams": [],
            "section_labels": []
        }

    # 2) rapporto di ripetizione (0..1)
    uniq = len(set(toks))
    rep_ratio = max(0.0, 1.0 - (uniq / total))

    # 3) n-gram frequenti
    big = ngrams(toks, 2)
    tri = ngrams(toks, 3)
    most_uni = Counter(toks).most_common(n_top_terms)
    most_big = Counter(big).most_common(5)
    most_tri = Counter(tri).most_common(5)

    # 4) euristiche chorus/hook su n-gram (percentuale sul totale token)
    #    Soglie “morbide”, funzionano bene su testi lunghi
    chorus_like = 1 if most_big and (most_big[0][1] / total) >= 0.03 else 0
    hook_like   = 1 if most_tri and (most_tri[0][1] / total) >= 0.02 else 0

    # 5) (opzionale) boost da etichette sezione nel testo originale
    labels = extract_section_labels(text)
    if section_boost and labels:
        # Se c'è un [chorus] → chorus_like = 1
        if any("chorus" in lb or "pre-chorus" in lb for lb in labels):
            chorus_like = 1
        # Se c'è un [hook] → hook_like = 1
        if any("hook" in lb for lb in labels):
            hook_like = 1

    # 6) impacchetta risultati
    top_terms = [w for (w, _) in most_uni]
    top_bigrams = [{"ngram": k, "count": v} for (k, v) in most_big]
    top_trigrams = [{"ngram": k, "count": v} for (k, v) in most_tri]

    return {
        "rep_ratio": round(rep_ratio, 3),
        "has_chorus_like": int(chorus_like),
        "has_hook_like": int(hook_like),
        "top_terms": top_terms,
        "top_bigrams": top_bigrams,
        "top_trigrams": top_trigrams,
        "section_labels": labels  # utile per debug/analisi
    }

# ----------------------------
# Enrichment su JSON
# ----------------------------

def enrich(json_in: str, json_out: str = None, rep_tag_thr: float = 0.25, section_boost: bool = True) -> None:
    """
    Carica il JSON, calcola i punteggi e:
    - aggiorna item["repetition"]
    - arricchisce i tag:
        * catchy_chorus se has_chorus_like
        * hook_repetition se has_hook_like
        * high_repetition se rep_ratio >= rep_tag_thr
    Scrive su json_out (o sovrascrive json_in se json_out non fornito) con commit atomico.
    """
    with open(json_in, "r", encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    for item in data:
        # Lyrics: usa "lyrics", fallback a "text" se non presente
        lyrics = item.get("lyrics") or item.get("text") or ""
        scores = repetition_scores(lyrics, section_boost=section_boost)

        # Sezione "repetition"
        item["repetition"] = scores

        # Tag arricchiti
        tags = set(item.get("tags", []))
        if scores["has_chorus_like"]:
            tags.add("catchy_chorus")
        if scores["has_hook_like"]:
            tags.add("hook_repetition")
        if scores["rep_ratio"] >= rep_tag_thr:
            tags.add("high_repetition")
        if tags:
            item["tags"] = sorted(tags)

        changed += 1

    out_path = json_out or json_in
    tmp_path = out_path + ".tmp"

    # Scrittura pretty con indentazione; ensure_ascii=False per mantenere eventuali caratteri speciali
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Commit atomico cross-versione Windows/Python
    if os.path.exists(out_path):
        os.replace(tmp_path, out_path)
    else:
        os.rename(tmp_path, out_path)

    print(f"Aggiornato: {out_path} - items processati: {changed}")

# ----------------------------
# CLI
# ----------------------------

def main():
    ap = argparse.ArgumentParser(description="Enrich repetition/chorus features into descr_music JSON (EN-only).")
    ap.add_argument("--json-in", required=True, help="Percorso del JSON sorgente (descr_music*.json)")
    ap.add_argument("--json-out", help="Percorso del JSON di output (se assente, sovrascrive json-in)")
    ap.add_argument("--rep-thr", type=float, default=0.25, help="Soglia per tag 'high_repetition' (default 0.25)")
    ap.add_argument("--no-section-boost", action="store_true",
                    help="Disabilita il boost dei flag se compaiono etichette [Chorus]/[Hook] nel testo")
    args = ap.parse_args()

    enrich(
        json_in=args.json_in,
        json_out=args.json_out,
        rep_tag_thr=args.rep_thr,
        section_boost=not args.no_section_boost
    )

if __name__ == "__main__":
    main()
