#!/usr/bin/env python3

"""
Unit and integration tests for tools/generate_source.py.

Run with:
    python3 -m unittest discover -s tools/tests -v
"""

import ast
import pathlib
import sys
import tempfile
import unittest

this_dir = pathlib.Path(__file__).parent
tools_dir = this_dir.parent
sys.path.insert(0, str(tools_dir))

import generate_source as gs  # noqa: E402


###############################################################################
class TestParseFormula(unittest.TestCase):
###############################################################################

    def setUp(self):
        self.known = {'a', 'b', 'c'}

    def test_simple_arithmetic_is_accepted(self):
        for formula in ['a + b', 'a - b', 'a * b', 'a / b', '(a + b) / c',
                         '-a', '+a', '2 * a', 'a ** 2']:
            with self.subTest(formula=formula):
                tree, deps, _ = gs.parse_formula('result', formula, self.known)
                self.assertIsInstance(tree, ast.Expression)

    def test_dependencies_are_collected(self):
        _, deps, _ = gs.parse_formula('result', 'a * b + c', self.known)
        self.assertEqual(deps, {'a', 'b', 'c'})

    def test_pow_flag(self):
        _, _, has_pow = gs.parse_formula('result', 'a + b', self.known)
        self.assertFalse(has_pow)
        _, _, has_pow = gs.parse_formula('result', 'a ** b', self.known)
        self.assertTrue(has_pow)

    def test_unknown_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown constant 'z'"):
            gs.parse_formula('result', 'a + z', self.known)

    def test_self_reference_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cannot reference itself'):
            gs.parse_formula('a', 'a + b', self.known)

    def test_syntax_error_is_rejected(self):
        with self.assertRaises(ValueError):
            gs.parse_formula('result', 'a +* b', self.known)

    def test_function_calls_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsupported syntax'):
            gs.parse_formula('result', "__import__('os').system('ls')", self.known)

    def test_boolean_and_comparison_ops_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unsupported syntax'):
            gs.parse_formula('result', 'a and b', self.known)
        with self.assertRaisesRegex(ValueError, 'unsupported syntax'):
            gs.parse_formula('result', 'a < b', self.known)

    def test_string_literal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'non-numeric literal'):
            gs.parse_formula('result', "'x' + a", self.known)


###############################################################################
class TestEmitExpr(unittest.TestCase):
###############################################################################

    def _emit(self, formula, lang, known=None):
        tree, _, _ = gs.parse_formula('result', formula, known or {'a', 'b'})
        return gs.emit_expr(tree, lang)

    def test_cxx_arithmetic(self):
        self.assertEqual(self._emit('a * b', 'cxx'), '(a * b)')
        self.assertEqual(self._emit('a + 2 * b', 'cxx'), '(a + (2.0 * b))')

    def test_f90_arithmetic_uses_dp_suffix(self):
        self.assertEqual(self._emit('a + 2 * b', 'f90'), '(a + (2.0_dp * b))')

    def test_pow_translation(self):
        self.assertEqual(self._emit('a ** b', 'cxx'), 'std::pow(a, b)')
        self.assertEqual(self._emit('a ** b', 'f90'), '(a**b)')

    def test_unary_minus(self):
        self.assertEqual(self._emit('-a', 'cxx'), '(-a)')


###############################################################################
class TestWrapF90Code(unittest.TestCase):
###############################################################################

    def test_short_code_is_not_wrapped(self):
        code = 'real(dp), parameter :: pi = 3.14_dp'
        self.assertEqual(gs.wrap_f90_code(code), ['    ' + code])

    def test_long_code_is_wrapped_under_free_form_limit(self):
        # A long formula, similar to the real dry_air_density_at_standard_
        # temperature_and_pressure / sea_ice_thermal_diffusivity_reference
        # entries that originally broke CI: their declaration alone (before
        # any trailing comment) exceeds Fortran's 132-column free-form
        # limit, and gfortran errors on that under -Wall -Werror (and
        # silently truncates -- corrupting the formula -- without it).
        code = ('real(dp), parameter :: dry_air_density_at_standard_temperature_and_pressure = '
                '(standard_atmosphere / (dry_air_specific_gas_constant_reference * '
                'pure_water_freezing_temperature_reference))')
        lines = gs.wrap_f90_code(code)
        self.assertGreater(len(lines), 1)
        for line in lines[:-1]:
            self.assertTrue(line.rstrip().endswith('&') is False)  # '&' added by the writer, not here
        for line in lines:
            self.assertLessEqual(len(line), gs._F90_MAX_LINE + 20)

    def test_wrapping_preserves_the_logical_statement(self):
        code = ('real(dp), parameter :: dry_air_density_at_standard_temperature_and_pressure = '
                '(standard_atmosphere / (dry_air_specific_gas_constant_reference * '
                'pure_water_freezing_temperature_reference))')
        lines = gs.wrap_f90_code(code)
        # Stripping the continuation marker/indentation and rejoining every
        # physical line must reconstruct the original logical statement,
        # i.e. the split never lands inside a token.
        rejoined = ' '.join(line.lstrip().lstrip('&') for line in lines)
        self.assertEqual(rejoined.split(), code.split())


###############################################################################
class TestTopologicalOrder(unittest.TestCase):
###############################################################################

    def test_preserves_order_when_no_reordering_needed(self):
        items = [{'name': 'a', 'deps': set()},
                 {'name': 'b', 'deps': {'a'}},
                 {'name': 'c', 'deps': {'a', 'b'}}]
        ordered = [it['name'] for it in gs.topological_order(items)]
        self.assertEqual(ordered, ['a', 'b', 'c'])

    def test_reorders_dependencies_before_dependents(self):
        # 'c' is listed FIRST even though it depends on 'a' and 'b', which
        # are listed after it -- this is exactly the situation the generator
        # must handle so that a derived constant's formula only ever
        # references already-declared constants.
        items = [{'name': 'c', 'deps': {'a', 'b'}},
                 {'name': 'a', 'deps': set()},
                 {'name': 'b', 'deps': set()}]
        ordered = [it['name'] for it in gs.topological_order(items)]
        self.assertLess(ordered.index('a'), ordered.index('c'))
        self.assertLess(ordered.index('b'), ordered.index('c'))

    def test_circular_dependency_is_detected(self):
        items = [{'name': 'a', 'deps': {'b'}},
                 {'name': 'b', 'deps': {'a'}}]
        with self.assertRaisesRegex(ValueError, 'Circular dependency'):
            gs.topological_order(items)


###############################################################################
class TestGenerateFileIntegration(unittest.TestCase):
###############################################################################
    """
    End-to-end tests that run against the real pcd.yaml.
    """

    def test_cxx_generation_orders_derived_constants_after_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / 'pcd_const.h'
            gs.generate_file('cxx', None, str(out))
            text = out.read_text(encoding='utf-8')

        def line_index(name):
            marker = f'double {name} ='
            for i, line in enumerate(text.splitlines()):
                if marker in line:
                    return i
            self.fail(f"constant '{name}' not found in generated file")

        self.assertLess(line_index('avogadro_constant'), line_index('molar_gas_constant'))
        self.assertLess(line_index('boltzmann_constant'), line_index('molar_gas_constant'))
        self.assertIn('molar_gas_constant = (avogadro_constant * boltzmann_constant);', text)

    def test_f90_generation_orders_derived_constants_after_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / 'pcd_const.F90'
            gs.generate_file('f90', None, str(out))
            text = out.read_text(encoding='utf-8')

        def line_index(name):
            marker = f':: {name} ='
            for i, line in enumerate(text.splitlines()):
                if marker in line:
                    return i
            self.fail(f"constant '{name}' not found in generated file")

        self.assertLess(line_index('avogadro_constant'), line_index('molar_gas_constant'))
        self.assertLess(line_index('boltzmann_constant'), line_index('molar_gas_constant'))

    def test_f90_output_stays_within_fortran_line_length_limit(self):
        # Regression test: a real derived-constant formula (e.g.
        # dry_air_density_at_standard_temperature_and_pressure) previously
        # produced a declaration longer than Fortran's 132-column free-form
        # line limit, which gfortran rejects under -Wall -Werror (see CI
        # failure on PR #21).
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / 'pcd_const.F90'
            gs.generate_file('f90', None, str(out))
            text = out.read_text(encoding='utf-8')

        for line in text.splitlines():
            self.assertLessEqual(len(line), 132,
                                 f"line exceeds Fortran's free-form limit: {line!r}")

    def test_groups_filter_rejects_missing_cross_group_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / 'pcd_const.h'
            with self.assertRaisesRegex(ValueError, "not included in the selected groups"):
                gs.generate_file('cxx', ['earth_atmosphere'], str(out))

    def test_every_constant_defines_exactly_one_of_value_or_formula(self):
        _, _, _, all_items, _ = gs.load_constants(None)
        self.assertGreater(len(all_items), 0)
        for it in all_items:
            has_value = 'value' in it['entry']
            has_formula = 'formula' in it['entry']
            self.assertNotEqual(has_value, has_formula,
                                f"Constant '{it['name']}' must define exactly one "
                                "of 'value' or 'formula'.")


if __name__ == '__main__':
    unittest.main()
