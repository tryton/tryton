# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from dateutil.relativedelta import relativedelta
from sql import Literal, Null
from sql.aggregate import Count, Min
from sql.conditionals import NullIf
from sql.functions import CurrentTimestamp, DateTrunc, Round

from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Context(ModelView):
    "Marketing Automation Reporting Context"
    __name__ = 'marketing.automation.reporting.context'

    from_date = fields.Date("From Date",
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ])
    to_date = fields.Date("To Date",
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ])
    period = fields.Selection([
            ('year', "Year"),
            ('month', "Month"),
            ('day', "Day"),
            ], "Period", required=True)

    @classmethod
    def default_from_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        if 'from_date' in context:
            return context['from_date']
        return Date.today() - relativedelta(years=1)

    @classmethod
    def default_to_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        context = Transaction().context
        if 'to_date' in context:
            return context['to_date']
        return Date.today()

    @classmethod
    def default_period(cls):
        return Transaction().context.get('period', 'month')


class Abstract(ModelSQL, ModelView):

    date = fields.Date("Date")

    @classmethod
    def table_query(cls):
        from_item, tables, withs = cls._joins()
        return from_item.select(*cls._columns(tables, withs),
            where=cls._where(tables, withs),
            group_by=cls._group_by(tables, withs),
            with_=withs.values())

    @classmethod
    def _columns(cls, tables, withs):
        return [
            cls._column_id(tables, withs).as_('id'),
            Literal(0).as_('create_uid'),
            CurrentTimestamp().as_('create_date'),
            cls.write_uid.sql_cast(Literal(Null)).as_('write_uid'),
            cls.write_date.sql_cast(Literal(Null)).as_('write_date'),
            cls._column_date(tables, withs).as_('date'),
            ]


class Scenario(Abstract):
    "Marketing Automation Reporting Scenario"
    __name__ = 'marketing.automation.reporting.scenario'

    scenario = fields.Many2One(
        'marketing.automation.scenario', "Scenario")
    record_count = fields.Integer("Records")
    record_count_blocked = fields.Integer("Records Blocked")
    block_rate = fields.Float("Block Rate")

    @classmethod
    def _joins(cls):
        pool = Pool()
        Record = pool.get('marketing.automation.record')
        tables = {}
        tables['record'] = record = Record.__table__()
        withs = {}
        return record, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        record = tables['record']

        record_count = Count(Literal('*'))
        record_count_blocked = Count(Literal('*'), filter_=record.blocked)

        return super()._columns(tables, withs) + [
            record.scenario.as_('scenario'),
            record_count.as_('record_count'),
            record_count_blocked.as_('record_count_blocked'),
            cls.block_rate.sql_cast(
                Round(record_count_blocked / NullIf(record_count, 0), 2)).as_(
                'block_rate'),
            ]

    @classmethod
    def _column_id(cls, tables, withs):
        record = tables['record']
        return Min(record.id)

    @classmethod
    def _column_date(cls, tables, withs):
        context = Transaction().context
        record = tables['record']

        date = DateTrunc(context.get('period', 'month'), record.create_date)
        return cls.date.sql_cast(date)

    @classmethod
    def _group_by(cls, tables, withs):
        record = tables['record']
        return [record.scenario, cls._column_date(tables, withs)]

    @classmethod
    def _where(cls, tables, withs):
        context = Transaction().context
        record = tables['record']

        where = Literal(True)
        from_date = context.get('from_date')
        if from_date:
            where &= record.create_date >= from_date
        to_date = context.get('to_date')
        if to_date:
            where &= record.create_date <= to_date
        return where


class Activity(Abstract):
    "Marketing Automation Reporting Activity"
    __name__ = 'marketing.automation.reporting.activity'

    activity = fields.Many2One(
        'marketing.automation.activity', "Activity")
    activity_action = fields.Function(
        fields.Selection('get_activity_actions', "Activity Action"),
        'on_change_with_activity_action')
    record_count = fields.Integer("Records")
    email_opened = fields.Integer(
        "E-Mails Opened",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            })
    email_clicked = fields.Integer(
        "E-Mails Clicked",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            })
    email_open_rate = fields.Float(
        "E-mail Open Rate",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            })
    email_click_rate = fields.Float(
        "E-mail Click Rate",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            })
    email_click_through_rate = fields.Float(
        "E-mail Click-Through Rate",
        states={
            'invisible': Eval('activity_action') != 'send_email',
            })

    @classmethod
    def get_activity_actions(cls):
        pool = Pool()
        Activity = pool.get('marketing.automation.activity')
        return Activity.fields_get(['action'])['action']['selection']

    @fields.depends('activity')
    def on_change_with_activity_action(self, name=None):
        if self.activity:
            return self.activity.action

    @classmethod
    def _joins(cls):
        pool = Pool()
        RecordActivity = pool.get('marketing.automation.record.activity')
        tables = {}
        tables['record_activity'] = record = RecordActivity.__table__()
        withs = {}
        return record, tables, withs

    @classmethod
    def _columns(cls, tables, withs):
        record_activity = tables['record_activity']

        record_count = Count(
            Literal('*'), filter_=record_activity.state == 'done')
        email_opened = Count(
            Literal('*'), filter_=record_activity.email_opened)
        email_clicked = Count(
            Literal('*'), filter_=record_activity.email_clicked)

        return super()._columns(tables, withs) + [
            record_activity.activity.as_('activity'),
            record_count.as_('record_count'),
            email_opened.as_('email_opened'),
            email_clicked.as_('email_clicked'),
            cls.email_open_rate.sql_cast(
                Round(email_opened / NullIf(record_count, 0), 2)).as_(
                    'email_open_rate'),
            cls.email_click_rate.sql_cast(
                Round(email_clicked / NullIf(record_count, 0), 2)).as_(
                    'email_click_rate'),
            cls.email_click_through_rate.sql_cast(
                Round(email_clicked / NullIf(email_opened, 0), 2)).as_(
                'email_click_through_rate'),
            ]

    @classmethod
    def _column_id(cls, tables, withs):
        record_activity = tables['record_activity']
        return Min(record_activity.id)

    @classmethod
    def _column_date(cls, tables, withs):
        context = Transaction().context
        record_activity = tables['record_activity']

        date = DateTrunc(context.get('period', 'month'), record_activity.at)
        return cls.date.sql_cast(date)

    @classmethod
    def _group_by(cls, tables, withs):
        record_activity = tables['record_activity']
        return [record_activity.activity, cls._column_date(tables, withs)]

    @classmethod
    def _where(cls, tables, withs):
        context = Transaction().context
        record_activity = tables['record_activity']

        where = Literal(True)
        from_date = context.get('from_date')
        if from_date:
            where &= record_activity.at >= from_date
        to_date = context.get('to_date')
        if to_date:
            where &= record_activity.at <= to_date
        return where
