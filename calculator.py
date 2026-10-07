import ast
import operator
import re

from text_utils import normalize_text

# Avaliador aritmético seguro - interpreta a árvore sintática manualmente e só
# aceita números e operadores, em vez de usar eval() (que executaria
# qualquer código Python, um risco real de segurança com texto vindo da voz).
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("expressão não suportada")


def safe_eval(expression):
    tree = ast.parse(expression, mode="eval")
    return _safe_eval(tree)


# Palavras faladas de operação -> símbolo. "por" só vira operador quando
# aparece logo depois de "dividido"/"multiplicado" ("dividido por 2"),
# senão é só uma preposição comum e seria perigoso tratar como "/" sempre.
_WORD_TO_OP = {
    "mais": "+",
    "soma": "+",
    "menos": "-",
    "vezes": "*",
    "multiplicado": "*",
    "dividido": "/",
    "elevado": "**",
}
_NUMBER_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def extract_expression(text):
    """Converte uma frase falada ("quanto é 23 vezes 7") numa expressão
    aritmética em texto ("23 * 7"), ignorando palavras que não são número
    nem operador. Devolve None se não achar nada parecido com uma conta.
    """
    tokens = normalize_text(text).split()
    parts = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if _NUMBER_RE.match(token):
            parts.append(token.replace(",", "."))
        elif token in _WORD_TO_OP:
            parts.append(_WORD_TO_OP[token])
            if token in ("dividido", "multiplicado") and i + 1 < len(tokens) and tokens[i + 1] == "por":
                i += 1  # pula o "por" de "dividido por"/"multiplicado por"
        i += 1
    return " ".join(parts) if parts else None


def calculate_spoken(text):
    """Tenta calcular uma conta falada em português. Devolve o resultado
    (int se for um número inteiro, float senão), ou None se não conseguir
    entender/calcular nada.
    """
    expression = extract_expression(text)
    if not expression:
        return None

    try:
        result = safe_eval(expression)
    except Exception:
        return None

    if isinstance(result, float) and result.is_integer():
        result = int(result)
    return result
