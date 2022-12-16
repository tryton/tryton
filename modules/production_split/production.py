# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button

__all__ = ['Production', 'SplitProduction', 'SplitProductionStart']


class Production:
    __metaclass__ = PoolMeta
    __name__ = 'production'

    @classmethod
    def __setup__(cls):
        super(Production, cls).__setup__()
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

    def split(self, quantity, uom, count=None):
        """
        Split production into productions of quantity.
        If count is not defined, the production will be split until remainder
        is less than quantity.
        Return the split productions
        """
        pool = Pool()
        Uom = pool.get('product.uom')

        productions = [self]
        remainder = Uom.compute_qty(self.uom, self.quantity, uom)
        if remainder <= quantity:
            return productions
        self.quantity = quantity
        self.uom = uom
        self.save()
        remainder -= quantity
        if count:
            count -= 1
        while (remainder > quantity
                and (count or count is None)):
            productions.extend(self.copy([self], {
                        'quantity': quantity,
                        'uom': uom.id,
                        'inputs': None,
                        'outputs': None,
                        }))
            remainder -= quantity
            remainder = uom.round(remainder)
            if count:
                count -= 1
        assert remainder >= 0
        if remainder:
            productions.extend(self.copy([self], {
                        'quantity': remainder,
                        'uom': uom.id,
                        }))
        for production in productions:
            production.explode_bom()
        self.__class__.save(productions)
        return productions


class SplitProduction(Wizard):
    'Split Production'
    __name__ = 'production.split'
    start = StateView('production.split.start',
        'production_split.split_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Split', 'split', 'tryton-ok', default=True),
            ])
    split = StateTransition()

    def default_start(self, fields):
        pool = Pool()
        Production = pool.get('production')
        default = {}
        production = Production(Transaction().context['active_id'])
        default['uom'] = production.uom.id
        default['unit_digits'] = production.unit_digits
        default['uom_category'] = production.uom.category.id
        return default

    def transition_split(self):
        pool = Pool()
        Production = pool.get('production')
        production = Production(Transaction().context['active_id'])
        production.split(
            self.start.quantity, self.start.uom, count=self.start.count)
        return 'end'


class SplitProductionStart(ModelView):
    'Split Production'
    __name__ = 'production.split.start'
    count = fields.Integer('Count', help='The limit number of productions')
    quantity = fields.Float('Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])
    uom = fields.Many2One('product.uom', 'Uom', required=True,
        domain=[
            ('category', '=', Eval('uom_category')),
            ],
        depends=['uom_category'])
    unit_digits = fields.Integer('Unit Digits', readonly=True)
    uom_category = fields.Many2One('product.uom.category', 'Uom Category',
        readonly=True)

    @fields.depends('uom')
    def on_change_with_unit_digits(self):
        if self.uom:
            return self.uom.digits
        return 2
