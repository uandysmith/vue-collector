from .. import style as _style_module


def _format_style(css: str) -> str:
    """Format a CSS/LESS string using lesscpy's PLY tokenizer."""
    if not css.strip():
        return ''
    lexer = _style_module._parser.lex.lexer.clone()
    lexer.input(css)

    out: list[str] = []
    buf: list[str] = []
    depth = 0
    paren_depth = 0
    had_property = False  # True after emitting a property inside a block

    for tok in lexer:
        t = tok.type
        v = tok.value

        if t == 't_ws':
            if buf:
                buf.append(' ')
        elif t == 't_popen':
            paren_depth += 1
            buf.append(v)
        elif t == 't_pclose':
            paren_depth -= 1
            buf.append(v)
        elif t == 't_bopen' and paren_depth == 0:
            sel = ''.join(buf).strip()
            buf.clear()
            indent = '  ' * depth
            if depth > 0 and had_property:
                out.append('\n')
            out.append(f'{indent}{sel} {{\n')
            depth += 1
            had_property = False
        elif t == 't_semicolon' and paren_depth == 0:
            prop = ''.join(buf).strip()
            buf.clear()
            if prop:
                indent = '  ' * depth
                out.append(f'{indent}{prop};\n')
                if depth > 0:
                    had_property = True
        elif t == 't_bclose':
            buf.clear()
            depth -= 1
            indent = '  ' * depth
            out.append(f'{indent}}}\n')
            had_property = False
        else:
            buf.append(v)

    return ''.join(out).rstrip('\n')
