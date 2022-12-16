# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import random
from decimal import Decimal
from functools import wraps

from trytond.i18n import gettext
from trytond.model import (
    ModelSQL, ModelView, Workflow, DeactivableMixin, fields, sequence_ordered,
    tree)
from trytond.model.exceptions import AccessError
from trytond.pool import Pool
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction

from trytond.modules.product import price_digits, round_price
from .exceptions import PickerError


class WorkCenterCategory(ModelSQL, ModelView):
    'Work Center Category'
    __name__ = 'production.work.center.category'
    name = fields.Char('Name', required=True, translate=True)


class WorkCenter(DeactivableMixin, tree(separator=' / '), ModelSQL, ModelView):
    'Work Center'
    __name__ = 'production.work.center'
    name = fields.Char('Name', required=True, translate=True)
    parent = fields.Many2One('production.work.center', 'Parent', select=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('warehouse', '=', Eval('warehouse', -1)),
            ],
        depends=['company', 'warehouse'])
    children = fields.One2Many('production.work.center', 'parent', 'Children',
        domain=[
            ('company', '=', Eval('company', -1)),
            ('warehouse', '=', Eval('warehouse', -1)),
            ],
        depends=['company', 'warehouse'])
    category = fields.Many2One('production.work.center.category', 'Category')
    cost_price = fields.Numeric('Cost Price', digits=price_digits,
        states={
            'required': Bool(Eval('cost_method')),
            },
        depends=['cost_method'])
    cost_method = fields.Selection([
            ('', ''),
            ('cycle', 'Per Cycle'),
            ('hour', 'Per Hour'),
            ], 'Cost Method',
        states={
            'required': Bool(Eval('cost_price')),
            },
        depends=['cost_price'])
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
    warehouse = fields.Many2One('stock.location', 'Warehouse', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ])

    @classmethod
    def __setup__(cls):
        super(WorkCenter, cls).__setup__()
        cls._order.insert(0, ('name', 'ASC'))

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @classmethod
    def default_warehouse(cls):
        Location = Pool().get('stock.location')
        return Location.get_default_warehouse()

    @classmethod
    def get_picker(cls):
        """Return a method that picks a work center
        for the category and the parent"""
        cache = {}

        def picker(parent, category):
            key = (parent, category)
            if key not in cache:
                work_centers = cls.search([
                        ('parent', 'child_of', [parent.id]),
                        ('category', '=', category.id),
                        ])
                if not work_centers:
                    raise PickerError(
                        gettext('production_work.msg_missing_work_center',
                            category=category.rec_name,
                            parent=parent.rec_name))
                cache[key] = work_centers
            return random.choice(cache[key])
        return picker


class Work(sequence_ordered(), ModelSQL, ModelView):
    'Production Work'
    __name__ = 'production.work'
    operation = fields.Many2One('production.routing.operation', 'Operation',
        required=True)
    production = fields.Many2One('production', 'Production', required=True,
        select=True, ondelete='CASCADE',
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    work_center_category = fields.Function(fields.Many2One(
            'production.work.center.category', 'Work Center Category'),
        'on_change_with_work_center_category')
    work_center = fields.Many2One('production.work.center', 'Work Center',
        domain=[
            If(~Eval('work_center_category'),
                (),
                ('category', '=', Eval('work_center_category'))),
            ('company', '=', Eval('company', -1)),
            ('warehouse', '=', Eval('warehouse', -1)),
            ],
        states={
            'required': ~Eval('state').in_(['request', 'draft']),
            },
        depends=['work_center_category', 'company', 'warehouse', 'state'])
    cycles = fields.One2Many('production.work.cycle', 'work', 'Cycles',
        states={
            'readonly': Eval('state').in_(['request', 'done']),
            },
        depends=['state'])
    active_cycles = fields.One2Many(
        'production.work.cycle', 'work', "Active Cycles",
        readonly=True,
        filter=[
            ('state', '=', 'running'),
            ])
    company = fields.Many2One('company.company', 'Company', required=True,
        select=True)
    warehouse = fields.Function(fields.Many2One('stock.location', 'Warehouse'),
        'on_change_with_warehouse')
    state = fields.Selection([
            ('request', 'Request'),
            ('draft', 'Draft'),
            ('waiting', 'Waiting'),
            ('running', 'Running'),
            ('finished', 'Finished'),
            ('done', 'Done'),
            ], 'State', select=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'start': {
                    'invisible': Bool(Eval('active_cycles', [])),
                    'readonly': Eval('state').in_(['request', 'done']),
                    'depends': ['active_cycles'],
                    },
                'stop': {
                    'invisible': ~Bool(Eval('active_cycles', [])),
                    'depends': ['active_cycles'],
                    },
                })

    @classmethod
    def __register__(cls, module_name):

        super().__register__(module_name)
        table = cls.__table_handler__(module_name)

        # Migration from 5.4: Drop not null on work_center
        table.not_null_action('work_center', 'remove')

    @fields.depends('operation')
    def on_change_with_work_center_category(self, name=None):
        if self.operation and self.operation.work_center_category:
            return self.operation.work_center_category.id

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')

    @fields.depends('production', '_parent_production.warehouse')
    def on_change_with_warehouse(self, name=None):
        if self.production:
            return self.production.warehouse.id

    @classmethod
    def default_state(cls):
        return 'request'

    @classmethod
    @ModelView.button
    def start(cls, works):
        pool = Pool()
        Cycle = pool.get('production.work.cycle')
        cycles = [Cycle(work=w) for w in works]
        Cycle.save(cycles)
        Cycle.run(cycles)

    @classmethod
    @ModelView.button
    def stop(cls, works):
        pool = Pool()
        Cycle = pool.get('production.work.cycle')

        to_do = []
        for work in works:
            for cycle in work.active_cycles:
                to_do.append(cycle)
        Cycle.do(to_do)

    @property
    def _state(self):
        if self.production.state == 'waiting':
            return 'request'
        elif self.production.state == 'done':
            return 'done'
        elif (not self.cycles
                or all(c.state == 'cancelled' for c in self.cycles)):
            return 'draft'
        elif all(c.state in ['done', 'cancelled'] for c in self.cycles):
            return 'finished'
        elif any(c.state == 'running' for c in self.cycles):
            return 'running'
        else:
            return 'waiting'

    @classmethod
    def set_state(cls, works):
        for work in works:
            work.state = work._state
        cls.save(works)

    def get_rec_name(self, name):
        return '%s @ %s' % (self.operation.rec_name, self.production.rec_name)

    @classmethod
    def search_rec_name(cls, name, clause):
        if clause[1].startswith('!') or clause[1].startswith('not '):
            bool_op = 'AND'
        else:
            bool_op = 'OR'
        return [bool_op,
            ('operation.rec_name',) + tuple(clause[1:]),
            ('production.rec_name',) + tuple(clause[1:]),
            ]

    @classmethod
    def create(cls, values):
        works = super(Work, cls).create(values)
        cls.set_state(works)
        return works

    @classmethod
    def delete(cls, works):
        for work in works:
            if work.state not in {'request', 'draft'}:
                raise AccessError(
                    gettext('production_work.msg_delete_request',
                        work=work.rec_name))
        super(Work, cls).delete(works)


def set_work_state(func):
    @wraps(func)
    def wrapper(cls, cycles):
        pool = Pool()
        Work = pool.get('production.work')
        func(cls, cycles)
        Work.set_state(Work.browse({c.work.id for c in cycles}))
    return wrapper


class WorkCycle(Workflow, ModelSQL, ModelView):
    'Work Cycle'
    __name__ = 'production.work.cycle'
    work = fields.Many2One('production.work', 'Work', required=True,
        ondelete='CASCADE', select=True)
    duration = fields.TimeDelta('Duration',
        states={
            'required': Eval('state') == 'done',
            'readonly': Eval('state').in_(['done', 'draft', 'cancelled']),
            },
        depends=['state'])
    cost = fields.Numeric('Cost', digits=price_digits, readonly=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
            ], 'State', required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(WorkCycle, cls).__setup__()
        cls._transitions |= set((
                ('draft', 'running'),
                ('running', 'done'),
                ('draft', 'cancelled'),
                ('running', 'cancelled'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state').in_(['done', 'cancelled']),
                    'depends': ['state'],
                    },
                'run': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                'do': {
                    'invisible': Eval('state') != 'running',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    @ModelView.button
    @set_work_state
    @Workflow.transition('cancelled')
    def cancel(cls, cycles):
        pass

    @classmethod
    @ModelView.button
    @set_work_state
    @Workflow.transition('running')
    def run(cls, cycles):
        pass

    @classmethod
    @ModelView.button
    @set_work_state
    @Workflow.transition('done')
    def do(cls, cycles):
        now = datetime.datetime.now()
        for cycle in cycles:
            cycle.set_duration(now)
            cycle.set_cost()
        cls.save(cycles)

    def set_duration(self, now):
        if self.duration is None:
            self.duration = now - self.write_date

    def set_cost(self):
        if self.cost is None:
            center = self.work.work_center
            if center.cost_method == 'cycle':
                self.cost = center.cost_price
            elif center.cost_method == 'hour':
                hours = self.duration.total_seconds() / (60 * 60)
                self.cost = center.cost_price * Decimal(str(hours))
                self.cost = round_price(self.cost)
