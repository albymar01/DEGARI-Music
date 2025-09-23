param(
  [Parameter(Mandatory=$true)] [string] $InputDir,     # cartella prototipi .txt
  [Parameter(Mandatory=$true)] [string] $TypicalDir,   # cartella profili typical
  [Parameter(Mandatory=$true)] [string] $RigidDir,     # cartella profili rigid
  [Parameter(Mandatory=$true)] [string] $GeniusJson,   # path a descr_music_GENIUS.json
  [Parameter(Mandatory=$true)] [string] $OutDir,       # cartella output
  [string] $PythonExe = "python",                      # opzionale: python da usare
  [switch] $FetchMissingLyrics                         # opzionale: prova a prendere testi mancanti via API
)

# NOTE: Se vuoi usare il recupero da Genius, assicurati di avere:
#   $env:GENIUS_TOKEN impostato (e le librerie lyricsgenius, slugify, unidecode installate)

Write-Host "Pulizia output: $OutDir"
if (Test-Path $OutDir) { Remove-Item -Recurse -Force -Path $OutDir }
New-Item -ItemType Directory -Path $OutDir | Out-Null

# Costruisci args
$commonArgs = @(
  "crawler_lyrics.py",
  "--input", $InputDir,
  "--typical", $TypicalDir,
  "--rigid", $RigidDir,
  "--genius", $GeniusJson,
  "--out", $OutDir,
  "--out-mode", "per-song",
  "--n_per_song", "1",
  "--clean"
)

if ($FetchMissingLyrics) {
  $commonArgs += "--fetch-missing-lyrics"
}

# Esegui
& $PythonExe @commonArgs
if ($LASTEXITCODE -ne 0) {
  Write-Error "Errore durante l'esecuzione di crawler_lyrics.py (exit $LASTEXITCODE)"
  exit $LASTEXITCODE
}

Write-Host "OK! Output creato in $OutDir"
