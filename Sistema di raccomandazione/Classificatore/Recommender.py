# Classificatore che restituisce tutte le istanze ordinate in base ad una graduatoria
# che rientrano nel nuovo genere fornito in input

import sys
import os
import json
from pprint import pprint

import Recommender_config as cfg
from DataFromInput import *  # ReadAttributes

# --------- helpers ---------
def as_text(v):
    """Rende qualsiasi campo (stringa/lista/numero) una stringa ricercabile."""
    if isinstance(v, list):
        return " ".join(map(str, v))
    return "" if v is None else str(v)

def contains_word(s, w):
    """Ricerca semplice 'parola' in stringa (conspazi o virgola)."""
    s = " " + as_text(s) + " "
    w = " " + str(w) + " "
    return (w in s) or ((" " + str(w) + ",") in s)

def contains_value(lista, w):
    for p in lista:
        if str(p[0]) == w:
            return True
    return False

# --------- core ---------
def elaboraGraduatoria(prop_list, not_prop_list=None):
    if not_prop_list is None:
        not_prop_list = []

    print("\nRecommended artworks:\n\n")

    graduatoria = {}
    lista_istanze = []
    chars_not_allowed_in_filename = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']

    tot_items = 0

    # Carica JSON (accetta lista o singolo oggetto)
    with open(cfg.jsonDescrFile, encoding="utf-8") as json_file:
        data = json.load(json_file)
        if isinstance(data, dict):
            data = [data]

    # --------- calcolo graduatoria (somma dei punteggi dei match nel prototipo Mod.1) ---------
    for instance in data:
        # skip se manca l'ID
        if cfg.instanceID not in instance:
            continue

        tot_items += 1
        inst_id = as_text(instance[cfg.instanceID])
        for ch in chars_not_allowed_in_filename:
            inst_id = inst_id.replace(ch, "")
        inst_id = inst_id.replace("'", "_")

        if inst_id not in graduatoria:
            # piccolo boost se le proprietà compaiono nel title
            boost = 0.0
            for prop in prop_list:
                for t in cfg.instanceTitle:
                    if t in instance and contains_word(instance[t], str(prop[0])):
                        boost = 0.1
                        break
            graduatoria[inst_id] = boost

            # somma dei pesi dal prototipo del Modulo 1
            proto_path = os.path.join(cfg.protPath, inst_id + ".txt")
            if os.path.exists(proto_path):
                with open(proto_path, "r", encoding="utf-8") as artworkFile:
                    for line in artworkFile:
                        word = line.split(':')
                        if len(word) >= 2:
                            key = word[0].strip()
                            if contains_value(prop_list, key):
                                try:
                                    score = round(float(word[1].strip()), 2)
                                except ValueError:
                                    score = 0.0
                                graduatoria[inst_id] += score
            else:
                # se non esiste il prototipo, lascia a 0 (verrà ignorato)
                pass

    # --------- filtra istanze che soddisfano la categoria (30% delle proprietà + assenza negate) ---------
    for instance in data:
        if cfg.instanceID not in instance:
            continue

        inst_id = as_text(instance[cfg.instanceID])
        for ch in chars_not_allowed_in_filename:
            inst_id = inst_id.replace(ch, "")
        inst_id = inst_id.replace("'", "_")

        # proprietà presenti nell'istanza
        matches = []
        for prop in prop_list:
            # cerca nei campi descrittivi
            inDescr = False
            i = 0
            while (not inDescr) and i < len(cfg.instanceDescr):
                fld = cfg.instanceDescr[i]
                if fld in instance and contains_word(instance[fld], str(prop[0])):
                    inDescr = True
                i += 1

            # cerca anche nel titolo/artist
            inTitle = False
            i = 0
            while (not inTitle) and i < len(cfg.instanceTitle):
                fld = cfg.instanceTitle[i]
                if fld in instance and contains_word(instance[fld], str(prop[0])):
                    inTitle = True
                i += 1

            if inDescr or inTitle:
                matches.append(str(prop[0]))

        # se contiene proprietà negate, scarta
        neg_hit = False
        for prop in not_prop_list:
            # descr
            i = 0
            while (not neg_hit) and i < len(cfg.instanceDescr):
                fld = cfg.instanceDescr[i]
                if fld in instance and contains_word(instance[fld], str(prop)):
                    neg_hit = True
                i += 1
            # title
            if (not neg_hit) and cfg.instanceTitle and cfg.instanceTitle[0] in instance:
                if contains_word(instance[cfg.instanceTitle[0]], str(prop)):
                    neg_hit = True

            if neg_hit:
                matches.clear()
                break

        # soglia 30%
        if len(prop_list) > 0 and int(len(matches)) >= int(len(prop_list) * 30 / 100):
            title_field = instance.get(cfg.instanceTitle[0], "")
            lista_istanze.append([
                f"{inst_id} - {as_text(title_field)}",
                "\n\t\\-> matches: " + str(matches)
            ])
        elif inst_id in graduatoria and len(matches) == 0:
            graduatoria[inst_id] = 0

    # --------- stampa graduatoria ---------
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

    if printed == 0:
        print("No recommendable contents for this category.")
    else:
        perc = (100 * printed) / max(1, tot_items)
        print(f"Classified {printed} of {tot_items} contents ({perc}%)")
        with open("resume.tsv", "a", encoding="utf-8") as f:
            f.write(category.replace("\t", " ") + "\t" + str(printed) + "\n")

# --------- main ---------
if __name__ == '__main__':
    if len(sys.argv) == 2:
        # nome prototipo da classificare
        prototipo = sys.argv[1]
        category = prototipo.split("/")[-1]

        # lettura prototipo (COCOS)
        f = ReadAttributes(prototipo)

        print("\nRecommendation for category: " + category + "\n\nCategory prototype: \n")

        # flags tipiche attive dal file COCOS
        r = [str(s) for s in f.result.split(',')]

        prop_list = []
        not_prop_list = []

        for p in f.attrs:
            if str(p).find('-') == -1:
                prop_list.append(p)
            else:
                not_prop_list.append(p[0].replace("-", "").strip())

        i = 0
        for p in f.tipical_attrs:
            if r[i].strip() == "'1'":
                prop_list.append(p)
            i += 1

        pprint(prop_list)
        pprint(not_prop_list)

        elaboraGraduatoria(prop_list, not_prop_list)

    elif len(sys.argv) > 2:  # parole libere da riga di comando
        prop_list = []
        for i in range(1, len(sys.argv)):
            prop_list.append(tuple([sys.argv[i], '1']))
        pprint(prop_list)
        elaboraGraduatoria(prop_list)

    else:
        print("Specify a prototype for the classification!")
