import math
import os
import json
import argparse
from typing import Dict, List, Any

import lib.read_attributes as ra
import lib.scenarios_table as st
import lib.scenarios_blocks as sb
import cocos_config as cfg


def scenario_to_properties(scenario: List[Any], typical_props: List[List[Any]]) -> Dict[str, Any]:
    """
    Converte lo scenario (bit + score finale) in un dict:
    - chiavi = proprietà selezionate
    - valori = pesi (dalle typical)
    - @scenario_probability / @scenario_score = score finale dello scenario
    """
    props = {}
    for i in range(len(typical_props)):
        if scenario[i] == 1:
            props[typical_props[i][0]] = typical_props[i][1]

    score = scenario[-1]
    # compat: mantieni il vecchio nome + aggiungi alias più chiaro
    props['@scenario_probability'] = score
    props['@scenario_score'] = score
    return props


def sort_props_for_printing(p: Dict[str, Any]) -> List[tuple]:
    """
    Ritorna items (chiave, valore) ordinati:
    - prima le proprietà (no campi @scenario_*), per valore desc poi nome asc
    - poi i campi @scenario_* (in coda)
    """
    core = [(k, v) for k, v in p.items() if not k.startswith('@scenario_')]
    meta = [(k, v) for k, v in p.items() if k.startswith('@scenario_')]

    core.sort(key=lambda kv: (-kv[1], kv[0]))
    meta.sort(key=lambda kv: kv[0])
    return core + meta


def clean_previous_results(filename: str) -> None:
    """Rimuove eventuali righe 'Result:'/'Scenario:' già presenti (per non accodare infinite volte)."""
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    filtered = [ln for ln in lines if not (ln.startswith('Result:') or ln.startswith('Scenario:'))]
    if filtered != lines:
        with open(filename, 'w', encoding='utf-8') as f:
            f.writelines(filtered)


def write_result(filename: str, best_props: Dict[str, Any], best_raw: List[Any]) -> None:
    """Scrive Result/Scenario in coda al file di input (dopo aver pulito eventuali vecchi risultati)."""
    clean_previous_results(filename)
    with open(filename, "a", encoding="utf-8") as f:
        f.write("\nResult: " + json.dumps(best_props, ensure_ascii=False))
        f.write("\nScenario: " + json.dumps(best_raw, ensure_ascii=False))


def dump_json(out_dir: str, head: str, mod: str, scenarios: List[Dict[str, Any]]) -> None:
    """Salva anche un JSON pulito (uno per coppia), con la lista degli scenari consigliati."""
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{head}_{mod}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"head": head, "modifier": mod, "recommended_scenarios": scenarios}, f, ensure_ascii=False, indent=2)


def run_cocos_on_file(filename: str, max_attrs: int, json_out_dir: str = None) -> None:
    # 1) leggi input
    input_data = ra.ReadAttributes(filename)

    # 2) costruisci tabella scenari non banali (con vincoli)
    tab = st.Table(input_data, max_attrs)

    head = input_data.head_conc
    mod = input_data.mod_conc
    print(f"\n\nHead Concept: {head}, Modifier Concept: {mod}")

    # 3) prendi i best block (possono essere più d'uno in caso di tie)
    best = sb.best_block(tab)
    if not best:
        print("\nNO recommended scenarios!")
        return

    # 4) prepara scenari ordinati per stampa/esportazione
    scenarios_for_print = []
    for scenario in best:
        props = scenario_to_properties(scenario, input_data.typical_attrs)
        # ordina per leggibilità
        ordered = dict(sort_props_for_printing(props))
        scenarios_for_print.append(ordered)

    print("\nRecommended scenario(s):")
    for sc in scenarios_for_print:
        print(f"  - {sc}")

    # 5) scrivi su file input (solo il primo scenario per compatibilità con il flusso attuale)
    write_result(filename, scenarios_for_print[0], best[0])

    # 6) export opzionale di tutti i best in un json separato
    if json_out_dir:
        dump_json(json_out_dir, head, mod, scenarios_for_print)


def main():
    parser = argparse.ArgumentParser(description="Run CoCoS on one file or on all files in cfg.COCOS_DIR.")
    parser.add_argument("filename", nargs="?", help="Percorso del file H_M.txt. Se omesso, esegue su tutta la cartella COCOS_DIR.")
    parser.add_argument("max_attrs", nargs="?", type=int, help="Max numero di typical da selezionare (default: cfg.MAX_ATTRS).")
    parser.add_argument("-o", "--json-out-dir", help="(Opzionale) Cartella dove salvare anche un JSON pulito per ciascuna coppia.")
    args = parser.parse_args()

    max_attrs = args.max_attrs if args.max_attrs is not None else cfg.MAX_ATTRS

    if args.filename:
        run_cocos_on_file(args.filename, max_attrs, args.json_out_dir)
    else:
        # run su tutti i file nella cartella configurata
        for file in sorted(os.listdir(cfg.COCOS_DIR)):
            if file.lower().endswith(".txt"):
                run_cocos_on_file(os.path.join(cfg.COCOS_DIR, file), max_attrs, args.json_out_dir)


if __name__ == "__main__":
    main()
