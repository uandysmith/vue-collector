from io import StringIO

from lesscpy.exceptions import CompilationError
from lesscpy.lessc.formatter import Formatter
from lesscpy.lessc.parser import LessParser
from lesscpy.plib.block import Block

_PASSTHROUGH_PREFIXES: tuple[str, ...] = (
    '@keyframes',
    '@-webkit-keyframes',
    '@-moz-keyframes',
    '@font-face',
)


class _MinifyArgs:
    minify = True
    xminify = False
    tabs = False
    spaces = 2


_parser: LessParser = LessParser(fail_with_exc=True)


def _scope_ast(nodes: list, scope_id: str, passthrough: bool = False) -> None:
    """Walk lesscpy AST and append [data-v-{scope_id}] token to every CSS selector."""
    attr = f'[data-v-{scope_id}]'
    for node in nodes:
        if not isinstance(node, Block):
            continue
        name_str = node.name.fmt({'nl': '', 'ws': ' ', 'tab': '', 'eb': ''}).strip().lower()
        is_passthrough = any(name_str.startswith(p) for p in _PASSTHROUGH_PREFIXES)
        if passthrough or is_passthrough:
            if hasattr(node, 'inner') and node.inner:
                _scope_ast(node.inner, scope_id, passthrough=True)
        elif node.name.subparse:
            if hasattr(node, 'inner') and node.inner:
                _scope_ast(node.inner, scope_id)
        else:
            node.name.parsed = [part + [attr] for part in node.name.parsed]
            # Recurse into LESS-nested blocks (e.g. .parent { .child {} }, &:hover {})
            if hasattr(node, 'inner') and node.inner:
                _scope_ast(node.inner, scope_id)


def _compile_style(raw: str, scope_id: str | None = None) -> str:
    """Compile a LESS/CSS style string via lesscpy, or return '' if empty.

    If scope_id is given, add [data-v-{scope_id}] to all selectors via AST modification.
    Raises ValueError for @import rules or CSS/LESS syntax errors.
    """
    global _parser
    if not raw:
        return ''
    for line in raw.splitlines():
        if line.strip().lower().startswith('@import'):
            raise ValueError('@import is not supported in component styles')
    try:
        _parser.parse(file=StringIO(raw))
    except CompilationError as e:
        _parser = LessParser(fail_with_exc=True)  # reset corrupted state before re-raising
        raise ValueError(f'CSS compilation error: {e}') from e
    if scope_id is not None:
        _scope_ast(_parser.result, scope_id)
    return Formatter(_MinifyArgs()).format(_parser)
