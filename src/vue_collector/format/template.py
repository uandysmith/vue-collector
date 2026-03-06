from html.parser import HTMLParser

from ..template import _SVG_ATTR_CASE_MAP, CustomHTML

_VOID_ELEMENTS = CustomHTML.VOID_ELEMENTS


def _fmt_tag_attrs(tag: str, attrs: list[tuple[str, str | None]], svg_depth: int) -> str:
    case_map = _SVG_ATTR_CASE_MAP if (tag == 'svg' or svg_depth > 0) else {}
    parts = []
    for k, v in attrs:
        k_out = case_map.get(k, k)
        parts.append(k_out if v is None else f'{k_out}="{v}"')
    return (' ' + ' '.join(parts)) if parts else ''


class _TemplateFormatter(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._out: list[str] = []
        self._indent: int = 0
        self._svg_depth: int = 0
        self._pre_depth: int = 0  # >0 while inside <pre>; content emitted raw

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrib = _fmt_tag_attrs(tag, attrs, self._svg_depth)
        if self._pre_depth > 0:
            self._out.append(f'<{tag}{attrib}>')
            if tag == 'pre':
                self._pre_depth += 1
            return
        if tag in _VOID_ELEMENTS:
            self._out.append('\n' + '  ' * self._indent + f'<{tag}{attrib} />')
        else:
            self._out.append('\n' + '  ' * self._indent + f'<{tag}{attrib}>')
            if tag == 'pre':
                self._pre_depth = 1  # don't change _indent — </pre> stays at same level
            else:
                self._indent += 1
        if tag == 'svg':
            self._svg_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._pre_depth > 0:
            if tag == 'pre':
                self._pre_depth -= 1
                if self._pre_depth == 0:
                    self._out.append(f'</{tag}>')  # no leading \n: content is raw, </pre> follows it directly
                    return
            self._out.append(f'</{tag}>')
            return
        if tag in _VOID_ELEMENTS:
            return
        if tag == 'svg' and self._svg_depth > 0:
            self._svg_depth -= 1
        self._indent -= 1
        self._out.append('\n' + '  ' * self._indent + f'</{tag}>')

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrib = _fmt_tag_attrs(tag, attrs, self._svg_depth)
        if self._pre_depth > 0:
            self._out.append(f'<{tag}{attrib} />')
        else:
            self._out.append('\n' + '  ' * self._indent + f'<{tag}{attrib} />')

    def handle_data(self, data: str) -> None:
        if self._pre_depth > 0:
            self._out.append(data)
            return
        stripped = data.strip()
        if stripped:
            self._out.append('\n' + '  ' * self._indent + stripped)


def _format_template(html: str) -> str:
    if not html.strip():
        return ''
    fmt = _TemplateFormatter()
    fmt.feed(html)
    return ''.join(fmt._out).lstrip('\n')
