"""
Illustrative end-to-end tests for the top-level vue-collector API.

Each test uses a realistic .vue file from tests/fixtures/ and verifies the
complete transformed output, serving as a human-readable specification of
what the collector produces.
"""

import hashlib
import os
import tempfile
import unittest

from vue_collector import VueComponent, VueSectionError, collect_vue, find_vue_files, prepare_compiled

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')


def read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as f:
        return f.read()


class TestVueComponentCounter(unittest.TestCase):
    """Counter component: template, script, unscoped style."""

    def setUp(self):
        self.vc = VueComponent('Counter.vue', read_fixture('Counter.vue'))

    def test_name(self):
        self.assertEqual(self.vc.name, 'Counter')

    def test_template_name(self):
        self.assertEqual(self.vc.template_name, 'template-counter')

    def test_template_wraps_content_in_id_tag(self):
        self.assertEqual(
            self.vc.template,
            '<template id="template-counter">\n'
            '  <div class="counter">\n'
            '    <span>{{ count }}</span>\n'
            '    <button @click="increment">+</button>\n'
            '  </div>\n'
            '</template>',
        )

    def test_component_body(self):
        self.assertIn("name: 'Counter'", self.vc.component)
        self.assertIn('return { count: 0 }', self.vc.component)
        self.assertIn('increment() { this.count++ }', self.vc.component)

    def test_variables_empty(self):
        self.assertEqual(self.vc.variables, '')

    def test_style_compiled(self):
        self.assertEqual(self.vc.style, '.counter{display:flex;gap:8px;}')


class TestVueComponentCardScoped(unittest.TestCase):
    """Card.vue: <style scoped> injects data-v-* into template and CSS selectors."""

    SCOPE_ID = hashlib.sha256('Card.vue'.encode()).hexdigest()[:8]

    def setUp(self):
        self.vc = VueComponent('Card.vue', read_fixture('Card.vue'))

    def test_scope_id_on_all_template_elements(self):
        attr = f'data-v-{self.SCOPE_ID}'
        self.assertIn(f'<div class="card" {attr}>', self.vc.template)
        self.assertIn(f'<h2 class="title" {attr}>', self.vc.template)
        self.assertIn(f'<p {attr}>', self.vc.template)

    def test_scope_selector_in_style(self):
        attr = f'[data-v-{self.SCOPE_ID}]'
        self.assertIn(f'.card{attr}', self.vc.style)
        self.assertIn(f'.title{attr}', self.vc.style)

    def test_style_content(self):
        sid = self.SCOPE_ID
        self.assertEqual(
            self.vc.style,
            f'.card[data-v-{sid}]{{border:1px solid #cccccc;}}\n.title[data-v-{sid}]{{font-weight:bold;}}',
        )


class TestVueComponentItemList(unittest.TestCase):
    """ItemList.vue: const before export default appears in variables."""

    def setUp(self):
        self.vc = VueComponent('ItemList.vue', read_fixture('ItemList.vue'))

    def test_variables_contains_const(self):
        self.assertIn('const PAGE_SIZE = 10', self.vc.variables)

    def test_component_body_contains_name(self):
        self.assertIn("name: 'ItemList'", self.vc.component)

    def test_template_passes_vue_directives_through(self):
        self.assertIn('v-for="item in items"', self.vc.template)
        self.assertIn(':key="item.id"', self.vc.template)

    def test_no_style(self):
        self.assertEqual(self.vc.style, '')

    def test_raises_on_import_statement(self):
        vue_with_import = (
            "<template><div></div></template>\n<script>import { ref } from 'vue'\nexport default {}</script>\n"
        )
        with self.assertRaises(VueSectionError) as ctx:
            VueComponent('Bad.vue', vue_with_import)
        self.assertEqual(ctx.exception.section, 'script')


class TestVueComponentStatic(unittest.TestCase):
    """Static.vue: template-only component, no script or style."""

    def setUp(self):
        self.vc = VueComponent('Static.vue', read_fixture('Static.vue'))

    def test_name(self):
        self.assertEqual(self.vc.name, 'Static')

    def test_component_empty(self):
        self.assertEqual(self.vc.component, '')

    def test_variables_empty(self):
        self.assertEqual(self.vc.variables, '')

    def test_style_empty(self):
        self.assertEqual(self.vc.style, '')

    def test_template_preserves_void_element(self):
        self.assertIn('<hr />', self.vc.template)


class TestFindVueFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_files_in_flat_dir(self):
        open(os.path.join(self.base, 'A.vue'), 'w').close()
        open(os.path.join(self.base, 'B.vue'), 'w').close()
        open(os.path.join(self.base, 'readme.txt'), 'w').close()
        names = sorted(os.path.basename(f) for f in find_vue_files(self.base))
        self.assertEqual(names, ['A.vue', 'B.vue'])

    def test_finds_files_recursively(self):
        sub = os.path.join(self.base, 'components')
        os.makedirs(sub)
        open(os.path.join(self.base, 'Root.vue'), 'w').close()
        open(os.path.join(sub, 'Child.vue'), 'w').close()
        names = sorted(os.path.basename(f) for f in find_vue_files(self.base))
        self.assertEqual(names, ['Child.vue', 'Root.vue'])

    def test_empty_dir(self):
        self.assertEqual(find_vue_files(self.base), [])

    def test_non_vue_excluded(self):
        open(os.path.join(self.base, 'app.js'), 'w').close()
        self.assertEqual(find_vue_files(self.base), [])


class TestCollectVue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_yields_one_component(self):
        with open(os.path.join(self.base, 'Counter.vue'), 'w') as f:
            f.write(read_fixture('Counter.vue'))
        components = list(collect_vue(self.base))
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0].name, 'Counter')

    def test_skips_non_vue_files(self):
        with open(os.path.join(self.base, 'Counter.vue'), 'w') as f:
            f.write(read_fixture('Counter.vue'))
        with open(os.path.join(self.base, 'notes.md'), 'w') as f:
            f.write('notes')
        components = list(collect_vue(self.base))
        self.assertEqual(len(components), 1)

    def test_recurses_into_subdirectories(self):
        sub = os.path.join(self.base, 'ui')
        os.makedirs(sub)
        with open(os.path.join(self.base, 'Counter.vue'), 'w') as f:
            f.write(read_fixture('Counter.vue'))
        with open(os.path.join(sub, 'Static.vue'), 'w') as f:
            f.write(read_fixture('Static.vue'))
        components = list(collect_vue(self.base))
        self.assertEqual(len(components), 2)

    def test_scoped_component_collected_correctly(self):
        with open(os.path.join(self.base, 'Card.vue'), 'w') as f:
            f.write(read_fixture('Card.vue'))
        sid = hashlib.sha256('Card.vue'.encode()).hexdigest()[:8]
        components = list(collect_vue(self.base))
        self.assertEqual(len(components), 1)
        self.assertIn(f'data-v-{sid}', components[0].template)
        self.assertIn(f'[data-v-{sid}]', components[0].style)


class TestPrepareCompiled(unittest.TestCase):
    TEMPLATE_HTML = (
        '<html><head><style><|style|></style></head>'
        '<body><|templates|><script><|variables|><|components|></script></body></html>'
    )

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = self.tmp.name
        self.vue_dir = os.path.join(self.base, 'vue')
        os.makedirs(self.vue_dir)
        with open(os.path.join(self.vue_dir, 'Counter.vue'), 'w') as f:
            f.write(read_fixture('Counter.vue'))

    def tearDown(self):
        self.tmp.cleanup()

    def test_style_placeholder_replaced(self):
        result = prepare_compiled(self.TEMPLATE_HTML, self.vue_dir)
        self.assertNotIn('<|style|>', result)
        self.assertIn('.counter{display:flex;gap:8px;}', result)

    def test_templates_placeholder_replaced(self):
        result = prepare_compiled(self.TEMPLATE_HTML, self.vue_dir)
        self.assertNotIn('<|templates|>', result)
        self.assertIn('<template id="template-counter">', result)

    def test_components_placeholder_replaced(self):
        result = prepare_compiled(self.TEMPLATE_HTML, self.vue_dir)
        self.assertNotIn('<|components|>', result)
        self.assertIn("app.component('Counter'", result)
        self.assertIn("template: '#template-counter'", result)

    def test_variables_placeholder_replaced(self):
        result = prepare_compiled(self.TEMPLATE_HTML, self.vue_dir)
        self.assertNotIn('<|variables|>', result)

    def test_scoped_component_in_output(self):
        with open(os.path.join(self.vue_dir, 'Card.vue'), 'w') as f:
            f.write(read_fixture('Card.vue'))
        sid = hashlib.sha256('Card.vue'.encode()).hexdigest()[:8]
        result = prepare_compiled(self.TEMPLATE_HTML, self.vue_dir)
        self.assertIn(f'data-v-{sid}', result)
        self.assertIn(f'[data-v-{sid}]', result)


if __name__ == '__main__':
    unittest.main()
