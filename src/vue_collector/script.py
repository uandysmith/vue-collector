def _js_advance(code: str, i: int) -> int:
    """Advance past a JS string literal or comment starting at code[i].

    Handles: string literals (', ", `), single-line comments (//), block comments (/* */).
    For a lone '/' not followed by '/' or '*', returns i + 1.
    Returns the new index positioned after the consumed token.
    """
    c = code[i]
    n = len(code)
    if c in ('"', "'", '`'):
        quote = c
        i += 1
        while i < n:
            if code[i] == '\\':
                i += 2
                continue
            if code[i] == quote:
                return i + 1
            i += 1
        return i
    if i + 1 < n and code[i + 1] == '/':
        # Single-line comment — stop at '\n' so caller can set at_stmt_start
        while i < n and code[i] != '\n':
            i += 1
        return i
    if i + 1 < n and code[i + 1] == '*':
        i += 2
        while i < n - 1:
            if code[i] == '*' and code[i + 1] == '/':
                return i + 2
            i += 1
        return i
    return i + 1


def _extract_export_default(script: str) -> tuple[str, str, str]:
    """Extract `export default { ... }` from a JS script string.

    Returns (before, component_body, after) where component_body is the
    content between the outer braces. Correctly skips string literals
    (single, double, template), single-line comments, and block comments.

    If `export default` is not found, returns (script, '', '').
    Raises ValueError if `export default` is not followed by `{`.
    """
    marker = 'export default'
    marker_idx = script.find(marker)
    if marker_idx == -1:
        return script, '', ''

    before = script[:marker_idx]
    rest = script[marker_idx + len(marker) :]

    # Skip whitespace after 'export default'
    i = 0
    while i < len(rest) and rest[i] in ' \t\n\r':
        i += 1

    if i >= len(rest) or rest[i] != '{':
        raise ValueError(f"'export default' must be followed by '{{', got {rest[i : i + 10]!r}")

    opening = i
    depth = 0
    while i < len(rest):
        c = rest[i]

        if c in ('"', "'", '`') or c == '/':
            i = _js_advance(rest, i)

        elif c == '{':
            depth += 1
            i += 1

        elif c == '}':
            depth -= 1
            if depth == 0:
                component_body = rest[opening + 1 : i].strip()
                after = rest[i + 1 :].strip()
                return before, component_body, after
            i += 1

        else:
            i += 1

    raise ValueError("Unclosed 'export default {' — no matching '}'")


def _has_import(code: str) -> bool:
    """Return True if code contains a top-level import statement.

    Scans character by character, skipping string literals (', ", `) and comments
    (// and /* */), so import keywords inside strings or comments are not flagged.
    A match is only recognised at a statement boundary: start of code, after a
    newline, or after a semicolon (leading whitespace is ignored).
    """
    i = 0
    n = len(code)
    at_stmt_start = True
    while i < n:
        c = code[i]

        if c in ('"', "'", '`'):
            at_stmt_start = False
            i = _js_advance(code, i)

        elif c == '/' and i + 1 < n and code[i + 1] in ('/', '*'):
            # Comment — at_stmt_start preserved; for '//' the '\n' is left for next iteration
            i = _js_advance(code, i)

        elif c in ('\n', ';'):
            at_stmt_start = True
            i += 1

        elif c in (' ', '\t', '\r') and at_stmt_start:
            i += 1

        elif at_stmt_start and (code[i : i + 7] == 'import ' or code[i : i + 7] == 'import{'):
            return True

        else:
            at_stmt_start = False
            i += 1

    return False


def _parse_script(name: str, raw: str) -> tuple[str, str]:
    """Parse a <script> section and return (variables, component_body).

    variables — JS code before and after `export default { ... }`.
    component_body — content inside the export default object.
    Raises ValueError if the script contains import statements.
    """
    if not raw:
        return '', ''
    before, component, after = _extract_export_default(raw)
    variables_parts = [p.strip() for p in (before, after) if p.strip()]
    variables = '\n'.join(variables_parts)
    if not component and not variables:
        return '', ''
    if _has_import(before) or _has_import(after):
        raise ValueError(f'Component {name} contains import statements which are not supported')
    if raw.strip() and not component:
        raise ValueError(f'Invalid component {name}: export default not found or not an object')
    return variables, component
