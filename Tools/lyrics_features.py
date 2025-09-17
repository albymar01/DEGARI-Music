#script per il feature di ripetizione/chorus
import json, os, re
from collections import Counter

JSON_PATH = r"C:\Users\Utente\Desktop\DEGARI-Music2.0\Creazione dei prototipi\descr_music.json"

def ngrams(tokens, n=2):
    return ["_".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

def repetition_scores(text: str):
    t = text.lower()
    t = re.sub(r"[^a-z0-9\s']", " ", t)
    toks = [w for w in t.split() if len(w)>1]
    if not toks:
        return 0,0,0,[]

    total = len(toks)
    uniq = len(set(toks))
    rep_ratio = 1 - (uniq/total)   # 0..1

    big = ngrams(toks,2)
    tri = ngrams(toks,3)
    most_big = Counter(big).most_common(3)
    most_tri = Counter(tri).most_common(3)

    chorus_like = 1 if (most_big and most_big[0][1]/max(1,total) >= 0.03) else 0
    hook_like   = 1 if (most_tri and most_tri[0][1]/max(1,total) >= 0.02) else 0

    top_terms = [x for x,_ in Counter(toks).most_common(5)]
    return rep_ratio, chorus_like, hook_like, top_terms

def enrich():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    for item in data:
        rep, chorus, hook, _ = repetition_scores(item.get("lyrics",""))
        tags = set(item.get("tags", []))
        if chorus: tags.add("catchy_chorus")
        if hook:   tags.add("hook_repetition")
        if rep >= 0.25: tags.add("high_repetition")
        item["tags"] = sorted(tags)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Aggiornato descr_music.json con tag di ripetizione.")

if __name__ == "__main__":
    enrich()
