# Run Pipeline for DEGARI-Music2.0
# This PowerShell script performs the full ETL / prototype / recommender pipeline
# Place this script in the project root (e.g. C:\Users\Utente\Desktop\DEGARI-Music2.0) and run it.

Param(
    [switch]$SaveOutput,
    [string]$LogDir = "$env:USERPROFILE\Desktop\DEGARI-Music2.0\Creazione dei prototipi\data",
    [switch]$SkipHeavy
)

function Write-Status { param($m) Write-Host "[PIPELINE] $m" }

# If user asked to save output, start a transcript
if ($SaveOutput) {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $LogPath = Join-Path $LogDir "pipeline_$timestamp.log"
    Start-Transcript -Path $LogPath -Force | Out-Null
    Write-Status "Transcript started -> $LogPath"
}

try {
    # Determine script root (assumes script placed in project root)
    $ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    if (-not $ScriptRoot) { $ScriptRoot = Get-Location }
    $ROOT = $ScriptRoot
    Write-Status "Project root: $ROOT"

    # 0) Ensure execution policy and venv
    Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force | Out-Null
    if (-not (Test-Path (Join-Path $ROOT ".venv"))) {
        Write-Status "Creating virtualenv (py -3.12 -m venv .venv)"
        py -3.12 -m venv (Join-Path $ROOT ".venv")
    }

    # Activate the venv for the current script/session
    & (Join-Path $ROOT ".venv\Scripts\Activate.ps1")
    Write-Status "Virtualenv activated"

    # 1) Install / verify required Python packages
    Write-Status "Installing packages..."
    python -m pip install -U pip
    python -m pip install nltk owlready2 rdflib treetaggerwrapper six lyricsgenius python-slugify unidecode requests beautifulsoup4

    # 2) Download NLTK tokenizer resources using a temporary Python script (PowerShell-friendly)
    Write-Status "Downloading NLTK data (punkt, punkt_tab)"
    $code = @'
import nltk, contextlib
for pkg in ("punkt","punkt_tab"):
    with contextlib.suppress(Exception):
        nltk.download(pkg, quiet=True)
print("NLTK data OK")
'@
    $tmp = Join-Path $env:TEMP "nltk_dl.py"
    Set-Content -Path $tmp -Value $code -Encoding UTF8
    python $tmp
    Remove-Item $tmp -Force

    # 3) TreeTagger: set environment variable (user + current session)
    $TTH = "C:\Users\Utente\Desktop\TreeTagger"
    Write-Status "Setting TREETAGGER_HOME -> $TTH"
    [System.Environment]::SetEnvironmentVariable('TREETAGGER_HOME', $TTH, 'User')
    $env:TREETAGGER_HOME = $TTH

    # 4) Quick TreeTagger python import/test (monkeypatch SafeConfigParser if needed)
    Write-Status "Testing TreeTagger import from Python"
    $ttcode = @'
import configparser
# compatibility shim: some older packages expect SafeConfigParser
if not hasattr(configparser, 'SafeConfigParser'):
    configparser.SafeConfigParser = configparser.RawConfigParser
import treetaggerwrapper
import os
print("TTHOME =", os.environ.get("TREETAGGER_HOME"))
# attempt to instantiate a tagger (language 'en' or 'it' available via param files)
try:
    tt = treetaggerwrapper.TreeTagger(TAGLANG="en")
    tags = treetaggerwrapper.make_tags(tt.tag_text("This is a small test."))
    print("TreeTagger OK. First 3 tags:", tags[:3])
except Exception as e:
    print("TreeTagger test failed:", e)
'@
    $tttmp = Join-Path $env:TEMP "tt_test.py"
    Set-Content -Path $tttmp -Value $ttcode -Encoding UTF8
    python $tttmp
    Remove-Item $tttmp -Force

    # 5) DEGARI pipeline modules
    if (-not $SkipHeavy) {
        Write-Status "Running Module 1: CRAWLER -> Tools/crawler_lyrics.py"
        Push-Location (Join-Path $ROOT "Tools")
        python crawler_lyrics.py
        python lyrics_features.py
        Pop-Location

        Write-Status "Running Module 2: PROTOTYPER -> Creazione dei prototipi/prototyper.py"
        Push-Location (Join-Path $ROOT "Creazione dei prototipi")
        python prototyper.py
        Pop-Location

        Write-Status "Running Module 3: PREPROCESSING -> Sistema di raccomandazione/cocos_preprocessing.py (all pairs)"
        Push-Location (Join-Path $ROOT "Sistema di raccomandazione")
        $genres = @("rap","metal","rock","pop","trap","reggae","rnb","country")
        foreach ($h in $genres) {
            foreach ($m in $genres) {
                if ($h -ne $m) { python cocos_preprocessing.py $h $m }
            }
        }
        Pop-Location

        Write-Status "Running Module 4: COCOS on generated prototypes (may be long)"
        Push-Location (Join-Path $ROOT "Sistema di raccomandazione")
        $protoDir = Join-Path (Get-Location) "prototipi_music"
        Get-ChildItem $protoDir -Filter *.txt | ForEach-Object {
            $p = Join-Path $protoDir $_.Name
            python cocos.py $p 14
        }
        Pop-Location

        Write-Status "Running Module 5: RECOMMENDER on valid prototypes"
        Push-Location (Join-Path $ROOT "Sistema di raccomandazione\Classificatore")
        $protoDir = Join-Path $ROOT "Sistema di raccomandazione\prototipi_music"
        Get-ChildItem $protoDir -Filter *.txt |
          Where-Object { Select-String -Path $_.FullName -Pattern '^(\s*)result\s*:' -Quiet } |
          ForEach-Object {
            python Recommender.py (Join-Path $protoDir $_.Name)
          }
        Pop-Location
    }
    else {
        Write-Status "SkipHeavy flag set: heavy modules (prototyper / preprocessing / cocos) will be skipped."
    }

    Write-Status "Pipeline finished"
}
catch {
    Write-Host "ERROR: $_" -ForegroundColor Red
}
finally {
    if ($SaveOutput) {
        try { Stop-Transcript | Out-Null; Write-Status "Transcript saved: $LogPath" } catch { Write-Status "Failed to stop transcript: $_" }
    }
}

# Usage examples (run from project root):
#   .
un_pipeline.ps1                     -> run normally
#   .
un_pipeline.ps1 -SaveOutput        -> save full console output into timestamped log inside default data folder
#   .
un_pipeline.ps1 -SaveOutput -LogDir "C:\Users\Utente\Desktop\DEGARI-Music2.0\Creazione dei prototipi\data"  -> save into your chosen folder
#   .
un_pipeline.ps1 -SkipHeavy         -> quick run: skip heavy modules (prototyper / preprocess / cocos)

# End of script
