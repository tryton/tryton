# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelView, fields, sequence_ordered, tree
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval, If


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    taskable = fields.Boolean(
        "Taskable",
        states={
            'invisible': (
                ~Eval('salable', False)
                | (Eval('type') != 'service')),
            },
        help="Create tasks on sale.")
    tasks = fields.One2Many(
        'product.project_task', 'template', "Tasks",
        states={
            'invisible': (
                ~Eval('taskable', False)
                | (Eval('type') != 'service')),
            },
        filter=[
            ('product', '=', None),
            ])


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    tasks = fields.One2Many(
        'product.project_task', 'product', "Tasks",
        states={
            'invisible': (
                ~Eval('taskable', False)
                | (Eval('type') != 'service')),
            })

    @property
    def tasks_used(self):
        yield from self.tasks
        yield from self.template.tasks


class ProjectTask(sequence_ordered(), tree(), ModelSQL, ModelView):
    __name__ = 'product.project_task'

    template = fields.Many2One(
        'product.template', "Template", ondelete='CASCADE',
        domain=[
            ('type', '=', 'service'),
            If(Bool(Eval('product')),
                ('products', '=', Eval('product', -1)),
                ()),
            If(Eval('parent'),
                ('id', '=', None),
                ()),
            ],
        states={
            'required': ~Eval('parent'),
            'invisible': Bool(Eval('parent')),
            })
    product = fields.Many2One(
        'product.product', "Product", ondelete='CASCADE',
        domain=[
            ('type', '=', 'service'),
            If(Bool(Eval('template')),
                ('template', '=', Eval('template', -1)),
                ()),
            If(Eval('parent'),
                ('id', '=', None),
                ()),
            ],
        states={
            'invisible': Bool(Eval('parent')),
            })
    parent = fields.Many2One(
        'product.project_task', "Parent", ondelete='CASCADE',
        states={
            'required': ~Eval('template'),
            'invisible': Bool(Eval('template')),
            })
    name = fields.Char("Name", required=True)
    timesheet_available = fields.Boolean("Available on timesheets")
    children = fields.One2Many(
        'product.project_task', 'parent', "Children")

    @fields.depends(
        'product', '_parent_product.template')
    def on_change_product(self):
        if self.product:
            self.template = self.product.template

    def get_sold_works(self, line):
        "Yield sold works for the sale line"
        pool = Pool()
        Work = pool.get('project.work')
        WorkStatus = pool.get('project.work.status')
        status = WorkStatus.get_default_status('task')
        yield Work(
            type='task',
            name=self.name,
            company=line.sale.company,
            origin=line,
            timesheet_available=self.timesheet_available,
            children=[
                w for c in self.children for w in c.get_sold_works(line)],
            status=status)
