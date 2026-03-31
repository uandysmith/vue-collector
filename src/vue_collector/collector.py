import hashlib
import os
from collections.abc import Generator
from pathlib import Path

from .script import _parse_script
from .style import _compile_style
from .template import CustomHTML
from .util import VueSectionError, _make_scope_id, _make_template_name


def _escape_js_template(s: str) -> str:
    """Escape HTML string for embedding inside a JS backtick template literal."""
    return s.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')


def _content_hash(vue_dir: str | list[str]) -> str:
    """SHA-256 (first 16 hex chars) of all .vue file contents under vue_dir, sorted by path."""
    hasher = hashlib.sha256()
    for path in sorted(find_vue_files(vue_dir)):
        with open(path, encoding='utf-8') as f:
            hasher.update(f.read().encode())
    return hasher.hexdigest()[:16]


class VueComponent:
    def __init__(self, file_name: str, content: str, *, forbid_imports: bool = False) -> None:
        name = file_name.split('.vue')[0]
        self.name: str = name
        self.template_name: str = _make_template_name(name)

        try:
            probe = CustomHTML()
            probe.feed(content)
            probe.validate()
        except ValueError as e:
            raise VueSectionError(file_name, None, str(e)) from e

        style_lang = next((v for k, v in probe.root_attrs['style'] if k == 'lang'), None)
        if probe.section_counts['style'] > 0 and style_lang is None:
            raise VueSectionError(
                file_name, 'style', '<style> must specify lang="less" for Vite compatibility'
            )
        if style_lang is not None and style_lang.lower() != 'less':
            raise VueSectionError(file_name, 'style', f'Only LESS is supported as style language, got {style_lang!r}')

        script_lang = next((v for k, v in probe.root_attrs['script'] if k == 'lang'), None)
        if script_lang is not None:
            raise VueSectionError(file_name, 'script', f'TypeScript is not supported, got lang={script_lang!r}')

        scope_id: str | None = _make_scope_id(file_name) if probe.is_scoped() else None

        if scope_id is not None:
            try:
                parser = CustomHTML(scope_id=scope_id)
                parser.feed(content)
                parser.validate()
            except ValueError as e:
                raise VueSectionError(file_name, None, str(e)) from e
        else:
            parser = probe

        self.raw_template: str = parser.get_content('template')
        self.template: str = f'<template id="{self.template_name}">{self.raw_template}</template>'

        try:
            self.variables, self.component = _parse_script(
                name, parser.get_content('script'), forbid_imports=forbid_imports
            )
        except ValueError as e:
            raise VueSectionError(file_name, 'script', str(e)) from e

        try:
            self.style = _compile_style(parser.get_content('style'), scope_id)
        except ValueError as e:
            raise VueSectionError(file_name, 'style', str(e)) from e


def collect_vue(vue_dir: str | list[str] = '.', *, forbid_imports: bool = False) -> Generator[VueComponent, None, None]:
    dirs = [vue_dir] if isinstance(vue_dir, str) else vue_dir
    seen: dict[str, VueComponent] = {}
    for full_path in find_vue_files(vue_dir):
        for d in dirs:
            rel = os.path.relpath(full_path, d)
            if not rel.startswith('..'):
                file_name = rel.replace(os.sep, '')
                break
        with open(full_path, encoding='utf-8') as f:
            vc = VueComponent(file_name, f.read(), forbid_imports=forbid_imports)
        seen[vc.name] = vc  # last wins: later dirs override earlier ones
    yield from seen.values()


def prepare_compiled(template: str, vue_dir: str | list[str] = '.', *, forbid_imports: bool = False) -> str:
    components = list(collect_vue(vue_dir, forbid_imports=forbid_imports))
    styles = '\n'.join(x.style for x in components)
    templates = '\n'.join(x.template for x in components)
    variables = '\n'.join(x.variables for x in components if x.variables)
    components_js = '\n'.join(
        f"app.component('{x.name}', {{\nname: '{x.name.lower()}',\ntemplate: '#{x.template_name}',\n{x.component}}});"
        for x in components
    )
    template = template.replace('<|style|>', styles.strip())
    template = template.replace('<|templates|>', templates)
    template = template.replace('<|variables|>', variables)
    template = template.replace('<|components|>', components_js)
    return template


def prepare_assets(
    vue_dir: str | list[str] = '.', extra_js: str = '', *, forbid_imports: bool = False
) -> tuple[str, str]:
    """Return (js_content, css_content) for the JS+CSS asset build mode.

    js_content contains module-level variables and a function initComponents(app)
    that calls app.component() with inline template strings for each component.
    extra_js (if provided) is prepended to the JS output verbatim.
    """
    components = list(collect_vue(vue_dir, forbid_imports=forbid_imports))

    css = '\n'.join(x.style for x in components if x.style)

    parts: list[str] = []
    if extra_js:
        parts.append(extra_js.rstrip())
        parts.append('')

    variables = '\n'.join(x.variables for x in components if x.variables)
    if variables:
        parts.append(variables)
        parts.append('')

    parts.append('function initComponents(app) {')
    for x in components:
        tpl = _escape_js_template(x.raw_template)
        body = x.component
        inner = f'template: `{tpl}`'
        if body:
            inner += f',\n{body}'
        parts.append(f"    app.component('{x.name}', {{{inner}}});")
    parts.append('}')

    return '\n'.join(parts), css


def write_assets(
    vue_dir: str | list[str] = '.',
    output_dir: str = '.',
    extra_js: str = '',
    *,
    forbid_imports: bool = False,
) -> tuple[str, str]:
    """Write components.{hash}.js and components.{hash}.css to output_dir.

    Returns (js_filename, css_filename). The hash covers all .vue files under
    vue_dir so filenames change whenever any component changes.
    """
    h = _content_hash(vue_dir)
    js_content, css_content = prepare_assets(vue_dir, extra_js, forbid_imports=forbid_imports)
    js_name = f'components.{h}.js'
    css_name = f'components.{h}.css'
    with open(os.path.join(output_dir, js_name), 'w', encoding='utf-8') as f:
        f.write(js_content)
    with open(os.path.join(output_dir, css_name), 'w', encoding='utf-8') as f:
        f.write(css_content)
    return js_name, css_name


def find_vue_files(base_dir: str | list[str] = '.') -> list[str]:
    dirs = [base_dir] if isinstance(base_dir, str) else base_dir
    result: list[str] = []
    for d in dirs:
        result.extend(str(p) for p in Path(d).rglob('*.vue'))
    return result
