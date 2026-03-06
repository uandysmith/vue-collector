from ..collector import find_vue_files
from .script import _format_script
from .style import _format_style
from .template import CustomHTML, _format_template


def _fmt_root_attrs(attrs: list[tuple[str, str | None]]) -> str:
    parts = []
    for k, v in attrs:
        parts.append(k if v is None else f'{k}="{v}"')
    return (' ' + ' '.join(parts)) if parts else ''


def _format_vue_file_content(content: str) -> str:
    parser = CustomHTML()
    try:
        parser.feed(content)
        parser.validate()
    except ValueError:
        return content  # don't touch files that fail validation

    sections = []

    if parser.section_counts['template']:
        inner = _format_template(parser.get_content('template'))
        attrs = _fmt_root_attrs(parser.root_attrs['template'])
        sections.append(f'<template{attrs}>\n{inner}\n</template>')

    if parser.section_counts['style']:
        inner = _format_style(parser.get_content('style'))
        attrs = _fmt_root_attrs(parser.root_attrs['style'])
        if inner:
            sections.append(f'<style{attrs}>\n{inner}\n</style>')
        else:
            sections.append(f'<style{attrs}></style>')

    if parser.section_counts['script']:
        inner = _format_script(parser.get_content('script'))
        sections.append(f'<script>\n{inner}\n</script>')

    return '\n'.join(sections) + '\n'


def format_vue_dir(vue_dir: str) -> list[str]:
    """Format all .vue files in vue_dir in-place. Returns paths of changed files."""
    changed = []
    for path in find_vue_files(vue_dir):
        with open(path, encoding='utf-8') as f:
            original = f.read()
        formatted = _format_vue_file_content(original)
        if formatted != original:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(formatted)
            changed.append(path)
    return changed
