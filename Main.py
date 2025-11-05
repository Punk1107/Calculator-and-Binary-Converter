"""
Professional Advanced Calculator & Number System Converter
A production-ready Tkinter application with modern UX/UI design

Features:
- Scientific Calculator with history
- Number System Converter (Binary, Decimal, Hex, Octal)
- Expression history with persistence
- Keyboard shortcuts
- Responsive design with smooth animations
- Professional dark/light themes
- Error handling and input validation
- Memory functions (M+, M-, MR, MC)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import ast
import re
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import json
import os


class SafeEvaluator:
    """Secure mathematical expression evaluator"""

    ALLOWED_NAMES = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}
    ALLOWED_NAMES.update({
        'abs': abs,
        'round': round,
        'pow': pow,
        'factorial': math.factorial,
        'min': min,
        'max': max
    })

    ALLOWED_NODES = (
        ast.Expression, ast.Call, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
        ast.Num, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
        ast.Pow, ast.USub, ast.UAdd, ast.LShift, ast.RShift, ast.BitXor,
        ast.BitAnd, ast.BitOr, ast.FloorDiv, ast.Tuple, ast.List
    )

    @classmethod
    def evaluate(cls, expr: str) -> float:
        """Safely evaluate mathematical expression"""
        if not expr or not expr.strip():
            raise ValueError("Empty expression")

        expr = expr.strip()
        expr = expr.replace('×', '*').replace('÷', '/').replace('^', '**').replace('π', 'pi')

        try:
            node = ast.parse(expr, mode='eval')
        except SyntaxError as e:
            raise ValueError(f"Syntax error: {str(e)}")

        for n in ast.walk(node):
            if not isinstance(n, cls.ALLOWED_NODES):
                raise ValueError(f"Unsupported operation: {type(n).__name__}")
            if isinstance(n, ast.Name) and n.id not in cls.ALLOWED_NAMES:
                raise ValueError(f"Unknown function or constant: {n.id}")

        compiled = compile(node, '<safe>', 'eval')
        result = eval(compiled, {'__builtins__': {}}, cls.ALLOWED_NAMES)

        if isinstance(result, complex):
            if result.imag == 0:
                return result.real
            raise ValueError("Complex numbers not supported")

        return result


class HistoryManager:
    """Manage calculation history with file persistence"""

    def __init__(self, filename: str = "calc_history.json"):
        self.filename = os.path.join(os.path.expanduser("~"), ".calculator", filename)
        self.history: List[Dict] = []
        self.max_history = 100
        self._ensure_dir()
        self.load()

    def _ensure_dir(self):
        """Create directory if it doesn't exist"""
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)

    def add(self, expression: str, result: str):
        """Add calculation to history"""
        entry = {
            'expression': expression,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
        self.history.insert(0, entry)

        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]

        self.save()

    def get_recent(self, limit: int = 20) -> List[Dict]:
        """Get recent calculations"""
        return self.history[:limit]

    def clear(self):
        """Clear all history"""
        self.history = []
        self.save()

    def save(self):
        """Save history to file"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.history, f, indent=2)
        except Exception:
            pass

    def load(self):
        """Load history from file"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    self.history = json.load(f)
        except Exception:
            self.history = []


class NumberConverter:
    """Number system conversion utilities"""

    BASES = {
        'Binary': 2,
        'Octal': 8,
        'Decimal': 10,
        'Hexadecimal': 16
    }

    @staticmethod
    def validate_input(value: str, base_name: str) -> bool:
        """Validate input for given base"""
        value = value.strip().replace(' ', '')
        if not value:
            return False

        base = NumberConverter.BASES[base_name]

        if base_name == 'Binary':
            return bool(re.match(r'^[01]+$', value))
        elif base_name == 'Octal':
            return bool(re.match(r'^[0-7]+$', value))
        elif base_name == 'Decimal':
            return bool(re.match(r'^-?\d+$', value))
        elif base_name == 'Hexadecimal':
            return bool(re.match(r'^[0-9A-Fa-f]+$', value))

        return False

    @staticmethod
    def convert(value: str, from_base: str, to_base: str) -> str:
        """Convert number between bases"""
        value = value.strip().replace(' ', '')

        if not NumberConverter.validate_input(value, from_base):
            raise ValueError(f"Invalid {from_base} number")

        decimal_value = int(value, NumberConverter.BASES[from_base])

        if to_base == 'Binary':
            return bin(decimal_value)[2:] if decimal_value >= 0 else '-' + bin(decimal_value)[3:]
        elif to_base == 'Octal':
            return oct(decimal_value)[2:] if decimal_value >= 0 else '-' + oct(decimal_value)[3:]
        elif to_base == 'Decimal':
            return str(decimal_value)
        elif to_base == 'Hexadecimal':
            return hex(decimal_value)[2:].upper() if decimal_value >= 0 else '-' + hex(decimal_value)[3:].upper()

        return ""


class Theme:
    """Theme configuration"""

    LIGHT = {
        'bg': '#f8f9fa',
        'panel': '#ffffff',
        'fg': '#212529',
        'secondary_fg': '#6c757d',
        'btn_bg': '#e9ecef',
        'btn_hover': '#dee2e6',
        'btn_active': '#ced4da',
        'accent': '#0d6efd',
        'accent_hover': '#0b5ed7',
        'border': '#dee2e6',
        'success': '#198754',
        'warning': '#ffc107',
        'error': '#dc3545',
        'display_bg': '#f8f9fa',
        'history_bg': '#ffffff'
    }

    DARK = {
        'bg': '#0d1117',
        'panel': '#161b22',
        'fg': '#e6edf3',
        'secondary_fg': '#8b949e',
        'btn_bg': '#21262d',
        'btn_hover': '#30363d',
        'btn_active': '#484f58',
        'accent': '#1f6feb',
        'accent_hover': '#388bfd',
        'border': '#30363d',
        'success': '#238636',
        'warning': '#d29922',
        'error': '#f85149',
        'display_bg': '#0d1117',
        'history_bg': '#161b22'
    }


class ModernButton(tk.Canvas):
    """Custom modern button with hover effects"""

    def __init__(self, parent, text: str, command, width: int = 60, height: int = 50,
                 style: str = 'default', **kwargs):
        super().__init__(parent, width=width, height=height,
                        highlightthickness=0, **kwargs)

        self.text = text
        self.command = command
        self.style = style
        self.hover = False

        self.bind('<Button-1>', self._on_click)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

        self.draw()

    def draw(self):
        """Draw button"""
        self.delete('all')

        app = self.master
        while not isinstance(app, CalculatorApp):
            app = app.master

        theme = Theme.DARK if app.dark_mode.get() else Theme.LIGHT

        if self.style == 'operator':
            bg = theme['accent']
            fg = '#ffffff'
            if self.hover:
                bg = theme['accent_hover']
        elif self.style == 'equals':
            bg = theme['success']
            fg = '#ffffff'
            if self.hover:
                bg = theme['success']
        elif self.style == 'clear':
            bg = theme['error']
            fg = '#ffffff'
            if self.hover:
                bg = theme['error']
        else:
            bg = theme['btn_hover'] if self.hover else theme['btn_bg']
            fg = theme['fg']

        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            w, h = int(self['width']), int(self['height'])

        radius = 8
        self.create_rounded_rect(2, 2, w-2, h-2, radius, fill=bg, outline='')

        font_size = 11 if len(self.text) > 4 else 13
        self.create_text(w/2, h/2, text=self.text, fill=fg,
                        font=('Segoe UI', font_size, 'bold'))

    def create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Create rounded rectangle"""
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _on_click(self, event):
        """Handle click"""
        if self.command:
            self.command()

    def _on_enter(self, event):
        """Handle mouse enter"""
        self.hover = True
        self.draw()

    def _on_leave(self, event):
        """Handle mouse leave"""
        self.hover = False
        self.draw()


class CalculatorFrame(tk.Frame):
    """Scientific calculator with history"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.history_manager = HistoryManager()
        self.memory = 0.0
        self.last_answer = 0.0

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)

        self._create_calculator_panel()
        self._create_history_panel()
        self._bind_keyboard()

    def _create_calculator_panel(self):
        """Create main calculator interface"""
        calc_panel = tk.Frame(self)
        calc_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 4))
        calc_panel.grid_rowconfigure(1, weight=1)
        calc_panel.grid_columnconfigure(0, weight=1)

        display_frame = tk.Frame(calc_panel)
        display_frame.grid(row=0, column=0, sticky='ew', padx=8, pady=8)
        display_frame.grid_columnconfigure(0, weight=1)

        memory_frame = tk.Frame(display_frame)
        memory_frame.grid(row=0, column=0, sticky='ew', pady=(0, 4))

        self.memory_label = tk.Label(memory_frame, text='', font=('Consolas', 9), anchor='w')
        self.memory_label.pack(side='left')

        self.expression_var = tk.StringVar()
        expression_entry = tk.Entry(display_frame, textvariable=self.expression_var,
                                    font=('Consolas', 14), justify='right',
                                    relief='flat', bd=8)
        expression_entry.grid(row=1, column=0, sticky='ew', ipady=4)
        expression_entry.bind('<Return>', lambda e: self.evaluate())
        expression_entry.bind('<Escape>', lambda e: self.clear())

        self.result_var = tk.StringVar(value='0')
        result_label = tk.Label(display_frame, textvariable=self.result_var,
                               font=('Consolas', 24, 'bold'), anchor='e')
        result_label.grid(row=2, column=0, sticky='ew', pady=(4, 0))

        buttons_frame = tk.Frame(calc_panel)
        buttons_frame.grid(row=1, column=0, sticky='nsew', padx=8, pady=(0, 8))

        for i in range(7):
            buttons_frame.grid_rowconfigure(i, weight=1)
        for i in range(5):
            buttons_frame.grid_columnconfigure(i, weight=1)

        buttons = [
            [('MC', 'default'), ('MR', 'default'), ('M+', 'default'), ('M-', 'default'), ('C', 'clear')],
            [('sin', 'default'), ('cos', 'default'), ('tan', 'default'), ('(', 'default'), (')', 'default')],
            [('√', 'default'), ('x²', 'default'), ('xʸ', 'default'), ('÷', 'operator'), ('⌫', 'default')],
            [('7', 'default'), ('8', 'default'), ('9', 'default'), ('×', 'operator'), ('ln', 'default')],
            [('4', 'default'), ('5', 'default'), ('6', 'default'), ('-', 'operator'), ('log', 'default')],
            [('1', 'default'), ('2', 'default'), ('3', 'default'), ('+', 'operator'), ('n!', 'default')],
            [('±', 'default'), ('0', 'default'), ('.', 'default'), ('=', 'equals'), ('Ans', 'default')]
        ]

        for r, row in enumerate(buttons):
            for c, (label, style) in enumerate(row):
                btn = ModernButton(buttons_frame, text=label,
                                  command=lambda l=label: self._on_button(l),
                                  style=style)
                btn.grid(row=r, column=c, padx=2, pady=2, sticky='nsew')

    def _create_history_panel(self):
        """Create history sidebar"""
        history_panel = tk.Frame(self)
        history_panel.grid(row=0, column=1, sticky='nsew', padx=(4, 0))
        history_panel.grid_rowconfigure(1, weight=1)
        history_panel.grid_columnconfigure(0, weight=1)

        header_frame = tk.Frame(history_panel)
        header_frame.grid(row=0, column=0, sticky='ew', padx=8, pady=8)
        header_frame.grid_columnconfigure(0, weight=1)

        tk.Label(header_frame, text='History', font=('Segoe UI', 12, 'bold')).pack(side='left')
        tk.Button(header_frame, text='Clear', command=self._clear_history,
                 font=('Segoe UI', 9), relief='flat', cursor='hand2').pack(side='right')

        history_frame = tk.Frame(history_panel)
        history_frame.grid(row=1, column=0, sticky='nsew', padx=8, pady=(0, 8))
        history_frame.grid_rowconfigure(0, weight=1)
        history_frame.grid_columnconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(history_frame)
        scrollbar.grid(row=0, column=1, sticky='ns')

        self.history_text = tk.Text(history_frame, wrap='word', state='disabled',
                                    font=('Consolas', 10), relief='flat',
                                    yscrollcommand=scrollbar.set)
        self.history_text.grid(row=0, column=0, sticky='nsew')
        scrollbar.config(command=self.history_text.yview)

        self.history_text.tag_config('expr', foreground='#6c757d')
        self.history_text.tag_config('result', font=('Consolas', 11, 'bold'))

        self._load_history()

    def _load_history(self):
        """Load history into text widget"""
        self.history_text.config(state='normal')
        self.history_text.delete(1.0, tk.END)

        for entry in self.history_manager.get_recent():
            self.history_text.insert(tk.END, entry['expression'] + '\n', 'expr')
            self.history_text.insert(tk.END, '= ' + entry['result'] + '\n\n', 'result')

        self.history_text.config(state='disabled')

    def _clear_history(self):
        """Clear all history"""
        if messagebox.askyesno('Clear History', 'Clear all calculation history?'):
            self.history_manager.clear()
            self._load_history()

    def _bind_keyboard(self):
        """Bind keyboard shortcuts"""
        self.bind_all('<Control-c>', lambda e: self.clear())
        self.bind_all('<Delete>', lambda e: self.clear())

    def _on_button(self, label: str):
        """Handle button press"""
        actions = {
            'C': self.clear,
            '⌫': self.backspace,
            '=': self.evaluate,
            'Ans': lambda: self._insert(str(self.last_answer)),
            '√': lambda: self._insert('sqrt('),
            'x²': lambda: self._insert('**2'),
            'xʸ': lambda: self._insert('**'),
            'sin': lambda: self._insert('sin('),
            'cos': lambda: self._insert('cos('),
            'tan': lambda: self._insert('tan('),
            'ln': lambda: self._insert('log('),
            'log': lambda: self._insert('log10('),
            'n!': lambda: self._insert('factorial('),
            '±': self._toggle_sign,
            'MC': self._memory_clear,
            'MR': self._memory_recall,
            'M+': self._memory_add,
            'M-': self._memory_subtract
        }

        if label in actions:
            actions[label]()
        else:
            self._insert(label)

    def _insert(self, text: str):
        """Insert text at cursor"""
        current = self.expression_var.get()
        self.expression_var.set(current + text)

    def clear(self):
        """Clear display"""
        self.expression_var.set('')
        self.result_var.set('0')

    def backspace(self):
        """Remove last character"""
        current = self.expression_var.get()
        self.expression_var.set(current[:-1])
        if not current[:-1]:
            self.result_var.set('0')

    def _toggle_sign(self):
        """Toggle sign of current number"""
        current = self.expression_var.get()
        if current:
            try:
                val = float(self.result_var.get())
                self.expression_var.set(str(-val))
            except:
                pass

    def _memory_clear(self):
        """Clear memory"""
        self.memory = 0.0
        self.memory_label.config(text='')

    def _memory_recall(self):
        """Recall memory"""
        self.expression_var.set(str(self.memory))

    def _memory_add(self):
        """Add to memory"""
        try:
            val = float(self.result_var.get())
            self.memory += val
            self.memory_label.config(text=f'M: {self.memory}')
        except:
            pass

    def _memory_subtract(self):
        """Subtract from memory"""
        try:
            val = float(self.result_var.get())
            self.memory -= val
            self.memory_label.config(text=f'M: {self.memory}')
        except:
            pass

    def evaluate(self):
        """Evaluate expression"""
        expr = self.expression_var.get().strip()
        if not expr:
            return

        try:
            result = SafeEvaluator.evaluate(expr)

            if isinstance(result, float):
                if result.is_integer():
                    result = int(result)
                else:
                    result = round(result, 10)

            result_str = str(result)
            self.result_var.set(result_str)
            self.last_answer = result

            self.history_manager.add(expr, result_str)
            self._load_history()

        except Exception as e:
            self.result_var.set('Error')
            messagebox.showerror('Calculation Error', str(e))


class ConverterFrame(tk.Frame):
    """Number system converter"""

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._create_interface()

    def _create_interface(self):
        """Create converter interface"""
        container = tk.Frame(self)
        container.grid(row=0, column=0, sticky='nsew', padx=40, pady=40)
        container.grid_columnconfigure(0, weight=1)

        tk.Label(container, text='Number System Converter',
                font=('Segoe UI', 18, 'bold')).grid(row=0, column=0, pady=(0, 20))

        input_frame = tk.LabelFrame(container, text='Input',
                                    font=('Segoe UI', 11, 'bold'), padx=20, pady=15)
        input_frame.grid(row=1, column=0, sticky='ew', pady=10)
        input_frame.grid_columnconfigure(0, weight=1)

        self.input_var = tk.StringVar()
        self.input_var.trace('w', self._on_input_change)

        tk.Entry(input_frame, textvariable=self.input_var,
                font=('Consolas', 16), justify='center').grid(row=0, column=0,
                                                               sticky='ew', pady=(0, 10))

        self.from_var = tk.StringVar(value='Decimal')
        self.from_var.trace('w', self._on_input_change)

        from_frame = tk.Frame(input_frame)
        from_frame.grid(row=1, column=0, sticky='ew')
        from_frame.grid_columnconfigure(1, weight=1)

        tk.Label(from_frame, text='From:', font=('Segoe UI', 10)).grid(row=0, column=0,
                                                                        sticky='w', padx=(0, 10))

        from_menu = ttk.Combobox(from_frame, textvariable=self.from_var,
                                values=list(NumberConverter.BASES.keys()),
                                state='readonly', font=('Segoe UI', 11))
        from_menu.grid(row=0, column=1, sticky='ew')

        output_frame = tk.LabelFrame(container, text='Output',
                                     font=('Segoe UI', 11, 'bold'), padx=20, pady=15)
        output_frame.grid(row=2, column=0, sticky='ew', pady=10)
        output_frame.grid_columnconfigure(0, weight=1)

        results_container = tk.Frame(output_frame)
        results_container.grid(row=0, column=0, sticky='ew')
        results_container.grid_columnconfigure(1, weight=1)

        self.result_vars = {}
        bases = ['Binary', 'Octal', 'Decimal', 'Hexadecimal']

        for i, base in enumerate(bases):
            tk.Label(results_container, text=f'{base}:',
                    font=('Segoe UI', 10, 'bold'), width=12,
                    anchor='w').grid(row=i, column=0, sticky='w', pady=5)

            var = tk.StringVar(value='0')
            self.result_vars[base] = var

            result_entry = tk.Entry(results_container, textvariable=var,
                                   font=('Consolas', 12), state='readonly',
                                   justify='left', relief='flat')
            result_entry.grid(row=i, column=1, sticky='ew', pady=5)

        btn_frame = tk.Frame(container)
        btn_frame.grid(row=3, column=0, pady=(20, 0))

        tk.Button(btn_frame, text='Clear', command=self._clear,
                 font=('Segoe UI', 11), width=15, height=2,
                 cursor='hand2').pack(side='left', padx=5)

        tk.Button(btn_frame, text='Copy All', command=self._copy_all,
                 font=('Segoe UI', 11), width=15, height=2,
                 cursor='hand2').pack(side='left', padx=5)

    def _on_input_change(self, *args):
        """Handle input change"""
        self._convert()

    def _convert(self):
        """Convert number to all bases"""
        input_val = self.input_var.get().strip()
        from_base = self.from_var.get()

        if not input_val:
            for var in self.result_vars.values():
                var.set('0')
            return

        if not NumberConverter.validate_input(input_val, from_base):
            for var in self.result_vars.values():
                var.set('Invalid input')
            return

        try:
            for to_base, var in self.result_vars.items():
                result = NumberConverter.convert(input_val, from_base, to_base)
                var.set(result)
        except Exception as e:
            for var in self.result_vars.values():
                var.set(f'Error: {str(e)}')

    def _clear(self):
        """Clear all fields"""
        self.input_var.set('')
        for var in self.result_vars.values():
            var.set('0')

    def _copy_all(self):
        """Copy all results to clipboard"""
        results = []
        for base, var in self.result_vars.items():
            results.append(f'{base}: {var.get()}')

        text = '\n'.join(results)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo('Copied', 'All results copied to clipboard')


class CalculatorApp(tk.Tk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        self.title('Professional Calculator')
        self.geometry('900x600')
        self.minsize(800, 500)

        self.dark_mode = tk.BooleanVar(value=False)
        self.current_frame = None

        self._create_ui()
        self._apply_theme()

        self.protocol('WM_DELETE_WINDOW', self._on_close)

    def _create_ui(self):
        """Create main UI"""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        toolbar = tk.Frame(self, height=50)
        toolbar.grid(row=0, column=0, sticky='ew')
        toolbar.grid_columnconfigure(1, weight=1)

        mode_frame = tk.Frame(toolbar)
        mode_frame.grid(row=0, column=0, padx=15, pady=10)

        self.mode_var = tk.StringVar(value='calculator')

        tk.Radiobutton(mode_frame, text='Scientific Calculator',
                      variable=self.mode_var, value='calculator',
                      command=self._switch_mode, font=('Segoe UI', 10),
                      cursor='hand2').pack(side='left', padx=5)

        tk.Radiobutton(mode_frame, text='Number Converter',
                      variable=self.mode_var, value='converter',
                      command=self._switch_mode, font=('Segoe UI', 10),
                      cursor='hand2').pack(side='left', padx=5)

        theme_frame = tk.Frame(toolbar)
        theme_frame.grid(row=0, column=2, padx=15, pady=10)

        tk.Checkbutton(theme_frame, text='🌙 Dark Mode',
                      variable=self.dark_mode, command=self._apply_theme,
                      font=('Segoe UI', 10), cursor='hand2').pack()

        self.container = tk.Frame(self)
        self.container.grid(row=1, column=0, sticky='nsew')
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (CalculatorFrame, ConverterFrame):
            frame = F(self.container, self)
            frame.grid(row=0, column=0, sticky='nsew')
            self.frames[F.__name__] = frame

        self._switch_mode()

    def _switch_mode(self):
        """Switch between calculator and converter"""
        frame_name = 'CalculatorFrame' if self.mode_var.get() == 'calculator' else 'ConverterFrame'
        self.current_frame = self.frames[frame_name]
        self.current_frame.tkraise()

    def _apply_theme(self):
        """Apply current theme"""
        theme = Theme.DARK if self.dark_mode.get() else Theme.LIGHT

        def style_widget(widget, is_button=False):
            """Recursively style widget and children"""
            try:
                widget_class = widget.__class__.__name__

                if isinstance(widget, ModernButton):
                    widget.draw()
                elif widget_class in ('Frame', 'LabelFrame', 'Tk'):
                    widget.configure(bg=theme['panel'] if widget_class == 'LabelFrame' else theme['bg'])
                    if widget_class == 'LabelFrame':
                        widget.configure(fg=theme['fg'])
                elif widget_class == 'Label':
                    widget.configure(bg=theme['panel'], fg=theme['fg'])
                elif widget_class == 'Entry':
                    state = widget.cget('state')
                    if state == 'readonly':
                        widget.configure(bg=theme['display_bg'], fg=theme['secondary_fg'],
                                       readonlybackground=theme['display_bg'])
                    else:
                        widget.configure(bg=theme['display_bg'], fg=theme['fg'],
                                       insertbackground=theme['fg'])
                elif widget_class == 'Text':
                    widget.configure(bg=theme['history_bg'], fg=theme['fg'],
                                   insertbackground=theme['fg'])
                elif widget_class == 'Button':
                    widget.configure(bg=theme['btn_bg'], fg=theme['fg'],
                                   activebackground=theme['btn_hover'])
                elif widget_class == 'Radiobutton':
                    widget.configure(bg=theme['bg'], fg=theme['fg'],
                                   selectcolor=theme['panel'],
                                   activebackground=theme['bg'])
                elif widget_class == 'Checkbutton':
                    widget.configure(bg=theme['bg'], fg=theme['fg'],
                                   selectcolor=theme['panel'],
                                   activebackground=theme['bg'])
            except:
                pass

            for child in widget.winfo_children():
                style_widget(child)

        self.configure(bg=theme['bg'])
        style_widget(self)

    def _on_close(self):
        """Handle window close"""
        self.destroy()


def main():
    """Main entry point"""
    app = CalculatorApp()
    app.mainloop()


if __name__ == '__main__':
    main()