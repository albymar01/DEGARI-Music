# Classificatore che restituisce le istanze ordinate e filtra i brani
# che soddisfano un prototipo di categoria (rigid + typical attive)

import sys
import os
import json
import argparse

import Recommender_config as cfg
from DataFromInput import *  # ReadAttributes

# --- helpers (invariati) ---
def as_text(v):
    if isinstance(v, list):
        return " ".join(map(str, v))
    return "" if v is None else str(v)

def contains_word(s, w):
    s = " " + as_text(s) + " "
    w = " " + str(w) + " "
    return (w in s) or ((" " + str(w) + ",") in s)

def contains_value(lista, w):
    for p in lista:
        if str(p[0]) == w:
            return True
    return False

def take_name(x):
    if isinstance(x, tuple) and len(x) >= 1:
        return as_text(x[0]).strip()
    return as_text(x).strip()

def is_bool_tuple(x):
    return isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], bool)

def parse_scenario_bits(raw_result: str):
    try:
        arr = json.loads(raw_result)
        if isinstance(arr, list) and len(arr) > 0:
            return [int(x) for x in arr[:-1]]
    except Exception:
        pass
    r = raw_result.strip().strip("[]")
    if not r:
        return []
    parts = [p.strip().strip("'").strip('"') for p in r.split(",")]
    bits = []
    for p in parts:
        if p == "1":
            bits.append(1)
        elif p == "0":
            bits.append(0)
    return bits

def build_clean_prototype(f):
    bits = parse_scenario_bits(f.result)
    anchors = []
    prop_list = []
    for p in f.attrs:
        name = take_name(p)
        if not name:
            continue
        if is_bool_tuple(p):
            anchors.append(name)
            prop_list.append((name, True))
        else:
            prop_list.append((name, True))
    for i, p in enumerate(f.tipical_attrs):
        if i < len(bits) and bits[i] == 1:
            name = take_name(p)
            if name:
                prop_list.append((name, True))
    seen = set()
    clean = []
    for name, flag in prop_list:
        if name and name not in seen:
            seen.add(name)
            clean.append((name, True))
    return clean, set(anchors)

# --- core ---
def elaboraGraduatoria(category, prop_list, anchors_set,
                       not_prop_list=None,
                       min_match_rate=0.15, min_anchors=1, max_print=None,
                       json_outfile=None):
    if not_prop_list:
        not_prop_list = [p for p in not_prop_list if p]
    else:
        not_prop_list = []

    results_out = []

    with open(cfg.jsonDescrFile, encoding="utf-8") as json_file:
        data = json.load(json_file)
        if isinstance(data, dict):
            data = [data]

    tot_items = len(data)
    printed = 0

    # scorri istanze
    for instance in data:
        inst_id = as_text(instance.get(cfg.instanceID, ""))
        if not inst_id:
            continue

        matches = []
        anchor_hits = set()
        for prop_name, _ in prop_list:
            in_hit = False
            for fld in cfg.instanceDescr + cfg.instanceTitle:
                if fld in instance and contains_word(instance[fld], prop_name):
                    in_hit = True
                    break
            if in_hit:
                matches.append(prop_name)
                if prop_name in anchors_set:
                    anchor_hits.add(prop_name)

        neg_hit = False
        for prop in not_prop_list:
            for fld in cfg.instanceDescr + cfg.instanceTitle:
                if fld in instance and contains_word(instance[fld], str(prop)):
                    neg_hit = True
                    break
            if neg_hit:
                break

        enough_coverage = (len(matches) >= int(len(prop_list) * min_match_rate))
        enough_anchors = (len(anchor_hits) >= min_anchors)

        if not neg_hit and enough_coverage and enough_anchors:
            printed += 1
            results_out.append({
                "id": inst_id,
                "title": instance.get(cfg.instanceTitle[0], ""),
                "artist": instance.get("artist", ""),
                "matches": sorted(matches),
                "anchors_hit": sorted(list(anchor_hits))
            })
            if max_print and printed >= max_print:
                break

    # --- salva JSON ---
    if json_outfile:
        with open(json_outfile, "w", encoding="utf-8") as f:
            json.dump({
                "category": category,
                "prototype": [p[0] for p in prop_list],
                "anchors": list(anchors_set),
                "results": results_out,
                "classified": printed,
                "total": tot_items
            }, f, indent=2, ensure_ascii=False)

    # --- stampa breve ---
    if printed == 0:
        print(f"[{category}] No recommendable contents.")
    else:
        perc = (100 * printed) / max(1, tot_items)
        print(f"[{category}] Classified {printed} of {tot_items} ({perc:.2f}%) -> saved to {json_outfile}")

# --- main ---
if __name__ == '__main__':
    if len(sys.argv) >= 2:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--min-match-rate", type=float, default=0.15)
        parser.add_argument("--min-anchors", type=int, default=1)
        parser.add_argument("--max-print", type=int, default=None)
        args, rest = parser.parse_known_args(sys.argv[2:])

        prototipo = sys.argv[1]
        category = os.path.basename(prototipo)

        f = ReadAttributes(prototipo)
        prop_list, anchors_set = build_clean_prototype(f)

        # salva output in JSON accanto al file del prototipo
        out_json = prototipo.replace(".txt", "_recommendations.json")

        not_prop_list = []
        for p in f.attrs:
            nm = take_name(p)
            if nm.startswith("-"):
                not_prop_list.append(nm.replace("-", "").strip())

        elaboraGraduatoria(category, prop_list, anchors_set, not_prop_list,
                           min_match_rate=args.min_match_rate,
                           min_anchors=args.min_anchors,
                           max_print=args.max_print,
                           json_outfile=out_json)
    else:
        print("Specify a prototype for the classification!")
