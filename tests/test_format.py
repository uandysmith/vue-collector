"""
Tests for vue_collector.format — template, style, script formatters,
full .vue file formatting, and format_vue_dir.
"""

import os
import tempfile
import unittest

from vue_collector.format import format_vue_dir
from vue_collector.format.script import _format_script
from vue_collector.format.style import _format_style
from vue_collector.format.template import _format_template
from vue_collector.format.vue import _format_vue_file_content

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()


class TestFormatTemplate(unittest.TestCase):
    def test_simple_div(self):
        self.assertEqual(_format_template('<div>hello</div>'), '<div>\n  hello\n</div>')

    def test_nested_elements(self):
        self.assertEqual(
            _format_template('<div><span>text</span></div>'),
            '<div>\n  <span>\n    text\n  </span>\n</div>',
        )

    def test_void_element_no_indent_change(self):
        self.assertEqual(
            _format_template('<div><br /><span>ok</span></div>'),
            '<div>\n  <br />\n  <span>\n    ok\n  </span>\n</div>',
        )

    def test_self_closing_custom_element(self):
        self.assertEqual(
            _format_template('<div><my-icon /></div>'),
            '<div>\n  <my-icon />\n</div>',
        )

    def test_attributes_passed_through(self):
        self.assertEqual(
            _format_template('<button @click="fn" :disabled="x">ok</button>'),
            '<button @click="fn" :disabled="x">\n  ok\n</button>',
        )

    def test_vue_directives_passed_through(self):
        self.assertEqual(
            _format_template('<li v-for="item in items" :key="item.id">{{ item }}</li>'),
            '<li v-for="item in items" :key="item.id">\n  {{ item }}\n</li>',
        )

    def test_svg_camelcase_attrs(self):
        self.assertEqual(
            _format_template('<svg viewBox="0 0 10 10"><circle /></svg>'),
            '<svg viewBox="0 0 10 10">\n  <circle />\n</svg>',
        )

    def test_multiple_children(self):
        self.assertEqual(
            _format_template('<ul><li>a</li><li>b</li></ul>'),
            '<ul>\n  <li>\n    a\n  </li>\n  <li>\n    b\n  </li>\n</ul>',
        )

    def test_hr_void_element(self):
        self.assertEqual(_format_template('<div><hr /></div>'), '<div>\n  <hr />\n</div>')

    def test_whitespace_only_data_skipped(self):
        self.assertEqual(_format_template('<div>  \n  </div>'), '<div>\n</div>')

    def test_empty_returns_empty(self):
        self.assertEqual(_format_template(''), '')
        self.assertEqual(_format_template('   \n  '), '')

    def test_pre_content_preserved(self):
        # Content inside <pre> must not be re-indented or stripped
        html = '<div><pre>  indented\ncode  </pre></div>'
        result = _format_template(html)
        self.assertIn('<pre>  indented\ncode  ', result)  # content preserved verbatim

    def test_pre_with_nested_code(self):
        # Tags inside <pre> emitted raw, content preserved
        html = '<div><pre><code>  x = 1\n  y = 2</code></pre></div>'
        result = _format_template(html)
        self.assertIn('<pre><code>  x = 1\n  y = 2</code>', result)

    def test_pre_siblings_still_formatted(self):
        # Elements after </pre> are formatted normally
        html = '<div><pre>raw</pre><p>text</p></div>'
        result = _format_template(html)
        self.assertIn('<p>\n    text\n  </p>', result)

    def test_idempotent(self):
        html = '<div>\n  <span>\n    text\n  </span>\n</div>'
        self.assertEqual(_format_template(_format_template(html)), _format_template(html))


class TestFormatStyle(unittest.TestCase):
    def test_simple_rule(self):
        self.assertEqual(_format_style('.foo { color: red; }'), '.foo {\n  color: red;\n}')

    def test_multiple_properties(self):
        self.assertEqual(
            _format_style('.counter { display: flex; gap: 8px; }'),
            '.counter {\n  display: flex;\n  gap: 8px;\n}',
        )

    def test_nested_rule_empty_line_after_property(self):
        self.assertEqual(
            _format_style('.parent { color: red; .child { color: blue; } }'),
            '.parent {\n  color: red;\n\n  .child {\n    color: blue;\n  }\n}',
        )

    def test_nested_rule_no_empty_line_when_no_property(self):
        self.assertEqual(
            _format_style('.parent { .child { color: blue; } }'),
            '.parent {\n  .child {\n    color: blue;\n  }\n}',
        )

    def test_multiple_rules(self):
        self.assertEqual(
            _format_style('.foo { color: red; } .bar { color: blue; }'),
            '.foo {\n  color: red;\n}\n.bar {\n  color: blue;\n}',
        )

    def test_pseudo_class_selector(self):
        self.assertEqual(
            _format_style('.btn:hover { color: red; }'),
            '.btn:hover {\n  color: red;\n}',
        )

    def test_media_query(self):
        self.assertEqual(
            _format_style('@media (max-width: 768px) { .foo { color: red; } }'),
            '@media (max-width: 768px) {\n  .foo {\n    color: red;\n  }\n}',
        )

    def test_extra_whitespace_stripped(self):
        self.assertEqual(_format_style('.foo {   color: red;   }'), '.foo {\n  color: red;\n}')

    def test_empty_returns_empty(self):
        self.assertEqual(_format_style(''), '')
        self.assertEqual(_format_style('   '), '')

    def test_idempotent(self):
        css = '.foo { color: red; }'
        first = _format_style(css)
        self.assertEqual(_format_style(first), first)


class TestFormatScript(unittest.TestCase):
    def test_simple_export_default(self):
        self.assertEqual(
            _format_script('export default {\n  data() { return {} }\n}'),
            'export default {\n  data() { return {} }\n}',
        )

    def test_trailing_spaces_removed(self):
        self.assertEqual(
            _format_script('export default {   \n  data() { return {} }   \n}'),
            'export default {\n  data() { return {} }\n}',
        )

    def test_empty_lines_preserved(self):
        self.assertEqual(
            _format_script('const x = 1\n\nexport default {}'),
            'const x = 1\n\nexport default {}',
        )

    def test_whitespace_only_lines_become_empty(self):
        self.assertEqual(
            _format_script('const x = 1\n   \nexport default {}'),
            'const x = 1\n\nexport default {}',
        )

    def test_indent_nested_block(self):
        self.assertEqual(
            _format_script('export default {\nmethods: {\nfn() { return 1 }\n}\n}'),
            'export default {\n  methods: {\n    fn() { return 1 }\n  }\n}',
        )

    def test_closing_brace_dedents(self):
        self.assertEqual(
            _format_script('function fn() {\nreturn 1\n}'),
            'function fn() {\n  return 1\n}',
        )

    def test_closing_brace_with_comma(self):
        self.assertEqual(
            _format_script('export default {\nmethods: {\nfn() {}\n},\ndata() { return {} }\n}'),
            'export default {\n  methods: {\n    fn() {}\n  },\n  data() { return {} }\n}',
        )

    def test_net_zero_braces_no_indent_change(self):
        self.assertEqual(
            _format_script('const obj = { a: 1 }\nexport default {}'),
            'const obj = { a: 1 }\nexport default {}',
        )

    def test_destructuring_net_zero(self):
        self.assertEqual(
            _format_script('const { a, b } = obj\nexport default {}'),
            'const { a, b } = obj\nexport default {}',
        )

    def test_line_comment_braces_not_counted(self):
        self.assertEqual(
            _format_script('const x = 1 // { not a brace }\nexport default {}'),
            'const x = 1 // { not a brace }\nexport default {}',
        )

    def test_string_literal_braces_not_counted(self):
        self.assertEqual(
            _format_script("const x = '{not a brace}'\nexport default {}"),
            "const x = '{not a brace}'\nexport default {}",
        )

    def test_single_line_template_literal_braces_not_counted(self):
        self.assertEqual(
            _format_script('const x = `{not a brace}`\nexport default {}'),
            'const x = `{not a brace}`\nexport default {}',
        )

    def test_multiline_template_literal_preserved(self):
        js = 'const x = `\nhello\nworld\n`\nexport default {}'
        self.assertEqual(_format_script(js), js)

    def test_block_comment_preserved(self):
        js = '/* this is\na block comment\n*/\nexport default {}'
        self.assertEqual(_format_script(js), js)

    def test_empty_returns_empty(self):
        self.assertEqual(_format_script(''), '')
        self.assertEqual(_format_script('   \n  '), '')

    def test_regex_literal_braces_not_counted(self):
        # Regex with { } inside must not throw off brace depth
        js = "const re = /(\\{)/\nexport default {}"
        self.assertEqual(_format_script(js), js)

    def test_regex_after_equals_with_character_class(self):
        # Real-world pattern: regex assigned with = containing { } in char class
        js = "this.re = /^[\\{\\}]*$/\nexport default {}"
        self.assertEqual(_format_script(js), js)

    def test_template_literal_trailing_spaces_preserved(self):
        # Trailing spaces inside a template literal must not be stripped
        js = "const s = `line with spaces   \nend`\nexport default {}"
        self.assertEqual(_format_script(js), js)

    def test_idempotent(self):
        js = (
            'export default {\n  data() {\n    return { count: 0 }\n  },'
            '\n  methods: {\n    fn() { this.count++ }\n  }\n}'
        )
        self.assertEqual(_format_script(_format_script(js)), _format_script(js))


class TestFormatVueFileContent(unittest.TestCase):
    def test_full_component(self):
        content = (
            '<script>\nexport default { data() { return {} } }\n</script>\n'
            '<style>\n.foo { color: red; }\n</style>\n'
            '<template>\n<div>hello</div>\n</template>\n'
        )
        self.assertEqual(
            _format_vue_file_content(content),
            '<template>\n<div>\n  hello\n</div>\n</template>\n'
            '<style>\n.foo {\n  color: red;\n}\n</style>\n'
            '<script>\nexport default { data() { return {} } }\n</script>\n',
        )

    def test_template_only_component(self):
        self.assertEqual(
            _format_vue_file_content('<template>\n<div>hello</div>\n</template>\n'),
            '<template>\n<div>\n  hello\n</div>\n</template>\n',
        )

    def test_scoped_style_attr_preserved(self):
        content = (
            '<template>\n<div class="x"></div>\n</template>\n'
            '<style scoped>\n.x { color: red; }\n</style>\n'
        )
        self.assertEqual(
            _format_vue_file_content(content),
            '<template>\n<div class="x">\n</div>\n</template>\n'
            '<style scoped>\n.x {\n  color: red;\n}\n</style>\n',
        )

    def test_style_lang_attr_preserved(self):
        content = (
            '<template>\n<div></div>\n</template>\n'
            '<style lang="less">\n.x { color: red; }\n</style>\n'
        )
        self.assertEqual(
            _format_vue_file_content(content),
            '<template>\n<div>\n</div>\n</template>\n'
            '<style lang="less">\n.x {\n  color: red;\n}\n</style>\n',
        )

    def test_invalid_content_returned_unchanged(self):
        content = '<template><div></template>'
        self.assertEqual(_format_vue_file_content(content), content)

    def test_idempotent_counter(self):
        first = _format_vue_file_content(read_fixture('Counter.vue'))
        self.assertEqual(_format_vue_file_content(first), first)

    def test_idempotent_itemlist(self):
        first = _format_vue_file_content(read_fixture('ItemList.vue'))
        self.assertEqual(_format_vue_file_content(first), first)

    def test_idempotent_static(self):
        first = _format_vue_file_content(read_fixture('Static.vue'))
        self.assertEqual(_format_vue_file_content(first), first)


class TestFormatVueDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, content: str) -> str:
        path = os.path.join(self.base, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_empty_dir_returns_empty_list(self):
        self.assertEqual(format_vue_dir(self.base), [])

    def test_already_formatted_not_in_result(self):
        formatted = _format_vue_file_content('<template>\n<div>hello</div>\n</template>\n')
        self._write('A.vue', formatted)
        self.assertEqual(format_vue_dir(self.base), [])

    def test_unformatted_file_reformatted(self):
        path = self._write('B.vue', '<template><div>hello</div></template>\n')
        changed = format_vue_dir(self.base)
        self.assertEqual(changed, [path])
        with open(path, encoding='utf-8') as f:
            self.assertEqual(f.read(), '<template>\n<div>\n  hello\n</div>\n</template>\n')

    def test_only_changed_files_returned(self):
        formatted = _format_vue_file_content('<template>\n<div>x</div>\n</template>\n')
        path_a = self._write('A.vue', formatted)
        path_b = self._write('B.vue', '<template><div>unformatted</div></template>\n')
        changed = format_vue_dir(self.base)
        self.assertNotIn(path_a, changed)
        self.assertIn(path_b, changed)

    def test_recurses_into_subdirectories(self):
        sub = os.path.join(self.base, 'ui')
        os.makedirs(sub)
        path = os.path.join(sub, 'X.vue')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('<template><div>test</div></template>\n')
        self.assertIn(path, format_vue_dir(self.base))

    def test_non_vue_files_ignored(self):
        with open(os.path.join(self.base, 'notes.md'), 'w') as f:
            f.write('# notes')
        self.assertEqual(format_vue_dir(self.base), [])


if __name__ == '__main__':
    unittest.main()
