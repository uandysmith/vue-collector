import unittest

from vue_collector.script import _extract_export_default, _has_import, _parse_script


class TestExtractExportDefault(unittest.TestCase):
    def test_simple_object(self):
        self.assertEqual(
            _extract_export_default('export default { name: "x" }'),
            ('', 'name: "x"', ''),
        )

    def test_empty_object(self):
        self.assertEqual(
            _extract_export_default('export default {}'),
            ('', '', ''),
        )

    def test_code_before_export(self):
        self.assertEqual(
            _extract_export_default('const x = 1\nexport default { name: "x" }'),
            ('const x = 1\n', 'name: "x"', ''),
        )

    def test_code_after_export(self):
        self.assertEqual(
            _extract_export_default('export default { name: "x" }\nconst y = 2'),
            ('', 'name: "x"', 'const y = 2'),
        )

    def test_code_before_and_after_export(self):
        self.assertEqual(
            _extract_export_default('const a = 1\nexport default { name: "x" }\nconst b = 2'),
            ('const a = 1\n', 'name: "x"', 'const b = 2'),
        )

    def test_nested_objects(self):
        self.assertEqual(
            _extract_export_default('export default { setup() { return {} } }'),
            ('', 'setup() { return {} }', ''),
        )

    def test_deeply_nested_objects(self):
        self.assertEqual(
            _extract_export_default('export default { data() { return { a: { b: 1 } } } }'),
            ('', 'data() { return { a: { b: 1 } } }', ''),
        )

    def test_string_with_braces_double_quotes(self):
        self.assertEqual(
            _extract_export_default('export default { label: "a{b}c" }'),
            ('', 'label: "a{b}c"', ''),
        )

    def test_string_with_braces_single_quotes(self):
        self.assertEqual(
            _extract_export_default("export default { label: 'a{b}c' }"),
            ('', "label: 'a{b}c'", ''),
        )

    def test_template_literal_with_braces(self):
        self.assertEqual(
            _extract_export_default('export default { tmpl: `{x}` }'),
            ('', 'tmpl: `{x}`', ''),
        )

    def test_escaped_quote_inside_string(self):
        self.assertEqual(
            _extract_export_default(r'export default { msg: "say \"hi\"" }'),
            ('', r'msg: "say \"hi\""', ''),
        )

    def test_single_line_comment(self):
        self.assertEqual(
            _extract_export_default('export default { // comment\n name: "x" }'),
            ('', '// comment\n name: "x"', ''),
        )

    def test_block_comment(self):
        self.assertEqual(
            _extract_export_default('export default { /* foo */ name: "x" }'),
            ('', '/* foo */ name: "x"', ''),
        )

    def test_block_comment_with_braces(self):
        self.assertEqual(
            _extract_export_default('export default { /* { not a brace } */ name: "x" }'),
            ('', '/* { not a brace } */ name: "x"', ''),
        )

    def test_no_export_default_returns_script_unchanged(self):
        self.assertEqual(
            _extract_export_default('const x = 1'),
            ('const x = 1', '', ''),
        )

    def test_empty_string_returns_empty(self):
        self.assertEqual(
            _extract_export_default(''),
            ('', '', ''),
        )

    def test_raises_when_not_followed_by_brace(self):
        with self.assertRaises(ValueError):
            _extract_export_default("export default 'not-an-object'")

    def test_raises_on_unclosed_brace(self):
        with self.assertRaises(ValueError):
            _extract_export_default('export default { name: "x"')

    def test_multiline_component(self):
        script = "export default {\n  name: 'my-comp',\n  data() {\n    return { count: 0 }\n  },\n}"
        _, body, after = _extract_export_default(script)
        self.assertEqual(after, '')
        self.assertIn("name: 'my-comp'", body)
        self.assertIn('return { count: 0 }', body)


class TestHasImport(unittest.TestCase):
    def test_import_at_start(self):
        self.assertTrue(_has_import("import { ref } from 'vue'"))

    def test_import_after_newline(self):
        self.assertTrue(_has_import("const x = 1\nimport { ref } from 'vue'"))

    def test_import_after_semicolon(self):
        self.assertTrue(_has_import("const x = 1;import { ref } from 'vue'"))

    def test_import_with_leading_whitespace_after_newline(self):
        self.assertTrue(_has_import("const x = 1\n  import { ref } from 'vue'"))

    def test_import_brace_no_space(self):
        self.assertTrue(_has_import("import{ref} from 'vue'"))

    def test_import_inside_single_quote_string(self):
        self.assertFalse(_has_import("const x = 'import { ref } from vue'"))

    def test_import_inside_double_quote_string(self):
        self.assertFalse(_has_import('const x = "import { ref } from vue"'))

    def test_import_inside_template_literal_single_line(self):
        self.assertFalse(_has_import("const x = `import { ref } from 'vue'`"))

    def test_import_inside_template_literal_multiline(self):
        code = "const docs = `\nimport { ref } from 'vue'\n`"
        self.assertFalse(_has_import(code))

    def test_import_as_part_of_identifier(self):
        # 'importSomething' is not an import statement
        self.assertFalse(_has_import('const importHelper = () => {}'))

    def test_underscore_import_identifier(self):
        # '_import' contains 'import ' after '_' but at_stmt_start is False
        self.assertFalse(_has_import('const _import = 42'))

    def test_import_inside_line_comment(self):
        self.assertFalse(_has_import("// import { ref } from 'vue'"))

    def test_import_inside_block_comment(self):
        self.assertFalse(_has_import("/* import { ref } from 'vue' */"))

    def test_import_inside_multiline_block_comment(self):
        code = "/*\nimport { ref } from 'vue'\n*/\nexport default {}"
        self.assertFalse(_has_import(code))

    def test_empty_string(self):
        self.assertFalse(_has_import(''))

    def test_no_import(self):
        self.assertFalse(_has_import('const x = 1\nexport default {}'))


class TestParseScript(unittest.TestCase):
    def test_empty_raw_returns_empty_tuple(self):
        self.assertEqual(_parse_script('X', ''), ('', ''))

    def test_whitespace_only_returns_empty_tuple(self):
        self.assertEqual(_parse_script('X', '   \n  '), ('', ''))

    def test_only_export_default_empty_object(self):
        self.assertEqual(_parse_script('X', 'export default {}'), ('', ''))

    def test_simple_component(self):
        variables, component = _parse_script('X', 'export default { name: "x" }')
        self.assertEqual(variables, '')
        self.assertEqual(component, 'name: "x"')

    def test_variables_before_export(self):
        raw = 'const helper = () => {}\nexport default { name: "x" }'
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, 'const helper = () => {}')
        self.assertEqual(component, 'name: "x"')

    def test_variables_after_export(self):
        raw = 'export default { name: "x" }\nconst after = 1'
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, 'const after = 1')
        self.assertEqual(component, 'name: "x"')

    def test_variables_before_and_after_export(self):
        raw = 'const a = 1\nexport default { name: "x" }\nconst b = 2'
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, 'const a = 1\nconst b = 2')
        self.assertEqual(component, 'name: "x"')

    def test_raises_on_script_with_content_but_no_export_default(self):
        with self.assertRaises(ValueError):
            _parse_script('Bad', 'const x = 1')

    def test_raises_on_invalid_export_default(self):
        with self.assertRaises(ValueError):
            _parse_script('Bad', "export default 'string'")

    def test_multiline_component_body(self):
        raw = "\nexport default {\n  name: 'comp',\n  data() { return { x: 1 } }\n}\n"
        variables, component = _parse_script('Comp', raw)
        self.assertEqual(variables, '')
        self.assertIn("name: 'comp'", component)
        self.assertIn('data() { return { x: 1 } }', component)

    def test_raises_on_import_before_export(self):
        raw = "import { ref } from 'vue'\nexport default { setup() { return { x: ref(0) } } }"
        with self.assertRaises(ValueError):
            _parse_script('X', raw)

    def test_raises_on_import_after_export(self):
        raw = "export default {}\nimport { x } from './x'"
        with self.assertRaises(ValueError):
            _parse_script('X', raw)

    def test_const_before_export_allowed(self):
        raw = 'const helper = () => {}\nexport default { name: "x" }'
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, 'const helper = () => {}')
        self.assertEqual(component, 'name: "x"')

    def test_import_word_inside_template_literal_not_raised(self):
        # A template literal variable that contains the word 'import' must not be rejected
        raw = "const docs = `\nimport { ref } from 'vue'\n`\nexport default { name: 'X' }"
        variables, component = _parse_script('X', raw)
        self.assertIn('docs', variables)
        self.assertEqual(component, "name: 'X'")


if __name__ == '__main__':
    unittest.main()
