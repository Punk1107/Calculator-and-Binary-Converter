"""
Professional Advanced Calculator & Number System Converter
A production-ready Tkinter application with modern UX/UI design

Features:
- Scientific Calculator with live-preview and history
- Number System Converter (Binary, Decimal, Hex, Octal) with nibble grouping
- Persistent expression history (atomic JSON writes, debounced saves)
- Persistent settings (theme, window geometry)
- Keyboard shortcuts (Ctrl+T = theme, Ctrl+Z = backspace, Escape = clear)
- Responsive dark / light themes applied via widget registry
- Memory functions (M+, M−, MR, MC)
- Clickable history entries
- Status bar with last-operation elapsed time
- Per-row copy buttons in converter
- Bit-length annotation on binary output
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import ast
import re
import json
import os
import time
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Callable

# ---------------------------------------------------------------------------
# Tuneable constants
# ---------------------------------------------------------------------------
DEBOUNCE_PREVIEW_MS: int = 150    # live-preview delay (ms)
STATUS_CLEAR_MS: int = 4_000      # auto-clear status bar after this delay
TOOLTIP_DELAY_MS: int = 600       # tooltip show delay (ms)
MAX_HISTORY: int = 100            # maximum stored history entries
HISTORY_DISPLAY: int = 20         # entries shown in the panel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("calculator")


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_APP_DIR = os.path.join(os.path.expanduser("~"), ".calculator")
_HISTORY_FILE = os.path.join(_APP_DIR, "calc_history.json")
_SETTINGS_FILE = os.path.join(_APP_DIR, "settings.json")
os.makedirs(_APP_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# SafeEvaluator
# ---------------------------------------------------------------------------
class SafeEvaluator:
    """Secure mathematical expression evaluator — no exec, no builtins."""

    ALLOWED_NAMES: Dict = {
        name: getattr(math, name)
        for name in dir(math)
        if not name.startswith("__")
    }
    ALLOWED_NAMES.update(
        {
            "abs": abs,
            "round": round,
            "pow": pow,
            "min": min,
            "max": max,
            "e": math.e,          # Euler's number
            "pi": math.pi,        # already in math namespace but explicit
            "inf": math.inf,
        }
    )
    # Frozenset for O(1) name lookup during AST walk
    _ALLOWED_NAME_SET: frozenset = frozenset(ALLOWED_NAMES)

    _BASE_NODES = [
        ast.Expression,
        ast.Call,
        ast.Name,
        ast.Load,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
        ast.Pow, ast.USub, ast.UAdd,
        ast.LShift, ast.RShift, ast.BitXor, ast.BitAnd, ast.BitOr,
        ast.FloorDiv,
        ast.Tuple,
        ast.List,
    ]
    for _node in ["Num", "Str", "Bytes", "NameConstant"]:
        if hasattr(ast, _node):
            _BASE_NODES.append(getattr(ast, _node))
    ALLOWED_NODES = tuple(_BASE_NODES)

    @classmethod
    def evaluate(cls, expr: str) -> float:
        """Safely evaluate a mathematical expression string."""
        if not expr or not expr.strip():
            raise ValueError("Empty expression")
        if len(expr) > 5000:
            raise ValueError("Expression too long")

        expr = (
            expr.strip()
            .replace("×", "*")
            .replace("÷", "/")
            .replace("^", "**")
            .replace("π", "pi")
        )

        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError as exc:
            raise ValueError(f"Syntax error: {exc}") from exc

        for node in ast.walk(tree):
            if not isinstance(node, cls.ALLOWED_NODES):
                raise ValueError(
                    f"Unsupported operation: {type(node).__name__}"
                )
            if isinstance(node, ast.Name) and node.id not in cls._ALLOWED_NAME_SET:
                raise ValueError(f"Unknown name: '{node.id}'")

        compiled = compile(tree, "<safe>", "eval")
        result = eval(compiled, {"__builtins__": {}}, cls.ALLOWED_NAMES)  # noqa: S307

        if isinstance(result, complex):
            if result.imag == 0:
                return result.real
            raise ValueError("Complex result not supported")

        return result


# ---------------------------------------------------------------------------
# Settings (persist theme + geometry)
# ---------------------------------------------------------------------------
class Settings:
    """Lightweight JSON settings store."""

    _data: Dict = {}

    @classmethod
    def load(cls):
        try:
            if os.path.exists(_SETTINGS_FILE):
                with open(_SETTINGS_FILE, "r", encoding="utf-8") as fh:
                    cls._data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            cls._data = {}

    @classmethod
    def save(cls):
        tmp = _SETTINGS_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(cls._data, fh, indent=2)
            os.replace(tmp, _SETTINGS_FILE)
        except OSError as exc:
            log.warning("settings save failed: %s", exc)

    @classmethod
    def get(cls, key, default=None):
        return cls._data.get(key, default)

    @classmethod
    def set(cls, key, value):
        cls._data[key] = value


# ---------------------------------------------------------------------------
# HistoryManager  (atomic writes + debounced save)
# ---------------------------------------------------------------------------
class HistoryManager:
    """Manage calculation history with debounced, atomic file persistence."""

    MAX = MAX_HISTORY
    DEBOUNCE_MS = 150

    def __init__(self):
        self.history: List[Dict] = []
        self._pending_save: Optional[str] = None   # after() id
        self._root: Optional[tk.Tk] = None         # set by app after init
        self._load()

    # ------------------------------------------------------------------
    def _load(self):
        try:
            if os.path.exists(_HISTORY_FILE):
                with open(_HISTORY_FILE, "r", encoding="utf-8") as fh:
                    self.history = json.load(fh)
        except (json.JSONDecodeError, OSError):
            self.history = []

    def _flush(self):
        """Perform the actual atomic write."""
        tmp = _HISTORY_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.history, fh, indent=2)
            os.replace(tmp, _HISTORY_FILE)
        except OSError as exc:
            log.warning("history save failed: %s", exc)
        self._pending_save = None

    def _schedule_save(self):
        """Debounce disk writes — only flush after DEBOUNCE_MS of silence."""
        if self._root is None:
            self._flush()
            return
        if self._pending_save is not None:
            self._root.after_cancel(self._pending_save)
        self._pending_save = self._root.after(self.DEBOUNCE_MS, self._flush)

    # ------------------------------------------------------------------
    def add(self, expression: str, result: str, elapsed_ms: float = 0.0):
        """Add a new entry to the history list."""
        entry = {
            "expression": expression,
            "result": result,
            "elapsed_ms": round(elapsed_ms, 3),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        self.history.insert(0, entry)
        if len(self.history) > self.MAX:
            self.history = self.history[: self.MAX]
        self._schedule_save()

    @staticmethod
    def friendly_time(iso: str) -> str:
        """Return a human-friendly relative label for an ISO timestamp."""
        try:
            dt = datetime.fromisoformat(iso)
            today = date.today()
            d = dt.date()
            if d == today:
                return dt.strftime("%H:%M")
            if d == today - timedelta(days=1):
                return f"Yesterday {dt.strftime('%H:%M')}"
            return dt.strftime("%d %b %H:%M")
        except Exception:
            return ""

    def get_recent(self, limit: int = HISTORY_DISPLAY) -> List[Dict]:
        """Return the most recent *limit* history entries."""
        return self.history[:limit]

    def clear(self):
        self.history = []
        self._flush()


# ---------------------------------------------------------------------------
# NumberConverter
# ---------------------------------------------------------------------------
class NumberConverter:
    """Number-system conversion with nibble grouping and signed support."""

    BASES = {
        "Binary": 2,
        "Octal": 8,
        "Decimal": 10,
        "Hexadecimal": 16,
    }

    _PATTERNS = {
        "Binary":      re.compile(r"^-?[01]+$"),
        "Octal":       re.compile(r"^-?[0-7]+$"),
        "Decimal":     re.compile(r"^-?\d+$"),
        "Hexadecimal": re.compile(r"^-?[0-9A-Fa-f]+$"),
    }

    @classmethod
    def validate_input(cls, value: str, base_name: str) -> bool:
        value = value.strip().replace(" ", "")
        if not value:
            return False
        pattern = cls._PATTERNS.get(base_name)
        return bool(pattern and pattern.match(value))

    @classmethod
    def convert(cls, value: str, from_base: str, to_base: str) -> str:
        value = value.strip().replace(" ", "")
        if not cls.validate_input(value, from_base):
            raise ValueError(f"Invalid {from_base} number: '{value}'")

        negative = value.startswith("-")
        raw = value.lstrip("-")

        decimal_val = int(raw, cls.BASES[from_base])
        if negative:
            decimal_val = -decimal_val

        sign = "-" if decimal_val < 0 else ""
        n = abs(decimal_val)

        if to_base == "Binary":
            raw_bits = bin(n)[2:]
            return sign + cls._group_nibbles(raw_bits)
        if to_base == "Octal":
            return sign + oct(n)[2:]
        if to_base == "Decimal":
            return str(decimal_val)
        if to_base == "Hexadecimal":
            return sign + hex(n)[2:].upper()
        return ""

    @staticmethod
    def _group_nibbles(bits: str) -> str:
        """Group binary digits into space-separated nibbles (right-aligned)."""
        pad = (4 - len(bits) % 4) % 4
        bits = "0" * pad + bits
        return " ".join(bits[i : i + 4] for i in range(0, len(bits), 4))

    @staticmethod
    def bit_length(decimal_val: int) -> int:
        if decimal_val == 0:
            return 1
        return decimal_val.bit_length()


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
class Theme:
    LIGHT = {
        "bg":           "#f3f4f6",
        "toolbar":      "#ffffff",
        "panel":        "#ffffff",
        "separator":    "#e5e7eb",
        "fg":           "#111827",
        "secondary_fg": "#6b7280",
        "btn_bg":       "#f9fafb",
        "btn_hover":    "#e5e7eb",
        "btn_active":   "#d1d5db",
        "accent":       "#2563eb",
        "accent_hover": "#1d4ed8",
        "border":       "#e5e7eb",
        "success":      "#10b981",
        "success_hover":"#059669",
        "error":        "#ef4444",
        "error_hover":  "#dc2626",
        "warning":      "#f59e0b",
        "display_bg":   "#f9fafb",
        "history_bg":   "#ffffff",
        "memory_bg":    "#fef3c7",
        "tag_expr":     "#6b7280",
        "tag_result":   "#111827",
        "status_bg":    "#f3f4f6",
        "status_fg":    "#4b5563",
        "valid":        "#10b981",
        "invalid":      "#ef4444",
    }

    DARK = {
        "bg":           "#111827",
        "toolbar":      "#1f2937",
        "panel":        "#1f2937",
        "separator":    "#374151",
        "fg":           "#f9fafb",
        "secondary_fg": "#9ca3af",
        "btn_bg":       "#374151",
        "btn_hover":    "#4b5563",
        "btn_active":   "#6b7280",
        "accent":       "#3b82f6",
        "accent_hover": "#60a5fa",
        "border":       "#374151",
        "success":      "#10b981",
        "success_hover":"#34d399",
        "error":        "#ef4444",
        "error_hover":  "#f87171",
        "warning":      "#f59e0b",
        "display_bg":   "#111827",
        "history_bg":   "#1f2937",
        "memory_bg":    "#78350f",
        "tag_expr":     "#9ca3af",
        "tag_result":   "#f9fafb",
        "status_bg":    "#1f2937",
        "status_fg":    "#9ca3af",
        "valid":        "#34d399",
        "invalid":      "#f87171",
    }

    @classmethod
    def get(cls, dark: bool) -> Dict:
        return cls.DARK if dark else cls.LIGHT


# ---------------------------------------------------------------------------
# ToolTip — lightweight delayed tooltip
# ---------------------------------------------------------------------------
class ToolTip:
    """Show a small tooltip window *TOOLTIP_DELAY_MS* ms after the mouse enters."""

    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text = text
        self._job: Optional[str] = None
        self._win: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._cancel, add="+")
        widget.bind("<ButtonPress>", self._cancel, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._job = self._widget.after(TOOLTIP_DELAY_MS, self._show)

    def _cancel(self, _event=None):
        if self._job:
            self._widget.after_cancel(self._job)
            self._job = None
        if self._win:
            self._win.destroy()
            self._win = None

    def _show(self):
        if self._win:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._win = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tw, text=self._text, justify="left",
            background="#ffffe0", foreground="#1a1a1a",
            relief="solid", borderwidth=1,
            font=("Segoe UI", 8), padx=6, pady=3,
        )
        lbl.pack()


# ---------------------------------------------------------------------------
# ModernButton — canvas-based, press animation, keyboard focus
# ---------------------------------------------------------------------------

# Button tooltip hints
_BUTTON_TIPS: Dict[str, str] = {
    "MC":  "Memory Clear",
    "MR":  "Memory Recall",
    "M+":  "Memory Add (current expression)",
    "M-":  "Memory Subtract (current expression)",
    "C":   "Clear all  [Esc]",
    "⌫":  "Backspace  [Ctrl+Z]",
    "=":   "Evaluate  [Enter]",
    "Ans": "Insert last answer",
    "√":   "Square root  √(x)",
    "x²":  "Square  x²",
    "xʸ":  "Power  x^y",
    "÷":   "Divide",
    "×":   "Multiply",
    "−":   "Subtract",
    "+":   "Add",
    "sin": "sin(x) — sine in radians",
    "cos": "cos(x) — cosine in radians",
    "tan": "tan(x) — tangent in radians",
    "ln":  "log(x) — natural logarithm",
    "log": "log10(x) — base-10 logarithm",
    "n!":  "factorial(x) — factorial",
    "(":   "Open parenthesis",
    ")":   "Close parenthesis",
    "±":   "Toggle sign of last number",
    ".":   "Decimal point",
}


class ModernButton(tk.Canvas):
    """Custom rounded button with hover/press animations and keyboard support."""

    RADIUS = 12
    ANIM_PRESS_OFFSET = 2   # shift down/right on press

    def __init__(
        self,
        parent,
        text: str,
        command: Callable,
        width: int = 60,
        height: int = 50,
        style: str = "default",
        controller=None,   # direct reference — no parent-walk needed
        **kwargs,
    ):
        super().__init__(
            parent, width=width, height=height,
            highlightthickness=0, **kwargs
        )
        self.text = text
        self.command = command
        self.style = style
        self._controller = controller
        self._hover = False
        self._pressed = False
        self._focused = False

        self.bind("<Button-1>",        self._on_press_start)
        self.bind("<ButtonRelease-1>", self._on_press_end)
        self.bind("<Enter>",           self._on_enter)
        self.bind("<Leave>",           self._on_leave)
        self.bind("<FocusIn>",         self._on_focus_in)
        self.bind("<FocusOut>",        self._on_focus_out)
        self.bind("<space>",           self._on_space)
        self.bind("<Return>",          self._on_space)
        self.configure(cursor="hand2")
        # Attach tooltip if a hint is defined
        tip = _BUTTON_TIPS.get(text)
        if tip:
            ToolTip(self, tip)
        self.draw()

    # ---- resolve theme ------------------------------------------------
    def _theme(self) -> Dict:
        if self._controller:
            return Theme.get(self._controller.dark_mode.get())
        # fallback: walk up
        w = self.master
        while w and not isinstance(w, CalculatorApp):
            w = w.master
        if w:
            self._controller = w
            return Theme.get(w.dark_mode.get())
        return Theme.DARK

    # ---- draw ---------------------------------------------------------
    def draw(self):
        self.delete("all")
        theme = self._theme()
        w = self.winfo_width() or int(self["width"])
        h = self.winfo_height() or int(self["height"])

        # pick colours
        if self.style == "operator":
            bg = theme["accent_hover"] if self._hover else theme["accent"]
            fg = "#ffffff"
        elif self.style == "equals":
            bg = theme["success_hover"] if self._hover else theme["success"]
            fg = "#ffffff"
        elif self.style == "clear":
            bg = theme["error_hover"] if self._hover else theme["error"]
            fg = "#ffffff"
        else:
            bg = theme["btn_hover"] if self._hover else theme["btn_bg"]
            fg = theme["fg"]

        # press offset
        off = self.ANIM_PRESS_OFFSET if self._pressed else 0

        # rounded rect
        r = self.RADIUS
        x1, y1, x2, y2 = 2 + off, 2 + off, w - 2, h - 2
        points = [
            x1+r, y1,  x2-r, y1,
            x2, y1,  x2, y1+r,
            x2, y2-r, x2, y2,
            x2-r, y2, x1+r, y2,
            x1, y2,  x1, y2-r,
            x1, y1+r, x1, y1,
        ]
        self.create_polygon(points, smooth=True, fill=bg, outline="")

        # focus ring
        if self._focused:
            self.create_polygon(points, smooth=True, fill="",
                                outline=theme["accent"], width=2)

        font_size = 10 if len(self.text) > 4 else 12
        self.create_text(
            w / 2 + off, h / 2 + off,
            text=self.text, fill=fg,
            font=("Segoe UI", font_size, "bold"),
        )

    # ---- event handlers -----------------------------------------------
    def _on_press_start(self, _event):
        self._pressed = True
        self.draw()

    def _on_press_end(self, _event):
        self._pressed = False
        self.draw()
        if self.command:
            self.command()

    def _on_enter(self, _event):
        self._hover = True
        self.draw()

    def _on_leave(self, _event):
        self._hover = False
        self._pressed = False
        self.draw()

    def _on_focus_in(self, _event):
        self._focused = True
        self.draw()

    def _on_focus_out(self, _event):
        self._focused = False
        self.draw()

    def _on_space(self, _event):
        if self.command:
            self.command()


# ---------------------------------------------------------------------------
# CalculatorFrame
# ---------------------------------------------------------------------------
class CalculatorFrame(tk.Frame):
    """Scientific calculator with live preview and clickable history."""

    def __init__(self, parent, controller: "CalculatorApp"):
        super().__init__(parent)
        self.controller = controller
        self.history_manager = controller.history_manager
        self.memory: float = 0.0
        self.last_answer: float = 0.0
        self._preview_job: Optional[str] = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)

        self._create_calculator_panel()
        self._create_history_panel()
        self._bind_keyboard()

    # ------------------------------------------------------------------
    def _create_calculator_panel(self):
        panel = tk.Frame(self)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        panel.grid_rowconfigure(2, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        # ---- display --------------------------------------------------
        disp = tk.Frame(panel)
        disp.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        disp.grid_columnconfigure(0, weight=1)

        # memory indicator
        mem_row = tk.Frame(disp)
        mem_row.grid(row=0, column=0, sticky="ew")
        self.memory_label = tk.Label(
            mem_row, text="", font=("Segoe UI", 9, "bold"),
            anchor="w", padx=4, pady=2,
        )
        self.memory_label.pack(side="left")

        # expression entry
        self.expression_var = tk.StringVar()
        self.expression_var.trace_add("write", self._on_expr_change)
        self.expr_entry = tk.Entry(
            disp, textvariable=self.expression_var,
            font=("Segoe UI", 18), justify="right",
            relief="flat", bd=8,
        )
        self.expr_entry.grid(row=1, column=0, sticky="ew", ipady=6)
        self.expr_entry.bind("<Return>",    lambda e: self.evaluate())
        self.expr_entry.bind("<Escape>",    lambda e: self.clear())
        self.expr_entry.bind("<BackSpace>", lambda e: None)  # handled globally

        # live preview
        self.preview_var = tk.StringVar(value="")
        self.preview_label = tk.Label(
            disp, textvariable=self.preview_var,
            font=("Segoe UI", 12), anchor="e",
            padx=4,
        )
        self.preview_label.grid(row=2, column=0, sticky="ew")

        # result display
        self.result_var = tk.StringVar(value="0")
        self.result_label = tk.Label(
            disp, textvariable=self.result_var,
            font=("Segoe UI", 36, "bold"), anchor="e",
            padx=4,
        )
        self.result_label.grid(row=3, column=0, sticky="ew", pady=(4, 0))

        # ---- buttons --------------------------------------------------
        btn_frame = tk.Frame(panel)
        btn_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))

        for i in range(7):
            btn_frame.grid_rowconfigure(i, weight=1)
        for i in range(5):
            btn_frame.grid_columnconfigure(i, weight=1)

        BUTTONS = [
            [("MC","default"),("MR","default"),("M+","default"),("M-","default"),("C","clear")],
            [("sin","default"),("cos","default"),("tan","default"),("(","default"),(")","default")],
            [("√","default"),("x²","default"),("xʸ","default"),("÷","operator"),("⌫","default")],
            [("7","default"),("8","default"),("9","default"),("×","operator"),("ln","default")],
            [("4","default"),("5","default"),("6","default"),("−","operator"),("log","default")],
            [("1","default"),("2","default"),("3","default"),("+","operator"),("n!","default")],
            [("±","default"),("0","default"),(".","default"),("=","equals"),("Ans","default")],
        ]

        for r, row in enumerate(BUTTONS):
            for c, (label, style) in enumerate(row):
                btn = ModernButton(
                    btn_frame, text=label,
                    command=lambda lbl=label: self._on_button(lbl),
                    style=style,
                    controller=self.controller,
                )
                btn.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                self.controller.register_widget(btn)

    # ------------------------------------------------------------------
    def _create_history_panel(self):
        panel = tk.Frame(self)
        panel.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        header = tk.Frame(panel)
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
        header.grid_columnconfigure(0, weight=1)

        tk.Label(header, text="History", font=("Segoe UI", 12, "bold")).pack(side="left")
        clear_btn = tk.Button(
            header, text="Clear", command=self._clear_history,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
        )
        clear_btn.pack(side="right")
        self.controller.register_widget(clear_btn, "button")

        hist_frame = tk.Frame(panel)
        hist_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        hist_frame.grid_rowconfigure(0, weight=1)
        hist_frame.grid_columnconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(hist_frame)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.history_text = tk.Text(
            hist_frame, wrap="word", state="disabled",
            font=("Segoe UI", 11), relief="flat",
            yscrollcommand=scrollbar.set,
            cursor="arrow",
        )
        self.history_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.config(command=self.history_text.yview)

        self.history_text.tag_config("expr",   foreground="#8b949e")
        self.history_text.tag_config("result", font=("Segoe UI", 13, "bold"))
        self.history_text.tag_config("clickable", underline=False)

        self.controller.register_widget(self.history_text, "text")

        self._load_history()

    # ------------------------------------------------------------------
    def _load_history(self):
        self.history_text.config(state="normal")
        self.history_text.delete("1.0", tk.END)
        theme = Theme.get(self.controller.dark_mode.get())

        for entry in self.history_manager.get_recent():
            expr = entry["expression"]
            res  = entry["result"]
            ts   = HistoryManager.friendly_time(entry.get("timestamp", ""))

            start = self.history_text.index(tk.END)
            # timestamp line
            if ts:
                self.history_text.insert(tk.END, f"  {ts}\n", "ts")
            self.history_text.insert(tk.END, f"  {expr}\n", "expr")
            self.history_text.insert(tk.END, f"  = {res}\n\n", "result")

            # make row clickable
            end = self.history_text.index(tk.END)
            tag = f"row_{start}"
            self.history_text.tag_add(tag, start, end)
            self.history_text.tag_config(tag, spacing1=2)
            self.history_text.tag_bind(
                tag, "<Button-1>",
                lambda _e, e=expr: self._load_from_history(e),
            )
            self.history_text.tag_bind(tag, "<Enter>",
                lambda _e: self.history_text.config(cursor="hand2"))
            self.history_text.tag_bind(tag, "<Leave>",
                lambda _e: self.history_text.config(cursor="arrow"))

        self.history_text.tag_config("expr",   foreground=theme["tag_expr"])
        self.history_text.tag_config("result", foreground=theme["tag_result"])
        self.history_text.tag_config("ts",     foreground=theme["secondary_fg"],
                                               font=("Segoe UI", 7))
        self.history_text.config(state="disabled")

    def _load_from_history(self, expr: str):
        """Load a history expression into the entry."""
        self.expression_var.set(expr)
        self.expr_entry.icursor(tk.END)

    def _clear_history(self):
        if messagebox.askyesno("Clear History", "Clear all calculation history?"):
            self.history_manager.clear()
            self._load_history()

    # ------------------------------------------------------------------
    def _bind_keyboard(self):
        # Scope Escape/Delete to THIS frame so they don't fire in Converter
        self.bind("<Escape>",            lambda e: self.clear())
        self.bind("<Delete>",            lambda e: self.clear())
        self.bind_all("<Control-z>",     lambda e: self._safe_backspace())
        self.bind_all("<Control-BackSpace>", lambda e: self._safe_clear())
        self.bind_all("<Control-Return>", lambda e: self._safe_evaluate())
        # <Control-c> left free for system copy

    def _safe_clear(self):
        """Clear only when Calculator tab is visible."""
        if self.winfo_ismapped():
            self.clear()

    def _safe_backspace(self):
        """Backspace only when Calculator tab is visible."""
        if self.winfo_ismapped():
            self.backspace()

    def _safe_evaluate(self):
        """Evaluate only when Calculator tab is visible."""
        if self.winfo_ismapped():
            self.evaluate()

    # ------------------------------------------------------------------
    def _on_expr_change(self, *_args):
        """Schedule a live preview (debounced)."""
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(DEBOUNCE_PREVIEW_MS, self._update_preview)

    def _update_preview(self):
        expr = self.expression_var.get().strip()
        if not expr:
            self.preview_var.set("")
            return
        try:
            val = SafeEvaluator.evaluate(expr)
            if isinstance(val, float):
                val = int(val) if val.is_integer() else round(val, 8)
            self.preview_var.set(f"≈ {val}")
        except Exception:
            self.preview_var.set("")

    # ------------------------------------------------------------------
    def _on_button(self, label: str):
        actions = {
            "C":   self.clear,
            "⌫":  self.backspace,
            "=":   self.evaluate,
            "Ans": lambda: self._insert_at_cursor(str(self.last_answer)),
            "√":   lambda: self._insert_at_cursor("sqrt("),
            "x²":  lambda: self._insert_at_cursor("**2"),
            "xʸ":  lambda: self._insert_at_cursor("**"),
            "sin": lambda: self._insert_at_cursor("sin("),
            "cos": lambda: self._insert_at_cursor("cos("),
            "tan": lambda: self._insert_at_cursor("tan("),
            "ln":  lambda: self._insert_at_cursor("log("),
            "log": lambda: self._insert_at_cursor("log10("),
            "n!":  lambda: self._insert_at_cursor("factorial("),
            "±":   self._toggle_sign,
            "MC":  self._memory_clear,
            "MR":  self._memory_recall,
            "M+":  self._memory_add,
            "M-":  self._memory_subtract,
            "−":   lambda: self._insert_at_cursor("-"),
        }
        if label in actions:
            actions[label]()
        else:
            self._insert_at_cursor(label)

    def _insert_at_cursor(self, text: str):
        """Insert text at the current cursor position of the Entry widget."""
        try:
            pos = self.expr_entry.index(tk.INSERT)
        except tk.TclError:
            pos = tk.END
        current = self.expression_var.get()
        # expr_entry.index returns an integer for plain Entry
        new_val = current[:pos] + text + current[pos:]
        self.expression_var.set(new_val)
        self.expr_entry.icursor(pos + len(text))

    def clear(self):
        self.expression_var.set("")
        self.result_var.set("0")
        self.preview_var.set("")

    def backspace(self):
        current = self.expression_var.get()
        try:
            pos = self.expr_entry.index(tk.INSERT)
        except tk.TclError:
            pos = len(current)
        if pos > 0:
            new_val = current[: pos - 1] + current[pos:]
            self.expression_var.set(new_val)
            self.expr_entry.icursor(pos - 1)
        if not self.expression_var.get():
            self.result_var.set("0")
            self.preview_var.set("")

    def _toggle_sign(self):
        """Toggle sign of the last numeric token in the expression."""
        expr = self.expression_var.get()
        if not expr:
            return
        m = re.search(r"(-?\d+\.?\d*(?:[eE][+-]?\d+)?)$", expr)
        if m:
            num_str = m.group(1)
            try:
                if "." in num_str or "e" in num_str.lower():
                    val = -float(num_str)
                    # avoid -0.0
                    replacement = str(int(val)) if val.is_integer() else str(val)
                else:
                    replacement = str(-int(num_str))
            except ValueError:
                return
            self.expression_var.set(expr[: m.start()] + replacement)

    # ---- memory -------------------------------------------------------
    def _fmt_memory(self) -> str:
        v = self.memory
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return f"{v:.6g}"

    def _memory_clear(self):
        self.memory = 0.0
        self.memory_label.config(text="")

    def _memory_recall(self):
        self.expression_var.set(str(int(self.memory) if float(self.memory).is_integer() else self.memory))

    def _memory_add(self):
        try:
            val = SafeEvaluator.evaluate(self.expression_var.get() or "0")
            self.memory += val
            self.memory_label.config(text=f" M: {self._fmt_memory()}")
        except Exception:
            pass

    def _memory_subtract(self):
        try:
            val = SafeEvaluator.evaluate(self.expression_var.get() or "0")
            self.memory -= val
            self.memory_label.config(text=f" M: {self._fmt_memory()}")
        except Exception:
            pass

    # ---- evaluate -----------------------------------------------------
    def evaluate(self):
        """Evaluate the current expression and update the display."""
        expr = self.expression_var.get().strip()
        if not expr:
            return

        t0 = time.perf_counter()
        try:
            result = SafeEvaluator.evaluate(expr)
            elapsed = (time.perf_counter() - t0) * 1000

            if isinstance(result, float):
                result = int(result) if result.is_integer() else round(result, 10)

            result_str = str(result)
            self.result_var.set(result_str)
            self.preview_var.set("")
            self.last_answer = result

            self.history_manager.add(expr, result_str, elapsed)
            self._load_history()
            self.controller.set_status(f"Calculated in {elapsed:.2f} ms")
            # Brief accent-colour flash on success
            self._flash_result()

        except Exception as exc:
            self.result_var.set("Error")
            self.controller.set_status(f"\u26a0 {exc}")
            # No messagebox — status bar is sufficient and non-blocking

    def _flash_result(self):
        """Briefly flash the result label in accent colour then restore."""
        theme = Theme.get(self.controller.dark_mode.get())
        accent = theme["accent"]
        default_fg = theme["fg"]
        if hasattr(self, 'result_label') and self.result_label.winfo_exists():
            self.result_label.config(fg=accent)
            self.result_label.after(220, lambda: hasattr(self, 'result_label') and self.result_label.winfo_exists() and self.result_label.config(fg=default_fg))

    # ---- theme update -------------------------------------------------
    def apply_theme(self, theme: Dict):
        self.history_text.tag_config("expr",   foreground=theme["tag_expr"])
        self.history_text.tag_config("result", foreground=theme["tag_result"])
        self.memory_label.config(
            bg=theme["memory_bg"] if self.memory != 0 else theme["panel"],
            fg=theme["fg"],
        )


# ---------------------------------------------------------------------------
# ConverterFrame
# ---------------------------------------------------------------------------
class ConverterFrame(tk.Frame):
    """Number system converter with validation feedback and per-row copy."""

    def __init__(self, parent, controller: "CalculatorApp"):
        super().__init__(parent)
        self.controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._create_interface()

    # ------------------------------------------------------------------
    def _create_interface(self):
        outer = tk.Frame(self)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(0, weight=1)

        # Centre-column with max-width feel
        container = tk.Frame(outer)
        container.grid(row=0, column=0, padx=60, pady=40, sticky="n")
        container.grid_columnconfigure(0, weight=1)

        tk.Label(
            container, text="Number System Converter",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, pady=(0, 24), sticky="w")
        self.controller.register_widget(
            container.grid_slaves(row=0, column=0)[0], "label"
        )

        # ---- Input ----------------------------------------------------
        in_frame = tk.LabelFrame(
            container, text="  Input  ",
            font=("Segoe UI", 10, "bold"), padx=20, pady=16,
        )
        in_frame.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        in_frame.grid_columnconfigure(0, weight=1)
        self.controller.register_widget(in_frame, "labelframe")

        # Use a sub-frame for input + swap button
        input_row = tk.Frame(in_frame)
        input_row.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        input_row.grid_columnconfigure(0, weight=1)
        self.controller.register_widget(input_row, "frame")

        self.input_var = tk.StringVar()
        self.input_var.trace_add("write", self._on_input_change)

        self.input_entry = tk.Entry(
            input_row, textvariable=self.input_var,
            font=("Segoe UI", 20, "bold"), justify="center",
        )
        self.input_entry.grid(row=0, column=0, sticky="ew", ipady=4)

        self.swap_btn = tk.Button(
            input_row, text="⇅", font=("Segoe UI", 14),
            relief="flat", cursor="hand2", width=3,
            command=self._swap_input,
        )
        self.swap_btn.grid(row=0, column=1, padx=(10, 0))
        self.controller.register_widget(self.swap_btn, "button")
        ToolTip(self.swap_btn, "Swap input with selected result")

        # validation label
        self.valid_label = tk.Label(in_frame, text="", font=("Segoe UI", 9), anchor="e")
        self.valid_label.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.controller.register_widget(self.valid_label, "label")

        base_row = tk.Frame(in_frame)
        base_row.grid(row=2, column=0, sticky="ew")
        base_row.grid_columnconfigure(1, weight=1)
        self.controller.register_widget(base_row, "frame")

        lbl_from = tk.Label(base_row, text="From:", font=("Segoe UI", 10))
        lbl_from.grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.controller.register_widget(lbl_from, "label")
        self.from_var = tk.StringVar(value="Decimal")
        self.from_var.trace_add("write", self._on_input_change)

        self.from_combo = ttk.Combobox(
            base_row, textvariable=self.from_var,
            values=list(NumberConverter.BASES.keys()),
            state="readonly", font=("Segoe UI", 11), width=16,
        )
        self.from_combo.grid(row=0, column=1, sticky="w")

        # ---- Output ---------------------------------------------------
        out_frame = tk.LabelFrame(
            container, text="  Results  ",
            font=("Segoe UI", 10, "bold"), padx=20, pady=16,
        )
        out_frame.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        out_frame.grid_columnconfigure(1, weight=1)
        self.controller.register_widget(out_frame, "labelframe")

        self.result_vars: Dict[str, tk.StringVar] = {}
        self.result_entries: Dict[str, tk.Entry] = {}
        self.bit_labels: Dict[str, tk.Label] = {}

        BASES = ["Binary", "Octal", "Decimal", "Hexadecimal"]
        for i, base in enumerate(BASES):
            lbl_base = tk.Label(
                out_frame, text=f"{base}:", font=("Segoe UI", 10, "bold"),
                width=12, anchor="w",
            )
            lbl_base.grid(row=i, column=0, sticky="w", pady=6)
            self.controller.register_widget(lbl_base, "label")

            var = tk.StringVar(value="0")
            self.result_vars[base] = var

            ent = tk.Entry(
                out_frame, textvariable=var,
                font=("Segoe UI", 14, "bold"), state="readonly",
                justify="left", relief="flat", readonlybackground="#f8f9fa",
            )
            ent.grid(row=i, column=1, sticky="ew", pady=6, padx=(0, 8))
            self.result_entries[base] = ent
            self.controller.register_widget(ent, "entry_ro")

            # bit-length/annotation label
            bit_lbl = tk.Label(out_frame, text="", font=("Segoe UI", 8), width=8, anchor="w")
            bit_lbl.grid(row=i, column=2, sticky="w", padx=(0, 4))
            self.bit_labels[base] = bit_lbl
            self.controller.register_widget(bit_lbl, "label")

            # per-row copy button
            copy_btn = tk.Button(
                out_frame, text="📋", font=("Segoe UI", 9),
                relief="flat", cursor="hand2", width=2,
                command=lambda b=base: self._copy_one(b),
            )
            copy_btn.grid(row=i, column=3, sticky="e", pady=6)
            self.controller.register_widget(copy_btn, "button")

        # ---- action buttons -------------------------------------------
        btn_row = tk.Frame(container)
        btn_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))

        clear_btn = tk.Button(
            btn_row, text="Clear", command=self._clear,
            font=("Segoe UI", 11), width=14, height=2, cursor="hand2",
        )
        clear_btn.pack(side="left", padx=(0, 12))
        self.controller.register_widget(clear_btn, "button")

        copy_all_btn = tk.Button(
            btn_row, text="Copy All", command=self._copy_all,
            font=("Segoe UI", 11), width=14, height=2, cursor="hand2",
        )
        copy_all_btn.pack(side="left")
        self.controller.register_widget(copy_all_btn, "button")

    # ------------------------------------------------------------------
    def _on_input_change(self, *_args):
        self._convert()

    def _convert(self):
        raw = self.input_var.get().strip()
        from_base = self.from_var.get()
        theme = Theme.get(self.controller.dark_mode.get())

        if not raw:
            for var in self.result_vars.values():
                var.set("0")
            for lbl in self.bit_labels.values():
                lbl.config(text="")
            self._set_valid_state(None, theme)
            return

        valid = NumberConverter.validate_input(raw, from_base)
        self._set_valid_state(valid, theme)
        if not valid:
            for var in self.result_vars.values():
                var.set("—")
            for lbl in self.bit_labels.values():
                lbl.config(text="")
            return

        try:
            decimal_val = int(raw.replace(" ", ""), NumberConverter.BASES[from_base])
            if raw.startswith("-"):
                decimal_val = -int(raw[1:].replace(" ", ""), NumberConverter.BASES[from_base])

            bit_len = NumberConverter.bit_length(decimal_val)

            for to_base, var in self.result_vars.items():
                result = NumberConverter.convert(raw, from_base, to_base)
                var.set(result)
                lbl = self.bit_labels[to_base]
                if to_base == "Binary":
                    lbl.config(text=f"{bit_len}-bit")
                else:
                    lbl.config(text="")
        except Exception as exc:
            for var in self.result_vars.values():
                var.set(f"Error")
            log.debug("converter error: %s", exc)

    def _set_valid_state(self, valid: Optional[bool], theme: Dict):
        if valid is None:
            self.valid_label.config(text="", fg=theme["fg"])
            self.input_entry.config(highlightbackground=theme["border"],
                                    highlightcolor=theme["border"], highlightthickness=1)
        elif valid:
            self.valid_label.config(text="✓ Valid input", fg=theme["valid"])
            self.input_entry.config(highlightbackground=theme["valid"],
                                    highlightcolor=theme["valid"], highlightthickness=2)
        else:
            self.valid_label.config(text="✗ Invalid input for selected base", fg=theme["invalid"])
            self.input_entry.config(highlightbackground=theme["invalid"],
                                    highlightcolor=theme["invalid"], highlightthickness=2)

    def _clear(self):
        self.input_var.set("")
        for var in self.result_vars.values():
            var.set("0")
        for lbl in self.bit_labels.values():
            lbl.config(text="")
        # reset validation border
        theme = Theme.get(self.controller.dark_mode.get())
        self._set_valid_state(None, theme)

    def _swap_input(self):
        """Swap current input with the currently selected 'from_base' target if valid."""
        theme = Theme.get(self.controller.dark_mode.get())
        current_base = self.from_var.get()
        # Find which base has a valid converted result other than "Error" or "—"
        candidate = self.result_vars.get(current_base, tk.StringVar()).get()
        if candidate and candidate not in ("0", "—", "Error"):
            self.input_var.set(candidate)
            self._set_valid_state(True, theme)

    def _copy_one(self, base: str):
        val = self.result_vars[base].get()
        self.clipboard_clear()
        self.clipboard_append(val)
        self.controller.set_status(f"Copied {base}: {val}")

    def _copy_all(self):
        lines = [f"{base}: {var.get()}" for base, var in self.result_vars.items()]
        text = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.controller.set_status("All results copied to clipboard")


# ---------------------------------------------------------------------------
# SegmentedControl — Custom pill toggle for modes
# ---------------------------------------------------------------------------
class SegmentedControl(tk.Frame):
    """A custom toggle control that replaces radio buttons for Mode switching."""

    def __init__(self, parent, variable: tk.StringVar, options: List[tuple[str, str]], command: Callable, controller=None):
        super().__init__(parent)
        self.variable = variable
        self.options = options
        self.command = command
        self._controller = controller
        self.buttons: Dict[str, tk.Label] = {}
        
        # We'll use a Canvas indicator that animating might be overkill, so we just style the labels.
        for i, (text, val) in enumerate(options):
            lbl = tk.Label(
                self, text=text, font=("Segoe UI", 10, "bold"),
                cursor="hand2", padx=12, pady=6,
            )
            lbl.grid(row=0, column=i, padx=2)
            lbl.bind("<Button-1>", lambda e, v=val: self._select(v))
            self.buttons[val] = lbl

        self.variable.trace_add("write", self._on_var_change)
        self._draw()

    def _select(self, val: str):
        self.variable.set(val)
        if self.command:
            self.command()

    def _on_var_change(self, *_args):
        self._draw()

    def _theme(self):
        if self._controller:
            return Theme.get(self._controller.dark_mode.get())
        w = self.master
        while w and not hasattr(w, "dark_mode"):
            w = w.master
        if w:
            self._controller = w
            return Theme.get(w.dark_mode.get())
        return Theme.DARK

    def draw(self):
        self._draw()

    def _draw(self):
        theme = self._theme()
        self.configure(bg=theme["toolbar"])
        current = self.variable.get()
        for val, lbl in self.buttons.items():
            if val == current:
                lbl.configure(
                    bg=theme["btn_hover"], fg=theme["fg"], relief="flat",
                )
            else:
                lbl.configure(
                    bg=theme["toolbar"], fg=theme["secondary_fg"], relief="flat",
                )


# ---------------------------------------------------------------------------
# CalculatorApp — main window with widget registry + ttk styling
# ---------------------------------------------------------------------------
class CalculatorApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        Settings.load()

        self.title("Professional Calculator")
        self.minsize(820, 520)

        # Restore geometry
        saved_geo = Settings.get("geometry", "920x620")
        self.geometry(saved_geo)

        self.dark_mode = tk.BooleanVar(value=Settings.get("dark_mode", False))

        # ---- widget registry ------------------------------------------
        # Maps widget -> kind ("frame","label","entry","entry_ro","button","text","root")
        self._widget_registry: Dict[tk.Widget, str] = {}

        # ---- shared subsystems ----------------------------------------
        self.history_manager = HistoryManager()
        self.history_manager._root = self

        self._create_ui()
        self._apply_ttk_style()
        self._apply_theme()

        self.bind_all("<Control-t>", lambda e: self._toggle_theme())
        self.bind_all("<Control-slash>", lambda e: self._show_shortcuts())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- widget registry ----------------------------------------------
    def register_widget(self, widget: tk.Widget, kind: str = "auto"):
        """Register a widget for batched theme updates."""
        self._widget_registry[widget] = kind

    # ------------------------------------------------------------------
    def _create_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # ---- toolbar --------------------------------------------------
        toolbar = tk.Frame(self, height=52)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_columnconfigure(1, weight=1)
        toolbar.grid_propagate(False)
        self.register_widget(toolbar, "toolbar")

        mode_frame = tk.Frame(toolbar)
        mode_frame.grid(row=0, column=0, padx=16, pady=12)
        self.register_widget(mode_frame, "toolbar")

        self.mode_var = tk.StringVar(value="calculator")
        opts = [("𝄑 Calculator", "calculator"), ("⇄ Converter", "converter")]
        
        self.mode_toggle = SegmentedControl(
            mode_frame, variable=self.mode_var,
            options=opts, command=self._switch_mode,
            controller=self,
        )
        self.mode_toggle.pack(side="left")
        self.register_widget(self.mode_toggle, "segmented")

        # separator
        sep = tk.Frame(toolbar, width=1)
        sep.grid(row=0, column=1, sticky="ns", pady=10)
        self.register_widget(sep, "separator")

        theme_frame = tk.Frame(toolbar)
        theme_frame.grid(row=0, column=2, padx=16, pady=12)
        self.register_widget(theme_frame, "toolbar")

        self.theme_btn = tk.Checkbutton(
            theme_frame, text="🌙 Dark",
            variable=self.dark_mode, command=self._apply_theme,
            font=("Segoe UI", 10), cursor="hand2",
        )
        self.theme_btn.pack()
        self.register_widget(self.theme_btn, "checkbutton")

        # shortcut hint
        hint = tk.Label(toolbar, text="Ctrl+T", font=("Segoe UI", 8))
        hint.grid(row=0, column=3, padx=(0, 16))
        self.register_widget(hint, "label_secondary")

        # ---- content container ----------------------------------------
        self.container = tk.Frame(self)
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        self.register_widget(self.container, "frame")

        self.frames: Dict[str, tk.Frame] = {}
        for Cls in (CalculatorFrame, ConverterFrame):
            frame = Cls(self.container, self)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[Cls.__name__] = frame
            self.register_widget(frame, "frame")

        self._switch_mode()

        # ---- status bar -----------------------------------------------
        self.status_bar = tk.Label(
            self, text="  Ready", anchor="w",
            font=("Segoe UI", 8), padx=8, pady=3,
        )
        self.status_bar.grid(row=2, column=0, sticky="ew")
        self.register_widget(self.status_bar, "status")
        self._status_job: Optional[str] = None

    # ------------------------------------------------------------------
    def _switch_mode(self):
        name = "CalculatorFrame" if self.mode_var.get() == "calculator" else "ConverterFrame"
        self.frames[name].tkraise()

    def set_status(self, msg: str):
        """Set a temporary status message that reverts to 'Ready'."""
        self.status_bar.config(text=f"  {msg}")
        if self._status_job:
            self.after_cancel(self._status_job)
        if msg.strip() != "Ready":
            self._status_job = self.after(STATUS_CLEAR_MS, lambda: self.set_status("Ready"))

    def _show_shortcuts(self):
        """Show a dialog listing all keyboard shortcuts."""
        tw = tk.Toplevel(self)
        tw.title("Keyboard Shortcuts")
        tw.geometry("320x340")
        tw.resizable(False, False)
        tw.transient(self)
        tw.grab_set()

        theme = Theme.get(self.dark_mode.get())
        tw.configure(bg=theme["bg"])
        
        tk.Label(
            tw, text="Keyboard Shortcuts", font=("Segoe UI", 14, "bold"),
            bg=theme["bg"], fg=theme["fg"],
        ).pack(pady=(16, 12))

        shortcuts = [
            ("Ctrl + /", "Show this help dialog"),
            ("Ctrl + T", "Toggle Theme (Dark/Light)"),
            ("Escape", "Clear All (Calculator)"),
            ("Delete", "Clear All (Calculator)"),
            ("Ctrl + Backspace", "Clear All (Calculator)"),
            ("Ctrl + Z", "Backspace (Calculator)"),
            ("Enter / Ctrl + Enter", "Evaluate Expression"),
        ]

        frame = tk.Frame(tw, bg=theme["panel"], bd=1, relief="solid")
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        for i, (keys, desc) in enumerate(shortcuts):
            tk.Label(
                frame, text=keys, font=("Consolas", 10, "bold"),
                bg=theme["panel"], fg=theme["accent"], anchor="e", width=16,
            ).grid(row=i, column=0, sticky="e", padx=(12, 8), pady=6)
            
            tk.Label(
                frame, text=desc, font=("Segoe UI", 10),
                bg=theme["panel"], fg=theme["fg"], anchor="w",
            ).grid(row=i, column=1, sticky="w", padx=(0, 12), pady=6)

    def _toggle_theme(self):
        self.dark_mode.set(not self.dark_mode.get())
        self._apply_theme()

    # ------------------------------------------------------------------
    def _apply_ttk_style(self):
        """Configure ttk widgets (Scrollbar, Combobox) for both themes."""
        style = ttk.Style(self)
        style.theme_use("default")

        def _configure(dark: bool):
            t = Theme.get(dark)
            style.configure("TScrollbar",
                            troughcolor=t["bg"],
                            background=t["btn_bg"],
                            arrowcolor=t["fg"])
            style.configure("TCombobox",
                            fieldbackground=t["display_bg"],
                            background=t["btn_bg"],
                            foreground=t["fg"],
                            selectbackground=t["accent"],
                            selectforeground="#ffffff")
            style.map("TCombobox",
                      fieldbackground=[("readonly", t["display_bg"])],
                      foreground=[("readonly", t["fg"])],
                      selectbackground=[("readonly", t["accent"])])

        self._configure_ttk = _configure
        _configure(self.dark_mode.get())

    # ------------------------------------------------------------------
    def _apply_theme(self):
        """Apply theme to all registered widgets — O(n) registry lookup."""
        dark = self.dark_mode.get()
        theme = Theme.get(dark)

        # ttk widgets
        self._configure_ttk(dark)

        # root window
        self.configure(bg=theme["bg"])

        # registered widgets - copy list to allow mutation (deletion) during iteration
        for widget, kind in list(self._widget_registry.items()):
            try:
                self._style_widget(widget, kind, theme)
            except tk.TclError:
                # widget destroyed
                self._widget_registry.pop(widget, None)

        # Walk remaining unstyled children (Entries etc that weren't caught)
        self._walk_style(self, theme)

        # per-frame theme updates
        calc_frame = self.frames.get("CalculatorFrame")
        if calc_frame:
            calc_frame.apply_theme(theme)

        Settings.set("dark_mode", dark)

    def _style_widget(self, widget: tk.Widget, kind: str, theme: Dict):
        wc = widget.__class__.__name__
        if kind in ("frame", "auto") or wc == "Frame":
            widget.configure(bg=theme["bg"])
        elif kind == "toolbar":
            widget.configure(bg=theme["toolbar"])
        elif kind == "separator":
            widget.configure(bg=theme["separator"])
        elif kind == "label" or wc == "Label":
            bg = theme["toolbar"] if kind == "toolbar" else theme["bg"]
            widget.configure(bg=bg, fg=theme["fg"])
        elif kind == "label_secondary":
            widget.configure(bg=theme["toolbar"], fg=theme["secondary_fg"])
        elif kind == "button" or wc == "Button":
            widget.configure(
                bg=theme["btn_bg"], fg=theme["fg"],
                activebackground=theme["btn_hover"],
                activeforeground=theme["fg"],
                relief="flat",
            )
        elif kind == "radiobutton" or wc == "Radiobutton":
            widget.configure(
                bg=theme["toolbar"], fg=theme["fg"],
                selectcolor=theme["toolbar"],
                activebackground=theme["toolbar"],
            )
        elif kind == "checkbutton" or wc == "Checkbutton":
            widget.configure(
                bg=theme["toolbar"], fg=theme["fg"],
                selectcolor=theme["toolbar"],
                activebackground=theme["toolbar"],
            )
        elif kind == "entry_ro":
            widget.configure(
                readonlybackground=theme["display_bg"],
                fg=theme["secondary_fg"],
            )
        elif kind == "text" or wc == "Text":
            widget.configure(bg=theme["history_bg"], fg=theme["fg"])
        elif kind == "status":
            widget.configure(bg=theme["status_bg"], fg=theme["status_fg"])
        elif isinstance(widget, ModernButton):
            widget.draw()
        elif kind == "segmented" or isinstance(widget, SegmentedControl):
            widget.draw()
        elif kind == "labelframe" or widget.__class__.__name__ == "LabelFrame":
            widget.configure(bg=theme["panel"], fg=theme["fg"])

    def _walk_style(self, widget: tk.Widget, theme: Dict):
        """Fallback recursive walk for widgets not in the registry."""
        if widget in self._widget_registry:
            return
        wc = widget.__class__.__name__
        try:
            if wc == "Frame":
                widget.configure(bg=theme["bg"])
            elif wc == "LabelFrame":
                widget.configure(bg=theme["panel"], fg=theme["fg"])
            elif wc == "Label":
                widget.configure(bg=theme["panel"], fg=theme["fg"])
            elif wc == "Entry":
                state = widget.cget("state")
                if str(state) == "readonly":
                    widget.configure(
                        readonlybackground=theme["display_bg"],
                        fg=theme["secondary_fg"],
                    )
                else:
                    widget.configure(
                        bg=theme["display_bg"], fg=theme["fg"],
                        insertbackground=theme["fg"],
                    )
            elif wc == "Text":
                widget.configure(bg=theme["history_bg"], fg=theme["fg"])
            elif wc == "Button":
                widget.configure(
                    bg=theme["btn_bg"], fg=theme["fg"],
                    activebackground=theme["btn_hover"],
                    relief="flat",
                )
            elif wc == "Radiobutton":
                widget.configure(
                    bg=theme["bg"], fg=theme["fg"],
                    selectcolor=theme["panel"],
                    activebackground=theme["bg"],
                )
            elif wc == "Checkbutton":
                widget.configure(
                    bg=theme["bg"], fg=theme["fg"],
                    selectcolor=theme["panel"],
                    activebackground=theme["bg"],
                )
            elif isinstance(widget, ModernButton):
                widget.draw()
            elif isinstance(widget, SegmentedControl):
                widget.draw()
        except tk.TclError:
            pass

        for child in widget.winfo_children():
            self._walk_style(child, theme)

    # ------------------------------------------------------------------
    def _on_close(self):
        Settings.set("geometry", self.geometry())
        Settings.save()
        self.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    try:
        app = CalculatorApp()
        app.mainloop()
    except Exception as exc:
        log.critical("Unhandled exception: %s", exc, exc_info=True)
        raise


if __name__ == "__main__":
    main()