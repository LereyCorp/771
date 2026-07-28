# ============================================
# gui.py (финальный)
# ============================================
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading, json, os, time, sys
from bot import VieFaucetBot

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VieFaucet Auto Clicker v3.0")
        self.geometry("1250x950")
        self.minsize(1150, 900)
        self.configure(bg="#0d1117")
        self.bot = None; self.bot_thread = None
        self.colors = {"bg": "#0d1117", "card": "#161b22", "border": "#30363d", "text": "#c9d1d9", "text_secondary": "#8b949e", "accent": "#58a6ff", "green": "#3fb950", "red": "#f85149", "orange": "#d2991d", "input_bg": "#0d1117", "input_border": "#30363d"}
        self.email_var = tk.StringVar(); self.password_var = tk.StringVar(); self.sctg_var = tk.StringVar(); self.proxy_var = tk.StringVar()
        self.window_var = tk.BooleanVar(value=True); self.iframe_var = tk.BooleanVar(value=True); self.youtube_var = tk.BooleanVar(value=True)
        self.faucet_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ожидание запуска"); self.balance_var = tk.StringVar(value="---")
        self.create_widgets(); self.load_config()

    def create_widgets(self):
        main = tk.Frame(self, bg=self.colors["bg"]); main.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        tk.Label(main, text="🎯  VIEFAUCET AUTO CLICKER", bg=self.colors["bg"], fg=self.colors["accent"], font=("Segoe UI", 16, "bold")).pack(anchor=tk.W, pady=(0, 10))
        content = tk.Frame(main, bg=self.colors["bg"]); content.pack(fill=tk.BOTH, expand=True)
        left = tk.Frame(content, bg=self.colors["bg"], width=360); left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10)); left.pack_propagate(False)
        
        card1 = tk.Frame(left, bg=self.colors["card"], padx=16, pady=12, highlightbackground=self.colors["border"], highlightthickness=1); card1.pack(fill=tk.X, pady=(0, 8))
        tk.Label(card1, text="🔑  АККАУНТ", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 8))
        for label_text, var, show in [("📧  Email", self.email_var, None), ("🔒  Пароль", self.password_var, "•"), ("🗝   SCTG Key", self.sctg_var, None), ("🌐  Proxy", self.proxy_var, None)]:
            tk.Label(card1, text=label_text, bg=self.colors["card"], fg=self.colors["text_secondary"], font=("Segoe UI", 9)).pack(anchor=tk.W)
            tk.Entry(card1, textvariable=var, show=show or "", bg=self.colors["input_bg"], fg=self.colors["text"], insertbackground=self.colors["text"], relief=tk.FLAT, font=("Segoe UI", 9), highlightbackground=self.colors["input_border"], highlightthickness=1).pack(fill=tk.X, pady=(2, 8), ipady=3)
        tk.Button(card1, text="💾  Сохранить настройки", command=self.save_config, bg=self.colors["accent"], fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, cursor="hand2", padx=14, pady=4).pack(anchor=tk.W, pady=(6, 0))
        
        card2 = tk.Frame(left, bg=self.colors["card"], padx=16, pady=12, highlightbackground=self.colors["border"], highlightthickness=1); card2.pack(fill=tk.X, pady=(0, 8))
        tk.Label(card2, text="📋  PTC", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 6))
        for text, var in [("🪟  Window PTC", self.window_var), ("📄  Iframe PTC", self.iframe_var), ("▶   YouTube PTC", self.youtube_var)]:
            tk.Checkbutton(card2, text=text, variable=var, bg=self.colors["card"], fg=self.colors["text"], selectcolor=self.colors["bg"], activebackground=self.colors["card"], activeforeground=self.colors["text"], font=("Segoe UI", 9)).pack(anchor=tk.W, pady=2)
        tk.Label(card2, text="🚰  FAUCET", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(10, 6))
        tk.Checkbutton(card2, text="Faucet (интервал 4:20)", variable=self.faucet_var, bg=self.colors["card"], fg=self.colors["text"], selectcolor=self.colors["bg"], activebackground=self.colors["card"], activeforeground=self.colors["text"], font=("Segoe UI", 9)).pack(anchor=tk.W, pady=2)
        
        card3 = tk.Frame(left, bg=self.colors["card"], padx=16, pady=10, highlightbackground=self.colors["border"], highlightthickness=1); card3.pack(fill=tk.X, pady=(0, 6))
        tk.Label(card3, text="СТАТУС", bg=self.colors["card"], fg=self.colors["text_secondary"], font=("Segoe UI", 8)).pack(anchor=tk.W)
        tk.Label(card3, textvariable=self.status_var, bg=self.colors["card"], fg=self.colors["green"], font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(3, 0))
        
        card4 = tk.Frame(left, bg=self.colors["card"], padx=16, pady=10, highlightbackground=self.colors["border"], highlightthickness=1); card4.pack(fill=tk.X, pady=(0, 8))
        tk.Label(card4, text="БАЛАНС", bg=self.colors["card"], fg=self.colors["text_secondary"], font=("Segoe UI", 8)).pack(anchor=tk.W)
        tk.Label(card4, textvariable=self.balance_var, bg=self.colors["card"], fg=self.colors["green"], font=("Segoe UI", 13, "bold"), wraplength=320).pack(anchor=tk.W, pady=(3, 0))
        
        card5 = tk.Frame(left, bg=self.colors["card"], padx=16, pady=14, highlightbackground=self.colors["border"], highlightthickness=1); card5.pack(fill=tk.X)
        self.start_btn = tk.Button(card5, text="▶   ЗАПУСТИТЬ", command=self.start_bot, bg=self.colors["green"], fg="white", font=("Segoe UI", 11, "bold"), relief=tk.FLAT, cursor="hand2", height=2, activebackground="#2ea043")
        self.start_btn.pack(fill=tk.X, pady=(0, 8))
        self.stop_btn = tk.Button(card5, text="■   ОСТАНОВИТЬ", command=self.stop_bot, state=tk.DISABLED, bg="#484f58", fg="white", font=("Segoe UI", 11, "bold"), relief=tk.FLAT, cursor="hand2", height=2, activebackground=self.colors["red"])
        self.stop_btn.pack(fill=tk.X, pady=(0, 8))
        
        right = tk.Frame(content, bg=self.colors["card"], padx=12, pady=10, highlightbackground=self.colors["border"], highlightthickness=1)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        h = tk.Frame(right, bg=self.colors["card"]); h.pack(fill=tk.X, pady=(0, 6))
        tk.Label(h, text="📝  ЛОГИ", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(h, text="🗑  Очистить", command=self.clear_logs, bg=self.colors["input_bg"], fg=self.colors["text_secondary"], font=("Segoe UI", 8), relief=tk.FLAT, cursor="hand2", padx=10).pack(side=tk.RIGHT)
        self.log_text = scrolledtext.ScrolledText(right, wrap=tk.WORD, bg=self.colors["bg"], fg=self.colors["text"], insertbackground=self.colors["text"], font=("Consolas", 9), relief=tk.FLAT, highlightthickness=0)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        for tag, color in [("INFO", self.colors["text"]), ("WARN", self.colors["orange"]), ("ERROR", self.colors["red"]), ("SUCCESS", self.colors["green"]), ("FAUCET", self.colors["accent"])]:
            self.log_text.tag_config(tag, foreground=color)

    def log_callback(self, message, level="INFO"):
        if "[FAUCET]" in message: level = "FAUCET"
        self.log_text.insert(tk.END, message + "\n", level); self.log_text.see(tk.END)
        print(message); sys.stdout.flush()

    def balance_callback(self, balance): self.balance_var.set(balance)
    def clear_logs(self): self.log_text.delete(1.0, tk.END)

    def load_config(self):
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
                for key, var in [("email", self.email_var), ("password", self.password_var), ("sctg_key", self.sctg_var), ("proxy", self.proxy_var)]:
                    var.set(config.get(key, ""))

    def save_config(self):
        config = {"email": self.email_var.get(), "password": self.password_var.get(), "sctg_key": self.sctg_var.get(), "proxy": self.proxy_var.get()}
        with open("config.json", "w") as f: json.dump(config, f, indent=4)
        self.log_callback("[OK] Настройки сохранены", "SUCCESS")

    def _get_selected_types(self):
        types = []
        if self.window_var.get(): types.append("window")
        if self.iframe_var.get(): types.append("iframe")
        if self.youtube_var.get(): types.append("youtube")
        return types

    def start_bot(self):
        if not self.email_var.get() or not self.password_var.get() or not self.sctg_var.get():
            return messagebox.showwarning("⚠ Предупреждение", "Заполните все поля!")
        if not self._get_selected_types() and not self.faucet_var.get():
            return messagebox.showwarning("⚠ Предупреждение", "Выберите PTC или Faucet!")
        self.save_config()
        self.start_btn.config(state=tk.DISABLED, bg="#484f58")
        self.stop_btn.config(state=tk.NORMAL, bg=self.colors["red"])
        self.status_var.set("✅ Работает...")
        self.bot = VieFaucetBot(log_callback=self.log_callback, balance_callback=self.balance_callback)
        self.bot.selected_types = self._get_selected_types()
        self.bot.enable_faucet = self.faucet_var.get()
        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()

    def _run_bot(self):
        try: self.bot.run()
        except Exception as e: self.after(0, self.log_callback, f"[ERROR] {str(e)}", "ERROR")
        finally: self.after(0, self._on_bot_stopped)

    def _on_bot_stopped(self):
        self.start_btn.config(state=tk.NORMAL, bg=self.colors["green"])
        self.stop_btn.config(state=tk.DISABLED, bg="#484f58")
        self.status_var.set("⏸ Остановлен")

    def stop_bot(self):
        if self.bot:
            self.bot.running = False
            self.status_var.set("⏳ Останавливается...")
            threading.Thread(target=self._stop_bot_thread, daemon=True).start()

    def _stop_bot_thread(self):
        if self.bot and self.bot.browser:
            try: self.bot.browser.quit()
            except: pass
        self.after(0, lambda: self.status_var.set("⏸ Остановлен"))

    def on_closing(self):
        if self.bot and self.bot.running:
            if messagebox.askokcancel("🚪 Выход", "Бот работает. Остановить и выйти?"):
                self.stop_bot(); time.sleep(1)
        self.destroy()