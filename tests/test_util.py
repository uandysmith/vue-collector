import hashlib
import unittest

from vue_collector.util import _make_scope_id, _make_template_name


class TestMakeTemplateName(unittest.TestCase):
    def test_camelcase_to_kebab(self):
        self.assertEqual(_make_template_name('MyComponent'), 'template-my-component')

    def test_single_capitalized_word(self):
        self.assertEqual(_make_template_name('Hello'), 'template-hello')

    def test_all_lowercase_no_hyphens(self):
        # lowercase letters are not prefixed with '-'
        self.assertEqual(_make_template_name('app'), 'templateapp')

    def test_leading_lowercase_then_camel(self):
        self.assertEqual(_make_template_name('myComponent'), 'templatemy-component')

    def test_multiword_camel(self):
        self.assertEqual(_make_template_name('UserProfileCard'), 'template-user-profile-card')

    def test_digit_gets_hyphen(self):
        # digits also satisfy x.capitalize() == x → treated like uppercase
        self.assertEqual(_make_template_name('AppV2'), 'template-app-v-2')


class TestMakeScopeId(unittest.TestCase):
    def test_returns_8_chars(self):
        self.assertEqual(len(_make_scope_id('MyComponent.vue')), 8)

    def test_returns_hex_string(self):
        int(_make_scope_id('MyComponent.vue'), 16)  # raises ValueError if not valid hex

    def test_deterministic(self):
        self.assertEqual(_make_scope_id('Foo.vue'), _make_scope_id('Foo.vue'))

    def test_different_files_produce_different_ids(self):
        self.assertNotEqual(_make_scope_id('A.vue'), _make_scope_id('B.vue'))

    def test_path_affects_id(self):
        self.assertNotEqual(_make_scope_id('components/Foo.vue'), _make_scope_id('Foo.vue'))

    def test_known_value(self):
        expected = hashlib.sha256('MyComponent.vue'.encode()).hexdigest()[:8]
        self.assertEqual(_make_scope_id('MyComponent.vue'), expected)


if __name__ == '__main__':
    unittest.main()
