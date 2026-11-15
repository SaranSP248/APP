#!/usr/bin/env python3
"""
Music Visualizer with synced LRC lyrics  (Python + Tkinter)

Requirements:
    pip install pygame numpy

Features:
    * Load MP3 / WAV / OGG / FLAC and an optional .lrc lyrics file
      (a .lrc with the same name as the song is auto-detected)
    * Real FFT spectrum analysis (log-spaced bands, smoothing, falling peaks)
    * 4 visual modes: Bars, Mirror, Radial, Wave
    * 5 colour themes, bass-reactive glow and beat particles
    * Smooth-scrolling synced lyrics with per-line progress bar
    * Seek bar, volume, keyboard shortcuts

Keys:
    Space  play / pause        Left / Right  seek -/+ 5 s
    M      next visual mode    T             next theme
    F11    fullscreen          Esc           leave fullscreen
"""

import math
import os
import random
import re
import time
import tkinter as tk
import tkinter.font as tkfont
from bisect import bisect_right
from tkinter import filedialog, messagebox, ttk

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

try:
    import numpy as np
    import pygame
except ImportError:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror(
        "Missing dependencies",
        "This app needs pygame and numpy.\n\nInstall them with:\n\n"
        "    pip install pygame numpy",
    )
    raise SystemExit(1)


# --------------------------------------------------------------------------- #
#  Colour helpers & themes
# --------------------------------------------------------------------------- #
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def blend(c1, c2, t):
    """Blend hex colour c1 -> c2 by t (0..1)."""
    t = max(0.0, min(1.0, t))
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return rgb_to_hex([a[i] + (b[i] - a[i]) * t for i in range(3)])


def make_palette(stops, n):
    out = []
    for i in range(n):
        pos = (i / max(1, n - 1)) * (len(stops) - 1)
        j = min(int(pos), len(stops) - 2)
        out.append(blend(stops[j], stops[j + 1], pos - j))
    return out


THEMES = {
    "Neon":   {"stops": ["#00f5ff", "#7a5cff", "#ff2fb9"], "bg": ("#0a0618", "#17093a"), "accent": "#ff5fd0"},
    "Sunset": {"stops": ["#ffd166", "#ff7b54", "#d7263d"], "bg": ("#140a12", "#321126"), "accent": "#ffb36b"},
    "Ocean":  {"stops": ["#7ee0ff", "#4895ef", "#7209b7"], "bg": ("#030b1a", "#08254a"), "accent": "#7ee0ff"},
    "Matrix": {"stops": ["#00ff6a", "#b6ff3b"],            "bg": ("#020a04", "#05200d"), "accent": "#6dff9c"},
    "Mono":   {"stops": ["#ffffff", "#7d8296"],            "bg": ("#0b0b0f", "#1a1a22"), "accent": "#ffffff"},
}
MODES = ["Bars", "Mirror", "Radial", "Wave"]


# --------------------------------------------------------------------------- #
#  LRC parsing
# --------------------------------------------------------------------------- #
TIME_TAG = re.compile(r"\[(\d+):(\d+(?:[.:]\d+)?)\]")
META_TAG = re.compile(r"^\[([A-Za-z#]+):(.*)\]\s*$")
WORD_TAG = re.compile(r"<\d+:\d+(?:[.:]\d+)?>")


def parse_lrc(path):
    """Return (times, texts, meta). Supports multi-timestamps, [offset:], enhanced tags."""
    raw = None
    for enc in ("utf-8-sig", "utf-16", "gb18030", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                raw = f.read()
            break
        except (UnicodeError, UnicodeDecodeError):
            continue
    if raw is None:
        raise ValueError("Could not decode the lyrics file.")

    entries, meta, offset = [], {}, 0.0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        stamps = list(TIME_TAG.finditer(line))
        if not stamps:
            m = META_TAG.match(line)
            if m:
                key, val = m.group(1).lower(), m.group(2).strip()
                meta[key] = val
                if key == "offset":
                    try:
                        offset = int(val) / 1000.0
                    except ValueError:
                        pass
            continue
        text = TIME_TAG.sub("", line)
        text = WORD_TAG.sub("", text).strip()
        for s in stamps:
            t = int(s.group(1)) * 60 + float(s.group(2).replace(":", "."))
            entries.append((t, text))

    entries.sort(key=lambda e: e[0])
    times = [max(0.0, e[0] - offset) for e in entries]
    texts = [e[1] for e in entries]
    return times, texts, meta


def fmt_time(s):
    s = max(0, int(s))
    return f"{s // 60}:{s % 60:02d}"


# --------------------------------------------------------------------------- #
#  Main application
# --------------------------------------------------------------------------- #
class MusicVisualizer:
    BARS = 64
    FFT_N = 4096

    def __init__(self, root):
        self.root = root
        root.title("Music Visualizer")
        root.geometry("1100x720")
        root.minsize(720, 520)
        root.configure(bg="#0c0c12")

        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
        self.sr = pygame.mixer.get_init()[0]

        # audio state
        self.mono = None
        self.duration = 0.0
        self.loaded = False
        self.playing = False
        self.paused = False
        self.offset = 0.0           # seconds where the current playback began
        self.track_name = ""
        self.dragging = False

        # lyrics state
        self.l_times, self.l_texts, self.l_meta = [], [], {}
        self.l_scroll = 0.0

        # visual state
        self.theme_name = "Neon"
        self.mode = "Bars"
        self.levels = np.zeros(self.BARS)
        self.peaks = np.zeros(self.BARS)
        self.wave = np.zeros(200)
        self.bass = 0.0
        self.bass_avg = 0.0
        self.beat_cooldown = 0
        self.particles = []
        self.rot = 0.0
        self.t0 = time.perf_counter()

        # FFT helpers
        self.win = np.hanning(self.FFT_N).astype(np.float32)
        freqs = np.fft.rfftfreq(self.FFT_N, 1.0 / self.sr)
        edges = np.logspace(math.log10(30), math.log10(min(16000, self.sr * 0.45)), self.BARS + 1)
        lo = np.searchsorted(freqs, edges[:-1])
        hi = np.maximum(np.searchsorted(freqs, edges[1:]), lo + 1)
        self.bands = list(zip(lo.tolist(), hi.tolist()))
        self.tilt = np.linspace(0, 14, self.BARS)

        # fonts
        avail = set(tkfont.families())
        fam = next((f for f in ("Segoe UI", "SF Pro Display", "Helvetica Neue", "DejaVu Sans", "Arial")
                    if f in avail), "Helvetica")
        self.f_big = tkfont.Font(family=fam, size=26, weight="bold")
        self.f_norm = tkfont.Font(family=fam, size=16)
        self.f_title = tkfont.Font(family=fam, size=15, weight="bold")
        self.f_small = tkfont.Font(family=fam, size=11)

        self._build_ui()
        self._apply_theme()
        self._bind_keys()
        self._tick()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        bg = "#12121a"
        style.configure("Bar.TFrame", background=bg)
        style.configure("Bar.TLabel", background=bg, foreground="#d6d9e8")
        style.configure("Bar.TButton", padding=(10, 5))
        style.configure("Bar.TCombobox", padding=3)
        style.configure("Horizontal.TScale", background=bg, troughcolor="#2a2a3a")

        self.canvas = tk.Canvas(self.root, bg="#0c0c12", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self._draw_bg())

        bar = ttk.Frame(self.root, style="Bar.TFrame", padding=(10, 8))
        bar.pack(fill="x", side="bottom")

        ttk.Button(bar, text="🎵 Open Music", style="Bar.TButton", command=self.open_music).pack(side="left")
        ttk.Button(bar, text="📝 Open LRC", style="Bar.TButton", command=self.open_lrc).pack(side="left", padx=(6, 0))
        self.play_btn = ttk.Button(bar, text="▶  Play", style="Bar.TButton", width=9, command=self.toggle_play)
        self.play_btn.pack(side="left", padx=(14, 0))
        ttk.Button(bar, text="■", style="Bar.TButton", width=3, command=self.stop).pack(side="left", padx=(4, 0))

        self.time_lbl = ttk.Label(bar, text="0:00 / 0:00", style="Bar.TLabel", width=11)
        self.time_lbl.pack(side="left", padx=(12, 4))

        self.seek_var = tk.DoubleVar(value=0)
        self.seek = ttk.Scale(bar, from_=0, to=1, variable=self.seek_var, orient="horizontal")
        self.seek.pack(side="left", fill="x", expand=True, padx=6)
        self.seek.bind("<ButtonPress-1>", lambda e: setattr(self, "dragging", True))
        self.seek.bind("<ButtonRelease-1>", self._seek_release)

        ttk.Label(bar, text="🔊", style="Bar.TLabel").pack(side="left", padx=(8, 0))
        self.vol_var = tk.DoubleVar(value=0.8)
        vol = ttk.Scale(bar, from_=0, to=1, variable=self.vol_var, orient="horizontal", length=90,
                        command=lambda v: pygame.mixer.music.set_volume(float(v)))
        vol.pack(side="left", padx=4)
        pygame.mixer.music.set_volume(0.8)

        self.mode_cb = ttk.Combobox(bar, values=MODES, width=8, state="readonly", style="Bar.TCombobox")
        self.mode_cb.set(self.mode)
        self.mode_cb.pack(side="left", padx=(10, 0))
        self.mode_cb.bind("<<ComboboxSelected>>", lambda e: self._set_mode(self.mode_cb.get()))

        self.theme_cb = ttk.Combobox(bar, values=list(THEMES), width=8, state="readonly", style="Bar.TCombobox")
        self.theme_cb.set(self.theme_name)
        self.theme_cb.pack(side="left", padx=(6, 0))
        self.theme_cb.bind("<<ComboboxSelected>>", lambda e: self._set_theme(self.theme_cb.get()))

    def _bind_keys(self):
        r = self.root
        r.bind("<space>", lambda e: self.toggle_play())
        r.bind("<Left>", lambda e: self.seek_by(-5))
        r.bind("<Right>", lambda e: self.seek_by(5))
        r.bind("<m>", lambda e: self._cycle_mode())
        r.bind("<t>", lambda e: self._cycle_theme())
        r.bind("<F11>", lambda e: r.attributes("-fullscreen", not r.attributes("-fullscreen")))
        r.bind("<Escape>", lambda e: r.attributes("-fullscreen", False))
        r.protocol("WM_DELETE_WINDOW", self._quit)

    def _quit(self):
        pygame.mixer.quit()
        self.root.destroy()

    # --------------------------------------------------------- themes/modes --
    def _apply_theme(self):
        th = THEMES[self.theme_name]
        self.pal = make_palette(th["stops"], self.BARS)
        self.bg_top, self.bg_bot = th["bg"]
        self.accent = th["accent"]
        self._draw_bg()

    def _set_theme(self, name):
        self.theme_name = name
        self.theme_cb.set(name)
        self._apply_theme()
        self.root.focus_set()

    def _cycle_theme(self):
        names = list(THEMES)
        self._set_theme(names[(names.index(self.theme_name) + 1) % len(names)])

    def _set_mode(self, mode):
        self.mode = mode
        self.mode_cb.set(mode)
        self.root.focus_set()

    def _cycle_mode(self):
        self._set_mode(MODES[(MODES.index(self.mode) + 1) % len(MODES)])

    def _draw_bg(self):
        c = self.canvas
        c.delete("bg")
        W, H = c.winfo_width(), c.winfo_height()
        if W < 10:
            return
        steps = 48
        h = H / steps
        for i in range(steps):
            col = blend(self.bg_top, self.bg_bot, i / (steps - 1))
            c.create_rectangle(0, i * h, W, (i + 1) * h + 1, fill=col, outline="", tags="bg")
        c.tag_lower("bg")

    # ----------------------------------------------------------- file loading --
    def open_music(self):
        path = filedialog.askopenfilename(
            title="Choose a music file",
            filetypes=[("Audio", "*.mp3 *.wav *.ogg *.flac"), ("All files", "*.*")])
        if path:
            self.load_music(path)

    def open_lrc(self):
        path = filedialog.askopenfilename(
            title="Choose a lyrics file", filetypes=[("LRC lyrics", "*.lrc"), ("All files", "*.*")])
        if path:
            self.load_lrc(path)

    def load_music(self, path):
        self.stop()
        self.root.title("Music Visualizer — loading…")
        self.root.update_idletasks()
        try:
            pygame.mixer.music.load(path)
        except pygame.error as e:
            messagebox.showerror("Cannot open file", str(e))
            self.root.title("Music Visualizer")
            return

        # Decode once for spectrum analysis & duration
        self.mono = None
        try:
            snd = pygame.mixer.Sound(path)
            self.duration = snd.get_length()
            arr = pygame.sndarray.array(snd).astype(np.float32) / 32768.0
            self.mono = arr.mean(axis=1) if arr.ndim == 2 else arr
            self.sr = pygame.mixer.get_init()[0]
            del snd, arr
        except Exception:
            self.duration = 0.0   # visualizer falls back to an idle animation

        self.loaded = True
        self.track_name = os.path.splitext(os.path.basename(path))[0]
        self.seek.configure(to=max(1.0, self.duration))
        self.seek_var.set(0)
        self.offset = 0.0
        self.l_scroll = 0.0
        self.root.title(f"Music Visualizer — {self.track_name}")

        # auto-detect lyrics next to the audio file
        lrc = os.path.splitext(path)[0] + ".lrc"
        if os.path.exists(lrc):
            self.load_lrc(lrc)
        else:
            self.l_times, self.l_texts, self.l_meta = [], [], {}
        self.toggle_play()

    def load_lrc(self, path):
        try:
            self.l_times, self.l_texts, self.l_meta = parse_lrc(path)
        except Exception as e:
            messagebox.showerror("Lyrics error", str(e))
            return
        if not self.l_times:
            messagebox.showwarning("No lyrics", "No timestamped lines were found in that file.")
        self.l_scroll = 0.0

    # ----------------------------------------------------------- transport --
    def toggle_play(self):
        if not self.loaded:
            self.open_music()
            return
        m = pygame.mixer.music
        if not self.playing:
            try:
                m.play(start=self.offset)
            except pygame.error:
                m.play()
                self.offset = 0.0
            self.playing, self.paused = True, False
            self.play_btn.configure(text="⏸  Pause")
        elif self.paused:
            m.unpause()
            self.paused = False
            self.play_btn.configure(text="⏸  Pause")
        else:
            m.pause()
            self.paused = True
            self.play_btn.configure(text="▶  Play")

    def stop(self):
        if self.loaded:
            pygame.mixer.music.stop()
        self.playing = self.paused = False
        self.offset = 0.0
        self.seek_var.set(0)
        self.l_scroll = 0.0
        if hasattr(self, "play_btn"):
            self.play_btn.configure(text="▶  Play")

    def current_time(self):
        if not self.loaded:
            return 0.0
        if self.playing:
            return self.offset + max(0, pygame.mixer.music.get_pos()) / 1000.0
        return self.offset

    def seek_to(self, t):
        if not self.loaded:
            return
        t = max(0.0, min(t, max(0.0, self.duration - 0.05))) if self.duration else max(0.0, t)
        was_paused = self.paused
        was_playing = self.playing
        self.offset = t
        if was_playing:
            try:
                pygame.mixer.music.play(start=t)
            except pygame.error:
                pass
            if was_paused:
                pygame.mixer.music.pause()
        self.seek_var.set(t)

    def seek_by(self, delta):
        self.seek_to(self.current_time() + delta)

    def _seek_release(self, _e):
        self.dragging = False
        self.seek_to(self.seek_var.get())

    # -------------------------------------------------------------- analysis --
    def analyze(self, t):
        """Return (levels[BARS], wave[200]) for time t."""
        if self.mono is None or not self.playing:
            # idle / synthetic animation
            now = time.perf_counter() - self.t0
            i = np.arange(self.BARS)
            lv = 0.10 + 0.07 * np.sin(now * 1.3 + i * 0.35) + 0.05 * np.sin(now * 2.1 - i * 0.9)
            if self.playing and self.mono is None:
                lv = lv + 0.35 * np.abs(np.sin(now * 3 + i * 0.25)) * (1 - i / self.BARS)
            wave = 0.25 * np.sin(np.linspace(0, 6 * math.pi, 200) + now * 2)
            return np.clip(lv, 0, 1), wave

        N = self.FFT_N
        s = max(0, int(t * self.sr) - N // 2)
        seg = self.mono[s:s + N]
        if len(seg) < N:
            seg = np.pad(seg, (0, N - len(seg)))
        spec = np.abs(np.fft.rfft(seg * self.win)) * (4.0 / N)
        vals = np.array([spec[lo:hi].max() for lo, hi in self.bands])
        db = 20 * np.log10(vals + 1e-7) + self.tilt
        lv = np.clip((db + 75) / 60, 0, 1) ** 1.5

        w0 = max(0, int(t * self.sr) - 500)
        w = self.mono[w0:w0 + 1000]
        if len(w) < 1000:
            w = np.pad(w, (0, 1000 - len(w)))
        wave = w[::5] * 2.2
        return lv, wave

    def _update_levels(self):
        t = self.current_time()
        target, wave = self.analyze(t)
        rise = np.where(target > self.levels, 0.65, 0.14)
        self.levels += (target - self.levels) * rise
        self.peaks = np.maximum(self.levels, self.peaks - 0.008)
        self.wave += (wave - self.wave) * 0.6

        self.bass = float(self.levels[:6].mean())
        self.bass_avg = self.bass_avg * 0.95 + self.bass * 0.05
        self.beat_cooldown = max(0, self.beat_cooldown - 1)
        if (self.playing and not self.paused and self.beat_cooldown == 0
                and self.bass > self.bass_avg * 1.25 + 0.06):
            self.beat_cooldown = 10
            self._spawn_particles(int(10 + self.bass * 14))

    # ------------------------------------------------------------- particles --
    def _spawn_particles(self, n):
        W, H = self.canvas.winfo_width(), self.canvas.winfo_height()
        vh = H * 0.64
        for _ in range(n):
            col = random.choice(self.pal)
            if self.mode == "Radial":
                a = random.uniform(0, 2 * math.pi)
                r = min(W, vh) * 0.22
                x, y = W / 2 + math.cos(a) * r, vh / 2 + math.sin(a) * r
                sp = random.uniform(1.5, 4.5)
                vx, vy = math.cos(a) * sp, math.sin(a) * sp
            else:
                x = random.uniform(40, W - 40)
                y = vh - 30 if self.mode != "Mirror" else vh / 2
                vx, vy = random.uniform(-1, 1), random.uniform(-4.5, -1.5)
                if self.mode == "Mirror" and random.random() < 0.5:
                    vy = -vy
            self.particles.append([x, y, vx, vy, 1.0, random.uniform(2, 5), col])

    def _draw_particles(self):
        c = self.canvas
        alive = []
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3]
            p[4] -= 0.018
            if p[4] > 0:
                alive.append(p)
                r = p[5] * p[4]
                c.create_oval(p[0] - r, p[1] - r, p[0] + r, p[1] + r,
                              fill=blend(p[6], self.bg_top, 1 - p[4]), outline="", tags="fx")
        self.particles = alive[-300:]

    # --------------------------------------------------------------- drawing --
    def _tick(self):
        try:
            self._frame()
        except tk.TclError:
            return
        self.root.after(16, self._tick)

    def _frame(self):
        c = self.canvas
        W, H = c.winfo_width(), c.winfo_height()
        if W < 50 or H < 50:
            return

        # transport bookkeeping
        if self.playing and not self.paused and not pygame.mixer.music.get_busy():
            self.stop()
        t = self.current_time()
        if not self.dragging:
            self.seek_var.set(t)
        shown = self.seek_var.get() if self.dragging else t
        self.time_lbl.configure(text=f"{fmt_time(shown)} / {fmt_time(self.duration)}")

        self._update_levels()
        c.delete("fx")
        vh = H * 0.64

        self._draw_glow(W, vh)
        mode = self.mode
        if mode == "Bars":
            self._draw_bars(W, vh)
        elif mode == "Mirror":
            self._draw_mirror(W, vh)
        elif mode == "Radial":
            self._draw_radial(W, vh)
        else:
            self._draw_wave(W, vh)
        self._draw_particles()
        self._draw_title(W)
        self._draw_lyrics(W, H, vh, t)

    def _draw_glow(self, W, vh):
        c = self.canvas
        if self.mode == "Radial":
            cx, cy = W / 2, vh / 2
        else:
            cx, cy = W / 2, vh * 0.9
        base = min(W, vh) * (0.45 + self.bass * 0.35)
        for k in range(6, 0, -1):
            r = base * k / 6 * 1.4
            col = blend(self.bg_top, self.accent, (0.05 + self.bass * 0.30) * (1 - k / 7))
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=col, outline="", tags="fx")

    def _draw_bars(self, W, vh):
        c = self.canvas
        n = self.BARS
        x0, x1 = 40, W - 40
        slot = (x1 - x0) / n
        bw = max(2, slot * 0.72)
        base = vh - 34
        maxh = vh - 90
        for i in range(n):
            x = x0 + i * slot
            h = max(3, self.levels[i] * maxh)
            c.create_rectangle(x, base - h, x + bw, base, fill=self.pal[i], outline="", tags="fx")
            # reflection
            rh = min(h * 0.3, 26)
            c.create_rectangle(x, base + 3, x + bw, base + 3 + rh,
                               fill=blend(self.pal[i], self.bg_top, 0.78), outline="", tags="fx")
            # falling peak cap
            py = base - self.peaks[i] * maxh - 7
            c.create_rectangle(x, py, x + bw, py + 3, fill=blend(self.pal[i], "#ffffff", 0.55),
                               outline="", tags="fx")

    def _draw_mirror(self, W, vh):
        c = self.canvas
        n = self.BARS
        x0, x1 = 40, W - 40
        slot = (x1 - x0) / n
        bw = max(2, slot * 0.72)
        cy = vh / 2
        maxh = (vh - 70) / 2
        for i in range(n):
            x = x0 + i * slot
            h = max(2, self.levels[i] * maxh)
            c.create_rectangle(x, cy - h, x + bw, cy + h, fill=self.pal[i], outline="", tags="fx")
            c.create_rectangle(x + bw * 0.3, cy - h * 0.55, x + bw * 0.7, cy + h * 0.55,
                               fill=blend(self.pal[i], "#ffffff", 0.45), outline="", tags="fx")

    def _draw_radial(self, W, vh):
        c = self.canvas
        n = self.BARS
        cx, cy = W / 2, vh / 2
        size = min(W, vh)
        r0 = size * 0.20 * (1 + self.bass * 0.18)
        maxlen = size * 0.27
        self.rot += 0.003 + self.bass * 0.012
        spokes = n * 2
        for j in range(spokes):
            idx = j if j < n else spokes - 1 - j
            a = j / spokes * 2 * math.pi - math.pi / 2 + self.rot
            ln = self.levels[idx] * maxlen + 3
            ca, sa = math.cos(a), math.sin(a)
            c.create_line(cx + ca * r0, cy + sa * r0, cx + ca * (r0 + ln), cy + sa * (r0 + ln),
                          fill=self.pal[idx], width=max(2, size * 0.008), capstyle="round", tags="fx")
        for rr, wd in ((r0 - 6, 2), (r0 - 14, 1)):
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                          outline=blend(self.accent, self.bg_top, 0.4), width=wd, tags="fx")

    def _draw_wave(self, W, vh):
        c = self.canvas
        n = len(self.wave)
        cy = vh / 2
        amp = (vh - 80) / 2 * (0.9 + self.bass * 0.5)
        x0, x1 = 30, W - 30
        for layer, (dy, col, wd) in enumerate((
                (5, blend(self.pal[0], self.bg_top, 0.5), 6),
                (0, self.pal[self.BARS // 2], 3),
                (-3, blend(self.pal[-1], "#ffffff", 0.4), 1))):
            pts = []
            for i in range(n):
                x = x0 + (x1 - x0) * i / (n - 1)
                pts += [x, cy + dy + float(np.clip(self.wave[i], -1, 1)) * amp]
            c.create_line(*pts, fill=col, width=wd, smooth=True, tags="fx")

    def _draw_title(self, W):
        c = self.canvas
        title = self.l_meta.get("ti") or self.track_name
        artist = self.l_meta.get("ar", "")
        if not title:
            title = "Open a music file to begin"
        c.create_text(26, 22, text=title, anchor="w", font=self.f_title,
                      fill=blend(self.accent, "#ffffff", 0.6), tags="fx")
        if artist:
            c.create_text(26, 46, text=artist, anchor="w", font=self.f_small,
                          fill=blend("#aab0c4", self.bg_top, 0.2), tags="fx")
        c.create_text(W - 20, 22, text=f"{self.mode}  ·  {self.theme_name}", anchor="e",
                      font=self.f_small, fill=blend("#aab0c4", self.bg_top, 0.45), tags="fx")

    def _draw_lyrics(self, W, H, top, t):
        c = self.canvas
        area_h = H - top
        cy = top + area_h * 0.52
        bg = blend(self.bg_top, self.bg_bot, 0.8)

        if not self.l_times:
            msg = ("No lyrics loaded — click “Open LRC”" if self.loaded
                   else "Click “Open Music” and pick a song (and optionally a .lrc file)")
            c.create_text(W / 2, cy, text=msg, font=self.f_norm, fill=blend("#aab0c4", bg, 0.35), tags="fx")
            return

        cur = bisect_right(self.l_times, t) - 1
        target = max(cur, 0)
        self.l_scroll += (target - self.l_scroll) * 0.16
        line_h = max(32, min(48, area_h / 5))
        wrap = int(W * 0.85)
        n = len(self.l_times)

        first = int(math.floor(self.l_scroll)) - 3
        for i in range(first, first + 8):
            if not 0 <= i < n:
                continue
            d = i - self.l_scroll
            ad = abs(d)
            y = cy + d * line_h
            if y < top - 10 or y > H + 10:
                continue
            text = self.l_texts[i] or "♪"
            if i == cur and ad < 0.7:
                c.create_text(W / 2 + 2, y + 2, text=text, font=self.f_big, width=wrap,
                              fill=blend(self.accent, bg, 0.75), tags="fx")
                c.create_text(W / 2, y, text=text, font=self.f_big, width=wrap,
                              fill="#ffffff", tags="fx")
                # progress bar under current line
                end = self.l_times[i + 1] if i + 1 < n else self.l_times[i] + 5
                prog = (t - self.l_times[i]) / max(0.1, end - self.l_times[i])
                bw = min(260, W * 0.4)
                by = y + line_h * 0.62
                c.create_rectangle(W / 2 - bw / 2, by, W / 2 + bw / 2, by + 3,
                                   fill=blend(self.accent, bg, 0.8), outline="", tags="fx")
                c.create_rectangle(W / 2 - bw / 2, by, W / 2 - bw / 2 + bw * max(0, min(1, prog)), by + 3,
                                   fill=self.accent, outline="", tags="fx")
            else:
                col = blend("#c3c8dc", bg, min(1.0, 0.25 + ad * 0.28))
                c.create_text(W / 2, y, text=text, font=self.f_norm, width=wrap, fill=col, tags="fx")


# --------------------------------------------------------------------------- #
def main():
    root = tk.Tk()
    MusicVisualizer(root)
    root.mainloop()


if __name__ == "__main__":
    main()