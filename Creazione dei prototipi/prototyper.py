# DEGARI-Music2.0 - Prototype Generator
# Reads the description of music tracks from JSON and writes one prototype file per track.

from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import string
import treetaggerwrapper
import json
import os
import prototyper_config as cfg

#####################################################
# FUNCTIONS
#####################################################

def getLemma(word):
    tags = treetaggerwrapper.make_tags(tagger.tag_text(word))
    return tags[0].lemma.split(":")[0]

def getTypeOfWord(word):
    tags = treetaggerwrapper.make_tags(tagger.tag_text(word))
    return tags[0].pos.split(":")[0]

# POS recognition for English
def isNumber(word):
    return getTypeOfWord(word) in ("CD","NUM")

def isVerb(word):
    return getTypeOfWord(word).startswith("VB")   # VB, VBD, VBG, ...

def isAdjective(word):
    return getTypeOfWord(word).startswith("JJ")   # JJ, JJR, JJS

def isAdverb(word):
    return getTypeOfWord(word).startswith("RB")   # RB, RBR, RBS

def to_text(value):
    """Flatten list fields to plain text and stringify everything else."""
    if isinstance(value, list):
        return " ".join(map(str, value))
    return str(value)

def insertArtworkInDict(instance):
    arttwork = instance[cfg.instanceID]

    # sanitize filename
    for char in chars_not_allowed_in_filename:
        arttwork = arttwork.replace(char, "")

    # build description from selected fields
    description = " " + " ".join(to_text(instance[d]) for d in cfg.instanceDescr if d in instance)

    word_tokens = word_tokenize(description)
    verbo = None

    for word in word_tokens:
        word = word.lower()

        if (len(word) > 1) and (word not in remove_words) and (not isNumber(word)) and (not isAdverb(word)):

            if isVerb(word):
                verbo = getLemma(word)
            else:
                word = getLemma(word)

                if arttwork not in dict_prototypes:
                    dict_prototypes[arttwork] = {}

                if word not in dict_prototypes[arttwork]:
                    dict_prototypes[arttwork][word] = 0

                dict_prototypes[arttwork][word] += 1
                if verbo is not None:
                    if verbo not in dict_prototypes[arttwork]:
                        dict_prototypes[arttwork][verbo] = 0
                    dict_prototypes[arttwork][verbo] += 1
                    verbo = None

def writeWordInFile(file, word, value):
    spaces = 20 - len(word) + 1
    stri = word + ":" + " " * spaces + str(value)
    file.write(stri + "\n")

#####################################################
# GLOBAL VARS
#####################################################
language = "en"
TAGDIR = r"C:\Users\sinog\Desktop\TreeTagger"

tagger = treetaggerwrapper.TreeTagger(
    TAGLANG=language,
    TAGDIR=TAGDIR,
    TAGPARFILE=rf"{TAGDIR}\lib\english-bnc.par"
)

prepositions = ["of","to","from","in","on","at","by","for",
                "with","about","against","between","into",
                "through","during","before","after","above",
                "below","up","down","out","off","over","under"]
articles = ["the","a","an"]
congiuntions = ["and","or","but","so","yet","for","nor","because",
                "although","though","while","if","when","where","that",
                "which","who","whom","whose","until","unless","since","as",
                "than","whether","either","neither","both","also","only"]
punctuation = list(string.punctuation) + ["...", "``"]

# ensure NLTK resources
try:
    stop_words = stopwords.words('english')
except LookupError:
    import nltk
    nltk.download('stopwords')
    stop_words = stopwords.words('english')

remove_words = prepositions + articles + congiuntions + punctuation + stop_words
chars_not_allowed_in_filename = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']

filename = cfg.jsonDescrFile
dict_prototypes = {}
path = cfg.outPath
encoding = "utf-8"
MIN_SCORE = 0.6
MAX_SCORE = 0.9

#####################################################
# MAIN
#####################################################
if __name__ == "__main__":
    with open(filename, "r", encoding=encoding) as file:
        data = json.load(file)

    # accept both a single object or a list of objects
    if isinstance(data, dict):
        instances = [data]
    elif isinstance(data, list):
        instances = data
    else:
        raise TypeError("Input JSON must be an object or a list of objects.")

    if not os.path.exists(path):
        os.makedirs(path)

    for instance in instances:
        insertArtworkInDict(instance)

    for arttwork in dict_prototypes:
        totWords = sum(dict_prototypes[arttwork].values())

        minFreq = 1
        maxFreq = 0
        for word in dict_prototypes[arttwork]:
            freq = dict_prototypes[arttwork][word] / totWords
            minFreq = min(minFreq, freq)
            maxFreq = max(maxFreq, freq)

        rangeFreq = maxFreq - minFreq
        rangeScore = MAX_SCORE - MIN_SCORE

        out_filename = path + arttwork.replace("'", "_") + ".txt"
        with open(out_filename, "w", encoding=encoding) as f:
            for word, count in sorted(dict_prototypes[arttwork].items(), key=lambda kv: kv[1], reverse=True):
                freq = count / totWords
                score = MAX_SCORE if rangeFreq == 0 else MIN_SCORE + (rangeScore * (freq - minFreq) / rangeFreq)
                writeWordInFile(f, word, score)

    print("File generated in " + os.getcwd() + "\\" + path)
