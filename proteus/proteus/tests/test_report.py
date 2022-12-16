# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
try:
    import pydot
except ImportError:
    pydot = None

from proteus import Report, Model
from .common import ProteusTestCase


class TestReport(ProteusTestCase):

    @unittest.skipIf(not pydot, 'requires pydot')
    def test_model_graph(self):
        IrModel = Model.get('ir.model')
        models = IrModel.find([])
        data = {
            'level': 1,
            'filter': '',
            }
        report = Report('ir.model.graph')
        type_, data, print_, name = report.execute(models, data)
        self.assertEqual(type_, 'png')
        self.assertEqual(print_, False)
        self.assertEqual(name, 'Graph')
