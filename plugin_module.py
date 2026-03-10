import math
import functools
import ast
import re

class PluginManager:
    """Manager to plug in all components and increase performance."""
    
    def __init__(self):
        self.math_names = {}
        self.ast_nodes = []
        self.converter_bases = {}
        self.converter_patterns = {}

    def plugin_everything(self):
        """Plugin everything that the calculator needs to use."""
        self._plugin_math()
        self._plugin_ast_nodes()
        self._plugin_converters()

    def _plugin_math(self):
        self.math_names = {
            name: getattr(math, name)
            for name in dir(math)
            if not name.startswith("__")
        }
        self.math_names.update({
            "abs": abs,
            "round": round,
            "pow": pow,
            "min": min,
            "max": max,
            "e": math.e,
            "pi": math.pi,
            "inf": math.inf,
        })

    def _plugin_ast_nodes(self):
        base_nodes = [
            ast.Expression, ast.Call, ast.Name, ast.Load, ast.BinOp, ast.UnaryOp,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow, ast.USub, ast.UAdd,
            ast.LShift, ast.RShift, ast.BitXor, ast.BitAnd, ast.BitOr, ast.FloorDiv,
            ast.Tuple, ast.List,
        ]
        for _node in ["Constant", "Num", "Str", "Bytes", "NameConstant"]:
            if hasattr(ast, _node):
                base_nodes.append(getattr(ast, _node))
        self.ast_nodes = tuple(base_nodes)

    def _plugin_converters(self):
        self.converter_bases = {
            "Binary": 2,
            "Octal": 8,
            "Decimal": 10,
            "Hexadecimal": 16,
        }
        self.converter_patterns = {
            "Binary":      re.compile(r"^-?[01]+$"),
            "Octal":       re.compile(r"^-?[0-7]+$"),
            "Decimal":     re.compile(r"^-?\d+$"),
            "Hexadecimal": re.compile(r"^-?[0-9A-Fa-f]+$"),
        }

    @staticmethod
    def increase_performance(maxsize=1024):
        """Returns a caching decorator to increase calculation performance."""
        def decorator(func):
            cache = {}
            @functools.wraps(func)
            def wrapper(*args):
                if maxsize and len(cache) >= maxsize:
                    cache.clear()
                if args not in cache:
                    cache[args] = func(*args)
                return cache[args]
            return wrapper
        return decorator

# Instantiate and setup
plugin_system = PluginManager()
plugin_system.plugin_everything()
