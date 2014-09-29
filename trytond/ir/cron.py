#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
import datetime
from dateutil.relativedelta import relativedelta
import traceback
import sys
import logging
from ..config import CONFIG
from ast import literal_eval

from ..model import ModelView, ModelSQL, fields
from ..transaction import Transaction
from ..pool import Pool
from ..backend import TableHandler

__all__ = [
    'Cron',
    ]

_INTERVALTYPES = {
    'days': lambda interval: relativedelta(days=interval),
    'hours': lambda interval: relativedelta(hours=interval),
    'weeks': lambda interval: relativedelta(weeks=interval),
    'months': lambda interval: relativedelta(months=interval),
    'minutes': lambda interval: relativedelta(minutes=interval),
}


class Cron(ModelSQL, ModelView):
    "Cron"
    __name__ = "ir.cron"
    name = fields.Char('Name', required=True, translate=True)
    user = fields.Many2One('res.user', 'Execution User', required=True,
        domain=[('active', '=', False)],
        help="The user used to execute this action")
    request_user = fields.Many2One(
        'res.user', 'Request User', required=True,
        help="The user who will receive requests in case of failure")
    active = fields.Boolean('Active', select=True)
    interval_number = fields.Integer('Interval Number', required=True)
    interval_type = fields.Selection([
       ('minutes', 'Minutes'),
       ('hours', 'Hours'),
       ('days', 'Days'),
       ('weeks', 'Weeks'),
       ('months', 'Months'),
       ], 'Interval Unit')
    number_calls = fields.Integer('Number of Calls', select=1, required=True,
       help=('Number of times the function is called, a negative '
           'number indicates that the function will always be '
           'called'))
    repeat_missed = fields.Boolean('Repeat Missed')
    next_call = fields.DateTime('Next Call', required=True,
            select=True)
    model = fields.Char('Model')
    function = fields.Char('Function')
    args = fields.Text('Arguments')

    @classmethod
    def __setup__(cls):
        super(Cron, cls).__setup__()
        cls._error_messages.update({
            'request_title': 'Scheduled action failed',
            'request_body': "The following action failed to execute "
                            "properly: \"%s\"\n Traceback: \n\n%s\n"
            })

    @classmethod
    def __register__(cls, module_name):
        cursor = Transaction().cursor

        # Migration from 2.0: rename numbercall, doall and nextcall
        table = TableHandler(cursor, cls, module_name)
        table.column_rename('numbercall', 'number_calls')
        table.column_rename('doall', 'repeat_missed')
        table.column_rename('nextcall', 'next_call')
        table.drop_column('running')

        super(Cron, cls).__register__(module_name)

        # Migration from 2.0: work_days removed
        cursor.execute('UPDATE "%s" '
            'SET interval_type = %%s '
            'WHERE interval_type = %%s' % cls._table,
            ('days', 'work_days'))

    @staticmethod
    def default_next_call():
        return datetime.datetime.now()

    @staticmethod
    def default_interval_number():
        return 1

    @staticmethod
    def default_interval_type():
        return 'months'

    @staticmethod
    def default_number_calls():
        return -1

    @staticmethod
    def default_active():
        return True

    @staticmethod
    def default_repeat_missed():
        return True

    @staticmethod
    def check_xml_record(crons, values):
        return True

    @staticmethod
    def get_delta(cron):
        '''
        Return the relativedelta for the next call
        '''
        return _INTERVALTYPES[cron.interval_type](cron.interval_number)

    @classmethod
    def _get_request_values(cls, cron):
        tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
        tb_s = tb_s.decode('utf-8', 'ignore')
        name = cls.raise_user_error('request_title',
            raise_exception=False)
        body = cls.raise_user_error('request_body', (cron.name, tb_s),
            raise_exception=False)
        values = {
            'name': name,
            'priority': '2',
            'act_from': cron.user.id,
            'act_to': cron.request_user.id,
            'body': body,
            'date_sent': datetime.datetime.now(),
            'references': [
                ('create', {
                    'reference': '%s,%s' % (cls.__name__, cron.id),
                }),
            ],
            'state': 'waiting',
            'trigger_date': datetime.datetime.now(),
        }
        return values

    @classmethod
    def _callback(cls, cron):
        pool = Pool()
        try:
            args = (cron.args or []) and literal_eval(cron.args)
            Model = pool.get(cron.model)
            with Transaction().set_user(cron.user.id):
                getattr(Model, cron.function)(*args)
        except Exception:
            Transaction().cursor.rollback()

            Request = pool.get('res.request')
            req_user = cron.request_user
            language = (req_user.language.code if req_user.language
                    else CONFIG['language'])
            with contextlib.nested(Transaction().set_user(cron.user.id),
                    Transaction().set_context(language=language)):
                values = cls._get_request_values(cron)
                Request.create(values)
            Transaction().cursor.commit()

    @classmethod
    def run(cls, db_name):
        now = datetime.datetime.now()
        with Transaction().start(db_name, 0) as transaction:
            transaction.cursor.lock(cls._table)
            crons = cls.search([
                    ('number_calls', '!=', 0),
                    ('next_call', '<=', datetime.datetime.now()),
                    ])

            for cron in crons:
                try:
                    next_call = cron.next_call
                    number_calls = cron.number_calls
                    first = True
                    while next_call < now and number_calls != 0:
                        if first or cron.repeat_missed:
                            cls._callback(cron)
                        next_call += cls.get_delta(cron)
                        if number_calls > 0:
                            number_calls -= 1
                        first = False

                    cron.next_call = next_call
                    cron.number_calls = number_calls
                    if not number_calls:
                        cron.active = False
                    cron.save()
                    transaction.cursor.commit()
                except Exception:
                    transaction.cursor.rollback()
                    tb_s = reduce(lambda x, y: x + y,
                            traceback.format_exception(*sys.exc_info()))
                    tb_s = tb_s.decode('utf-8', 'ignore')
                    logger = logging.getLogger('cron')
                    logger.error('Exception:\n%s' % tb_s)
