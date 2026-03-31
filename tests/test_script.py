import unittest

from vue_collector.script import (
    _extract_export_default,
    _has_import,
    _parse_script,
    _strip_imports,
    _strip_object_key,
)


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
        variables, component = _parse_script('X', 'export default { data() { return {} } }')
        self.assertEqual(variables, '')
        self.assertEqual(component, 'data() { return {} }')

    def test_variables_before_export(self):
        raw = 'const helper = () => {}\nexport default { data() { return {} } }'
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, 'const helper = () => {}')
        self.assertEqual(component, 'data() { return {} }')

    def test_variables_after_export(self):
        raw = 'export default { data() { return {} } }\nconst after = 1'
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, 'const after = 1')
        self.assertEqual(component, 'data() { return {} }')

    def test_variables_before_and_after_export(self):
        raw = 'const a = 1\nexport default { data() { return {} } }\nconst b = 2'
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, 'const a = 1\nconst b = 2')
        self.assertEqual(component, 'data() { return {} }')

    def test_raises_on_script_with_content_but_no_export_default(self):
        with self.assertRaises(ValueError):
            _parse_script('Bad', 'const x = 1')

    def test_raises_on_invalid_export_default(self):
        with self.assertRaises(ValueError):
            _parse_script('Bad', "export default 'string'")

    def test_multiline_component_body(self):
        raw = "\nexport default {\n  data() { return { x: 1 } }\n}\n"
        variables, component = _parse_script('Comp', raw)
        self.assertEqual(variables, '')
        self.assertIn('data() { return { x: 1 } }', component)

    def test_import_before_export_stripped(self):
        raw = "import { ref } from 'vue'\nexport default { setup() { return { x: ref(0) } } }"
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, '')
        self.assertEqual(component, 'setup() { return { x: ref(0) } }')

    def test_import_after_export_stripped(self):
        raw = "export default {}\nimport { x } from './x'"
        variables, _ = _parse_script('X', raw)
        self.assertEqual(variables, '')

    def test_forbid_imports_raises_before(self):
        raw = "import { ref } from 'vue'\nexport default {}"
        with self.assertRaises(ValueError):
            _parse_script('X', raw, forbid_imports=True)

    def test_forbid_imports_raises_after(self):
        raw = "export default {}\nimport { x } from './x'"
        with self.assertRaises(ValueError):
            _parse_script('X', raw, forbid_imports=True)

    def test_components_stripped_from_body(self):
        raw = "import Foo from './Foo.vue'\nexport default { components: { Foo }, data() { return {} } }"
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, '')
        self.assertEqual(component, 'data() { return {} }')

    def test_const_before_export_allowed(self):
        raw = 'const helper = () => {}\nexport default { data() { return {} } }'
        variables, component = _parse_script('X', raw)
        self.assertEqual(variables, 'const helper = () => {}')
        self.assertEqual(component, 'data() { return {} }')

    def test_import_word_inside_template_literal_not_raised(self):
        # A template literal variable that contains the word 'import' must not be rejected
        raw = "const docs = `\nimport { ref } from 'vue'\n`\nexport default { data() { return {} } }"
        variables, component = _parse_script('X', raw)
        self.assertIn('docs', variables)
        self.assertEqual(component, 'data() { return {} }')

    def test_trailing_semicolon_after_export_default_not_in_variables(self):
        # export default { ... }; — the trailing ';' must NOT end up in variables
        raw = 'export default {\n  data() { return {} }\n};'
        variables, component = _parse_script('Foo', raw)
        self.assertEqual(variables, '')
        self.assertEqual(component, 'data() { return {} }')

    def test_code_after_export_default_semicolon_captured(self):
        # export default { ... }; const X = 1; — only the real code after ';' goes into variables
        raw = 'export default { data() { return {} } };\nconst X = 1;'
        variables, _ = _parse_script('Foo', raw)
        self.assertEqual(variables, 'const X = 1;')


class TestStripImports(unittest.TestCase):
    def test_single_import(self):
        self.assertEqual(_strip_imports("import { ref } from 'vue'\nconst x = 1"), 'const x = 1')

    def test_multiple_imports(self):
        code = "import { ref } from 'vue'\nimport Foo from './Foo.vue'\nconst x = 1"
        self.assertEqual(_strip_imports(code), 'const x = 1')

    def test_multiline_import(self):
        code = "import {\n  ref,\n  computed\n} from 'vue'\nconst x = 1"
        self.assertEqual(_strip_imports(code), 'const x = 1')

    def test_default_import(self):
        self.assertEqual(_strip_imports("import Foo from './Foo.vue'"), '')

    def test_star_import(self):
        self.assertEqual(_strip_imports("import * as utils from './utils'"), '')

    def test_side_effect_import(self):
        self.assertEqual(_strip_imports("import 'polyfill'"), '')

    def test_no_space_import(self):
        self.assertEqual(_strip_imports("import{ref} from 'vue'"), '')

    def test_preserves_non_import_code(self):
        code = 'const helper = () => {}\nconst x = 1'
        self.assertEqual(_strip_imports(code), code)

    def test_import_in_string_preserved(self):
        code = "const x = 'import y from z'"
        self.assertEqual(_strip_imports(code), code)

    def test_import_in_comment_preserved(self):
        code = "// import x from 'y'\nconst y = 1"
        self.assertEqual(_strip_imports(code), code)

    def test_empty_string(self):
        self.assertEqual(_strip_imports(''), '')

    def test_import_between_code(self):
        code = "const a = 1\nimport { ref } from 'vue'\nconst b = 2"
        self.assertEqual(_strip_imports(code), 'const a = 1\nconst b = 2')


class TestStripObjectKey(unittest.TestCase):
    # --- components (object value) ---
    def test_components_simple(self):
        self.assertEqual(
            _strip_object_key('components: { Foo }, data() { return {} }', 'components'),
            'data() { return {} }',
        )

    def test_components_multiline(self):
        body = 'components: {\n  Foo,\n  Bar\n},\ndata() { return {} }'
        self.assertEqual(_strip_object_key(body, 'components'), 'data() { return {} }')

    def test_components_preserves_other_keys(self):
        body = 'data() { return {} }'
        self.assertEqual(_strip_object_key(body, 'components'), body)

    def test_components_in_nested_object_preserved(self):
        body = 'data() { return { components: {} } }'
        self.assertEqual(_strip_object_key(body, 'components'), body)

    def test_components_trailing_comma_removed(self):
        body = 'components: { Foo },\ndata() { return {} }'
        self.assertEqual(_strip_object_key(body, 'components'), 'data() { return {} }')

    def test_components_only(self):
        self.assertEqual(_strip_object_key('components: { Foo }', 'components'), '')

    def test_components_after_other_key(self):
        body = 'data() { return {} },\ncomponents: { Foo }'
        self.assertEqual(_strip_object_key(body, 'components'), 'data() { return {} },')

    # --- name (string value) ---
    def test_name_single_quotes(self):
        self.assertEqual(
            _strip_object_key("name: 'Foo', data() { return {} }", 'name'),
            'data() { return {} }',
        )

    def test_name_double_quotes(self):
        self.assertEqual(
            _strip_object_key('name: "Foo", data() { return {} }', 'name'),
            'data() { return {} }',
        )

    def test_name_in_nested_not_stripped(self):
        body = "data() { return { name: 'x' } }"
        self.assertEqual(_strip_object_key(body, 'name'), body)

    def test_name_only(self):
        self.assertEqual(_strip_object_key("name: 'Foo'", 'name'), '')

    def test_name_at_end(self):
        self.assertEqual(_strip_object_key("data() {},\nname: 'Foo'", 'name'), 'data() {},')

    # --- general ---
    def test_empty_body(self):
        self.assertEqual(_strip_object_key('', 'anything'), '')

    def test_key_not_present_unchanged(self):
        body = 'data() { return {} }'
        self.assertEqual(_strip_object_key(body, 'name'), body)

    def test_key_in_comment_not_stripped(self):
        body = "// name: 'x'\ndata() { return {} }"
        self.assertEqual(_strip_object_key(body, 'name'), body)

    def test_key_in_string_not_stripped(self):
        body = 'label: "name: foo"'
        self.assertEqual(_strip_object_key(body, 'name'), body)


if __name__ == '__main__':
    unittest.main()
