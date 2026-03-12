from html.parser import HTMLParser

# HTMLParser lowercases all attribute names.
# This map restores case-sensitive SVG attributes — applied only inside <svg> elements.
_SVG_ATTR_CASE_MAP: dict[str, str] = {
    'viewbox': 'viewBox',
    'preserveaspectratio': 'preserveAspectRatio',
    'gradientunits': 'gradientUnits',
    'gradienttransform': 'gradientTransform',
    'patternunits': 'patternUnits',
    'patterntransform': 'patternTransform',
    'clippathunits': 'clipPathUnits',
    'markerunits': 'markerUnits',
    'markerwidth': 'markerWidth',
    'markerheight': 'markerHeight',
    'refx': 'refX',
    'refy': 'refY',
    'startoffset': 'startOffset',
    'textlength': 'textLength',
    'lengthadjust': 'lengthAdjust',
    'basefrequency': 'baseFrequency',
    'numoctaves': 'numOctaves',
    'stddeviation': 'stdDeviation',
    'tablevalues': 'tableValues',
    'xchannelselector': 'xChannelSelector',
    'ychannelselector': 'yChannelSelector',
    'diffuseconstant': 'diffuseConstant',
    'kernelmatrix': 'kernelMatrix',
    'kernelunitlength': 'kernelUnitLength',
    'pointsatx': 'pointsAtX',
    'pointsaty': 'pointsAtY',
    'pointsatz': 'pointsAtZ',
    'specularconstant': 'specularConstant',
    'specularexponent': 'specularExponent',
    'surfacescale': 'surfaceScale',
    'targetx': 'targetX',
    'targety': 'targetY',
    'primitiveunits': 'primitiveUnits',
    'calcmode': 'calcMode',
    'attributename': 'attributeName',
    'attributetype': 'attributeType',
    'keysplines': 'keySplines',
    'keytimes': 'keyTimes',
    'repeatcount': 'repeatCount',
    'repeatdur': 'repeatDur',
    'filterunits': 'filterUnits',
    'spreadmethod': 'spreadMethod',
    'maskunits': 'maskUnits',
    'maskcontentunits': 'maskContentUnits',
    'pathlength': 'pathLength',
}


class CustomHTML(HTMLParser):
    ROOT_TAGS: frozenset[str] = frozenset({'template', 'script', 'style'})
    VOID_ELEMENTS: frozenset[str] = frozenset(
        {
            'area',
            'base',
            'br',
            'col',
            'embed',
            'hr',
            'img',
            'input',
            'link',
            'meta',
            'param',
            'source',
            'track',
            'wbr',
        }
    )

    def __init__(self, scope_id: str | None = None) -> None:
        super().__init__()
        self.scope_id: str | None = scope_id
        self.levels: dict[str, int] = {x: 0 for x in self.ROOT_TAGS}
        self.content: dict[str, list[str]] = {x: [] for x in self.ROOT_TAGS}
        self.root_attrs: dict[str, list[tuple[str, str | None]]] = {x: [] for x in self.ROOT_TAGS}
        self.section_counts: dict[str, int] = {x: 0 for x in self.ROOT_TAGS}
        self.inner_stack: list[str] = []
        self._svg_depth: int = 0

    @property
    def current_root_tag(self) -> str | None:
        current_tag = [k for k, v in self.levels.items() if v > 0]
        return current_tag[0] if current_tag else None

    def _append_open_tag(self, tag: str, attrs: list[tuple[str, str | None]], self_closing: bool = False) -> None:
        if not self.current_root_tag:
            return
        case_map = _SVG_ATTR_CASE_MAP if (tag == 'svg' or self._svg_depth > 0) else {}
        attrib = ' '.join(
            case_map.get(k, k) if v is None else f'{case_map.get(k, k)}="{v}"' for k, v in attrs
        )
        if attrib:
            attrib = f' {attrib}'
        if self.current_root_tag == 'template' and self.scope_id is not None:
            attrib = f'{attrib} data-v-{self.scope_id}'
        if self_closing or tag in self.VOID_ELEMENTS:
            attrib = f'{attrib} /'
        self.content[self.current_root_tag].append(f'<{tag}{attrib}>')

    def _is_root_boundary(self, tag: str) -> bool:
        """Return True if tag is a root section tag and no other root section is currently open."""
        return tag in self.ROOT_TAGS and all(self.levels[x] == 0 for x in self.ROOT_TAGS if x != tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._append_open_tag(tag, attrs, self_closing=True)
        # self-closing <svg /> has no children — do not touch _svg_depth

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._is_root_boundary(tag):
            if self.levels[tag] > 0:
                # Already inside this root section — treat as a nested inner tag (named slot, v-if, etc.)
                self._append_open_tag(tag, attrs)
                if self.current_root_tag == 'template' and tag not in self.VOID_ELEMENTS:
                    self.inner_stack.append(tag)
                return
            if self.section_counts[tag] > 0:
                raise ValueError(f'Duplicate <{tag}> section')
            self.section_counts[tag] += 1
            self.levels[tag] += 1
            self.root_attrs[tag] = list(attrs)
            return
        self._append_open_tag(tag, attrs)
        if self.current_root_tag == 'template' and tag not in self.VOID_ELEMENTS:
            self.inner_stack.append(tag)
        if tag == 'svg' and self.current_root_tag:
            self._svg_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.VOID_ELEMENTS:
            return
        if self._is_root_boundary(tag):
            if self.inner_stack and tag in self.inner_stack:
                # Nested root-tag closing (e.g., </template> for a named slot inside <template>)
                if self.current_root_tag == 'template':
                    expected = self.inner_stack.pop()
                    if expected != tag:
                        raise ValueError(f'Mismatched tag: expected </{expected}>, got </{tag}>')
                self.content[self.current_root_tag].append(f'</{tag}>')
                return
            if tag == 'template' and self.inner_stack:
                raise ValueError(f'Unclosed tag <{self.inner_stack[-1]}> in <template>')
            self.levels[tag] -= 1
            return
        if self.current_root_tag:
            if self.current_root_tag == 'template':
                if not self.inner_stack:
                    raise ValueError(f'Unexpected closing tag </{tag}> in <template>')
                expected = self.inner_stack.pop()
                if expected != tag:
                    raise ValueError(f'Mismatched tag: expected </{expected}>, got </{tag}>')
            self.content[self.current_root_tag].append(f'</{tag}>')
        if tag == 'svg' and self._svg_depth > 0:
            self._svg_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.current_root_tag:
            self.content[self.current_root_tag].append(data)

    def validate(self) -> None:
        """Raise ValueError if any root section was not properly closed."""
        for tag in self.ROOT_TAGS:
            if self.levels[tag] > 0:
                raise ValueError(f'Unclosed <{tag}> section')

    def is_scoped(self) -> bool:
        return any(k == 'scoped' for k, _v in self.root_attrs.get('style', []))

    def get_content(self, tag: str) -> str:
        return ''.join(self.content[tag])
