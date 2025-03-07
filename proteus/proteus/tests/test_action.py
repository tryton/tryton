# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

try:
    import pydot
except ImportError:
    pydot = None

from proteus import Model, Wizard, launch_action

from .common import ProteusTestCase


class TestAction(ProteusTestCase):

    def test_act_window(self):
        IrModel = Model.get('ir.model')
        actions = IrModel.find([
                ('name', '=', 'ir.action'),
                ])
        model_access = launch_action(
            'ir.act_model_access_form_relate_model', actions)
        self.assertEqual(
            {m.__class__.__name__ for m in model_access},
            {'ir.model.access'})

    def test_wizard(self):
        IrModel = Model.get('ir.model')
        actions = IrModel.find([
                ('name', '=', 'ir.action'),
                ])
        wizard = launch_action('ir.print_model_graph', actions)
        self.assertIsInstance(wizard, Wizard)
        self.assertEqual(wizard.name, 'ir.model.print_model_graph')

    @unittest.skipIf(not pydot, 'requires pydot')
    def test_report(self):
        IrModel = Model.get('ir.model')
        actions = IrModel.find([
                ('name', '=', 'ir.action'),
                ])
        ftype, data, direct_print, report_name = launch_action(
            'ir.report_model_workflow_graph', actions)
        self.assertIsInstance(ftype, str)
        self.assertIsInstance(data, bytes)
        self.assertIsInstance(direct_print, bool)
        self.assertIsInstance(report_name, str)
