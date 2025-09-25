# Config file for DEGARI-MUSIC (Recommender module)
# Set of fields used to classify music tracks using prototypes generated in Module 1.

# --- Input dataset ---
# JSON with the track descriptions written in English
jsonDescrFile = r"C:\Users\Utente\Desktop\DEGARI-Music\Creazione dei prototipi\descr_music_GENIUS.json"

# Unique identifier of each track (must match the JSON field name)
instanceID = "ID"

# Fields to show as the title/summary in the output
instanceTitle = ["title", "artist"]

# Fields used to compute textual compatibility (bag of terms)
instanceDescr = [
    "lyrics", "tags", "moods", "instruments", "subgenres", "contexts",
    "artist", "album", "year"
]

# --- Prototypes folder (output of Module 1) ---
# Cartella con i prototipi “singoli” usati dal classificatore
protPath = r"C:\Users\Utente\Desktop\DEGARI-Music\Creazione dei prototipi\music_for_cocos"
