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
                remainder = rest[i + 1 :].lstrip()
                if remainder.startswith(';'):
                    remainder = remainder[1:]
                after = remainder.strip()
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


def _strip_imports(code: str) -> str:
    """Remove all top-level import statements from JS code.

    Scans character by character (like _has_import), skipping string literals
    and comments. When an import statement is found, its byte range is recorded
    and removed from the output. Handles all import forms including multiline
    imports (import { ... } from ...).
    """
    if not code:
        return code
    i = 0
    n = len(code)
    at_stmt_start = True
    ranges: list[tuple[int, int]] = []

    while i < n:
        c = code[i]

        if c in ('"', "'", '`'):
            at_stmt_start = False
            i = _js_advance(code, i)

        elif c == '/' and i + 1 < n and code[i + 1] in ('/', '*'):
            i = _js_advance(code, i)

        elif c in ('\n', ';'):
            at_stmt_start = True
            i += 1

        elif c in (' ', '\t', '\r') and at_stmt_start:
            i += 1

        elif at_stmt_start and (code[i : i + 7] == 'import ' or code[i : i + 7] == 'import{'):
            # Include leading whitespace on this line
            start = i
            while start > 0 and code[start - 1] in (' ', '\t'):
                start -= 1
            # Find end of the import statement
            j = i + 6
            while j < n and code[j] in (' ', '\t'):
                j += 1
            if j < n and code[j] == '{':
                depth = 1
                j += 1
                while j < n and depth > 0:
                    if code[j] == '{':
                        depth += 1
                    elif code[j] == '}':
                        depth -= 1
                    j += 1
            # Skip to end of line
            while j < n and code[j] != '\n':
                j += 1
            # Include trailing newline
            if j < n and code[j] == '\n':
                j += 1
            ranges.append((start, j))
            i = j
            at_stmt_start = True

        else:
            at_stmt_start = False
            i += 1

    if not ranges:
        return code

    parts: list[str] = []
    prev = 0
    for start, end in ranges:
        parts.append(code[prev:start])
        prev = end
    parts.append(code[prev:])
    return ''.join(parts)


def _strip_object_key(component: str, key: str) -> str:
    """Remove a top-level key and its value from a JS object body.

    Finds `key` at brace depth 0 followed by `:`, skips the value (object,
    array, string literal, or plain identifier/number), and removes the entire
    key-value pair including trailing comma and surrounding whitespace.
    """
    if not component:
        return component
    key_len = len(key)
    i = 0
    n = len(component)
    at_key_start = True
    depth = 0

    while i < n:
        c = component[i]
        if c in ('"', "'", '`') or (c == '/' and i + 1 < n and component[i + 1] in ('/', '*')):
            at_key_start = False
            i = _js_advance(component, i)
        elif c == '{':
            depth += 1
            at_key_start = True
            i += 1
        elif c == '}':
            depth -= 1
            at_key_start = True
            i += 1
        elif c in ('\n', ',') and depth == 0:
            at_key_start = True
            i += 1
        elif c in (' ', '\t', '\r') and at_key_start:
            i += 1
        elif at_key_start and depth == 0 and component[i : i + key_len] == key:
            j = i + key_len
            while j < n and component[j] in (' ', '\t'):
                j += 1
            if j < n and component[j] == ':':
                key_start = i
                j += 1
                while j < n and component[j] in (' ', '\t', '\n', '\r'):
                    j += 1
                # Skip value based on its first character
                if j < n and component[j] in ('{', '['):
                    open_ch = component[j]
                    close_ch = '}' if open_ch == '{' else ']'
                    val_depth = 1
                    j += 1
                    while j < n and val_depth > 0:
                        vc = component[j]
                        if vc in ('"', "'", '`') or (vc == '/' and j + 1 < n and component[j + 1] in ('/', '*')):
                            j = _js_advance(component, j)
                        elif vc == open_ch:
                            val_depth += 1
                            j += 1
                        elif vc == close_ch:
                            val_depth -= 1
                            j += 1
                        else:
                            j += 1
                elif j < n and component[j] in ('"', "'"):
                    j = _js_advance(component, j)
                else:
                    while j < n and component[j] not in (',', '\n'):
                        j += 1
                # Skip trailing comma and whitespace
                while j < n and component[j] in (' ', '\t'):
                    j += 1
                if j < n and component[j] == ',':
                    j += 1
                while j < n and component[j] in (' ', '\t', '\n', '\r'):
                    j += 1
                # Strip leading whitespace/newline before the key
                while key_start > 0 and component[key_start - 1] in (' ', '\t'):
                    key_start -= 1
                if key_start > 0 and component[key_start - 1] == '\n':
                    key_start -= 1
                return component[:key_start] + component[j:]
            at_key_start = False
            i += 1
        else:
            at_key_start = False
            i += 1

    return component


def _parse_script(name: str, raw: str, *, forbid_imports: bool = False) -> tuple[str, str]:
    """Parse a <script> section and return (variables, component_body).

    variables — JS code before and after `export default { ... }`.
    component_body — content inside the export default object.

    By default, import statements are silently stripped and the 'components'
    key is removed from the component body. When forbid_imports=True, import
    statements raise ValueError instead.
    """
    if not raw:
        return '', ''
    before, component, after = _extract_export_default(raw)
    if forbid_imports:
        if _has_import(before) or _has_import(after):
            raise ValueError(f'Component {name} contains import statements which are not supported')
    else:
        before = _strip_imports(before)
        after = _strip_imports(after)
    component = _strip_object_key(component, 'components')
    component = _strip_object_key(component, 'name')
    variables_parts = [p.strip() for p in (before, after) if p.strip()]
    variables = '\n'.join(variables_parts)
    if not component and not variables:
        return '', ''
    if raw.strip() and not component:
        raise ValueError(f'Invalid component {name}: export default not found or not an object')
    return variables, component
