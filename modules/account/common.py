# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from sql.conditionals import Coalesce

from trytond.model import Model, fields
from trytond.pyson import Eval, If, Bool
from trytond.pool import Pool
from trytond.transaction import Transaction


class PeriodMixin(Model):

    start_date = fields.Date(
        "Start Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('start_date', '<=', Eval('end_date')),
                ()),
            ],
        depends=['end_date'])
    end_date = fields.Date(
        "End Date",
        domain=[
            If(Eval('start_date') & Eval('end_date'),
                ('end_date', '>=', Eval('start_date')),
                ()),
            ],
        depends=['start_date'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        if (hasattr(cls, 'parent')
                and hasattr(cls, 'childs')
                and hasattr(cls, 'company')):
            cls.parent.domain = [
                ('company', '=', Eval('company', 0)),
                ['OR',
                    If(Bool(Eval('start_date')),
                        ('start_date', '>=', Eval('start_date', None)),
                        ()),
                    ('start_date', '=', None),
                    ],
                ['OR',
                    If(Bool(Eval('end_date')),
                        ('end_date', '<=', Eval('end_date', None)),
                        ()),
                    ('end_date', '=', None),
                    ],
                ]
            cls.parent.depends.extend(['company', 'start_date', 'end_date'])

            cls.childs.domain = [
                ('company', '=', Eval('company', 0)),
                If(Bool(Eval('start_date')),
                    ('start_date', '>=', Eval('start_date', None)),
                    ()),
                If(Bool(Eval('end_date')),
                    ('end_date', '<=', Eval('end_date', None)),
                    ()),
                ]
            cls.childs.depends.extend(['company', 'start_date', 'end_date'])


class ActivePeriodMixin(PeriodMixin):

    active = fields.Function(
        fields.Boolean("Active"), 'get_active', searcher='search_active')

    @classmethod
    def _active_dates(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        FiscalYear = pool.get('account.fiscalyear')
        Period = pool.get('account.period')
        context = Transaction().context
        today = Date.today()

        date = context.get('date')
        from_date, to_date = context.get('from_date'), context.get('to_date')
        period_ids = context.get('periods')
        fiscalyear_id = context.get('fiscalyear')
        if date:
            fiscalyears = FiscalYear.search([
                    ('start_date', '<=', date),
                    ('end_date', '>=', date),
                    ])
        elif from_date or to_date:
            domain = []
            if from_date:
                domain.append(('end_date', '>=', from_date))
            if to_date:
                domain.append(('start_date', '<=', to_date))
            fiscalyears = FiscalYear.search(domain)
        elif period_ids:
            periods = Period.browse(period_ids)
            fiscalyears = list(set(p.fiscalyear for p in periods))
        elif fiscalyear_id:
            fiscalyears = FiscalYear.browse([fiscalyear_id])
        else:
            fiscalyears = FiscalYear.search([
                    ('start_date', '<=', today),
                    ('end_date', '>=', today),
                    ], limit=1)
        if not fiscalyears:
            return (from_date or date or today, to_date or date or today)
        return (
            min(f.start_date for f in fiscalyears),
            max(f.end_date for f in fiscalyears))

    def get_active(self, name):
        from_date, to_date = self._active_dates()
        start_date = self.start_date or datetime.date.min
        end_date = self.end_date or datetime.date.max
        return (start_date <= to_date <= end_date
            or start_date <= from_date <= end_date
            or (from_date <= start_date and end_date <= to_date))

    @classmethod
    def search_active(cls, name, domain):
        table = cls.__table__()
        _, operator, value = domain

        if operator in {'=', '!='}:
            if (operator == '=') == value:
                operator = 'in'
            else:
                operator = 'not in'
        elif operator in {'in', 'not in'}:
            if True in value and False not in value:
                operator = 'in'
            elif False in value and True not in value:
                operator = 'not in'
            else:
                return []
        else:
            return []

        from_date, to_date = cls._active_dates()
        start_date = Coalesce(table.start_date, datetime.date.min)
        end_date = Coalesce(table.end_date, datetime.date.max)

        query = table.select(table.id,
            where=((start_date <= to_date) & (end_date >= to_date))
            | ((start_date <= from_date) & (end_date >= from_date))
            | ((start_date >= from_date) & (end_date <= to_date)))
        return [('id', operator, query)]
