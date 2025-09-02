# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelView
from trytond.pool import PoolMeta

from .quality import ControlledMixin


class Production(ControlledMixin, metaclass=PoolMeta):
    __name__ = 'production'

    def quality_control_pattern(self, operation):
        pattern = super().quality_control_pattern(operation)
        pattern['company'] = self.company.id
        if operation == 'run':
            pattern['products'] = {m.product.id for m in self.inputs}
        elif operation == 'do':
            pattern['products'] = {m.product.id for m in self.outputs}
        return pattern

    @classmethod
    @ModelView.button
    @ControlledMixin.control('run', 'quality.wizard_production_inspect_run')
    def run(cls, productions):
        return super().run(productions)

    @classmethod
    @ModelView.button
    @ControlledMixin.control('do', 'quality.wizard_production_inspect_do')
    def do(cls, productions):
        return super().do(productions)
