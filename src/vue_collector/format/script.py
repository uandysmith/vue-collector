from ..script import _js_advance


def _skip_regex(line: str, i: int) -> int:
    """Skip a JS regex literal starting at line[i] (the opening '/'). Returns new i."""
    i += 1  # skip opening /
    n = len(line)
    in_class = False
    while i < n:
        c = line[i]
        if c == '\\':
            i += 2
        elif c == '[':
            in_class = True
            i += 1
        elif c == ']' and in_class:
            in_class = False
            i += 1
        elif c == '/' and not in_class:
            i += 1
            while i < n and line[i].isalpha():  # skip flags: g, i, m, s, u, y
                i += 1
            return i
        else:
            i += 1
    return i


def _scan_line(
    line: str, in_template: bool, in_block_comment: bool
) -> tuple[int, int, bool, bool]:
    """Scan a JS line and count real { and } (outside strings/comments/regex).

    Returns (opens, closes, new_in_template, new_in_block_comment).
    Braces inside template literals, string literals, or regex literals are NOT counted.
    """
    opens = closes = 0
    i = 0
    n = len(line)
    prev_was_operand = False  # True after identifier/number/)/] — '/' is then division

    while i < n:
        c = line[i]

        if in_block_comment:
            if c == '*' and i + 1 < n and line[i + 1] == '/':
                in_block_comment = False
                i += 2
            else:
                i += 1
        elif in_template:
            if c == '\\':
                i += 2  # skip escaped char
            elif c == '`':
                in_template = False
                i += 1
            else:
                i += 1
        elif c in ('"', "'"):
            i = _js_advance(line, i)
            prev_was_operand = True
        elif c == '`':
            in_template = True
            prev_was_operand = False
            i += 1
        elif c == '/':
            if i + 1 < n and line[i + 1] == '/':
                break  # rest of line is a comment
            elif i + 1 < n and line[i + 1] == '*':
                in_block_comment = True
                prev_was_operand = False
                i += 2
            elif not prev_was_operand:
                i = _skip_regex(line, i)
                prev_was_operand = True
            else:
                prev_was_operand = False
                i += 1
        elif c == '{':
            opens += 1
            prev_was_operand = False
            i += 1
        elif c == '}':
            closes += 1
            prev_was_operand = True
            i += 1
        elif c == '(':
            prev_was_operand = False
            i += 1
        elif c == ')':
            prev_was_operand = True
            i += 1
        elif c == '[':
            prev_was_operand = False
            i += 1
        elif c == ']':
            prev_was_operand = True
            i += 1
        elif c in (' ', '\t'):
            i += 1  # whitespace: preserve prev_was_operand
        elif c.isalnum() or c in ('_', '$'):
            prev_was_operand = True
            i += 1
        else:
            prev_was_operand = False
            i += 1

    return opens, closes, in_template, in_block_comment


def _format_script(js: str) -> str:
    if not js.strip():
        return ''
    lines = js.split('\n')
    result: list[str] = []
    depth = 0
    in_template = False
    in_block_comment = False

    for line in lines:
        stripped = line.strip()

        if in_template or in_block_comment:
            # Preserve lines inside multiline constructs as-is (no re-indent).
            # Template literal content must not be modified (trailing spaces are significant);
            # block comment lines can have trailing spaces stripped safely.
            result.append(line if in_template else line.rstrip())
            opens, closes, in_template, in_block_comment = _scan_line(
                line, in_template, in_block_comment
            )
            depth = max(0, depth + opens - closes)
            continue

        if not stripped:
            result.append('')
            continue

        opens, closes, in_template, in_block_comment = _scan_line(line, False, False)
        line_depth = depth - closes if stripped.startswith('}') else depth
        line_depth = max(0, line_depth)
        # If the line opens a multiline template literal, trailing content is part of the
        # string and must not be stripped; use lstrip() to re-indent without losing it.
        line_out = line.lstrip() if in_template else stripped
        result.append('  ' * line_depth + line_out)
        depth = max(0, depth + opens - closes)

    return '\n'.join(result).strip()
