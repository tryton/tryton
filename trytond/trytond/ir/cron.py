#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from __future__ import with_statement
import contextlib
import datetime
from dateutil.relativedelta import relativedelta
import traceback
import sys
from trytond.backend import Database
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval
from trytond.transaction import Transaction

_INTERVALTYPES = {
    'work_days': lambda interval: relativedelta(days=interval),
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
                           help="The user used to execute this action")
    request_user = fields.Many2One(
        'res.user', 'Request User', required=True,
        help="The user who will receive requests in case of failure")
    active = fields.Boolean('Active', select=1)
    interval_number = fields.Integer('Interval Number')
    interval_type = fields.Selection( [
       ('minutes', 'Minutes'),
       ('hours', 'Hours'),
       ('work_days', 'Work Days'),
       ('days', 'Days'),
       ('weeks', 'Weeks'),
       ('months', 'Months'),
       ], 'Interval Unit')
    numbercall = fields.Integer('Number of calls', select=1,
       help='Number of times the function is called,\n' \
               'a negative number indicates that the function ' \
               'will always be called')
    doall = fields.Boolean('Repeat missed')
    nextcall = fields.DateTime('Next call date', required=True,
            select=1)
    model = fields.Char('Model')
    function = fields.Char('Function')
    args = fields.Text('Arguments')
    priority = fields.Integer('Priority',
       help='0=Very Urgent\n10=Not urgent')
    running = fields.Boolean('Running', readonly=True, select=1)

    def __init__(self):
        super(Cron, self).__init__()
        self._error_messages.update({
            'request_title': 'Scheduled action failed',
            'request_body': "The following action failed to execute "
                            "properly: \"%s\"\n Traceback: \n\n%s\n"
            })

    def default_nextcall(self):
        return datetime.datetime.now()

    def default_priority(self):
        return 5

    def default_user(self):
        return int(Transaction().user)

    def default_interval_number(self):
        return 1

    def default_interval_type(self):
        return 'months'

    def default_numbercall(self):
        return 1

    def default_active(self):
        return True

    def default_doall(self):
        return True

    def default_running(self):
        return False

    def check_xml_record(self, ids, values):
        return True

    def _callback(self, cron):
        try:
            args = (cron['args'] or []) and safe_eval(cron['args'])
            obj = self.pool.get(cron['model'])
            if not obj and hasattr(obj, cron['function']):
                return False
            fct = getattr(obj, cron['function'])
            with Transaction().set_user(cron['user']):
                fct(*args)
        except Exception, error:
            Transaction().cursor.rollback()

            tb_s = ''
            for line in traceback.format_exception(*sys.exc_info()):
                try:
                    line = line.encode('utf-8', 'ignore')
                except Exception:
                    continue
                tb_s += line
            try:
                tb_s += error.message.decode('utf-8', 'ignore')
            except Exception:
                pass

            request_obj = self.pool.get('res.request')
            try:
                user_obj = self.pool.get('res.user')
                req_user = user_obj.browse(cron['request_user'])
                language = (req_user.language.code if req_user.language
                        else 'en_US')
                with contextlib.nested(Transaction().set_user(cron['user']),
                        Transaction().set_context(language=language)):
                    rid = request_obj.create({
                        'name': self.raise_user_error('request_title',
                            raise_exception=False),
                         'priority': '2',
                         'act_from': cron['user'],
                         'act_to': cron['request_user'],
                         'body': self.raise_user_error('request_body',
                             (cron['name'], tb_s), raise_exception=False),
                         'date_sent': datetime.datetime.now(),
                         'references': [
                                ('create', {
                                    'reference': "ir.cron,%s" % cron['id'],
                                    }),
                                ],
                         'state': 'waiting',
                         'trigger_date': datetime.datetime.now(),
                         })
                Transaction().cursor.commit()
            except Exception:
                Transaction().cursor.rollback()

    def pool_jobs(self, db_name):
        now = datetime.datetime.now()
        with Transaction().start(db_name, 0) as transaction:
            try:
                transaction.cursor.lock(self._table)
                transaction.cursor.execute('SELECT * FROM ir_cron '
                        'WHERE numbercall <> 0 '
                            'AND active '
                            'AND nextcall <= %s '
                            'AND NOT running '
                            'ORDER BY priority', (datetime.datetime.now(),))
                crons = transaction.cursor.dictfetchall()

                for cron in crons:
                    transaction.cursor.execute('UPDATE ir_cron '
                        'SET running = %s '
                        'WHERE id = %s', (True, cron['id']))
                    nextcall = cron['nextcall']
                    numbercall = cron['numbercall']
                    done = False

                    while nextcall < now and numbercall:
                        if numbercall > 0:
                            numbercall -= 1
                        if not done or cron['doall']:
                            self._callback(cron)
                        if numbercall:
                            nextcall += _INTERVALTYPES[cron['interval_type']](
                                    cron['interval_number'])
                        done = True

                    addsql = ''
                    addsql_param = []
                    if not numbercall:
                        addsql = ', active = %s'
                        addsql_param = [False]
                    transaction.cursor.execute("UPDATE ir_cron "
                        "SET nextcall = %s, "
                            "running = %s, "
                            "numbercall = %s" + addsql + " "
                        "WHERE id = %s",
                        [nextcall, False, numbercall] + addsql_param +
                        [cron['id']])
                    transaction.cursor.commit()
            except Exception:
                transaction.cursor.rollback()
                raise

Cron()
