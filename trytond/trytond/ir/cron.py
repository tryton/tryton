#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"""
SPEC: Execute "model.function(*eval(args))" periodically
   date        : date to execute the job or NULL if directly
   delete_after: delete the ir.cron entry after execution
   interval_*  : period
   max_repeat  : number of execution or NULL if endlessly
"""

from trytond.backend import Database
from trytond.model import ModelView, ModelSQL, fields
from trytond.tools import safe_eval
import datetime
from dateutil.relativedelta import relativedelta
import traceback
import sys

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

    def default_nextcall(self, cursor, user, context=None):
        return datetime.datetime.now()

    def default_priority(self, cursor, user, context=None):
        return 5

    def default_user(self, cursor, user, context=None):
        return int(user)

    def default_interval_number(self, cursor, user, context=None):
        return 1

    def default_interval_type(self, cursor, user, context=None):
        return 'months'

    def default_numbercall(self, cursor, user, context=None):
        return 1

    def default_active(self, cursor, user, context=None):
        return True

    def default_doall(self, cursor, user, context=None):
        return True

    def default_running(self, cursor, user, context=None):
        return False

    def check_xml_record(self, cursor, user, ids, values, context=None):
        return True

    def _callback(self, cursor, cron):
        try:
            args = (cron['args'] or []) and safe_eval(cron['args'])
            obj = self.pool.get(cron['model'])
            if not obj and hasattr(obj, cron['function']):
                return False
            fct = getattr(obj, cron['function'])
            fct(cursor, cron['user'], *args)
        except Exception, error:
            cursor.rollback()

            tb_s = ''
            for line in traceback.format_exception(*sys.exc_info()):
                try:
                    line = line.encode('utf-8', 'ignore')
                except:
                    continue
                tb_s += line
            try:
                tb_s += error.message.decode('utf-8', 'ignore')
            except:
                pass

            request_obj = self.pool.get('res.request')
            try:
                user_obj = self.pool.get('res.user')
                req_user = user_obj.browse(cursor, cron['user'], cron['request_user'])
                rid = request_obj.create(
                    cursor, cron['user'],
                    {'name': self.raise_user_error(
                            cursor, 'request_title', raise_exception=False,
                            context={'language': req_user.language and \
                                         req_user.language.code or "en_US"}),
                     'priority': '2',
                     'act_from': cron['user'],
                     'act_to': cron['request_user'],
                     'body': self.raise_user_error(
                            cursor, 'request_body', (cron['name'], tb_s),
                            raise_exception=False),
                     'date_sent': datetime.datetime.now(),
                     'references': [
                            ('create',{'reference': "ir.cron,%s"%cron['id']})],
                     'state': 'waiting',
                     'trigger_date': datetime.datetime.now(),
                     })
                cursor.commit()
            except:
                cursor.rollback()

    def pool_jobs(self, db_name):
        now = datetime.datetime.now()
        try:
            database = Database(db_name).connect()
            cursor = database.cursor()
        except:
            return
        try:
            try:
                cursor.lock(self._table)
                cursor.execute('SELECT * FROM ir_cron ' \
                        'WHERE numbercall <> 0 ' \
                            'AND active ' \
                            'AND nextcall <= %s ' \
                            'AND NOT running ' \
                            'ORDER BY priority', (datetime.datetime.now(),))
                crons = cursor.dictfetchall()

                for cron in crons:
                    cursor.execute('UPDATE ir_cron SET running = %s ' \
                                       'WHERE id = %s', (True, cron['id']))
                    nextcall = cron['nextcall']
                    numbercall = cron['numbercall']
                    done = False

                    while nextcall < now and numbercall:
                        if numbercall > 0:
                            numbercall -= 1
                        if not done or cron['doall']:
                            self._callback(cursor, cron)
                        if numbercall:
                            nextcall += _INTERVALTYPES[cron['interval_type']](
                                    cron['interval_number'])
                        done = True

                    addsql = ''
                    addsql_param = []
                    if not numbercall:
                        addsql = ', active = %s'
                        addsql_param = [False]
                    cursor.execute("UPDATE ir_cron SET nextcall = %s, " \
                                "running = %s, numbercall = %s" + addsql + " " \
                                "WHERE id = %s", [nextcall, False, numbercall] \
                                + addsql_param + [cron['id']])
                    cursor.commit()
            except Exception, e:
                cursor.rollback()
                raise
        finally:
            cursor.close()

Cron()
