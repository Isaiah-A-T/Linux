"""Parser for Valve's text KeyValues format (libraryfolders.vdf, *.acf)."""


def _tokens(text):
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
        elif ch == "/" and text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                return
        elif ch in "{}":
            yield ch
            i += 1
        elif ch == '"':
            i += 1
            out = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    out.append({"n": "\n", "t": "\t"}.get(text[i + 1], text[i + 1]))
                    i += 2
                else:
                    out.append(text[i])
                    i += 1
            i += 1
            yield ("s", "".join(out))
        else:
            start = i
            while i < n and not text[i].isspace() and text[i] not in '{}"':
                i += 1
            yield ("s", text[start:i])


def loads(text):
    """Return nested dicts; keys keep their case, values are strings."""
    root = {}
    stack = [root]
    key = None
    for tok in _tokens(text):
        if tok == "{":
            child = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        elif tok == "}":
            if len(stack) > 1:
                stack.pop()
            key = None
        elif key is None:
            key = tok[1]
        else:
            stack[-1][key] = tok[1]
            key = None
    return root


def load(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return loads(f.read())
