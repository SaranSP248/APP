# CYBERDEX — Cyberpunk Hacker Workstation

A rich, offline-first Python Tkinter desktop application. No database is used.
Bundled city artwork, icons, and WAV sound effects are included in `assets/`.

## Quick start (Windows)

1. Install Python 3.10 or newer from https://www.python.org/downloads/
   During installation, enable **Add Python to PATH**.
2. Extract this ZIP into a new folder.
3. Open Command Prompt in the extracted `CYBERDEX` folder.
4. Install the optional enhancements:

   ```bash
   python -m pip install -r requirements.txt
   ```

5. Start the application:

   ```bash
   python main.py
   ```

If `pip` cannot install packages, the app still starts with Tkinter. Pillow enables bundled artwork,
psutil enables live CPU/RAM/disk metrics, and pygame enables cross-platform sound playback.
On Windows, WAV sounds can fall back to the built-in `winsound` module. On macOS/Linux, install pygame
for sound effects.

## Features

- Dashboard with bundled cyber-city artwork, animated radar HUD, status cards, and quick navigation.
- Five themes: Cyberpunk Hacker, Matrix, Purple Neon, Blood Red, and Cyber Blue.
- Local system telemetry (CPU, RAM, disk) using optional `psutil`.
- Safe terminal simulator with a restricted command set: `help`, `clear`, `date`, `time`, `whoami`,
  `hostname`, `pwd`, `ls`, `sysinfo`, `cpu`, `ram`, `disk`, `ping`, `hash`, `theme`, and `open`.
  It does **not** run arbitrary shell commands.
- Network DNS lookup and optional ping diagnostics (network required).
- Password generator using Python's `secrets` module and SHA-256 file integrity checker.
- Lightweight Python editor to open, save, and run scripts.
- Local file browser.
- Local settings stored in JSON. No database and no account required.
- Sound and animation toggles.

## Offline behavior

Dashboard, themes, local terminal commands, file browser, password generator, hashing, and editor
work offline. DNS and ping need network access. CPU/RAM/disk monitoring uses the local OS and
`psutil`; no internet is involved.

## Notes and safety

- The terminal is a **simulator / restricted local utility console**, not a hacking tool.
- The Python editor executes code with your normal operating-system permissions. Only run scripts
  you wrote or trust.
- The optional `pygame` dependency is used for sound on macOS/Linux and preferred on Windows.
- If the artwork does not show, install Pillow with `python -m pip install Pillow`.
- All project artwork and sounds are bundled locally; the application does not download images.
