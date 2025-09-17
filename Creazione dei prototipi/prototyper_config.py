# Config file for DEGARI's prototyper module
# Here are specified the features of a dataset in order to generate its artworks prototypes


# configuration for WikiArt dataset

# name of json description file for input
jsonDescrFile = "descr_music.json"

# instance's artwork identifier attribute in json description file
instanceID = "ID"

# list of instance description attributes in json description file
instanceDescr = [
    "title","artist","album","year",
    "lyrics","tags","moods","instruments","subgenres","contexts"
]

# output folder path
outPath = "music_for_cocos/"


