# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt
import functools
import logging
import warnings

from trytond.config import config
from trytond.exceptions import UserError, UserWarning
from trytond.model import (
    Index, ModelSQL, ModelView, Workflow, dualmethod, fields)
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.tools import firstline
from trytond.transaction import Transaction

logger = logging.getLogger(__name__)
clean_days = config.getint('error', 'clean_days', default=90)


def set_user(field):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(cls, records, *args, **kwargs):
            result = func(cls, records, *args, **kwargs)
            cls.write(
                [r for r in records
                    if not getattr(r, field)], {
                    field: Transaction().user,
                    })
            return result
        return wrapper
    return decorator


def reset_user(*fields):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(cls, records, *args, **kwargs):
            result = func(cls, records, *args, **kwargs)
            cls.write(records, {f: None for f in fields})
            return result
        return wrapper
    return decorator


class Error(Workflow, ModelView, ModelSQL):
    "Error"
    __name__ = 'ir.error'

    origin = fields.Reference("Origin", [
            ('ir.cron', "Action"),
            ('ir.queue', "Task"),
            ], readonly=True)
    origin_string = origin.translated('origin')
    message = fields.Text("Message", readonly=True)
    description = fields.Text("Description", readonly=True)
    summary = fields.Function(fields.Char("Summary"), 'on_change_with_summary')

    processed_by = fields.Many2One(
        'res.user', "Processed by",
        states={
            'readonly': Eval('state').in_(['processing', 'solved']),
            },
        depends=['state'])
    solved_by = fields.Many2One(
        'res.user', "Solved by",
        states={
            'readonly': Eval('state').in_(['solved']),
            },
        depends=['state'])

    state = fields.Selection([
            ('open', "Open"),
            ('processing', "Processing"),
            ('solved', "Solved"),
            ], "State", readonly=True, sort=False)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        table = cls.__table__()

        cls._sql_indexes.add(
            Index(
                table,
                (table.state, Index.Equality()),
                where=table.state.in_(['open', 'processing'])))
        cls._transitions |= {
            ('open', 'processing'),
            ('processing', 'solved'),
            ('processing', 'open'),
            }
        cls._buttons.update({
                'open': {
                    'invisible': Eval('state') != 'processing',
                    'depends': ['state'],
                    },
                'process': {
                    'invisible': Eval('state') != 'open',
                    'depends': ['state'],
                    },
                'solve': {
                    'invisible': Eval('state') != 'processing',
                    'depends': ['state'],
                    },
                })

    @classmethod
    def default_state(cls):
        return 'open'

    @fields.depends('message')
    def on_change_with_summary(self, name=None):
        return firstline(self.message or '')

    def get_rec_name(self, name):
        if self.origin:
            return "%s - %s" % (self.origin_string, self.origin.rec_name)
        return super().get_rec_name(name)

    @dualmethod
    def log(cls, *args, **kwargs):
        # Test if it is a ModelStorage.log call
        if len(args) <= 1 or not isinstance(args[1], Exception):
            return super().log(*args, **kwargs)
        warnings.warn(
            "Call report instead of log to store exception",
            DeprecationWarning)
        cls.report(*args, **kwargs)

    @classmethod
    def report(cls, origin, exception):
        try:
            assert isinstance(exception, (UserError, UserWarning))
            with Transaction().new_transaction(autocommit=True):
                if not cls.search([
                            ('origin', '=', str(origin)),
                            ('message', '=', exception.message),
                            ('description', '=', exception.description),
                            ('state', '!=', 'solved'),
                            ]):
                    cls.create([{
                                'origin': str(origin),
                                'message': exception.message,
                                'description': exception.description,
                                }])
        except Exception:
            logger.critical(
                "failed to store exception %s of %s", exception, origin,
                exc_info=True)

    @classmethod
    def clean(cls, date=None):
        if date is None:
            date = (
                dt.datetime.now() - dt.timedelta(days=clean_days))
        errors = cls.search([('create_date', '<', date)])
        cls.delete(errors)

    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    @reset_user('processed_by')
    def open(cls, errors):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('processing')
    @set_user('processed_by')
    def process(cls, errors):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('solved')
    @set_user('solved_by')
    def solve(cls, errors):
        pool = Pool()
        Cron = pool.get('ir.cron')
        Queue = pool.get('ir.queue')
        for error in errors:
            if isinstance(error.origin, Cron):
                Cron.__queue__.run_once([error.origin])
            elif isinstance(error.origin, Queue):
                task = error.origin
                Queue.push(task.name, task.data)
