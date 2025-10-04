# Configuration file for the Conceptual Combination module

from pathlib import Path

# Base = cartella "Sistema di raccomandazione"
BASE = Path(__file__).resolve().parent

# path to the prototyped corpus file (se serve)
CORPUS_FILE = str(BASE / "prototyped.tsv")

# path to the directory containing the description of typical properties
TYPICAL_PROP_DIR = str(BASE / "typical")
# path to the directory containing the description of rigid properties
RIGID_PROP_DIR = str(BASE / "rigid")

# path to the directory where the combinations are saved (cartella dei *.txt)
COCOS_DIR = r"C:\Users\Utente\Desktop\DEGARI-Music\prototipi_music"

# max number of typical properties in the combined concept
# max 14
MAX_ATTRS = 2
