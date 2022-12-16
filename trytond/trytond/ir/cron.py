#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import contextlib
import datetime
from dateutil.relativedelta import relativedelta
import traceback
import sys
import logging
from trytond.backend import Database
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.backend import TableHandler

_INTERVALTYPES = {
    'days': lambda interval: relativedelta(days=interval),
    'hours': lambda interval: relativedelta(hours=interval),
    'weeks': lambda interval: relativedelta(weeks=interval),
    'months': lambda interval: relativedelta(months=interval),
    'minutes': lambda interval: relativedelta(minutes=interval),
}

class Cron(ModelSQL, ModelView):
    "Cron"
    _name = "ir.cron"
    _description = __doc__
    name = fields.Char('Name', required=True, translate=True)
    user = fields.Many2One('res.user', 'Execution User', required=True,
        domain=[('active', '=', False)],
        help="The user used to execute this action")
    request_user = fields.Many2One(
        'res.user', 'Request User', required=True,
        help="The user who will receive requests in case of failure")
    active = fields.Boolean('Active', select=1)
    interval_number = fields.Integer('Interval Number')
    interval_type = fields.Selection( [
       ('minutes', 'Minutes'),
       ('hours', 'Hours'),
       ('days', 'Days'),
       ('weeks', 'Weeks'),
       ('months', 'Months'),
       ], 'Interval Unit')
    number_calls = fields.Integer('Number of Calls', select=1,
       help=('Number of times the function is called, a negative '
           'number indicates that the function will always be '
           'called'))
    repeat_missed = fields.Boolean('Repeat Missed')
    next_call = fields.DateTime('Next Call', required=True,
            select=1)
    model = fields.Char('Model')
    function = fields.Char('Function')
    args = fields.Text('Arguments')

    def __init__(self):
        super(Cron, self).__init__()
        self._error_messages.update({
            'request_title': 'Scheduled action failed',
            'request_body': "The following action failed to execute "
                            "properly: \"%s\"\n Traceback: \n\n%s\n"
            })

    def init(self, module_name):
        cursor = Transaction().cursor

        # Migration from 2.0: rename numbercall, doall and nextcall
        table = TableHandler(cursor, self, module_name)
        table.column_rename('numbercall', 'number_calls')
        table.column_rename('doall', 'repeat_missed')
        table.column_rename('nextcall', 'next_call')
        table.drop_column('running')

        super(Cron, self).init(module_name)

        # Migration from 2.0: work_days removed
        cursor.execute('UPDATE "%s" '
            'SET interval_type = %%s '
            'WHERE interval_type = %%s' % self._table,
            ('days', 'work_days'))

    def default_next_call(self):
        return datetime.datetime.now()

    def default_interval_number(self):
        return 1

    def default_interval_type(self):
        return 'months'

    def default_number_calls(self):
        return -1

    def default_active(self):
        return True

    def default_repeat_missed(self):
        return True

    def check_xml_record(self, ids, values):
        return True

    def get_delta(self, cron):
        '''
        Return the relativedelta for the next call
        '''
        return _INTERVALTYPES[cron.interval_type](cron.interval_number)

    def _get_request_values(self, cron):
        tb_s = reduce(lambda x, y: x + y,
                traceback.format_exception(*sys.exc_info()))
        tb_s = tb_s.decode('utf-8', 'ignore')
        name = self.raise_user_error('request_title',
            raise_exception=False)
        body = self.raise_user_error('request_body', (cron.name, tb_s),
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
                    'reference': '%s,%s' % (self._name, cron.id),
                }),
            ],
            'state': 'waiting',
            'trigger_date': datetime.datetime.now(),
        }
        return values

    def _callback(self, cron):
        pool = Pool()
        try:
            args = (cron.args or []) and safe_eval(cron.args)
            model_obj = pool.get(cron.model)
            with Transaction().set_user(cron.user.id):
                getattr(model_obj, cron.function)(*args)
        except Exception, error:
            Transaction().cursor.rollback()

            request_obj = pool.get('res.request')
            req_user = cron.request_user
            language = (req_user.language.code if req_user.language
                    else 'en_US')
            with contextlib.nested(Transaction().set_user(cron.user.id),
                    Transaction().set_context(language=language)):
                values = self._get_request_values(cron)
                rid = request_obj.create(values)
            Transaction().cursor.commit()

    def run(self, db_name):
        now = datetime.datetime.now()
        with Transaction().start(db_name, 0) as transaction:
            transaction.cursor.lock(self._table)
            cron_ids = self.search([
                ('number_calls', '!=', 0),
                ('next_call', '<=', datetime.datetime.now()),
            ])
            crons = self.browse(cron_ids)

            for cron in crons:
                try:
                    next_call = cron.next_call
                    number_calls = cron.number_calls
                    first = True
                    while next_call < now and number_calls != 0:
                        if first or cron.repeat_missed:
                            self._callback(cron)
                        next_call += self.get_delta(cron)
                        if number_calls > 0:
                            number_calls -= 1
                        first = False

                    values = {
                        'next_call': next_call,
                        'number_calls': number_calls,
                    }
                    if not number_calls:
                        values['active'] = False
                    self.write(cron.id, values)
                    transaction.cursor.commit()
                except Exception:
                    transaction.cursor.rollback()
                    tb_s = reduce(lambda x, y: x + y,
                            traceback.format_exception(*sys.exc_info()))
                    tb_s = tb_s.decode('utf-8', 'ignore')
                    logger = logging.getLogger('cron')
                    logger.error('Exception:\n%s' % tb_s)

Cron()
