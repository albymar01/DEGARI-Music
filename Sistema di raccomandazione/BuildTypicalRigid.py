import argparse, json, re, math
from collections import defaultdict, Counter
from pathlib import Path

# MACRO_GENRES:
#   L’insieme dei macro-generi che il sistema riconosce
#   Indicizzare i brani per genere
#   Produrce un file typical/rigid per ciascun genere
MACRO_GENRES = ["rap","metal","rock","pop","trap","reggae","rnb","country"]

# SUB2MACRO:
#   Mappa da etichette (subgenere/tag) a macro-genere.
#   Usata in choose_macrogenres() per ricondurre i brani ai macro-generi.
SUB2MACRO = {
    "hip_hop":"rap","hiphop":"rap","boom_bap":"rap","boom-bap":"rap","rap":"rap","drill":"rap",
    "trap":"trap",
    "rnb":"rnb","r&b":"rnb","contemporary_rnb":"rnb","alternative_rnb":"rnb",
    "reggae":"reggae","dancehall":"reggae",
    "metal":"metal","heavy_metal":"metal","nu_metal":"metal",
    "rock":"rock","alt_rock":"rock","alternative_rock":"rock","punk_rock":"rock",
    "pop":"pop","synthpop":"pop","dance_pop":"pop","electropop":"pop",
    "country":"country","classic_country":"country","alt_country":"country"
}

# COMMON_GLOBAL:
#   Proprietà molto “globali” (ricorrenti in tanti generi).
#   Sono penalizzate in fase di scoring typical con COMMON_PENALTY.
#   ↑ Aggiungere proprietà qui le rende meno influenti come typical.
COMMON_GLOBAL = {"high_repetition","catchy_chorus","hook_repetition"}

# COMMON_PENALTY:
#   Fattore moltiplicativo (<1) applicato ai COMMON_GLOBAL.
#   Aumentarlo (es. 0.40 -> 0.60) riduce la penalizzazione → i globaloni pesano di più.
#   Diminuirlo (es. 0.40 -> 0.25) li penalizza di più → pesano meno nei typical.
COMMON_PENALTY = 0.40

# DISTINCTIVE_MAX_GENRES:
#   Una proprietà ottiene un “boost distintivo” se compare in ≤ questo numero
#   di macro-generi (cioè è relativamente “di nicchia”).
#   Aumentarlo (2 -> 3) rende più facile prendere il boost → più proprietà avranno boost.
#   Diminuirlo rende il boost più raro (solo le proprietà davvero “di genere” lo prendono).
DISTINCTIVE_MAX_GENRES = 2

# DISTINCTIVE_BOOST:
#   Fattore (>1) di aumento del punteggio per proprietà distintive.
#   Aumentarlo (1.20 -> 1.50) enfatizza maggiormente la specificità di genere.
#   Diminuirlo riduce l’enfasi sulla specificità (più equilibrio con la prevalenza).
DISTINCTIVE_BOOST = 1.20

# ALPHA:
#   Peso (0..1) che equilibra prevalenza nel genere e “specificità cross-genere” (tipo IDF).
#   Score ≈ ALPHA * prevalenza + (1-ALPHA) * (prevalenza / idf)
#   ALPHA → dai più peso alla prevalenza interna al genere (tendenza a scegliere i
#   tratti più frequenti in quel genere).
#   ALPHA → dai più peso alla specificità rispetto agli altri generi (tratti più distintivi).
ALPHA = 0.45

# MIN_W, MAX_W:
#   Range finale dei pesi “typical” dopo normalizzazione (rescaling min-max).
#   Allargare il range (es. 0.50..0.98) aumenta “dinamica” dei pesi.
#   Restringere il range (es. 0.70..0.90) rende i pesi più uniformi tra loro.
MIN_W, MAX_W = 0.60, 0.95

# TOKEN_RE:
#   Regex per estrarre token alfabetici/apostrofi di almeno 3 caratteri.
#   Cambiarla influenza quali parole entrano nel vocabolario.
TOKEN_RE = re.compile(r"[a-zA-Z']{3,}")

# STOP_EN:
#   Stoplist inglese: parole funzionali/comuni che vogliamo ignorare.
#   NOTA: se una parola è anche nel DOMAIN_WHITELIST, NON viene trattata come stopword
#   (vedi is_stop_en())
STOP_EN = {
  "the","all","a","an","and","or","but","for","to","of","in","on","at","by","with","from","as",
  "is","are","was","were","be","been","am","do","does","did","doing",
  "that","this","these","those","there","here","then","than","so",
  "i","you","he","she","we","they","it","me","him","her","us","them","my","your","his","her","our","their",
  "what","which","who","whom","whose","where","when","why","how",
  "not","no","yes","yeah","yah","yo","uh","oh","nah","hmm",
  "im","i'm","ive","i've","ill","i'll","id","i'd",
  "youre","you're","youve","you've","youll","you'll","youd","you'd",
  "hes","he's","shes","she's","were","we're","weve","we've","well","we'll","wed","we'd",
  "theyre","they're","theyve","they've","theyll","they'll","theyd","they'd",
  "its","it's","dont","don't","doesnt","doesn't","didnt","didn't","cant","can't","couldnt","couldn't",
  "shouldnt","shouldn't","wouldnt","wouldn't","aint","ain't","isnt","isn't","wasnt","wasn't","werent","weren't",
  "havent","haven't","hasnt","hasn't","hadnt","hadn't","wont","won't","gonna","wanna","gotta","lemme","kinda","sorta","tryna","'cause","cause",
  "ya","ok","okay","alright","like","just","really","right","way","thing","things","stuff",
  "get","got","make","makes","made","take","takes","took","put","puts","keep","keeps","kept",
  "back","out","up","down","over","under","again","still","now","then","ever","never","always","sometimes",
  "one","two","three","time","times","day","night"
}

# DOMAIN_WHITELIST:
#   Lessico “di dominio” che vogliamo includere SEMPRE anche se sembrerebbe generico,
#   e/o consentire come possibili RIGID dalle lyrics (oltre ai tag).
#   ↑ Aggiungere parole qui permette, se frequenti, di farle entrare come typical/rigid
DOMAIN_WHITELIST = {
  "hook_repetition","catchy_chorus","high_repetition","flow","wordplay","storytelling","battle",
  "trap","drill","boom_bap","hip_hop","hiphop","rnb","reggae","metal","rock","pop","country",
  "skrrt","flex","ice","bando","lean","molly","perc","xan","opps","gang","plug","rollie","guap","racks","bands",
  "glizzy","draco","blick","blicky","wraith","bentley","lambo","woah","lit","savage","shawty","woke","sauce","drip",
  "patek","cartier","vvs","chain","chains","whip","808","808s","distorted_guitar","riff","bassline","piano_loop"
}

# Normalizza token:
# - lower
# - uniforma apostrofi tipografici
# - rimuove underscore/trattini/whitespace dagli estremi
def norm_token(t:str)->str:
    return t.lower().replace("’","'").replace("‘","'").strip("_- ")

# True se t è una stopword inglese (ma NON se è nel DOMAIN_WHITELIST)
#   → in questo modo, termini di dominio come "hiphop" o "808" non vengono filtrati.
def is_stop_en(t:str)->bool:
    return (t in STOP_EN) and (t not in DOMAIN_WHITELIST)

# Estrae le parole “utili” da un testo:
#   - tokeniz. con TOKEN_RE
#   - normalizza
#   - filtra stopword e token < 3 caratteri
# ↑ Se aumenta la qualità di lyrics (meno rumore), si può ridurre il filtro;
# ↓ Se lyrics sono rumorose, conviene tenerlo com’è o inasprire la stoplist.
def extract_words(text:str):
    if not text: return []
    toks = [norm_token(m.group()) for m in TOKEN_RE.finditer(text)]
    return [t for t in toks if len(t)>=3 and not is_stop_en(t)]

# Determina i macro-generi per un brano “entry”:
#   - guarda subgenres e tags (mappati via SUB2MACRO),
#   - fa un check anche su title/album/artist per eventuali occorrenze di chiavi mappate.
# Ritorna solo quelli presenti in MACRO_GENRES.
# ↑ Ampliare SUB2MACRO aumenta la probabilità di mappare correttamente.
def choose_macrogenres(entry):
    out=set()
    for s in entry.get("subgenres",[]) or []:
        s2=norm_token(s);  out.add(SUB2MACRO.get(s2,s2))
    for tg in entry.get("tags",[]) or []:
        s2=norm_token(tg); out.add(SUB2MACRO.get(s2,s2))
    blob=(" ".join(str(entry.get(k,"")) for k in ["title","album","artist"])).lower()
    for k,v in SUB2MACRO.items():
        if k in blob: out.add(v)
    return [g for g in out if g in MACRO_GENRES]

# Clippa un valore nel range [MIN_W, MAX_W] (usato dopo la normalizzazione dei typical).
def clamp(x,lo=MIN_W,hi=MAX_W): return max(lo,min(hi,x))

# ================================
# MAIN: COSTRUZIONE TYPICAL/RIGID
# ================================
def main():
    base = Path(__file__).resolve().parent
    default_in = base.parent / "Creazione dei prototipi" / "descr_music_GENIUS.json"

    ap = argparse.ArgumentParser()

    # DEFAULT “LIGHT” 
    #   Impostazioni più permissive: più proprietà entrano nei typical/rigid.
    #   Utile per massimizzare copertura scenari ma più rumore.
    #ap.add_argument("--input","-i", default=str(default_in))
    #ap.add_argument("--out","-o",   default=str(base))
    #ap.add_argument("--typical_thr_tags",  type=float, default=0.60)
    #ap.add_argument("--rigid_thr_tags",    type=float, default=0.95)
    #ap.add_argument("--typical_thr_words", type=float, default=0.60)
    #ap.add_argument("--rigid_thr_words",   type=float, default=0.95)
    #ap.add_argument("--min_df_words", type=int, default=3)
    #ap.add_argument("--topk_typical", type=int, default=12)
    #ap.add_argument("--max_rigid",    type=int, default=5)
    #args = ap.parse_args()

    # DEFAULT “STRICT”
    #   Impostazioni più severe: selezione più pulita e stabile, ma minore copertura.
    ap.add_argument("--input","-i", default=str(default_in))
    ap.add_argument("--out","-o",   default=str(base))
    # Soglie per entrare nei "typical":
    #   - typical_thr_tags: frazione minima (0..1) di tracce del genere che devono avere un TAG
    #   - typical_thr_words: idem per PAROLE (da lyrics)
    # ↑ Alzare (es. 0.85 -> 0.90): meno typical (più selettivi).
    # ↓ Abbassare (es. 0.85 -> 0.75): più typical (più permissivi).
    ap.add_argument("--typical_thr_tags",  type=float, default=0.85)
    ap.add_argument("--rigid_thr_tags",    type=float, default=0.98)  # soglia ancora più alta per entrare nei RIGID
    ap.add_argument("--typical_thr_words", type=float, default=0.85)
    ap.add_argument("--rigid_thr_words",   type=float, default=0.98)  # idem per parole (solo se in DOMAIN_WHITELIST)
    # min_df_words:
    #   Frequenza minima assoluta (conteggio documenti nel genere) per considerare una parola.
    # ↑ Alzare (10 -> 15): elimina parole rare → vocab più pulito (rischi di perdere segnali utili).
    # ↓ Abbassare (10 -> 5): include più parole → più copertura (più rumore).
    ap.add_argument("--min_df_words", type=int, default=10)
    # topk_typical / max_rigid:
    #   Limiti sul numero di proprietà che teniamo.
    # ↑ Aumentare topk_typical: più materiale nei typical (aiuta CoCoS ma può aggiungere rumore).
    # ↑ Aumentare max_rigid: più ancore (mixing più facile, ma rischia over-constrain).
    ap.add_argument("--topk_typical", type=int, default=5)
    ap.add_argument("--max_rigid",    type=int, default=3)
    args = ap.parse_args()

    # Cartelle di output (create se non esistono)
    out_dir = Path(args.out)
    typ_dir = out_dir/"typical"; typ_dir.mkdir(parents=True, exist_ok=True)
    rig_dir = out_dir/"rigid";   rig_dir.mkdir(parents=True, exist_ok=True)

    # Caricamento dati:
    #   Accetta sia una lista di tracce che un oggetto {"tracks": [...]}
    data = json.load(open(args.input,"r",encoding="utf-8"))
    if isinstance(data, dict) and "tracks" in data: data = data["tracks"]

    # Partiziona le tracce per macro-genere (ogni brano può contribuire a più generi)
    songs_by_genre = defaultdict(list)
    for e in data:
        for g in choose_macrogenres(e):
            songs_by_genre[g].append(e)

    # Contatori: per ogni genere calcoliamo DF (document frequency) di tag e parole
    tag_df_by_g = {g: Counter() for g in MACRO_GENRES}
    word_df_by_g= {g: Counter() for g in MACRO_GENRES}
    n_docs_g    = {g: len(songs_by_genre[g]) for g in MACRO_GENRES}

    # Costruzione DF per genere:
    #   - TAG: set per brano (niente duplicati intra-brano)
    #   - WORD: set delle parole estratte dalle lyrics
    for g,songs in songs_by_genre.items():
        for e in songs:
            tags  = set(norm_token(t) for t in (e.get("tags") or []))
            words = set(extract_words(e.get("lyrics","")))
            tag_df_by_g[g].update(tags)
            word_df_by_g[g].update(words)

    # Conteggio “cross-genere”:
    #   Quanti generi contengono una certa proprietà (serve per specificità/IDF-like)
    global_genre_count = Counter()
    for g in MACRO_GENRES:
        props = set(tag_df_by_g[g]) | set(word_df_by_g[g])
        for p in props: global_genre_count[p] += 1

    # “IDF” semplificato su generi:
    #   Più un tratto appare in molti generi, più cresce gcount → più cresce il denominatore
    #   nella parte di specificità → riduce l’impatto della proprietà (meno distintiva).
    def idf_prop(p:str)->float:
        gcount = global_genre_count.get(p,0)
        return math.log(1 + (1 + gcount))

    # LOOP sui generi per produrre i file typical/rigid
    for g in MACRO_GENRES:
        # Nessun brano per questo genere → file vuoti
        if n_docs_g[g] == 0:
            (typ_dir/f"{g}.txt").write_text("", encoding="utf-8")
            (rig_dir/f"{g}.txt").write_text("", encoding="utf-8")
            continue

        # Frazione (0..1) di brani del genere che contengono ciascun tag/parola
        frac_tag  = {t: tag_df_by_g[g][t]/n_docs_g[g] for t in tag_df_by_g[g]}
        frac_word = {w: word_df_by_g[g][w]/n_docs_g[g]
                     for w in word_df_by_g[g] if word_df_by_g[g][w] >= args.min_df_words}

        # Selezione “raw” dei typical: sopra soglia
        #   NB: per le parole, scartiamo i “globaloni” se NON sono nel DOMAIN_WHITELIST.
        typical_tags_raw  = {t:v for t,v in frac_tag.items()  if v >= args.typical_thr_tags}
        typical_words_raw = {w:v for w,v in frac_word.items()
                             if v >= args.typical_thr_words and not (w in COMMON_GLOBAL and w not in DOMAIN_WHITELIST)}

        # Scoring delle proprietà typical:
        #   combinazione di prevalenza (v) e specificità (v / idf_prop)
        #   con peso ALPHA; per le parole applichiamo anche un 0.8 per prudenza.
        scores = Counter()
        for t,v in typical_tags_raw.items():
            w = ALPHA*v + (1-ALPHA)*(v / idf_prop(t))
            scores[t] += w
        for w_,v in typical_words_raw.items():
            w = (ALPHA*v + (1-ALPHA)*(v / idf_prop(w_))) * 0.8
            scores[w_] += w

        # Penalità/Boost:
        #   - penalizza i globaloni (COMMON_PENALTY)
        #   - boosta le proprietà distintive (DISTINCTIVE_BOOST)
        for p in list(scores.keys()):
            s = scores[p]
            if p in COMMON_GLOBAL: s *= COMMON_PENALTY
            if global_genre_count.get(p,99) <= DISTINCTIVE_MAX_GENRES: s *= DISTINCTIVE_BOOST
            scores[p] = s

        # Prendi le top-k proprietà con score più alto
        top_items = dict(scores.most_common(args.topk_typical))

        # Normalizzazione nel range [MIN_W, MAX_W] → pesi finali “typical”
        if top_items:
            mn, mx = min(top_items.values()), max(top_items.values())
            for p,v in list(top_items.items()):
                if mx == mn: w = 0.80              # caso degenerato: tutti uguali
                else:        w = MIN_W + (v - mn) / (mx - mn) * (MAX_W - MIN_W)
                top_items[p] = clamp(round(w,3))

        # Scelta RIGID (ancore):
        #   - tag sopra rigid_thr_tags
        #   - parole sopra rigid_thr_words MA solo se in DOMAIN_WHITELIST
        #   - limita a max_rigid (ordine di apparizione)
        rigid = []
        rigid += [t for t,v in frac_tag.items()  if v >= args.rigid_thr_tags]
        rigid += [w for w,v in frac_word.items() if v >= args.rigid_thr_words and w in DOMAIN_WHITELIST]
        rigid = list(dict.fromkeys(rigid))[:args.max_rigid]

        # Scrittura file di output:
        #   typical/<genere>.txt  → "prop: peso"
        #   rigid/<genere>.txt    → "prop" (una per riga)
        with open(typ_dir/f"{g}.txt","w",encoding="utf-8") as f:
            for k,v in sorted(top_items.items(), key=lambda kv:(-kv[1],kv[0])):
                f.write(f"{k}: {v}\n")
        with open(rig_dir/f"{g}.txt","w",encoding="utf-8") as f:
            for k in rigid: f.write(f"{k}\n")

    print("Done. Generated typical/ and rigid/ from", Path(args.input).name)

if __name__ == "__main__":
    main()
