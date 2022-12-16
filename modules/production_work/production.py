# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from sql.aggregate import Sum

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.product import round_price


class Production(metaclass=PoolMeta):
    __name__ = 'production'
    work_center = fields.Many2One('production.work.center', 'Work Center',
        states={
            'required': (Bool(Eval('routing'))
                & (Eval('state') != 'request')),
            'invisible': ~Eval('routing'),
            'readonly': ~Eval('state').in_(['request', 'draft']),
            },
        domain=[
            ('company', '=', Eval('company', -1)),
            ('warehouse', '=', Eval('warehouse', -1)),
            ],
        depends=['routing', 'company', 'warehouse', 'state'])
    works = fields.One2Many('production.work', 'production', 'Works',
        states={
            'readonly': Eval('state').in_(
                ['request', 'draft', 'done', 'cancelled']),
            },
        domain=[
            ('company', '=', Eval('company', -1)),
            ],
        depends=['state', 'company'])

    def get_cost(self, name):
        pool = Pool()
        Work = pool.get('production.work')
        Cycle = pool.get('production.work.cycle')
        table = self.__table__()
        work = Work.__table__()
        cycle = Cycle.__table__()
        cursor = Transaction().connection.cursor()

        cost = super(Production, self).get_cost(name)

        cursor.execute(*table.join(work, 'LEFT',
                condition=work.production == table.id
                ).join(cycle, 'LEFT', condition=cycle.work == work.id
                ).select(Sum(cycle.cost),
                where=(cycle.state == 'done')
                & (table.id == self.id)))
        cycle_cost, = cursor.fetchone()
        if cycle_cost is not None:
            # SQLite uses float for SUM
            if not isinstance(cycle_cost, Decimal):
                cycle_cost = Decimal(cycle_cost)
            cost += cycle_cost

        return round_price(cost)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, productions):
        pool = Pool()
        Work = pool.get('production.work')
        super(Production, cls).draft(productions)
        Work.delete([w for p in productions for w in p.works
                if w.state in ['request', 'draft']])

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, productions):
        pool = Pool()
        Work = pool.get('production.work')
        super(Production, cls).cancel(productions)
        Work.delete([w for p in productions for w in p.works
                if w.state in ['request', 'draft']])

    @classmethod
    @ModelView.button
    @Workflow.transition('waiting')
    def wait(cls, productions):
        pool = Pool()
        Work = pool.get('production.work')
        WorkCenter = pool.get('production.work.center')

        draft_productions = [p for p in productions if p.state == 'draft']

        super(Production, cls).wait(productions)

        work_center_picker = WorkCenter.get_picker()
        works = []
        for production in draft_productions:
            works.extend(production.get_works(work_center_picker))
        Work.save(works)

    def get_works(self, work_center_picker):
        if not self.routing:
            return []
        return [step.get_work(self, work_center_picker)
            for step in self.routing.steps]

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def run(cls, productions):
        pool = Pool()
        Work = pool.get('production.work')

        super(Production, cls).run(productions)

        Work.set_state([w for p in productions for w in p.works])

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, productions):
        pool = Pool()
        Work = pool.get('production.work')
        for production in productions:
            for work in production.works:
                if work.state != 'finished':
                    raise AccessError(
                        gettext('production_work.msg_do_finished_work',
                            production=production.rec_name,
                            work=work.rec_name))
        super(Production, cls).done(productions)
        Work.set_state([w for p in productions for w in p.works])

    @classmethod
    def copy(cls, productions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('works')
        return super().copy(productions, default=default)
