# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model import ModelView, Workflow, fields
from trytond.model.exceptions import AccessError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval


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
            ])
    works = fields.One2Many('production.work', 'production', 'Works',
        states={
            'readonly': Eval('state').in_(
                ['request', 'draft', 'done', 'cancelled']),
            },
        domain=[
            ('company', '=', Eval('company', -1)),
            ])

    def get_cost(self, name):
        cost = super().get_cost(name)
        for work in self.works:
            cost += work.cost
        return cost

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, productions):
        pool = Pool()
        Work = pool.get('production.work')
        super().draft(productions)
        Work.delete([w for p in productions for w in p.works
                if w.state in ['request', 'draft']])

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, productions):
        pool = Pool()
        Work = pool.get('production.work')
        super().cancel(productions)
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

        super().wait(productions)

        work_center_picker = WorkCenter.get_picker()
        works = []
        for production in draft_productions:
            works.extend(production.get_works(work_center_picker))
        Work.save(works)
        Work.set_state([w for p in productions for w in p.works])

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

        super().run(productions)

        Work.set_state([w for p in productions for w in p.works])

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, productions):
        pool = Pool()
        Work = pool.get('production.work')
        for production in productions:
            for work in production.works:
                if work.state != 'finished':
                    raise AccessError(
                        gettext('production_work.msg_do_finished_work',
                            production=production.rec_name,
                            work=work.rec_name))
        super().do(productions)
        Work.set_state([w for p in productions for w in p.works])

    @classmethod
    def copy(cls, productions, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('works')
        return super().copy(productions, default=default)
