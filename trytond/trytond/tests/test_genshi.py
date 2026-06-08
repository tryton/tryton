# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from genshi.template import MarkupTemplate, TextTemplate
from genshi.template.eval import UndefinedError


class GenshiTestCase(unittest.TestCase):

    def test_no_builtins(self):
        "Test no builtins"
        with self.assertRaises(UndefinedError):
            str(TextTemplate("${open('%s').read()}" % __file__).generate())

    def test_no_private_name(self):
        "Test no private name"
        with self.assertRaisesRegex(ValueError, r"invalid name '__import__'"):
            str(TextTemplate("${__import__('os')}").generate())

    def test_no_private_attribute(self):
        "Test no private attribute"
        with self.assertRaisesRegex(
                ValueError, r"invalid attribute '__getattribute__'"):
            str(TextTemplate("${True.__getattribute__}").generate())

    def test_no_import(self):
        "Test no import"
        with self.assertRaisesRegex(ValueError, r"invalid import"):
            str(MarkupTemplate("<?python import os?>").generate())

    def test_no_import_from(self):
        "Test no import from"
        with self.assertRaisesRegex(ValueError, r"invalid import from"):
            str(MarkupTemplate("<?python from os import popen?>").generate())
