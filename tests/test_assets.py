import hashlib
import os
import tempfile
import unittest

from vue_collector import VueComponent, prepare_assets, write_assets
from vue_collector.collector import _content_hash, _escape_js_template

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()


def _make_vue_dir(tmp: str, *names: str) -> str:
    """Create tmp/vue/ and copy named fixtures into it. Returns vue_dir path."""
    vue_dir = os.path.join(tmp, 'vue')
    os.makedirs(vue_dir, exist_ok=True)
    for name in names:
        with open(os.path.join(vue_dir, name), 'w', encoding='utf-8') as f:
            f.write(read_fixture(name))
    return vue_dir


class TestEscapeJsTemplate(unittest.TestCase):
    def test_plain_string_unchanged(self):
        self.assertEqual(_escape_js_template('<div>hello</div>'), '<div>hello</div>')

    def test_backtick_escaped(self):
        self.assertEqual(_escape_js_template('a`b'), 'a\\`b')

    def test_dollar_brace_escaped(self):
        self.assertEqual(_escape_js_template('${x}'), '\\${x}')

    def test_backslash_doubled(self):
        self.assertEqual(_escape_js_template('a\\b'), 'a\\\\b')

    def test_backslash_before_backtick(self):
        # backslash first, then backtick — both escaped, order matters
        self.assertEqual(_escape_js_template('\\`'), '\\\\\\`')

    def test_vue_mustache_unchanged(self):
        # {{ count }} is NOT a JS template literal interpolation — must not be escaped
        self.assertEqual(_escape_js_template('{{ count }}'), '{{ count }}')

    def test_empty_string(self):
        self.assertEqual(_escape_js_template(''), '')


class TestContentHash(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_empty_dir_produces_sha256_of_empty_input(self):
        expected = hashlib.sha256(b'').hexdigest()[:16]
        self.assertEqual(_content_hash(self.tmp.name), expected)

    def test_same_content_same_hash(self):
        _make_vue_dir(self.tmp.name, 'Counter.vue')
        h1 = _content_hash(self.tmp.name)
        h2 = _content_hash(self.tmp.name)
        self.assertEqual(h1, h2)

    def test_hash_changes_when_content_changes(self):
        vue_dir = _make_vue_dir(self.tmp.name, 'Counter.vue')
        h1 = _content_hash(self.tmp.name)
        with open(os.path.join(vue_dir, 'Counter.vue'), 'a', encoding='utf-8') as f:
            f.write('\n')
        h2 = _content_hash(self.tmp.name)
        self.assertNotEqual(h1, h2)

    def test_hash_changes_when_file_added(self):
        _make_vue_dir(self.tmp.name, 'Counter.vue')
        h1 = _content_hash(self.tmp.name)
        with open(os.path.join(self.tmp.name, 'Extra.vue'), 'w', encoding='utf-8') as f:
            f.write('<template><div></div></template>')
        h2 = _content_hash(self.tmp.name)
        self.assertNotEqual(h1, h2)

    def test_returns_16_hex_chars(self):
        h = _content_hash(self.tmp.name)
        self.assertEqual(len(h), 16)
        self.assertRegex(h, r'^[0-9a-f]{16}$')


class TestPrepareAssets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def _setup(self, *names: str) -> tuple[str, str]:
        vue_dir = _make_vue_dir(self.base, *names)
        return prepare_assets(vue_dir)

    def test_js_contains_init_components_function(self):
        js, _ = self._setup('Counter.vue')
        self.assertIn('function initComponents(app) {', js)

    def test_js_contains_app_component_call(self):
        js, _ = self._setup('Counter.vue')
        self.assertIn("app.component('Counter',", js)

    def test_js_contains_inline_template(self):
        js, _ = self._setup('Counter.vue')
        self.assertIn('template: `', js)
        self.assertIn('counter', js)

    def test_js_template_uses_backtick_not_id_reference(self):
        js, _ = self._setup('Counter.vue')
        self.assertNotIn("template: '#", js)

    def test_css_contains_compiled_style(self):
        _, css = self._setup('Counter.vue')
        self.assertEqual(css, '.counter{display:flex;gap:8px;}')

    def test_css_empty_when_no_styles(self):
        _, css = self._setup('Static.vue')
        self.assertEqual(css, '')

    def test_extra_js_prepended(self):
        vue_dir = _make_vue_dir(self.base, 'Counter.vue')
        extra = 'const app = Vue.createApp({});'
        js, _ = prepare_assets(vue_dir, extra_js=extra)
        self.assertTrue(js.startswith(extra))
        idx_extra = js.index(extra)
        idx_fn = js.index('function initComponents')
        self.assertLess(idx_extra, idx_fn)

    def test_variables_appear_before_init_components(self):
        js, _ = self._setup('ItemList.vue')
        self.assertIn('const PAGE_SIZE = 10', js)
        idx_var = js.index('const PAGE_SIZE = 10')
        idx_fn = js.index('function initComponents')
        self.assertLess(idx_var, idx_fn)

    def test_scoped_template_has_data_v_attrs(self):
        js, _ = self._setup('Card.vue')
        self.assertIn('data-v-', js)

    def test_scoped_css_has_scope_selector(self):
        _, css = self._setup('Card.vue')
        self.assertIn('[data-v-', css)
        self.assertIn('.card[data-v-', css)

    def test_static_component_no_script_no_crash(self):
        js, css = self._setup('Static.vue')
        self.assertIn("app.component('Static',", js)
        self.assertIn('template: `', js)
        self.assertEqual(css, '')

    def test_multiple_components_all_registered(self):
        js, _ = self._setup('Counter.vue', 'Static.vue')
        self.assertIn("app.component('Counter',", js)
        self.assertIn("app.component('Static',", js)

    def test_multiple_css_concatenated(self):
        _, css = self._setup('Counter.vue', 'Card.vue')
        self.assertIn('.counter{', css)
        self.assertIn('.card[data-v-', css)

    def test_extra_js_empty_by_default(self):
        vue_dir = _make_vue_dir(self.base, 'Counter.vue')
        js, _ = prepare_assets(vue_dir)
        self.assertTrue(js.startswith('function initComponents'))

    def test_raw_template_field_accessible(self):
        vc = VueComponent('Counter.vue', read_fixture('Counter.vue'))
        self.assertIn('<div class="counter">', vc.raw_template)
        self.assertNotIn('<template id=', vc.raw_template)


class TestWriteAssets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        self.vue_dir = _make_vue_dir(self.base, 'Counter.vue')

    def tearDown(self):
        self.tmp.cleanup()

    def test_creates_js_and_css_files(self):
        js_name, css_name = write_assets(self.vue_dir, self.base)
        self.assertTrue(os.path.exists(os.path.join(self.base, js_name)))
        self.assertTrue(os.path.exists(os.path.join(self.base, css_name)))

    def test_filenames_contain_hash(self):
        js_name, css_name = write_assets(self.vue_dir, self.base)
        self.assertRegex(js_name, r'^components\.[0-9a-f]{16}\.js$')
        self.assertRegex(css_name, r'^components\.[0-9a-f]{16}\.css$')

    def test_js_and_css_share_same_hash(self):
        js_name, css_name = write_assets(self.vue_dir, self.base)
        js_hash = js_name.split('.')[1]
        css_hash = css_name.split('.')[1]
        self.assertEqual(js_hash, css_hash)

    def test_js_file_content_is_valid(self):
        js_name, _ = write_assets(self.vue_dir, self.base)
        with open(os.path.join(self.base, js_name), encoding='utf-8') as f:
            content = f.read()
        self.assertIn('function initComponents(app) {', content)
        self.assertIn("app.component('Counter',", content)

    def test_css_file_content_is_valid(self):
        _, css_name = write_assets(self.vue_dir, self.base)
        with open(os.path.join(self.base, css_name), encoding='utf-8') as f:
            content = f.read()
        self.assertEqual(content, '.counter{display:flex;gap:8px;}')

    def test_filename_changes_when_content_changes(self):
        js_name1, _ = write_assets(self.vue_dir, self.base)
        with open(os.path.join(self.vue_dir, 'Counter.vue'), 'a', encoding='utf-8') as f:
            f.write('\n')
        js_name2, _ = write_assets(self.vue_dir, self.base)
        self.assertNotEqual(js_name1, js_name2)

    def test_filename_stable_for_same_content(self):
        js_name1, _ = write_assets(self.vue_dir, self.base)
        js_name2, _ = write_assets(self.vue_dir, self.base)
        self.assertEqual(js_name1, js_name2)

    def test_output_dir_separate_from_base(self):
        out_dir = tempfile.mkdtemp()
        try:
            js_name, css_name = write_assets(self.vue_dir, out_dir)
            self.assertTrue(os.path.exists(os.path.join(out_dir, js_name)))
            self.assertTrue(os.path.exists(os.path.join(out_dir, css_name)))
        finally:
            import shutil

            shutil.rmtree(out_dir)


if __name__ == '__main__':
    unittest.main()
