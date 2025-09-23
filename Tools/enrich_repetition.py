# enrich_repetition.py
# Aggiunge feature di ripetizione/chorus agli item in descr_music*.json

import argparse, json, re, os
from collections import Counter
from typing import List, Tuple, Dict, Any

def ngrams(tokens: List[str], n: int) -> List[str]:
    return ["_".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)] if n>1 else tokens[:]

def normalize_text(text: str) -> List[str]:
    # minuscole + tieni lettere, numeri e apostrofo
    t = text.lower()
    t = re.sub(r"[^a-z0-9\s']", " ", t)
    toks = [w for w in t.split() if len(w) > 1]
    return toks

def repetition_scores(text: str, n_top_terms: int = 5) -> Dict[str, Any]:
    if not text or not text.strip():
        return {
            "rep_ratio": 0.0,
            "has_chorus_like": 0,
            "has_hook_like": 0,
            "top_terms": [],
            "top_bigrams": [],
            "top_trigrams": []
        }
    toks = normalize_text(text)
    total = len(toks)
    if total == 0:
        return {
            "rep_ratio": 0.0,
            "has_chorus_like": 0,
            "has_hook_like": 0,
            "top_terms": [],
            "top_bigrams": [],
            "top_trigrams": []
        }

    uniq = len(set(toks))
    rep_ratio = max(0.0, 1.0 - (uniq / total))  # 0..1

    # n-gram
    big = ngrams(toks, 2)
    tri = ngrams(toks, 3)
    most_big = Counter(big).most_common(5)
    most_tri = Counter(tri).most_common(5)

    # euristiche semplici per "chorus" e "hook"
    # (percentuali sul totale token — regola grossolana ma pratica)
    has_chorus_like = 1 if most_big and (most_big[0][1] / total) >= 0.03 else 0
    has_hook_like   = 1 if most_tri and (most_tri[0][1] / total) >= 0.02 else 0

    top_terms = [w for (w,_) in Counter(toks).most_common(n_top_terms)]
    top_bigrams = [{"ngram": k, "count": v} for (k,v) in most_big]
    top_trigrams = [{"ngram": k, "count": v} for (k,v) in most_tri]

    return {
        "rep_ratio": round(rep_ratio, 3),
        "has_chorus_like": has_chorus_like,
        "has_hook_like": has_hook_like,
        "top_terms": top_terms,
        "top_bigrams": top_bigrams,
        "top_trigrams": top_trigrams
    }

def enrich(json_in: str, json_out: str = None, rep_tag_thr: float = 0.25) -> None:
    with open(json_in, "r", encoding="utf-8") as f:
        data = json.load(f)
    changed = 0

    for item in data:
        lyrics = item.get("lyrics") or item.get("text") or ""
        scores = repetition_scores(lyrics)

        # Aggiorna/aggiungi sezione "repetition"
        item["repetition"] = scores

        # Gestione tag
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
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # commit atomico
    if os.path.exists(out_path):
        os.replace(tmp_path, out_path)
    else:
        os.rename(tmp_path, out_path)

    print(f"Aggiornato: {out_path} - items processati: {changed}")

def main():
    ap = argparse.ArgumentParser(description="Enrich repetition/chorus features into descr_music JSON.")
    ap.add_argument("--json-in", required=True, help="Percorso del JSON sorgente (descr_music*.json)")
    ap.add_argument("--json-out", help="Percorso del JSON di output (se assente, sovrascrive json-in)")
    ap.add_argument("--rep-thr", type=float, default=0.25, help="Soglia per tag 'high_repetition' (default 0.25)")
    args = ap.parse_args()
    enrich(args.json_in, args.json_out, args.rep_thr)

if __name__ == "__main__":
    main()
