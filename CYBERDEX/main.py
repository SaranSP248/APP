"""
CYBERDEX // Cyberpunk Hacker Workstation
Offline-first Tkinter desktop application. No database required.
Optional packages: Pillow, psutil, pygame.
"""
import os, sys, time, math, random, socket, hashlib, platform, subprocess, threading, json
from pathlib import Path
from datetime import datetime

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except Exception as e:
    raise SystemExit("Tkinter is required. Install Python with Tcl/Tk support.") from e

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

try:
    from PIL import Image, ImageTk, ImageEnhance
    PIL_OK = True
except Exception:
    PIL_OK = False
try:
    import psutil
    PSUTIL_OK = True
except Exception:
    PSUTIL_OK = False
try:
    import pygame
    pygame.mixer.init()
    PYGAME_OK = True
except Exception:
    PYGAME_OK = False

THEMES = {
 "Cyberpunk Hacker": {"bg":"#070b16","panel":"#0d1728","panel2":"#101f34","fg":"#d9f8f5","muted":"#76949d","accent":"#19f5d0","accent2":"#ff3da8","line":"#164b55"},
 "Matrix": {"bg":"#030907","panel":"#07150e","panel2":"#0b2115","fg":"#d7ffe0","muted":"#6d9d79","accent":"#39ff75","accent2":"#b8ff3d","line":"#174d2b"},
 "Purple Neon": {"bg":"#0b0718","panel":"#17112b","panel2":"#21183b","fg":"#f0e6ff","muted":"#a494bd","accent":"#bb72ff","accent2":"#39dcff","line":"#49336c"},
 "Blood Red": {"bg":"#100809","panel":"#211012","panel2":"#321619","fg":"#ffe8e8","muted":"#b58c8c","accent":"#ff4b59","accent2":"#ff9b40","line":"#653038"},
 "Cyber Blue": {"bg":"#050d18","panel":"#0b1a2d","panel2":"#102640","fg":"#e2f3ff","muted":"#82a4c2","accent":"#36baff","accent2":"#54ffe0","line":"#1b5275"}
}
DEFAULTS={"theme":"Cyberpunk Hacker","sound":True,"animation":True,"volume":65,"username":os.environ.get("USERNAME") or os.environ.get("USER") or "operator"}
SETTINGS_FILE=DATA/"settings.json"

def load_settings():
    try:
        return {**DEFAULTS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
    except Exception:
        return DEFAULTS.copy()

def save_settings(settings):
    try: SETTINGS_FILE.write_text(json.dumps(settings,indent=2),encoding="utf-8")
    except Exception: pass

class CyberDex(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings=load_settings()
        self.theme_name=self.settings.get("theme","Cyberpunk Hacker")
        self.c=THEMES.get(self.theme_name,THEMES["Cyberpunk Hacker"])
        self.title("CYBERDEX // Cyberpunk Workstation")
        self.geometry("1450x900")
        self.minsize(1120,720)
        self.configure(bg=self.c["bg"])
        self.current_page="Dashboard"
        self.nav_buttons={}
        self.images={}
        self.anim_phase=0
        self.terminal_history=[]
        self.sound_enabled=bool(self.settings.get("sound",True))
        self.animation_enabled=bool(self.settings.get("animation",True))
        self._build_shell()
        self.show_page("Dashboard")
        self.after(250,self._tick)
        if self.sound_enabled: self.play_sound("startup")

    def play_sound(self,name):
        if not self.sound_enabled: return
        path=ASSETS/"sounds"/(name+".wav")
        if not path.exists(): return
        try:
            if PYGAME_OK:
                snd=pygame.mixer.Sound(str(path))
                snd.set_volume(max(0,min(1,float(self.settings.get("volume",65))/100)))
                snd.play()
            elif sys.platform.startswith("win"):
                import winsound
                winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
            else:
                # Optional pygame provides cross-platform audio; fail silently if absent.
                pass
        except Exception: pass

    def _build_shell(self):
        self.shell=tk.Frame(self,bg=self.c["bg"]); self.shell.pack(fill="both",expand=True)
        self.sidebar=tk.Frame(self.shell,bg=self.c["panel"],width=238,highlightthickness=1,highlightbackground=self.c["line"])
        self.sidebar.pack(side="left",fill="y"); self.sidebar.pack_propagate(False)
        brand=tk.Frame(self.sidebar,bg=self.c["panel"]); brand.pack(fill="x",padx=18,pady=(20,20))
        tk.Label(brand,text="◈",font=("Segoe UI Symbol",28,"bold"),fg=self.c["accent"],bg=self.c["panel"]).pack(side="left")
        btxt=tk.Frame(brand,bg=self.c["panel"]); btxt.pack(side="left",padx=8)
        tk.Label(btxt,text="CYBERDEX",font=("Segoe UI",17,"bold"),fg=self.c["fg"],bg=self.c["panel"]).pack(anchor="w")
        tk.Label(btxt,text="PERSONAL CYBER WORKSTATION",font=("Segoe UI",7,"bold"),fg=self.c["muted"],bg=self.c["panel"]).pack(anchor="w")
        self.status_dot=tk.Label(self.sidebar,text="●  SYSTEM ONLINE",font=("Consolas",9,"bold"),fg=self.c["accent"],bg=self.c["panel"])
        self.status_dot.pack(anchor="w",padx=22,pady=(0,16))
        nav_groups=[("WORKSPACE",["Dashboard","System Monitor","Terminal","Network Center"]),("TOOLS",["Security Lab","Developer Studio","File Center"]),("SYSTEM",["Themes & Settings","About CYBERDEX"])]
        for group,items in nav_groups:
            tk.Label(self.sidebar,text=group,font=("Segoe UI",8,"bold"),fg=self.c["muted"],bg=self.c["panel"]).pack(anchor="w",padx=22,pady=(9,6))
            for item in items:
                btn=tk.Button(self.sidebar,text="  "+self._symbol(item)+"   "+item,anchor="w",bd=0,relief="flat",
                    font=("Segoe UI",10),fg=self.c["muted"],bg=self.c["panel"],activebackground=self.c["panel2"],
                    activeforeground=self.c["accent"],command=lambda p=item:self.show_page(p),padx=10,pady=10,cursor="hand2")
                btn.pack(fill="x",padx=10,pady=2); self.nav_buttons[item]=btn
        tk.Frame(self.sidebar,bg=self.c["line"],height=1).pack(fill="x",padx=16,pady=16)
        tk.Label(self.sidebar,text="LOCAL MODE  •  NO DATABASE",font=("Consolas",8),fg=self.c["muted"],bg=self.c["panel"]).pack(anchor="w",padx=20)
        tk.Label(self.sidebar,text="v1.0  //  OFFLINE READY",font=("Consolas",8),fg=self.c["accent"],bg=self.c["panel"]).pack(anchor="w",padx=20,pady=6)

        self.main=tk.Frame(self.shell,bg=self.c["bg"]); self.main.pack(side="left",fill="both",expand=True)
        self.topbar=tk.Frame(self.main,bg=self.c["bg"],height=66); self.topbar.pack(fill="x",padx=26,pady=(14,4)); self.topbar.pack_propagate(False)
        self.page_title=tk.Label(self.topbar,text="COMMAND CENTER",font=("Segoe UI",17,"bold"),fg=self.c["fg"],bg=self.c["bg"])
        self.page_title.pack(side="left",anchor="center")
        self.clock=tk.Label(self.topbar,text="",font=("Consolas",10),fg=self.c["accent"],bg=self.c["bg"]); self.clock.pack(side="right",padx=12)
        self.online=tk.Label(self.topbar,text="● LOCAL SYSTEM",font=("Consolas",9,"bold"),fg=self.c["muted"],bg=self.c["bg"]); self.online.pack(side="right",padx=12)
        self.content=tk.Frame(self.main,bg=self.c["bg"]); self.content.pack(fill="both",expand=True,padx=26,pady=(4,22))

    def _symbol(self,p):
        return {"Dashboard":"▦","System Monitor":"◉","Terminal":"⌘","Network Center":"⌁","Security Lab":"⬡","Developer Studio":"</>","File Center":"▤","Themes & Settings":"⚙","About CYBERDEX":"◇"}.get(p,"•")

    def _clear(self):
        for w in self.content.winfo_children(): w.destroy()

    def show_page(self,page):
        self.current_page=page; self.play_sound("click")
        self._clear(); self.page_title.config(text=page.upper())
        for name,btn in self.nav_buttons.items():
            active=name==page
            btn.config(bg=self.c["panel2"] if active else self.c["panel"],fg=self.c["accent"] if active else self.c["muted"])
        getattr(self,"page_"+page.lower().replace(" ","_").replace("&","and"))()

    def card(self,parent,title,value,sub="",accent=None):
        f=tk.Frame(parent,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"])
        tk.Label(f,text=title.upper(),font=("Segoe UI",8,"bold"),fg=self.c["muted"],bg=self.c["panel"]).pack(anchor="w",padx=14,pady=(12,4))
        tk.Label(f,text=value,font=("Segoe UI",22,"bold"),fg=accent or self.c["accent"],bg=self.c["panel"]).pack(anchor="w",padx=14)
        if sub: tk.Label(f,text=sub,font=("Segoe UI",8),fg=self.c["muted"],bg=self.c["panel"]).pack(anchor="w",padx=14,pady=(2,12))
        else: tk.Frame(f,bg=self.c["panel"],height=12).pack()
        return f

    def section(self,parent,title,sub=None):
        row=tk.Frame(parent,bg=self.c["bg"]); row.pack(fill="x",pady=(0,10))
        tk.Label(row,text=title,font=("Segoe UI",12,"bold"),fg=self.c["fg"],bg=self.c["bg"]).pack(side="left")
        if sub: tk.Label(row,text=sub,font=("Segoe UI",8),fg=self.c["muted"],bg=self.c["bg"]).pack(side="right")
        return row

    def button(self,parent,text,command,primary=False):
        return tk.Button(parent,text=text,command=command,bd=0,relief="flat",cursor="hand2",
            bg=self.c["accent"] if primary else self.c["panel2"],
            fg="#041116" if primary else self.c["fg"],activebackground=self.c["accent2"],
            activeforeground="#071018",font=("Segoe UI",9,"bold"),padx=13,pady=9)

    def page_dashboard(self):
        # Hero with local artwork background
        hero=tk.Frame(self.content,bg=self.c["panel"],height=245,highlightthickness=1,highlightbackground=self.c["line"])
        hero.pack(fill="x",pady=(0,16)); hero.pack_propagate(False)
        if PIL_OK:
            try:
                im=Image.open(ASSETS/"backgrounds"/"cyber_city.png").resize((1100,245))
                self.images["hero"]=ImageTk.PhotoImage(im)
                tk.Label(hero,image=self.images["hero"],bd=0).place(x=0,y=0,relwidth=1,relheight=1)
            except Exception: pass
        overlay=tk.Frame(hero,bg="#07121e"); overlay.place(x=25,y=25)
        tk.Label(overlay,text="WELCOME BACK, OPERATOR",font=("Consolas",10,"bold"),fg=self.c["accent"],bg="#07121e").pack(anchor="w",padx=16,pady=(13,5))
        tk.Label(overlay,text="YOUR DIGITAL\nCOMMAND DECK.",font=("Segoe UI",25,"bold"),fg="#eaffff",bg="#07121e",justify="left").pack(anchor="w",padx=16)
        tk.Label(overlay,text="LOCAL SYSTEMS • SECURE WORKSPACE • OFFLINE READY",font=("Consolas",8),fg="#9bbec5",bg="#07121e").pack(anchor="w",padx=16,pady=(8,14))
        row=tk.Frame(self.content,bg=self.c["bg"]); row.pack(fill="x",pady=(0,16))
        stats=self._get_stats()
        for title,val,sub in [("CPU LOAD",stats["cpu"],"Processor utilization"),("MEMORY",stats["ram"],"Physical memory used"),("STORAGE",stats["disk"],"System drive usage"),("HOST",platform.node()[:16] or "LOCAL PC","This device")]:
            c=self.card(row,title,val,sub); c.pack(side="left",fill="x",expand=True,padx=(0,10))
        lower=tk.Frame(self.content,bg=self.c["bg"]); lower.pack(fill="both",expand=True)
        left=tk.Frame(lower,bg=self.c["bg"]); left.pack(side="left",fill="both",expand=True,padx=(0,12))
        right=tk.Frame(lower,bg=self.c["bg"]); right.pack(side="left",fill="both",expand=True)
        self.section(left,"QUICK ACCESS","Launch a module")
        q=tk.Frame(left,bg=self.c["bg"]); q.pack(fill="x")
        for name in ["System Monitor","Terminal","Network Center","Security Lab","Developer Studio","File Center"]:
            self.button(q,name,lambda n=name:self.show_page(n)).pack(side="left",padx=(0,7),pady=5)
        self.section(left,"SYSTEM ACTIVITY","Local event stream")
        self.activity=tk.Text(left,height=8,bg=self.c["panel"],fg=self.c["accent"],insertbackground=self.c["accent"],bd=0,font=("Consolas",9),padx=12,pady=10)
        self.activity.pack(fill="both",expand=True)
        for line in ["[BOOT] CYBERDEX workstation initialized","[ASSET] Local cyber-city artwork loaded","[MODE] Offline-first operation enabled","[SECURITY] No database connection configured","[READY] Awaiting operator command"]:
            self.activity.insert("end",line+"\n")
        self.activity.config(state="disabled")
        self.section(right,"VISUAL STATUS","Animated local HUD")
        viz=tk.Frame(right,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]); viz.pack(fill="both",expand=True)
        self.viz=tk.Canvas(viz,bg=self.c["panel"],highlightthickness=0,height=180); self.viz.pack(fill="both",expand=True,padx=8,pady=8)
        self._draw_viz()

    def _draw_viz(self):
        if not hasattr(self,"viz") or not self.viz.winfo_exists(): return
        c=self.viz; c.delete("all"); w=max(200,c.winfo_width()); h=max(130,c.winfo_height())
        col=self.c["accent"]
        for x in range(0,w,28): c.create_line(x,0,x,h,fill=self.c["line"])
        for y in range(0,h,28): c.create_line(0,y,w,y,fill=self.c["line"])
        cx,cy=w//2,h//2
        for r in [25,48,72]:
            c.create_oval(cx-r,cy-r,cx+r,cy+r,outline=self.c["line"],width=1)
        angle=(self.anim_phase*3)%360; rad=math.radians(angle)
        c.create_line(cx,cy,cx+70*math.cos(rad),cy+70*math.sin(rad),fill=col,width=2)
        c.create_oval(cx-5,cy-5,cx+5,cy+5,fill=col,outline="")
        for i in range(18):
            x=(i*73+self.anim_phase*2)%w; y=(i*37+int(math.sin(self.anim_phase/10+i)*20))%h
            c.create_oval(x-2,y-2,x+2,y+2,fill=self.c["accent2"],outline="")

    def _get_stats(self):
        stats={"cpu":"N/A","ram":"N/A","disk":"N/A"}
        if PSUTIL_OK:
            try:
                stats["cpu"]=f"{psutil.cpu_percent(interval=None):.0f}%"
                stats["ram"]=f"{psutil.virtual_memory().percent:.0f}%"
                stats["disk"]=f"{psutil.disk_usage(str(Path.home().anchor or '/')).percent:.0f}%"
            except Exception: pass
        return stats

    def page_system_monitor(self):
        self.section(self.content,"LIVE SYSTEM TELEMETRY","Refreshes automatically when available")
        row=tk.Frame(self.content,bg=self.c["bg"]); row.pack(fill="x",pady=8)
        self.monitor_labels={}
        for key,title in [("cpu","CPU UTILIZATION"),("ram","MEMORY UTILIZATION"),("disk","DISK UTILIZATION")]:
            f=tk.Frame(row,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]); f.pack(side="left",fill="x",expand=True,padx=(0,12))
            tk.Label(f,text=title,font=("Segoe UI",9,"bold"),fg=self.c["muted"],bg=self.c["panel"]).pack(anchor="w",padx=18,pady=(16,6))
            val=tk.Label(f,text="--",font=("Segoe UI",30,"bold"),fg=self.c["accent"],bg=self.c["panel"]); val.pack(anchor="w",padx=18)
            bar=ttk.Progressbar(f,maximum=100,length=240); bar.pack(fill="x",padx=18,pady=14)
            self.monitor_labels[key]=(val,bar)
        info=tk.Frame(self.content,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]); info.pack(fill="both",expand=True,pady=12)
        tk.Label(info,text="DEVICE INFORMATION",font=("Segoe UI",11,"bold"),fg=self.c["fg"],bg=self.c["panel"]).pack(anchor="w",padx=18,pady=14)
        details=[("Operating system",platform.platform()),("Processor",platform.processor() or "Not reported by OS"),("Machine",platform.machine()),("Hostname",platform.node()),("Python",sys.version.split()[0]),("Monitoring backend","psutil" if PSUTIL_OK else "Basic mode — install psutil for live metrics")]
        for k,v in details:
            r=tk.Frame(info,bg=self.c["panel"]); r.pack(fill="x",padx=18,pady=5)
            tk.Label(r,text=k.upper(),width=22,anchor="w",font=("Consolas",8),fg=self.c["muted"],bg=self.c["panel"]).pack(side="left")
            tk.Label(r,text=v,anchor="w",font=("Segoe UI",9),fg=self.c["fg"],bg=self.c["panel"]).pack(side="left")
        if not PSUTIL_OK:
            self.button(info,"INSTALL OPTIONAL MONITORING (see README)",lambda:messagebox.showinfo("psutil","Run: python -m pip install psutil")).pack(anchor="w",padx=18,pady=15)
        self.refresh_monitor()

    def refresh_monitor(self):
        if self.current_page!="System Monitor": return
        s=self._get_stats()
        for k,(lab,bar) in self.monitor_labels.items():
            val=s[k]; lab.config(text=val)
            try: bar["value"]=float(val.strip("%"))
            except Exception: bar["value"]=0
        self.after(1800,self.refresh_monitor)

    def page_terminal(self):
        self.section(self.content,"LOCAL TERMINAL SIMULATOR","Safe built-in commands • does not execute arbitrary shell scripts")
        outer=tk.Frame(self.content,bg="#02070b",highlightthickness=1,highlightbackground=self.c["accent"]); outer.pack(fill="both",expand=True)
        header=tk.Frame(outer,bg="#07141b"); header.pack(fill="x")
        tk.Label(header,text="● ● ●     CYBERDEX CONSOLE  //  LOCAL SESSION",font=("Consolas",9,"bold"),fg=self.c["accent"],bg="#07141b").pack(anchor="w",padx=14,pady=10)
        self.term=tk.Text(outer,bg="#02070b",fg="#9dffe1",insertbackground="#9dffe1",font=("Consolas",10),bd=0,wrap="word",padx=14,pady=12)
        self.term.pack(fill="both",expand=True)
        self.term.insert("end","CYBERDEX LOCAL CONSOLE v1.0\nType 'help' to view supported commands.\n\noperator@cyberdex:~$ ")
        self.term_input=tk.Entry(outer,bg="#07141b",fg="#eaffff",insertbackground="#19f5d0",font=("Consolas",10),bd=0)
        self.term_input.pack(fill="x",padx=12,pady=(0,12),ipady=9)
        self.term_input.bind("<Return>",self.run_terminal)
        self.term_input.focus_set()

    def run_terminal(self,event=None):
        cmd=self.term_input.get().strip(); self.term_input.delete(0,"end")
        if not cmd: return
        self.term.insert("end",cmd+"\n")
        parts=cmd.split(); op=parts[0].lower(); arg=" ".join(parts[1:])
        out=""
        if op=="help":
            out="COMMANDS: help, clear, date, time, whoami, hostname, pwd, ls, sysinfo, cpu, ram, disk, ping <host>, hash <file-path>, theme <name>, open <folder-path>\nNote: commands are restricted; arbitrary shell execution is disabled."
        elif op=="clear": self.term.delete("1.0","end"); self.term_input.focus_set(); return
        elif op=="date": out=datetime.now().strftime("%A, %d %B %Y")
        elif op=="time": out=datetime.now().strftime("%H:%M:%S")
        elif op=="whoami": out=self.settings.get("username","operator")
        elif op=="hostname": out=platform.node()
        elif op=="pwd": out=str(Path.cwd())
        elif op=="ls":
            target=Path(arg).expanduser() if arg else Path.cwd()
            try: out="\n".join(("DIR  " if p.is_dir() else "FILE ") + p.name for p in sorted(target.iterdir())[:100]) or "(empty)"
            except Exception as e: out=f"Cannot list folder: {e}"
        elif op=="sysinfo": out=f"{platform.system()} {platform.release()} | {platform.machine()} | Python {sys.version.split()[0]}"
        elif op=="cpu": out=self._get_stats()["cpu"]
        elif op=="ram": out=self._get_stats()["ram"]
        elif op=="disk": out=self._get_stats()["disk"]
        elif op=="ping":
            if not arg: out="Usage: ping <hostname>"
            else:
                try:
                    # A single bounded ping; network access is required.
                    flag="-n" if sys.platform.startswith("win") else "-c"
                    res=subprocess.run(["ping",flag,"1",arg],capture_output=True,text=True,timeout=5)
                    out=(res.stdout or res.stderr)[-1200:] or f"Ping exit code: {res.returncode}"
                except Exception as e: out=f"Ping unavailable: {e}"
        elif op=="hash":
            try:
                p=Path(" ".join(parts[1:]).strip('"')).expanduser()
                h=hashlib.sha256()
                with p.open("rb") as f:
                    for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
                out=f"SHA-256  {h.hexdigest()}"
            except Exception as e: out=f"Hash error: {e}"
        elif op=="theme":
            name=arg.strip()
            if name in THEMES: self.apply_theme(name); out=f"Theme changed to {name}"
            else: out="Available themes: "+", ".join(THEMES)
        elif op=="open":
            p=Path(arg).expanduser()
            if p.exists() and p.is_dir():
                try:
                    if sys.platform.startswith("win"): os.startfile(str(p))
                    elif sys.platform=="darwin": subprocess.Popen(["open",str(p)])
                    else: subprocess.Popen(["xdg-open",str(p)])
                    out=f"Opened {p}"
                except Exception as e: out=str(e)
            else: out="Folder not found."
        else: out=f"Unknown command: {op}. Type help."
        self.term.insert("end",out+"\n\noperator@cyberdex:~$ "); self.term.see("end")
        self.play_sound("typing"); self.term_input.focus_set()

    def page_network_center(self):
        self.section(self.content,"NETWORK DIAGNOSTICS","Network checks require a connection; other modules work offline")
        grid=tk.Frame(self.content,bg=self.c["bg"]); grid.pack(fill="x")
        self.card(grid,"HOSTNAME",platform.node() or "LOCAL","Device name").pack(side="left",fill="x",expand=True,padx=(0,10))
        try: ip=socket.gethostbyname(socket.gethostname())
        except Exception: ip="Unavailable"
        self.card(grid,"LOCAL IP",ip,"Local network address").pack(side="left",fill="x",expand=True,padx=(0,10))
        self.card(grid,"DNS BACKEND","SOCKET","Python standard library").pack(side="left",fill="x",expand=True)
        panel=tk.Frame(self.content,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]); panel.pack(fill="both",expand=True,pady=15)
        tk.Label(panel,text="PING / DNS LOOKUP",font=("Segoe UI",11,"bold"),fg=self.c["fg"],bg=self.c["panel"]).pack(anchor="w",padx=18,pady=(18,8))
        entry=tk.Entry(panel,font=("Consolas",11),bg=self.c["panel2"],fg=self.c["fg"],insertbackground=self.c["accent"],bd=0)
        entry.pack(fill="x",padx=18,ipady=10); entry.insert(0,"example.com")
        result=tk.Text(panel,height=12,bg="#030a12",fg=self.c["accent"],font=("Consolas",9),bd=0); result.pack(fill="both",expand=True,padx=18,pady=12)
        def run_dns():
            host=entry.get().strip()
            if not host: return
            result.delete("1.0","end"); result.insert("end",f"Resolving {host} ...\n")
            def worker():
                try:
                    infos=socket.getaddrinfo(host,None)
                    lines=sorted({i[4][0] for i in infos})
                    msg="DNS RESULT\n"+"\n".join(lines)
                except Exception as e: msg=f"DNS lookup failed: {e}"
                self.after(0,lambda:(result.insert("end",msg+"\n"),self.play_sound("notification")))
            threading.Thread(target=worker,daemon=True).start()
        self.button(panel,"RUN DNS LOOKUP",run_dns,True).pack(anchor="w",padx=18,pady=(0,18))

    def page_security_lab(self):
        self.section(self.content,"SECURITY LAB","Local security utilities • no credentials are transmitted")
        panel=tk.Frame(self.content,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]); panel.pack(fill="x",pady=6)
        tk.Label(panel,text="SECURE PASSWORD GENERATOR",font=("Segoe UI",11,"bold"),fg=self.c["fg"],bg=self.c["panel"]).pack(anchor="w",padx=18,pady=(16,8))
        row=tk.Frame(panel,bg=self.c["panel"]); row.pack(fill="x",padx=18,pady=8)
        length=tk.IntVar(value=20)
        tk.Label(row,text="Length",fg=self.c["muted"],bg=self.c["panel"]).pack(side="left")
        tk.Spinbox(row,from_=8,to=64,textvariable=length,width=5,bg=self.c["panel2"],fg=self.c["fg"],buttonbackground=self.c["panel2"]).pack(side="left",padx=10)
        out=tk.Entry(panel,font=("Consolas",13),bg=self.c["panel2"],fg=self.c["accent"],insertbackground=self.c["accent"],bd=0)
        out.pack(fill="x",padx=18,pady=8,ipady=10)
        def generate():
            import secrets,string
            alphabet=string.ascii_letters+string.digits+"!@#$%^&*()-_=+"
            pw="".join(secrets.choice(alphabet) for _ in range(max(8,min(64,length.get()))))
            out.delete(0,"end"); out.insert(0,pw); self.play_sound("notification")
        def copy():
            self.clipboard_clear(); self.clipboard_append(out.get()); self.play_sound("click")
        actions=tk.Frame(panel,bg=self.c["panel"]); actions.pack(anchor="w",padx=18,pady=(4,16))
        self.button(actions,"GENERATE PASSWORD",generate,True).pack(side="left",padx=(0,8))
        self.button(actions,"COPY",copy).pack(side="left")
        hashpanel=tk.Frame(self.content,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]); hashpanel.pack(fill="both",expand=True,pady=12)
        tk.Label(hashpanel,text="FILE INTEGRITY // SHA-256",font=("Segoe UI",11,"bold"),fg=self.c["fg"],bg=self.c["panel"]).pack(anchor="w",padx=18,pady=16)
        chosen=tk.StringVar(value="No file selected")
        tk.Label(hashpanel,textvariable=chosen,fg=self.c["muted"],bg=self.c["panel"],wraplength=800).pack(anchor="w",padx=18)
        hashout=tk.Text(hashpanel,height=4,bg="#030a12",fg=self.c["accent"],font=("Consolas",9),bd=0); hashout.pack(fill="x",padx=18,pady=12)
        def pick():
            path=filedialog.askopenfilename()
            if not path:return
            chosen.set(path); h=hashlib.sha256()
            try:
                with open(path,"rb") as f:
                    for ch in iter(lambda:f.read(1024*1024),b""):h.update(ch)
                hashout.delete("1.0","end");hashout.insert("end",h.hexdigest())
                self.play_sound("notification")
            except Exception as e: messagebox.showerror("Hash error",str(e))
        self.button(hashpanel,"CHOOSE FILE & CALCULATE HASH",pick,True).pack(anchor="w",padx=18,pady=(0,18))

    def page_developer_studio(self):
        self.section(self.content,"DEVELOPER STUDIO","Lightweight Python editor • run scripts with your local Python interpreter")
        bar=tk.Frame(self.content,bg=self.c["bg"]); bar.pack(fill="x",pady=(0,8))
        editor=tk.Text(self.content,bg="#050b14",fg="#c8fff0",insertbackground=self.c["accent"],font=("Consolas",10),bd=0,wrap="none",undo=True)
        editor.pack(fill="both",expand=True)
        editor.insert("1.0",'# CYBERDEX Python Studio\nprint("Hello, operator!")\n')
        output=tk.Text(self.content,height=7,bg=self.c["panel"],fg=self.c["accent"],font=("Consolas",9),bd=0); output.pack(fill="x",pady=8)
        path=[None]
        def open_file():
            p=filedialog.askopenfilename(filetypes=[("Python files","*.py"),("All files","*.*")])
            if p:
                try: editor.delete("1.0","end");editor.insert("1.0",Path(p).read_text(encoding="utf-8"));path[0]=p
                except Exception as e: messagebox.showerror("Open error",str(e))
        def save_file():
            p=path[0] or filedialog.asksaveasfilename(defaultextension=".py",filetypes=[("Python files","*.py")])
            if p:
                Path(p).write_text(editor.get("1.0","end-1c"),encoding="utf-8");path[0]=p;self.play_sound("notification")
        def run_code():
            save_file()
            if not path[0]:return
            try:
                res=subprocess.run([sys.executable,path[0]],capture_output=True,text=True,timeout=15,cwd=str(Path(path[0]).parent))
                output.delete("1.0","end");output.insert("end",(res.stdout or "")+(res.stderr or "")+f"\n[exit code {res.returncode}]")
                self.play_sound("notification")
            except subprocess.TimeoutExpired: output.insert("end","\nExecution stopped: 15-second time limit.")
            except Exception as e: output.insert("end",str(e))
        self.button(bar,"OPEN",open_file).pack(side="left",padx=(0,8))
        self.button(bar,"SAVE",save_file).pack(side="left",padx=(0,8))
        self.button(bar,"RUN PYTHON",run_code,True).pack(side="left")

    def page_file_center(self):
        self.section(self.content,"FILE & STORAGE CENTER","Browse real folders on this computer")
        bar=tk.Frame(self.content,bg=self.c["bg"]); bar.pack(fill="x",pady=8)
        path=tk.StringVar(value=str(Path.home()))
        entry=tk.Entry(bar,textvariable=path,bg=self.c["panel2"],fg=self.c["fg"],insertbackground=self.c["accent"],bd=0,font=("Consolas",10))
        entry.pack(side="left",fill="x",expand=True,ipady=9,padx=(0,8))
        tree=ttk.Treeview(self.content,columns=("kind","size"),show="tree headings")
        tree.heading("#0",text="NAME");tree.heading("kind",text="TYPE");tree.heading("size",text="SIZE")
        tree.column("#0",width=500);tree.column("kind",width=120);tree.column("size",width=140)
        tree.pack(fill="both",expand=True,pady=10)
        def browse(p=None):
            folder=Path(p or path.get()).expanduser()
            tree.delete(*tree.get_children())
            try:
                path.set(str(folder))
                for item in sorted(folder.iterdir(),key=lambda x:(not x.is_dir(),x.name.lower()))[:500]:
                    try: size=f"{item.stat().st_size:,} B" if item.is_file() else "—"
                    except Exception:size="?"
                    tree.insert("", "end",text=item.name,values=("Folder" if item.is_dir() else "File",size),tags=(str(item),))
            except Exception as e: messagebox.showerror("Browse error",str(e))
        def selected(event=None):
            sel=tree.selection()
            if sel:
                item=Path(tree.item(sel[0],"tags")[0])
                if item.is_dir():browse(item)
                else:
                    try:
                        if sys.platform.startswith("win"):os.startfile(str(item))
                        elif sys.platform=="darwin":subprocess.Popen(["open",str(item)])
                        else:subprocess.Popen(["xdg-open",str(item)])
                    except Exception as e:messagebox.showerror("Open error",str(e))
        tree.bind("<Double-1>",selected)
        self.button(bar,"GO",lambda:browse(),True).pack(side="left")
        self.button(bar,"HOME",lambda:browse(Path.home())).pack(side="left",padx=8)
        browse()

    def page_themes_and_settings(self):
        self.section(self.content,"PERSONALIZE YOUR DECK","Changes are saved locally in data/settings.json")
        panel=tk.Frame(self.content,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]);panel.pack(fill="x",pady=6)
        tk.Label(panel,text="COLOR SYSTEMS",font=("Segoe UI",11,"bold"),fg=self.c["fg"],bg=self.c["panel"]).pack(anchor="w",padx=18,pady=16)
        for name,theme in THEMES.items():
            b=tk.Button(panel,text="   "+name+"   ",command=lambda n=name:self.apply_theme(n),bg=theme["bg"],fg=theme["accent"],activebackground=theme["panel2"],bd=1,relief="solid",font=("Segoe UI",10,"bold"),padx=10,pady=12)
            b.pack(side="left",padx=8,pady=(0,18))
        toggles=tk.Frame(self.content,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]);toggles.pack(fill="x",pady=12)
        tk.Label(toggles,text="EXPERIENCE",font=("Segoe UI",11,"bold"),fg=self.c["fg"],bg=self.c["panel"]).pack(anchor="w",padx=18,pady=16)
        sound=tk.BooleanVar(value=self.sound_enabled); anim=tk.BooleanVar(value=self.animation_enabled)
        def save_toggles():
            self.sound_enabled=sound.get();self.animation_enabled=anim.get()
            self.settings.update({"sound":self.sound_enabled,"animation":self.animation_enabled});save_settings(self.settings)
            messagebox.showinfo("Settings saved","Your preferences have been saved locally.")
        tk.Checkbutton(toggles,text="Enable sound effects",variable=sound,bg=self.c["panel"],fg=self.c["fg"],selectcolor=self.c["panel2"],activebackground=self.c["panel"],activeforeground=self.c["accent"]).pack(anchor="w",padx=18,pady=5)
        tk.Checkbutton(toggles,text="Enable animated HUD background",variable=anim,bg=self.c["panel"],fg=self.c["fg"],selectcolor=self.c["panel2"],activebackground=self.c["panel"],activeforeground=self.c["accent"]).pack(anchor="w",padx=18,pady=5)
        self.button(toggles,"SAVE PREFERENCES",save_toggles,True).pack(anchor="w",padx=18,pady=16)
        note=tk.Label(self.content,text="Sound playback uses pygame when installed. On Windows, bundled WAV effects can fall back to winsound. For best cross-platform audio, install pygame.",fg=self.c["muted"],bg=self.c["bg"],font=("Segoe UI",9),wraplength=900,justify="left")
        note.pack(anchor="w",pady=10)

    def apply_theme(self,name):
        if name not in THEMES:return
        self.theme_name=name;self.c=THEMES[name];self.settings["theme"]=name;save_settings(self.settings)
        # Rebuild UI using selected palette
        self.configure(bg=self.c["bg"])
        for w in self.winfo_children():w.destroy()
        self.images={}
        self._build_shell();self.show_page(self.current_page if self.current_page in self.nav_buttons else "Dashboard")

    def page_about_cyberdex(self):
        self.section(self.content,"ABOUT THE WORKSTATION","A local-first Python desktop environment")
        panel=tk.Frame(self.content,bg=self.c["panel"],highlightthickness=1,highlightbackground=self.c["line"]);panel.pack(fill="both",expand=True)
        tk.Label(panel,text="◈  CYBERDEX",font=("Segoe UI",30,"bold"),fg=self.c["accent"],bg=self.c["panel"]).pack(pady=(55,12))
        tk.Label(panel,text="A CYBERPUNK WORKSTATION FOR YOUR DESKTOP",font=("Consolas",11,"bold"),fg=self.c["fg"],bg=self.c["panel"]).pack()
        tk.Label(panel,text="Built with Python + Tkinter. No database. No cloud account.\nLocal assets, local settings, and offline-first tools.",font=("Segoe UI",11),fg=self.c["muted"],bg=self.c["panel"],justify="center").pack(pady=18)
        tk.Label(panel,text=f"Python {sys.version.split()[0]}  •  Pillow {'OK' if PIL_OK else 'missing'}  •  psutil {'OK' if PSUTIL_OK else 'missing'}  •  pygame {'OK' if PYGAME_OK else 'missing'}",font=("Consolas",9),fg=self.c["accent2"],bg=self.c["panel"]).pack(pady=10)
        tk.Label(panel,text="Terminal is intentionally restricted to a safe command set.\nPython scripts launched from the editor run as your current OS user; only run code you trust.",font=("Segoe UI",9),fg=self.c["muted"],bg=self.c["panel"],justify="center").pack(pady=18)

    def _tick(self):
        if not self.winfo_exists():return
        self.clock.config(text=datetime.now().strftime("%a %d %b  •  %H:%M:%S"))
        self.anim_phase+=1
        if self.animation_enabled and self.current_page=="Dashboard": self._draw_viz()
        self.after(100,self._tick)

if __name__=="__main__":
    app=CyberDex()
    app.mainloop()
