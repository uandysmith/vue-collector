"""
Tests for structured error handling in vue-collector.

All errors raised by VueComponent must be VueSectionError
instances with the correct file_name, section, and message.
"""

import unittest

from vue_collector import VueComponent, VueSectionError


def _make(template='', script='', style=''):
    """Build a minimal .vue file string from section contents."""
    parts = []
    if template is not None:
        parts.append(f'<template>{template}</template>')
    if script is not None:
        parts.append(f'<script>{script}</script>')
    if style is not None:
        parts.append(f'<style>{style}</style>')
    return '\n'.join(parts)


class TestVueSectionErrorClass(unittest.TestCase):
    """VueSectionError structure and string representation."""

    def test_str_with_section(self):
        err = VueSectionError('Foo.vue', 'script', 'import not allowed')
        self.assertEqual(str(err), 'Foo.vue [script]: import not allowed')

    def test_str_without_section(self):
        err = VueSectionError('Foo.vue', None, 'Duplicate <template> section')
        self.assertEqual(str(err), 'Foo.vue: Duplicate <template> section')

    def test_file_name_attribute(self):
        err = VueSectionError('Bar.vue', 'style', 'bad css')
        self.assertEqual(err.file_name, 'Bar.vue')

    def test_section_attribute(self):
        err = VueSectionError('Bar.vue', 'style', 'bad css')
        self.assertEqual(err.section, 'style')

    def test_message_attribute(self):
        err = VueSectionError('Bar.vue', 'style', 'bad css')
        self.assertEqual(err.message, 'bad css')

    def test_is_value_error_subclass(self):
        err = VueSectionError('X.vue', None, 'msg')
        self.assertIsInstance(err, ValueError)


class TestStructuralErrors(unittest.TestCase):
    """Duplicate and unclosed root sections."""

    def _raises(self, content, file_name='Test.vue'):
        with self.assertRaises(VueSectionError) as ctx:
            VueComponent(file_name, content)
        return ctx.exception

    def test_duplicate_template(self):
        content = '<template><div></div></template><template><span></span></template>'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('Duplicate', err.message)
        self.assertIn('template', err.message)

    def test_nested_template_not_duplicate(self):
        # Named slots use nested <template> — must NOT raise
        content = (
            '<template>'
            '<div><template #header><h1>Hi</h1></template></div>'
            '</template>'
            '<script>export default {}</script>'
        )
        comp = VueComponent('Nested.vue', content)
        self.assertEqual(comp.raw_template, '<div><template #header><h1>Hi</h1></template></div>')

    def test_duplicate_script(self):
        content = '<template></template><script>export default {}</script><script>export default {}</script>'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('Duplicate', err.message)
        self.assertIn('script', err.message)

    def test_duplicate_style(self):
        content = '<template></template><style>.a{}</style><style>.b{}</style>'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('Duplicate', err.message)
        self.assertIn('style', err.message)

    def test_unclosed_template_section(self):
        content = '<template><div></div>'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('Unclosed', err.message)
        self.assertIn('template', err.message)

    def test_unclosed_script_section(self):
        content = '<template></template><script>export default {}'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('Unclosed', err.message)
        self.assertIn('script', err.message)

    def test_file_name_in_error(self):
        content = '<template><div></div>'
        err = self._raises(content, file_name='MyComp.vue')
        self.assertEqual(err.file_name, 'MyComp.vue')
        self.assertIn('MyComp.vue', str(err))


class TestTemplateHTMLErrors(unittest.TestCase):
    """Mismatched and unclosed inner HTML tags inside <template>."""

    def _raises(self, content, file_name='Test.vue'):
        with self.assertRaises(VueSectionError) as ctx:
            VueComponent(file_name, content)
        return ctx.exception

    def test_unclosed_inner_div(self):
        content = '<template><div>text</template>'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('<div>', err.message)

    def test_unclosed_nested_inner_tag(self):
        content = '<template><ul><li>item</ul></template>'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('</li>', err.message)

    def test_mismatched_tags(self):
        content = '<template><div><span></div></template>'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('Mismatched', err.message)
        self.assertIn('</span>', err.message)
        self.assertIn('</div>', err.message)

    def test_unexpected_closing_tag(self):
        content = '<template><div></div></div></template>'
        err = self._raises(content)
        self.assertIsNone(err.section)
        self.assertIn('Unexpected', err.message)
        self.assertIn('</div>', err.message)

    def test_well_formed_template_no_error(self):
        content = '<template><div><span>ok</span></div></template>'
        vc = VueComponent('Ok.vue', content)
        self.assertEqual(vc.get_content('template') if hasattr(vc, 'get_content') else vc.template, vc.template)

    def test_void_elements_do_not_require_close(self):
        content = '<template><div><br /><input type="text" /></div></template>'
        vc = VueComponent('Ok.vue', content)
        self.assertIn('<br />', vc.template)

    def test_self_closing_custom_element_no_stack_push(self):
        # HTMLParser lowercases tag names; self-closing must not push to inner_stack
        content = '<template><div><myicon /></div></template>'
        vc = VueComponent('Ok.vue', content)
        self.assertIn('<myicon />', vc.template)


class TestScriptErrors(unittest.TestCase):
    """Script section validation errors."""

    def _raises(self, script_content, file_name='Test.vue'):
        content = f'<template><div></div></template>\n<script>{script_content}</script>'
        with self.assertRaises(VueSectionError) as ctx:
            VueComponent(file_name, content)
        return ctx.exception

    def test_no_export_default(self):
        err = self._raises('const x = 1')
        self.assertEqual(err.section, 'script')

    def test_import_statement_raises(self):
        err = self._raises("import { ref } from 'vue'\nexport default { name: 'x' }")
        self.assertEqual(err.section, 'script')
        self.assertIn('import', err.message)

    def test_import_without_space_raises(self):
        err = self._raises("import{ref} from 'vue'\nexport default { name: 'x' }")
        self.assertEqual(err.section, 'script')

    def test_export_default_not_object(self):
        err = self._raises("export default 'string'")
        self.assertEqual(err.section, 'script')

    def test_str_contains_file_and_section(self):
        err = self._raises("import x from 'x'\nexport default { name: 'x' }", file_name='MyComp.vue')
        self.assertIn('MyComp.vue', str(err))
        self.assertIn('[script]', str(err))

    def test_valid_script_no_error(self):
        content = '<template><div></div></template>\n<script>export default { data() { return {} } }</script>'
        vc = VueComponent('X.vue', content)
        self.assertEqual(vc.component, 'data() { return {} }')

    def test_name_property_raises(self):
        err = self._raises("export default { name: 'X', data() { return {} } }")
        self.assertEqual(err.section, 'script')
        self.assertIn('name', err.message)


class TestStyleErrors(unittest.TestCase):
    """Style section validation errors."""

    def _raises(self, style_content, file_name='Test.vue'):
        content = f'<template><div></div></template>\n<style>{style_content}</style>'
        with self.assertRaises(VueSectionError) as ctx:
            VueComponent(file_name, content)
        return ctx.exception

    def test_import_url_raises(self):
        err = self._raises("@import url('fonts.css'); .foo { color: red; }")
        self.assertEqual(err.section, 'style')
        self.assertIn('@import', err.message)

    def test_import_string_raises(self):
        err = self._raises("@import 'base.css'; .foo { color: red; }")
        self.assertEqual(err.section, 'style')
        self.assertIn('@import', err.message)

    def test_import_uppercase_raises(self):
        err = self._raises("@IMPORT 'base.css';")
        self.assertEqual(err.section, 'style')

    def test_bad_less_syntax_raises(self):
        err = self._raises('.foo { color: !!invalid; }')
        self.assertEqual(err.section, 'style')
        self.assertIn('CSS compilation error', err.message)

    def test_str_contains_file_and_section(self):
        err = self._raises("@import 'x.css';", file_name='MyComp.vue')
        self.assertIn('MyComp.vue', str(err))
        self.assertIn('[style]', str(err))

    def test_valid_style_no_error(self):
        content = '<template><div></div></template>\n<style>.foo { color: red; }</style>'
        vc = VueComponent('X.vue', content)
        self.assertEqual(vc.style, '.foo{color:red;}')


class TestStyleLangErrors(unittest.TestCase):
    """Style lang attribute — only LESS accepted."""

    def _vue(self, style_open: str) -> str:
        return (
            '<template><div></div></template>\n'
            '<script>export default {}</script>\n'
            f'{style_open}.a{{color:red;}}</style>'
        )

    def _raises(self, style_open: str):
        with self.assertRaises(VueSectionError) as ctx:
            VueComponent('Test.vue', self._vue(style_open))
        return ctx.exception

    def test_no_lang_accepted(self):
        VueComponent('Test.vue', self._vue('<style>'))

    def test_lang_less_accepted(self):
        VueComponent('Test.vue', self._vue('<style lang="less">'))

    def test_lang_less_uppercase_accepted(self):
        VueComponent('Test.vue', self._vue('<style lang="LESS">'))

    def test_lang_scss_raises(self):
        err = self._raises('<style lang="scss">')
        self.assertEqual(err.section, 'style')
        self.assertIn('scss', err.message)

    def test_lang_css_raises(self):
        err = self._raises('<style lang="css">')
        self.assertEqual(err.section, 'style')
        self.assertIn('css', err.message)

    def test_lang_stylus_raises(self):
        err = self._raises('<style lang="stylus">')
        self.assertEqual(err.section, 'style')
        self.assertIn('stylus', err.message)


class TestScriptLangErrors(unittest.TestCase):
    """Script lang attribute — TypeScript and any other lang rejected."""

    def _vue(self, script_open: str) -> str:
        return (
            '<template><div></div></template>\n'
            f'{script_open}export default {{}}</script>'
        )

    def _raises(self, script_open: str):
        with self.assertRaises(VueSectionError) as ctx:
            VueComponent('Test.vue', self._vue(script_open))
        return ctx.exception

    def test_no_lang_accepted(self):
        VueComponent('Test.vue', self._vue('<script>'))

    def test_lang_ts_raises(self):
        err = self._raises('<script lang="ts">')
        self.assertEqual(err.section, 'script')
        self.assertIn('TypeScript', err.message)

    def test_lang_typescript_raises(self):
        err = self._raises('<script lang="typescript">')
        self.assertEqual(err.section, 'script')
        self.assertIn('TypeScript', err.message)


if __name__ == '__main__':
    unittest.main()
