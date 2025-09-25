# Classificatore che restituisce le istanze ordinate e filtra i brani
# che soddisfano un prototipo di categoria (rigid + typical attive)

import sys
import os
import json
from pprint import pprint
import argparse

import Recommender_config as cfg
from DataFromInput import *  # ReadAttributes

# --------- helpers ---------
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
    """Estrai il nome della proprietà da stringa/tupla."""
    if isinstance(x, tuple) and len(x) >= 1:
        return as_text(x[0]).strip()
    return as_text(x).strip()

def is_bool_tuple(x):
    return isinstance(x, tuple) and len(x) == 2 and isinstance(x[1], bool)

def is_weighted_tuple(x):
    return isinstance(x, tuple) and len(x) >= 2 and isinstance(x[1], (int, float))

def parse_scenario_bits(raw_result: str):
    # nuovo formato JSON: [1,0,1,..., score]
    try:
        arr = json.loads(raw_result)
        if isinstance(arr, list) and len(arr) > 0:
            return [int(x) for x in arr[:-1]]
    except Exception:
        pass
    # legacy: "'1','0',..."
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
    """
    Ritorna:
      prop_list_clean: [(name, True)] per ogni proprietà attiva (rigid + typical attive)
      anchors: set di nomi rigid (head/modifier) usati per la soglia min-anchors
    """
    bits = parse_scenario_bits(f.result)

    # rigid (head/modifier)
    anchors = []
    prop_list = []
    for p in f.attrs:
        name = take_name(p)
        if not name:
            continue
        if is_bool_tuple(p):
            anchors.append(name)     # ancora di genere
            prop_list.append((name, True))
        else:
            # alcuni dump possono arrivare come stringhe "pure"
            prop_list.append((name, True))

    # typical attive secondo i bit
    for i, p in enumerate(f.tipical_attrs):
        if i < len(bits) and bits[i] == 1:
            name = take_name(p)
            if name:
                prop_list.append((name, True))

    # dedup + pulizia
    seen = set()
    clean = []
    for name, flag in prop_list:
        if name and name not in seen:
            seen.add(name)
            clean.append((name, True))

    return clean, set(anchors)

# --------- core ---------
def elaboraGraduatoria(prop_list, anchors_set, not_prop_list=None,
                       min_match_rate=0.15, min_anchors=1, max_print=None):
    if not_prop_list:
        not_prop_list = [p for p in not_prop_list if p]  # safety
    else:
        not_prop_list = []

    # per stampa più chiara
    print("\nRecommended artworks:\n")
    print(f"(thresholds: min-match-rate={min_match_rate:.2f}, min-anchors={min_anchors})\n")

    graduatoria = {}
    lista_istanze = []
    chars_not_allowed_in_filename = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']

    tot_items = 0
    # Carica JSON (accetta lista o singolo oggetto)
    with open(cfg.jsonDescrFile, encoding="utf-8") as json_file:
        data = json.load(json_file)
        if isinstance(data, dict):
            data = [data]

    # --------- graduatoria: somma punteggi dal prototipo Mod.1 ---------
    for instance in data:
        if cfg.instanceID not in instance:
            continue
        tot_items += 1
        inst_id = as_text(instance[cfg.instanceID])
        for ch in chars_not_allowed_in_filename:
            inst_id = inst_id.replace(ch, "")
        inst_id = inst_id.replace("'", "_")

        if inst_id not in graduatoria:
            # piccolo boost se qualsiasi prop compare nel titolo
            boost = 0.0
            for prop in prop_list:
                for t in cfg.instanceTitle:
                    if t in instance and contains_word(instance[t], str(prop[0])):
                        boost = 0.1
                        break
            graduatoria[inst_id] = boost

            proto_path = os.path.join(cfg.protPath, inst_id + ".txt")
            if os.path.exists(proto_path):
                with open(proto_path, "r", encoding="utf-8") as artworkFile:
                    for line in artworkFile:
                        parts = line.split(':')
                        if len(parts) >= 2:
                            key = parts[0].strip()
                            if contains_value(prop_list, key):
                                try:
                                    score = round(float(parts[1].strip()), 2)
                                except ValueError:
                                    score = 0.0
                                graduatoria[inst_id] += score

    # --------- filtro istanze che soddisfano la categoria ---------
    names_only = [p[0] for p in prop_list]
    for instance in data:
        if cfg.instanceID not in instance:
            continue
        inst_id = as_text(instance[cfg.instanceID])
        for ch in chars_not_allowed_in_filename:
            inst_id = inst_id.replace(ch, "")
        inst_id = inst_id.replace("'", "_")

        matches = []
        anchor_hits = set()

        # match su campi descrittivi/titolo
        for prop_name in names_only:
            in_hit = False
            # descr
            for fld in cfg.instanceDescr:
                if fld in instance and contains_word(instance[fld], prop_name):
                    in_hit = True
                    break
            # title/artist
            if not in_hit:
                for fld in cfg.instanceTitle:
                    if fld in instance and contains_word(instance[fld], prop_name):
                        in_hit = True
                        break
            if in_hit:
                matches.append(prop_name)
                if prop_name in anchors_set:
                    anchor_hits.add(prop_name)

        # proprietà negate → escludi
        neg_hit = False
        for prop in not_prop_list:
            # descr
            for fld in cfg.instanceDescr:
                if fld in instance and contains_word(instance[fld], str(prop)):
                    neg_hit = True
                    break
            # title
            if not neg_hit and cfg.instanceTitle and cfg.instanceTitle[0] in instance:
                if contains_word(instance[cfg.instanceTitle[0]], str(prop)):
                    neg_hit = True
            if neg_hit:
                matches.clear()
                break

        # soglie
        enough_coverage = (len(names_only) > 0 and int(len(matches)) >= int(len(names_only) * min_match_rate))
        enough_anchors = (len(anchor_hits) >= min_anchors)

        if enough_coverage and enough_anchors:
            title_field = instance.get(cfg.instanceTitle[0], "")
            lista_istanze.append([
                f"{inst_id} - {as_text(title_field)}",
                "\n\t\\-> matches: " + str(sorted(matches))
            ])
        elif inst_id in graduatoria and (not enough_coverage or not enough_anchors):
            # se non passa i filtri, azzera lo score (non verrà stampato)
            graduatoria[inst_id] = 0.0

    # --------- stampa finale ---------
    printed = 0
    for artwork, score in sorted(graduatoria.items(), key=lambda kv: kv[1], reverse=True):
        if score == 0:
            break
        print(f"{artwork}-{score}")
        for istanza in lista_istanze:
            if (" " + artwork + " ") in (" " + istanza[0] + " "):
                printed += 1
                print("\t" + istanza[0] + istanza[1] + "\n")
                with open("recommendations.tsv", "a", encoding="utf-8") as f:
                    f.write(istanza[0].replace("\t", " ") + "\t" + category + "\n")
                if max_print and printed >= max_print:
                    break
        if max_print and printed >= max_print:
            break

    if printed == 0:
        print("No recommendable contents for this category.")
    else:
        perc = (100 * printed) / max(1, tot_items)
        print(f"Classified {printed} of {tot_items} contents ({perc:.2f}%)")
        with open("resume.tsv", "a", encoding="utf-8") as f:
            f.write(category.replace("\t", " ") + "\t" + str(printed) + "\n")

# --------- main ---------
if __name__ == '__main__':
    if len(sys.argv) >= 2:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--min-match-rate", type=float, default=0.15)
        parser.add_argument("--min-anchors", type=int, default=1)
        parser.add_argument("--max-print", type=int, default=None)
        args, rest = parser.parse_known_args(sys.argv[2:])

        prototipo = sys.argv[1]
        category = prototipo.split("/")[-1]

        f = ReadAttributes(prototipo)

        # costruisci prototipo pulito
        prop_list, anchors_set = build_clean_prototype(f)

        # stampa prototipo in modo leggibile
        names = [p[0] for p in prop_list]
        print("\nRecommendation for category: " + category + "\n\nCategory prototype: \n")
        print(names)
        print("anchors:", sorted(list(anchors_set)))
        print("")

        # NOT list (se in futuro inserirai negate con prefisso '-')
        not_prop_list = []
        for p in f.attrs:
            nm = take_name(p)
            if nm.startswith("-"):
                not_prop_list.append(nm.replace("-", "").strip())

        elaboraGraduatoria(prop_list, anchors_set, not_prop_list,
                           min_match_rate=args.min_match_rate,
                           min_anchors=args.min_anchors,
                           max_print=args.max_print)
    else:
        print("Specify a prototype for the classification!")
