"""Deterministic tools: safe math evaluation and unit conversion (no eval, no model guessing)."""
import ast
import math
import operator as op

BIN = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.FloorDiv: op.floordiv, ast.Mod: op.mod, ast.Pow: op.pow}
UNARY = {ast.UAdd: op.pos, ast.USub: op.neg}
FUNCS = {
    "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos,
    "atan": math.atan, "log": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp,
    "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil, "min": min, "max": max,
}
CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
MAX_DEPTH = 40


def evaluate(expression: str) -> float | int:
    if len(expression) > 200:
        raise ValueError("Expression is too long")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        raise ValueError("Could not parse the expression") from exc

    def walk(node: ast.AST, depth: int = 0):
        if depth > MAX_DEPTH:
            raise ValueError("Expression is too deeply nested")
        if isinstance(node, ast.Expression):
            return walk(node.body, depth + 1)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name) and node.id in CONSTS:
            return CONSTS[node.id]
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
            return UNARY[type(node.op)](walk(node.operand, depth + 1))
        if isinstance(node, ast.BinOp) and type(node.op) in BIN:
            left, right = walk(node.left, depth + 1), walk(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ValueError("Exponent is too large")
            return BIN[type(node.op)](left, right)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS and not node.keywords:
            return FUNCS[node.func.id](*[walk(a, depth + 1) for a in node.args])
        raise ValueError("Only numbers, + - * / // % **, parentheses, constants (pi, e) and basic functions are allowed")

    try:
        result = walk(tree)
    except (ZeroDivisionError, OverflowError, TypeError) as exc:
        raise ValueError("The calculation is not valid") from exc
    if isinstance(result, float) and (math.isnan(result) or math.isinf(result)):
        raise ValueError("The result is not a finite number")
    return result


# category -> {unit: factor to the base unit}
UNITS: dict[str, dict[str, float]] = {
    "length": {"mm": 0.001, "cm": 0.01, "m": 1, "km": 1000, "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344},
    "mass": {"mg": 1e-6, "g": 0.001, "kg": 1, "lb": 0.45359237, "oz": 0.028349523125},
    "volume": {"ml": 0.001, "l": 1, "gal": 3.785411784},
    "time": {"s": 1, "min": 60, "h": 3600, "day": 86400},
    "data": {"b": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12},
}
TEMPERATURE = {"c", "f", "k"}


def _category(unit: str) -> str | None:
    for name, table in UNITS.items():
        if unit in table:
            return name
    return "temperature" if unit in TEMPERATURE else None


def convert(value: float, src: str, dst: str) -> float:
    src, dst = src.lower(), dst.lower()
    cat_src, cat_dst = _category(src), _category(dst)
    if cat_src is None or cat_dst is None:
        raise ValueError("Unknown unit")
    if cat_src != cat_dst:
        raise ValueError(f"Cannot convert {cat_src} to {cat_dst}")
    if cat_src == "temperature":
        kelvin = {"c": value + 273.15, "f": (value - 32) * 5 / 9 + 273.15, "k": value}[src]
        return {"c": kelvin - 273.15, "f": (kelvin - 273.15) * 9 / 5 + 32, "k": kelvin}[dst]
    return value * UNITS[cat_src][src] / UNITS[cat_src][dst]


def unit_catalog() -> dict[str, list[str]]:
    return {**{k: list(v) for k, v in UNITS.items()}, "temperature": sorted(TEMPERATURE)}
