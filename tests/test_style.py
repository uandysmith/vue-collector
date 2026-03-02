import unittest

from vue_collector.style import _compile_style


class TestCompileStyleUnscoped(unittest.TestCase):
    """_compile_style without scope_id compiles via lesscpy."""

    def test_empty_returns_empty(self):
        self.assertEqual(_compile_style(''), '')

    def test_unscoped_minifies_css(self):
        result = _compile_style('.foo { color: red; }')
        self.assertEqual(result, '.foo{color:red;}')

    def test_unscoped_multiple_rules(self):
        result = _compile_style('div { color: red; } span { color: blue; }')
        self.assertEqual(result, 'div{color:red;}\nspan{color:blue;}')


class TestCompileStyleScoped(unittest.TestCase):
    """_compile_style with scope_id appends [data-v-{id}] via lesscpy AST."""

    def test_empty_returns_empty(self):
        self.assertEqual(_compile_style('', 'a1b2c3d4'), '')

    def test_class_selector(self):
        self.assertEqual(_compile_style('.foo { color: red; }', 'a1b2c3d4'), '.foo[data-v-a1b2c3d4]{color:red;}')

    def test_element_selector(self):
        self.assertEqual(_compile_style('div { margin: 0; }', 'a1b2c3d4'), 'div[data-v-a1b2c3d4]{margin:0;}')

    def test_body_selector(self):
        self.assertEqual(
            _compile_style('body { margin: 0; padding: 0; }', 'a1b2c3d4'),
            'body[data-v-a1b2c3d4]{margin:0;padding:0;}',
        )

    def test_descendant_selector(self):
        self.assertEqual(
            _compile_style('.a .b { color: red; }', 'a1b2c3d4'),
            '.a .b[data-v-a1b2c3d4]{color:red;}',
        )

    def test_comma_separated_selectors(self):
        self.assertEqual(
            _compile_style('div, span { color: red; }', 'a1b2c3d4'),
            'div[data-v-a1b2c3d4],span[data-v-a1b2c3d4]{color:red;}',
        )

    def test_multiple_comma_groups(self):
        self.assertEqual(
            _compile_style('.a, .b { color: red; } .c { color: blue; }', 'xx'),
            '.a[data-v-xx],.b[data-v-xx]{color:red;}\n.c[data-v-xx]{color:blue;}',
        )

    def test_multiple_rules(self):
        self.assertEqual(
            _compile_style('div { color: red; } span { color: blue; }', 'xx'),
            'div[data-v-xx]{color:red;}\nspan[data-v-xx]{color:blue;}',
        )

    def test_multiple_properties(self):
        self.assertEqual(
            _compile_style('.btn { color: red; font-size: 14px; }', 'xx'),
            '.btn[data-v-xx]{color:red;font-size:14px;}',
        )

    def test_scope_id_suffix_correct(self):
        result = _compile_style('.foo { color: red; }', 'deadbeef')
        self.assertEqual(result, '.foo[data-v-deadbeef]{color:red;}')


class TestCompileStyleLESSFeatures(unittest.TestCase):
    """LESS-specific features compiled and scoped correctly."""

    def test_less_variable(self):
        css = '@primary: red; .btn { color: @primary; }'
        self.assertEqual(_compile_style(css, 'xx'), '.btn[data-v-xx]{color:red;}')

    def test_less_nesting(self):
        css = '.parent { color: blue; .child { color: red; } }'
        self.assertEqual(
            _compile_style(css, 'xx'),
            '.parent[data-v-xx]{color:blue;}\n.parent .child[data-v-xx]{color:red;}',
        )

    def test_less_ampersand_hover(self):
        css = '.btn { color: blue; &:hover { color: darkblue; } }'
        self.assertEqual(
            _compile_style(css, 'xx'),
            '.btn[data-v-xx]{color:blue;}\n.btn:hover[data-v-xx]{color:darkblue;}',
        )

    def test_less_variable_and_nesting(self):
        css = '@color: green; .card { background: @color; .title { font-weight: bold; } }'
        result = _compile_style(css, 'xx')
        self.assertEqual(result, '.card[data-v-xx]{background:green;}\n.card .title[data-v-xx]{font-weight:bold;}')


class TestCompileStyleAtRules(unittest.TestCase):
    """@-rule handling: @media scopes inner rules; @keyframes/@font-face are passthrough."""

    def test_media_query_scopes_inner_rules(self):
        self.assertEqual(
            _compile_style('@media screen { .foo { color: red; } }', 'a1b2c3d4'),
            '@media screen{.foo[data-v-a1b2c3d4]{color:red;}}',
        )

    def test_media_query_with_plain_rule(self):
        css = '.a { color: red; } @media screen { .a { color: blue; } }'
        self.assertEqual(
            _compile_style(css, 'xx'),
            '.a[data-v-xx]{color:red;}\n@media screen{.a[data-v-xx]{color:blue;}}',
        )

    def test_keyframes_not_scoped(self):
        css = '@keyframes spin { from { opacity: 0; } to { opacity: 1; } }'
        self.assertEqual(
            _compile_style(css, 'a1b2c3d4'),
            '@keyframes spin{from{opacity:0;}\nto{opacity:1;}}',
        )

    def test_font_face_not_scoped(self):
        css = '@font-face { font-family: Foo; }'
        self.assertEqual(_compile_style(css, 'xx'), '@font-face{font-family:Foo;}')


if __name__ == '__main__':
    unittest.main()
