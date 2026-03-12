import unittest

from vue_collector.template import CustomHTML


class TestCustomHTMLParser(unittest.TestCase):
    def test_extracts_template_content(self):
        parser = CustomHTML()
        parser.feed('<template><div>Hello</div></template>')
        self.assertEqual(parser.get_content('template'), '<div>Hello</div>')

    def test_extracts_script_content(self):
        parser = CustomHTML()
        parser.feed('<template></template><script>\nconst x = 1;\nexport default {}\n</script>')
        self.assertEqual(parser.get_content('script'), '\nconst x = 1;\nexport default {}\n')

    def test_extracts_style_content(self):
        parser = CustomHTML()
        parser.feed('<template></template><style>.foo { color: red; }</style>')
        self.assertEqual(parser.get_content('style'), '.foo { color: red; }')

    def test_absent_sections_return_empty_string(self):
        parser = CustomHTML()
        parser.feed('<template><div></div></template>')
        self.assertEqual(parser.get_content('script'), '')
        self.assertEqual(parser.get_content('style'), '')

    def test_preserves_element_attributes(self):
        parser = CustomHTML()
        parser.feed('<template><div class="foo" id="bar">text</div></template>')
        self.assertEqual(parser.get_content('template'), '<div class="foo" id="bar">text</div>')

    def test_boolean_attribute(self):
        parser = CustomHTML()
        parser.feed('<template><input disabled></template>')
        self.assertEqual(parser.get_content('template'), '<input disabled />')

    def test_deeply_nested_elements(self):
        parser = CustomHTML()
        parser.feed('<template><ul><li><span>item</span></li></ul></template>')
        self.assertEqual(parser.get_content('template'), '<ul><li><span>item</span></li></ul>')

    def test_mixed_text_and_elements(self):
        parser = CustomHTML()
        parser.feed('<template><p>Hello <strong>world</strong>!</p></template>')
        self.assertEqual(parser.get_content('template'), '<p>Hello <strong>world</strong>!</p>')

    def test_vue_directive_attributes_pass_through(self):
        parser = CustomHTML()
        parser.feed('<template><div v-if="show" @click="handle" :class="cls">x</div></template>')
        self.assertEqual(
            parser.get_content('template'),
            '<div v-if="show" @click="handle" :class="cls">x</div>',
        )

    def test_data_attributes_pass_through(self):
        parser = CustomHTML()
        parser.feed('<template><span data-id="42" data-label="ok">x</span></template>')
        self.assertEqual(parser.get_content('template'), '<span data-id="42" data-label="ok">x</span>')

    def test_sections_are_independent(self):
        parser = CustomHTML()
        parser.feed('<template><div>tpl</div></template><script>const x = 1</script><style>.a{}</style>')
        self.assertEqual(parser.get_content('template'), '<div>tpl</div>')
        self.assertEqual(parser.get_content('script'), 'const x = 1')
        self.assertEqual(parser.get_content('style'), '.a{}')


class TestVoidElements(unittest.TestCase):
    def test_xhtml_self_closing_input_no_end_tag(self):
        """Regression: <input /> must not produce </input>."""
        parser = CustomHTML()
        parser.feed('<template><div><input /></div></template>')
        self.assertEqual(parser.get_content('template'), '<div><input /></div>')

    def test_xhtml_self_closing_br_no_end_tag(self):
        """Regression: <br /> must not produce </br>."""
        parser = CustomHTML()
        parser.feed('<template><div><br /></div></template>')
        self.assertEqual(parser.get_content('template'), '<div><br /></div>')

    def test_xhtml_self_closing_img_no_end_tag(self):
        """Regression: <img /> must not produce </img>."""
        parser = CustomHTML()
        parser.feed('<template><img src="test.png" /></template>')
        self.assertEqual(parser.get_content('template'), '<img src="test.png" />')

    def test_html_void_br_no_end_tag(self):
        """HTML-style void <br> (no slash) must not produce </br>."""
        parser = CustomHTML()
        parser.feed('<template><br></template>')
        self.assertEqual(parser.get_content('template'), '<br />')

    def test_compact_self_closing_br_no_end_tag(self):
        """<br/> (no space before slash) must not produce </br>."""
        parser = CustomHTML()
        parser.feed('<template><br/></template>')
        self.assertEqual(parser.get_content('template'), '<br />')

    def test_all_void_elements_no_closing_tags(self):
        """Multiple void elements should not produce closing tags."""
        parser = CustomHTML()
        parser.feed('<template><input /><br /><img src="x" /><hr /></template>')
        self.assertEqual(parser.get_content('template'), '<input /><br /><img src="x" /><hr />')

    def test_non_void_elements_keep_closing_tags(self):
        """Regular elements must still have their closing tags."""
        parser = CustomHTML()
        parser.feed('<template><div><span>text</span></div></template>')
        self.assertEqual(parser.get_content('template'), '<div><span>text</span></div>')

    def test_void_element_with_attributes(self):
        parser = CustomHTML()
        parser.feed('<template><input type="checkbox" checked /></template>')
        self.assertEqual(parser.get_content('template'), '<input type="checkbox" checked />')

    def test_img_with_multiple_attributes(self):
        parser = CustomHTML()
        parser.feed('<template><img src="a.png" alt="A" width="100" /></template>')
        self.assertEqual(parser.get_content('template'), '<img src="a.png" alt="A" width="100" />')


class TestCustomHTMLScoped(unittest.TestCase):
    def test_is_scoped_false_without_attribute(self):
        parser = CustomHTML()
        parser.feed('<template><div></div></template><style>.foo{}</style>')
        self.assertEqual(parser.is_scoped(), False)

    def test_is_scoped_true_with_scoped_attribute(self):
        parser = CustomHTML()
        parser.feed('<template><div></div></template><style scoped>.foo{}</style>')
        self.assertEqual(parser.is_scoped(), True)

    def test_scope_id_added_to_plain_element(self):
        parser = CustomHTML(scope_id='a1b2c3d4')
        parser.feed('<template><div>text</div></template>')
        self.assertEqual(parser.get_content('template'), '<div data-v-a1b2c3d4>text</div>')

    def test_scope_id_added_to_element_with_attrs(self):
        parser = CustomHTML(scope_id='a1b2c3d4')
        parser.feed('<template><div class="foo">text</div></template>')
        self.assertEqual(parser.get_content('template'), '<div class="foo" data-v-a1b2c3d4>text</div>')

    def test_scope_id_added_to_void_element(self):
        parser = CustomHTML(scope_id='a1b2c3d4')
        parser.feed('<template><input type="text" /></template>')
        self.assertEqual(parser.get_content('template'), '<input type="text" data-v-a1b2c3d4 />')

    def test_scope_id_added_to_bare_void_element(self):
        parser = CustomHTML(scope_id='a1b2c3d4')
        parser.feed('<template><br /></template>')
        self.assertEqual(parser.get_content('template'), '<br data-v-a1b2c3d4 />')

    def test_scope_id_added_to_all_nested_elements(self):
        parser = CustomHTML(scope_id='ab12cd34')
        parser.feed('<template><div><p><span>x</span></p></div></template>')
        self.assertEqual(
            parser.get_content('template'),
            '<div data-v-ab12cd34><p data-v-ab12cd34><span data-v-ab12cd34>x</span></p></div>',
        )

    def test_scope_id_not_injected_without_scope_id(self):
        parser = CustomHTML()
        parser.feed('<template><div class="foo">text</div></template>')
        self.assertEqual(parser.get_content('template'), '<div class="foo">text</div>')

    def test_scope_id_not_injected_in_script(self):
        parser = CustomHTML(scope_id='a1b2c3d4')
        parser.feed('<template></template><script>const x = 1</script>')
        self.assertEqual(parser.get_content('script'), 'const x = 1')

    def test_scope_id_not_injected_in_style(self):
        parser = CustomHTML(scope_id='a1b2c3d4')
        parser.feed('<template></template><style>.foo{color:red}</style>')
        self.assertEqual(parser.get_content('style'), '.foo{color:red}')


class TestCaseSensitiveAttrs(unittest.TestCase):
    def test_svg_viewbox_preserves_case(self):
        parser = CustomHTML()
        parser.feed('<template><svg viewBox="0 0 100 100"><circle r="50" /></svg></template>')
        content = parser.get_content('template')
        self.assertIn('viewBox="0 0 100 100"', content)
        self.assertNotIn('viewbox=', content)

    def test_svg_viewbox_self_closing(self):
        parser = CustomHTML()
        parser.feed('<template><svg viewBox="0 0 24 24" /></template>')
        content = parser.get_content('template')
        self.assertIn('viewBox="0 0 24 24"', content)

    def test_svg_preserve_aspect_ratio(self):
        parser = CustomHTML()
        parser.feed('<template><svg preserveAspectRatio="xMidYMid meet" /></template>')
        content = parser.get_content('template')
        self.assertIn('preserveAspectRatio="xMidYMid meet"', content)
        self.assertNotIn('preserveaspectratio=', content)

    def test_svg_child_gradient_attrs(self):
        parser = CustomHTML()
        parser.feed(
            '<template><svg><linearGradient gradientUnits="userSpaceOnUse"'
            ' gradientTransform="rotate(45)"><stop /></linearGradient></svg></template>'
        )
        content = parser.get_content('template')
        self.assertIn('gradientUnits="userSpaceOnUse"', content)
        self.assertIn('gradientTransform="rotate(45)"', content)

    def test_svg_child_std_deviation(self):
        parser = CustomHTML()
        parser.feed('<template><svg><feGaussianBlur stdDeviation="3" /></svg></template>')
        content = parser.get_content('template')
        self.assertIn('stdDeviation="3"', content)
        self.assertNotIn('stddeviation=', content)

    def test_svg_marker_attrs(self):
        parser = CustomHTML()
        parser.feed(
            '<template><svg><marker markerWidth="10" markerHeight="10"'
            ' refX="5" refY="5"></marker></svg></template>'
        )
        content = parser.get_content('template')
        self.assertIn('markerWidth="10"', content)
        self.assertIn('markerHeight="10"', content)
        self.assertIn('refX="5"', content)
        self.assertIn('refY="5"', content)

    def test_non_svg_element_not_corrected(self):
        # viewbox on a non-svg element should stay lowercase (not a valid attr, but must not be "corrected")
        parser = CustomHTML()
        parser.feed('<template><div viewbox="0 0 100 100"></div></template>')
        content = parser.get_content('template')
        self.assertIn('viewbox="0 0 100 100"', content)
        self.assertNotIn('viewBox=', content)

    def test_correction_applies_to_nested_svg_children(self):
        parser = CustomHTML()
        parser.feed(
            '<template><svg><defs><pattern patternUnits="userSpaceOnUse"'
            ' patternTransform="scale(2)"></pattern></defs></svg></template>'
        )
        content = parser.get_content('template')
        self.assertIn('patternUnits="userSpaceOnUse"', content)
        self.assertIn('patternTransform="scale(2)"', content)

    def test_after_svg_closes_correction_stops(self):
        parser = CustomHTML()
        parser.feed('<template><svg></svg><div viewbox="0 0 10 10"></div></template>')
        content = parser.get_content('template')
        # div after svg must not get correction
        self.assertIn('viewbox="0 0 10 10"', content)
        self.assertNotIn('viewBox=', content)


class TestCustomHTMLNamedSlots(unittest.TestCase):
    def _parse(self, content):
        p = CustomHTML()
        p.feed(content)
        p.validate()
        return p

    def test_named_slot_hash_syntax(self):
        p = self._parse('<template><template #header><h1>Title</h1></template></template>')
        self.assertEqual(p.get_content('template'), '<template #header><h1>Title</h1></template>')

    def test_named_slot_vslot_syntax(self):
        p = self._parse('<template><template v-slot:body><p>body</p></template></template>')
        self.assertEqual(p.get_content('template'), '<template v-slot:body><p>body</p></template>')

    def test_template_v_if(self):
        p = self._parse('<template><template v-if="ok"><span>yes</span></template></template>')
        self.assertEqual(p.get_content('template'), '<template v-if="ok"><span>yes</span></template>')

    def test_template_v_for(self):
        p = self._parse('<template><template v-for="x in xs"><li>{{ x }}</li></template></template>')
        self.assertEqual(
            p.get_content('template'), '<template v-for="x in xs"><li>{{ x }}</li></template>'
        )

    def test_multiple_named_slots(self):
        p = self._parse(
            '<template><template #header>H</template><template #footer>F</template></template>'
        )
        self.assertEqual(
            p.get_content('template'),
            '<template #header>H</template><template #footer>F</template>',
        )

    def test_nested_template_inside_div(self):
        p = self._parse('<template><div><template #slot><span>x</span></template></div></template>')
        self.assertEqual(
            p.get_content('template'), '<div><template #slot><span>x</span></template></div>'
        )

    def test_deeply_nested_templates(self):
        p = self._parse(
            '<template><template #a><template #b><span>deep</span></template></template></template>'
        )
        self.assertEqual(
            p.get_content('template'),
            '<template #a><template #b><span>deep</span></template></template>',
        )

    def test_section_count_still_one(self):
        p = self._parse('<template><template #header>H</template></template>')
        self.assertEqual(p.section_counts['template'], 1)

    def test_closing_tag_in_content(self):
        p = self._parse('<template><template #slot><div>x</div></template></template>')
        self.assertEqual(p.get_content('template'), '<template #slot><div>x</div></template>')


if __name__ == '__main__':
    unittest.main()
