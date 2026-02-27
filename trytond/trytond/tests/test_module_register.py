# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.

import io
import os.path
import pathlib
import tempfile
from unittest.mock import patch

from trytond.modules import (
    get_module_info, get_module_register, get_module_register_mixin)
from trytond.tests.test_tryton import TestCase

FLAT_MODULE_CFG = """
[tryton]
depends:
    flat_a
    flat_b
extras_depend:
    flat_extra1
    flat_extra2
xml:
    flat_file1.xml
    flat_file2.xml
test_include_dirs:
    tests
[register]
model:
    flat_model.Model
"""

TEST_MODULE_CFG = """
[tryton]
xml:
    test_file.xml
[register]
model:
    test_model.TestModel
"""

NESTED_MODULE_CFG = """
[tryton]
depends:
    root_a
    root_b
xml:
    root_file1.xml
include_dirs:
    sub1
    sub2

[register]
model:
    root_model.A
wizard:
    root_wizard.wiz_A

[register_mixin]
test.TestMixin: path.to.nested.mixin
"""

NESTED_MODULE_SUB1_CFG = """
[tryton]
depends:
    nested_s1_1
    nested_s1_2
xml:
    nested_file_s1.xml
"""

NESTED_MODULE_SUB2_CFG = """
[tryton]
xml:
    nested_file_s2.xml
include_dirs:
    sub

[register]
report:
    nested_report.report_sub2

[register_mixin]
test.TestMixin: path.to.sub2.mixin
"""

NESTED_MODULE_SUB2SUB_CFG = """
[tryton]
xml:
    nested_file_s2_s.xml

[register depend_s2s]
model:
    nested_model.s2s_A
"""


class ModuleRegisterTestCase(TestCase):
    "Test module registration"

    @classmethod
    def setUpClass(cls):
        cls.tmp_modules = tempfile.TemporaryDirectory()

        modules = pathlib.Path(cls.tmp_modules.name)
        flat = modules / 'flat'
        tests = flat / 'tests'
        nested = modules / 'nested'
        nested_sub1 = nested / 'sub1'
        nested_sub2 = nested / 'sub2'
        nested_sub2sub = nested_sub2 / 'sub'

        for path, config in [
                (flat, FLAT_MODULE_CFG),
                (tests, TEST_MODULE_CFG),
                (nested, NESTED_MODULE_CFG),
                (nested_sub1, NESTED_MODULE_SUB1_CFG),
                (nested_sub2, NESTED_MODULE_SUB2_CFG),
                (nested_sub2sub, NESTED_MODULE_SUB2SUB_CFG),
                ]:
            path.mkdir(parents=True)
            with open(path / 'tryton.cfg', 'w') as f:
                f.write(config)

        cls.file_open = patch('trytond.tools.file_open')
        file_open = cls.file_open.start()
        file_open.side_effect = lambda name: io.open(modules / name, 'r')

    @classmethod
    def tearDownClass(cls):
        cls.tmp_modules.cleanup()
        cls.file_open.stop()

    def test_module_info_flat(self):
        "Test fetching tryton.cfg information from a flat module"
        mod_info = get_module_info('flat')

        self.assertEqual(mod_info['depends'], ['flat_a', 'flat_b'])
        self.assertEqual(
            mod_info['extras_depend'], ['flat_extra1', 'flat_extra2'])
        self.assertEqual(
            mod_info['xml'], ['flat_file1.xml', 'flat_file2.xml'])

    def test_module_info_with_test(self):
        "Test fetching tryton.cfg information when in a testing context"
        mod_info = get_module_info('flat', with_test=True)

        self.assertEqual(
            mod_info['xml'],
            ['flat_file1.xml', 'flat_file2.xml',
                os.path.join('tests', 'test_file.xml')])

    def test_module_info_nested(self):
        "Test fetching tryton.cfg information from a nested module"
        mod_info = get_module_info('nested')

        self.assertEqual(
            mod_info['xml'],
            ['root_file1.xml',
                os.path.join('sub1', 'nested_file_s1.xml'),
                os.path.join('sub2', 'nested_file_s2.xml'),
                os.path.join('sub2', 'sub', 'nested_file_s2_s.xml'),
                ])

    def test_module_register(self):
        "Test module registration"
        self.assertEqual(
            list(get_module_register('flat')),
            [
                (['flat_model.Model'],
                    {'module': 'flat', 'type_': 'model', 'depends': []}),
                ])

        for registration, expected in zip(
                get_module_register('nested'),
                [
                    (['root_model.A'],
                        {'module': 'nested', 'type_': 'model', 'depends': []}),
                    (['root_wizard.wiz_A'],
                        {
                            'module': 'nested',
                            'type_': 'wizard',
                            'depends': [],
                            }),
                    (['sub2.nested_report.report_sub2'],
                        {
                            'module': 'nested',
                            'type_': 'report',
                            'depends': [],
                            }),
                    (['sub2.sub.nested_model.s2s_A'],
                        {
                            'module': 'nested',
                            'type_': 'model',
                            'depends': ['depend_s2s'],
                            }),
                    ]):
            with self.subTest(value=expected[0]):
                self.assertEqual(registration, expected)

    def test_module_register_mixin(self):
        "Test module registration of mixins"
        for registration, expected in zip(
                get_module_register_mixin('nested'),
                [
                    (['test.TestMixin', 'path.to.nested.mixin'],
                        {'module': 'nested'}),
                    (['test.TestMixin', 'path.to.sub2.mixin'],
                        {'module': 'nested'}),
                    ]):
            with self.subTest(value=expected[0]):
                self.assertEqual(registration, expected)

    def test_module_register_with_tests(self):
        "Test module registration in a testing context"
        self.assertEqual(
            list(get_module_register('flat', with_test=True)),
            [
                (['flat_model.Model'],
                    {'module': 'flat', 'type_': 'model', 'depends': []}),
                (['tests.test_model.TestModel'],
                    {'module': 'flat', 'type_': 'model', 'depends': []}),
                ])
