# android-log-browser

`android-log-browser` is a CLI to parse and browse Android bugreport/dumpstate logs.

## Features in v1

- Parse `.zip` bugreports and extracted `.txt`/`.log` inputs.
- For `.zip` and directory input, auto-pick the primary analysis text
  (prefers `dumpstate-*.txt`, then `bugreport-*.txt`).
- Filter regex across selected buffers: `logcat`, `radio`, `events`.
- Extract/filter `dumpsys` service sections by exact names or regex.
- List all detected section headers from dumpstate/bugreport text.
- Generate interactive lightweight sections HTML (search + click-to-load content).

## Setup

### macOS/Linux

One-command setup (venv + editable install + shell completion):

```bash
bash components/android-log-browser/scripts/setup.sh
```

Optional shell override:

```bash
bash components/android-log-browser/scripts/setup.sh zsh
```

Manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e components/android-log-browser
```

### Windows (PowerShell)

One-command setup (venv + editable install):

```powershell
powershell -ExecutionPolicy Bypass -File components\android-log-browser\scripts\setup.ps1
```

Manual setup:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e components\android-log-browser
```

### Windows (Command Prompt)

```bat
py -3 -m venv .venv
.\.venv\Scripts\activate.bat
pip install -e components\android-log-browser
```

## Usage

Run from repository root:

```bash
android-log-browser buffers --input /path/to/bugreport.zip --buffers logcat,radio --regex "SIP/2.0 5\\d\\d"
```

```bash
android-log-browser dumpsys --input /path/to/bugreport.zip --list-services
```

```bash
android-log-browser dumpsys --input /path/to/bugreport.zip --services batterystats,alarm
```

```bash
android-log-browser dumpsys --input /path/to/bugreport.zip --service-regex "telephony|connectivity" --json
```

```bash
android-log-browser sections --input /path/to/dumpstate.txt
```

```bash
android-log-browser sections --input /path/to/dumpstate.txt --all --include-noisy
```

Generate interactive sections viewer (HTML metadata only; no embedded log text):

```bash
android-log-browser sections-html --input /path/to/dumpstate.txt
```

Default output file: `dumpstate-sections.html` (current working directory).

Optional index export:

```bash
android-log-browser sections-html --input /path/to/dumpstate.txt --output /tmp/sections_viewer.html --index-json /tmp/sections_index.json
```

Write output to a file (also prints to terminal):

```bash
android-log-browser sections --input /path/to/dumpstate.txt --output /tmp/sections.txt
```

Windows-safe output path examples (PowerShell):

```powershell
android-log-browser sections-html --input C:\logs\dumpstate.txt --output "$env:TEMP\sections_viewer.html"
android-log-browser sections --input C:\logs\dumpstate.txt --output "$env:TEMP\sections.txt"
```

Alternative invocation (without install):

```bash
python -m android_log_browser sections --input /path/to/dumpstate.txt
```

## Notes

- CLI commands are cross-platform (macOS/Linux/Windows) because the parser and command logic are pure Python.
- Setup helper scripts are OS-specific:
  - macOS/Linux: `components/android-log-browser/scripts/setup.sh`
  - Windows PowerShell: `components/android-log-browser/scripts/setup.ps1`
- Buffer/service parsing uses heuristics because bugreport formats vary across Android/OEM versions.
- `sections-html` keeps HTML lightweight and uses browser File API. Open the HTML and select the dumpstate file once via file picker to load section content dynamically.
- This is a CLI-first foundation; RCA synthesis and domain routing come next.
