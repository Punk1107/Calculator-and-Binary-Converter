"""
Advanced Calculator & Number System Converter
Tkinter app with:
- Mode selection (Scientific Calculator / Number Converter)
- Number conversion between Binary, Decimal, Hexadecimal, Octal
- Real-time Light / Dark mode toggle
- Enhanced scientific calculator with more functions (trig, log, exponent, factorial, constants, etc.)
- Improved UI/UX: cleaner layout, consistent fonts, responsive buttons

Save as: advanced_tk_calculator.py
Run: python advanced_tk_calculator.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
import math
import ast

# ---------------- safe evaluator -----------------
ALLOWED_NAMES = {name: getattr(math, name) for name in dir(math) if not name.startswith("__")}
ALLOWED_NAMES.update({
    'abs': abs,
    'round': round,
    'pow': pow,
    'factorial': math.factorial
})

ALLOWED_NODES = (
    ast.Expression, ast.Call, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
    ast.Num, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
    ast.Pow, ast.USub, ast.UAdd, ast.LShift, ast.RShift, ast.BitXor,
    ast.BitAnd, ast.BitOr, ast.FloorDiv, ast.Tuple, ast.List, ast.Subscript,
    ast.Index, ast.Slice
)

def safe_eval(expr: str):
    expr = expr.replace('×', '*').replace('÷', '/').replace('^', '**')
    try:
        node = ast.parse(expr, mode='eval')
    except Exception as e:
        raise ValueError(f"Invalid expression: {e}")

    for n in ast.walk(node):
        if not isinstance(n, ALLOWED_NODES):
            raise ValueError(f"Disallowed expression: {type(n).__name__}")
        if isinstance(n, ast.Name) and n.id not in ALLOWED_NAMES:
            raise ValueError(f"Use of name '{n.id}' is not allowed")

    compiled = compile(node, '<safe>', 'eval')
    return eval(compiled, {'__builtins__': {}}, ALLOWED_NAMES)

# --------------- UI App -----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Advanced Calculator & Number Converter')
        self.geometry('800x450')
        self.minsize(680, 400)

        self.themes = {
            'light': {'bg':'#f3f4f6','panel':'#ffffff','fg':'#111827','btn_bg':'#e5e7eb','accent':'#2563eb'},
            'dark': {'bg':'#0b1220','panel':'#0f1724','fg':'#e6eef8','btn_bg':'#1f2937','accent':'#60a5fa'}
        }
        self.current_theme = 'light'

        control = tk.Frame(self)
        control.pack(fill='x', padx=8, pady=8)

        self.mode_var = tk.StringVar(value='calculator')
        ttk.Radiobutton(control, text='Scientific Calculator', variable=self.mode_var, value='calculator', command=self.switch_mode).pack(side='left', padx=4)
        ttk.Radiobutton(control, text='Number Converter', variable=self.mode_var, value='converter', command=self.switch_mode).pack(side='left', padx=4)

        self.theme_btn = ttk.Checkbutton(control, text='Dark Mode', command=self.toggle_theme, style='Toggle.TButton')
        self.theme_btn.pack(side='right')

        self.container = tk.Frame(self)
        self.container.pack(fill='both', expand=True, padx=8, pady=(0,8))

        self.frames = {}
        for F in (CalculatorFrame, ConverterFrame):
            frame = F(parent=self.container, controller=self)
            frame.grid(row=0, column=0, sticky='nsew')
            self.frames[F.__name__] = frame

        self.switch_mode()
        self.apply_theme()

    def switch_mode(self):
        self.show_frame('CalculatorFrame' if self.mode_var.get()=='calculator' else 'ConverterFrame')

    def show_frame(self, name):
        self.frames[name].tkraise()

    def toggle_theme(self):
        self.current_theme = 'dark' if self.current_theme=='light' else 'light'
        self.apply_theme()

    def apply_theme(self):
        th = self.themes[self.current_theme]
        self.configure(bg=th['bg'])
        def style_widget(w):
            cls = w.__class__.__name__
            try:
                if cls in ('Frame','LabelFrame'): w.configure(bg=th['bg'])
                elif cls=='Label': w.configure(bg=th['panel'], fg=th['fg'])
                elif cls=='Button': w.configure(bg=th['btn_bg'], fg=th['fg'], activebackground=th['accent'])
                elif cls=='Entry': w.configure(bg=th['panel'], fg=th['fg'], insertbackground=th['fg'])
                elif cls=='Text': w.configure(bg=th['panel'], fg=th['fg'], insertbackground=th['fg'])
            except: pass
            for child in w.winfo_children(): style_widget(child)
        style_widget(self)

# --------------- Calculator Frame -----------------
class CalculatorFrame(tk.Frame):
    def __init__(self,parent,controller):
        super().__init__(parent)
        self.controller = controller
        left = tk.Frame(self)
        left.pack(side='left', fill='both', expand=True, padx=(0,6))

        self.display_var = tk.StringVar()
        self.result_var = tk.StringVar()
        disp_frame = tk.Frame(left)
        disp_frame.pack(fill='x', padx=6, pady=6)
        self.entry = tk.Entry(disp_frame,textvariable=self.display_var,font=('Consolas',18),justify='right')
        self.entry.pack(fill='x',ipady=8)
        self.entry.bind('<Return>',lambda e:self.evaluate())
        res_label = tk.Label(disp_frame,textvariable=self.result_var,anchor='e',font=('Consolas',12))
        res_label.pack(fill='x')

        btn_frame = tk.Frame(left)
        btn_frame.pack(fill='both',expand=True,padx=6,pady=6)
        buttons = [
            ['7','8','9','/','sqrt'],['4','5','6','*','^'],['1','2','3','-','('],['0','.','=','+',')'],
            ['sin','cos','tan','log','ln'],['pi','e','Ans','C','DEL'],['factorial','exp','abs','round','%']
        ]
        for r,row in enumerate(buttons):
            for c,label in enumerate(row):
                b=tk.Button(btn_frame,text=label,command=lambda x=label:self.on_button(x),width=8,height=2)
                b.grid(row=r,column=c,padx=4,pady=4,sticky='nsew')
        for i in range(len(buttons[0])): btn_frame.grid_columnconfigure(i,weight=1)

    def on_button(self,label):
        if label=='C': self.clear()
        elif label=='DEL': self.backspace()
        elif label=='=': self.evaluate()
        elif label=='Ans': self.insert_text(self.result_var.get())
        elif label=='sqrt': self.insert_text('sqrt(')
        elif label=='^': self.insert_text('**')
        elif label in ('pi','e'): self.insert_text(label)
        elif label=='factorial': self.insert_text('factorial(')
        elif label=='exp': self.insert_text('exp(')
        elif label in ('abs','round','log','ln','sin','cos','tan'): self.insert_text(label+'(')
        else: self.insert_text(label)

    def insert_text(self,txt):
        cur=self.entry.index(tk.INSERT)
        self.entry.insert(cur,txt)
        self.entry.focus_set()

    def clear(self): self.display_var.set(''); self.result_var.set('')
    def backspace(self): s=self.display_var.get(); self.display_var.set(s[:-1])

    def evaluate(self):
        expr=self.display_var.get().strip()
        if not expr: return
        try:
            expr=expr.replace('ln(','log(')
            val=safe_eval(expr)
            if isinstance(val,float) and val.is_integer(): val=int(val)
            self.result_var.set(str(val))
        except Exception as e:
            messagebox.showerror('Error',f'Could not evaluate expression:\n{e}')

# --------------- Converter Frame -----------------
class ConverterFrame(tk.Frame):
    def __init__(self,parent,controller):
        super().__init__(parent)
        self.controller=controller
        container=tk.Frame(self)
        container.pack(fill='both',expand=True,padx=10,pady=10)

        left=tk.Frame(container)
        left.pack(side='left',fill='both',expand=True)
        tk.Label(left,text='Number System Converter',font=('Helvetica',14,'bold')).pack(anchor='w')
        tk.Label(left,text='Enter number:',anchor='w').pack(fill='x',pady=(8,0))

        self.input_var=tk.StringVar()
        self.result_var=tk.StringVar()
        self.from_var=tk.StringVar(value='Binary')
        self.to_var=tk.StringVar(value='Decimal')

        tk.Entry(left,textvariable=self.input_var,font=('Consolas',16)).pack(fill='x',pady=6)
        tk.OptionMenu(left,self.from_var,'Binary','Decimal','Hexadecimal','Octal').pack(fill='x',pady=4)
        tk.OptionMenu(left,self.to_var,'Binary','Decimal','Hexadecimal','Octal').pack(fill='x',pady=4)

        btn_frame=tk.Frame(left); btn_frame.pack(fill='x',pady=6)
        tk.Button(btn_frame,text='Convert',command=self.convert).pack(side='left',padx=4)
        tk.Button(btn_frame,text='Clear',command=self.clear).pack(side='left',padx=4)

        tk.Label(left,text='Result:',anchor='w').pack(fill='x',pady=(8,0))
        tk.Label(left,textvariable=self.result_var,font=('Consolas',16),anchor='w').pack(fill='x',pady=4)

    def convert(self):
        s=self.input_var.get().strip().replace(' ','')
        try:
            val=self.to_decimal(s,self.from_var.get())
            res=self.from_decimal(val,self.to_var.get())
            self.result_var.set(res)
        except Exception as e:
            self.result_var.set(f'Error: {e}')

    def clear(self): self.input_var.set(''); self.result_var.set('')

    def to_decimal(self,s,from_sys):
        if from_sys=='Binary': return int(s,2)
        elif from_sys=='Decimal': return int(s,10)
        elif from_sys=='Hexadecimal': return int(s,16)
        elif from_sys=='Octal': return int(s,8)
        else: raise ValueError('Unknown input system')

    def from_decimal(self,val,to_sys):
        if to_sys=='Binary': return bin(val)[2:]
        elif to_sys=='Decimal': return str(val)
        elif to_sys=='Hexadecimal': return hex(val)[2:].upper()
        elif to_sys=='Octal': return oct(val)[2:]
        else: raise ValueError('Unknown output system')

if __name__=='__main__':
    app=App()
    app.mainloop()
