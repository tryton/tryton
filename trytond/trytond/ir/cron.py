# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import time
from dateutil.relativedelta import relativedelta
import logging

from trytond import backend
from trytond.config import config
from trytond.model import (
    ModelView, ModelSQL, DeactivableMixin, fields, dualmethod)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.worker import run_task

logger = logging.getLogger(__name__)


class Cron(DeactivableMixin, ModelSQL, ModelView):
    "Cron"
    __name__ = "ir.cron"
    interval_number = fields.Integer('Interval Number', required=True)
    interval_type = fields.Selection([
            ('minutes', 'Minutes'),
            ('hours', 'Hours'),
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
            ], "Interval Type", sort=False, required=True)
    minute = fields.Integer("Minute",
        states={
            'invisible': Eval('interval_type').in_(['minutes']),
            },
        depends=['interval_type'])
    hour = fields.Integer("Hour",
        states={
            'invisible': Eval('interval_type').in_(['minutes', 'hours']),
            },
        depends=['interval_type'])
    weekday = fields.Many2One(
        'ir.calendar.day', "Day of Week",
        states={
            'invisible': Eval('interval_type').in_(
                ['minutes', 'hours', 'days']),
            },
        depends=['interval_type'])
    day = fields.Integer("Day",
        states={
            'invisible': Eval('interval_type').in_(
                ['minutes', 'hours', 'days', 'weeks']),
            },
        depends=['interval_type'])

    next_call = fields.DateTime("Next Call", select=True)
    method = fields.Selection([
            ('ir.trigger|trigger_time', "Run On Time Triggers"),
            ('ir.queue|clean', "Clean Task Queue"),
            ], "Method", required=True)

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls._buttons.update({
                'run_once': {
                    'icon': 'tryton-launch',
                    },
                })

    @classmethod
    def __register__(cls, module_name):
        super().__register__(module_name)

        table_h = cls.__table_handler__(module_name)

        # Migration from 5.0: remove fields
        for column in ['name', 'user', 'request_user', 'number_calls',
                'repeat_missed', 'model', 'function', 'args']:
            table_h.drop_column(column)

        # Migration from 5.0: remove required on next_call
        table_h.not_null_action('next_call', 'remove')

    @staticmethod
    def check_xml_record(crons, values):
        return True

    @classmethod
    def view_attributes(cls):
        return [(
                '//label[@id="time_label"]', 'states', {
                    'invisible': Eval('interval_type') == 'minutes',
                }),
            ]

    def compute_next_call(self, now):
        return (now
            + relativedelta(**{self.interval_type: self.interval_number})
            + relativedelta(
                microsecond=0,
                second=0,
                minute=self.minute,
                hour=self.hour,
                day=self.day,
                weekday=int(self.weekday.index) if self.weekday else None))

    @dualmethod
    @ModelView.button
    def run_once(cls, crons):
        pool = Pool()
        for cron in crons:
            model, method = cron.method.split('|')
            Model = pool.get(model)
            getattr(Model, method)()

    @classmethod
    def run(cls, db_name):
        logger.info('cron started for "%s"', db_name)
        now = datetime.datetime.now()
        retry = config.getint('database', 'retry')
        with Transaction().start(db_name, 0) as transaction:
            transaction.database.lock(transaction.connection, cls._table)
            crons = cls.search(['OR',
                    ('next_call', '<=', now),
                    ('next_call', '=', None),
                    ])

            for cron in crons:
                logger.info("Run cron %s", cron.id)
                for count in range(retry, -1, -1):
                    if count != retry:
                        time.sleep(0.02 * (retry - count))
                    try:
                        cron.run_once()
                        transaction.commit()
                    except Exception as e:
                        transaction.rollback()
                        if (isinstance(e, backend.DatabaseOperationalError)
                                and count):
                            continue
                        logger.error('Running cron %s', cron.id, exc_info=True)
                    cron.next_call = cron.compute_next_call(now)
                    cron.save()
                    transaction.commit()
                    break
        while transaction.tasks:
            task_id = transaction.tasks.pop()
            run_task(db_name, task_id)
        logger.info('cron finished for "%s"', db_name)
