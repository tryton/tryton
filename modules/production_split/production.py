# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.wizard import Button, StateTransition, StateView, Wizard


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'split_wizard': {
                    'invisible': (~Eval('state').in_(['request', 'draft'])
                        | ~Eval('bom') | ~Eval('quantity', 0)),
                    'depends': ['state', 'bom', 'quantity'],
                    },
                })

    @classmethod
    @ModelView.button_action('production_split.wizard_split_production')
    def split_wizard(cls, productions):
        pass

    def split(self, quantity, unit, count=None):
        """
        Split production into productions of quantity.
        If count is not defined, the production will be split until remainder
        is less than quantity.
        Return the split productions
        """
        pool = Pool()
        Uom = pool.get('product.uom')

        productions = [self]
        remainder = Uom.compute_qty(self.unit, self.quantity, unit)
        if remainder <= quantity:
            return productions
        self.quantity = quantity
        self.unit = unit
        self.save()
        remainder -= quantity
        if count:
            count -= 1
        while (remainder > quantity
                and (count or count is None)):
            productions.extend(self.copy([self], {
                        'quantity': quantity,
                        'unit': unit.id,
                        'inputs': None,
                        'outputs': None,
                        }))
            remainder -= quantity
            remainder = unit.round(remainder)
            if count:
                count -= 1
        assert remainder >= 0
        if remainder:
            productions.extend(self.copy([self], {
                        'quantity': remainder,
                        'unit': unit.id,
                        }))
        for production in productions:
            production.explode_bom()
        self.__class__.save(productions)
        return productions


class SplitProduction(Wizard):
    __name__ = 'production.split'
    start = StateView('production.split.start',
        'production_split.split_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Split', 'split', 'tryton-ok', default=True),
            ])
    split = StateTransition()

    def default_start(self, fields):
        return {
            'unit': self.record.unit.id,
            'uom_category': self.record.unit.category.id,
            }

    def transition_split(self):
        self.record.split(
            self.start.quantity, self.start.unit, count=self.start.count)
        return 'end'


class SplitProductionStart(ModelView):
    __name__ = 'production.split.start'
    count = fields.Integer('Count', help='The limit number of productions')
    quantity = fields.Float("Quantity", digits='unit', required=True)
    unit = fields.Many2One(
        'product.uom', "Unit", required=True,
        domain=[
            ('category', '=', Eval('uom_category', -1)),
            ])
    uom_category = fields.Many2One(
        'product.uom.category', "UoM Category", readonly=True,
        help="The category of Unit of Measure.")
