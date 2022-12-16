# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from dateutil.relativedelta import relativedelta
import traceback
import sys
import logging
from email.mime.text import MIMEText
from email.header import Header
from ast import literal_eval

from ..model import ModelView, ModelSQL, DeactivableMixin, fields, dualmethod
from ..transaction import Transaction
from ..pool import Pool
from ..config import config
from ..sendmail import sendmail
from trytond.worker import run_task

__all__ = [
    'Cron',
    ]

logger = logging.getLogger(__name__)

_INTERVALTYPES = {
    'days': lambda interval: relativedelta(days=interval),
    'hours': lambda interval: relativedelta(hours=interval),
    'weeks': lambda interval: relativedelta(weeks=interval),
    'months': lambda interval: relativedelta(months=interval),
    'minutes': lambda interval: relativedelta(minutes=interval),
}


class Cron(DeactivableMixin, ModelSQL, ModelView):
    "Cron"
    __name__ = "ir.cron"
    name = fields.Char('Name', required=True, translate=True)
    user = fields.Many2One('res.user', 'Execution User', required=True,
        domain=[('active', '=', False)],
        help="The user used to execute this action")
    request_user = fields.Many2One(
        'res.user', 'Request User', required=True,
        help="The user who will receive requests in case of failure")
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
                'request_body': ("The following action failed to execute "
                    "properly: \"%s\"\n%s\n Traceback: \n\n%s\n")
                })
        cls._buttons.update({
                'run_once': {
                    'icon': 'tryton-launch',
                    },
                })

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

    def send_error_message(self):
        pool = Pool()
        Config = pool.get('ir.configuration')

        if self.request_user.language:
            language = self.request_user.language.code
        else:
            language = Config.get_language()

        with Transaction().set_user(self.user.id), \
                Transaction().set_context(language=language):
            tb_s = ''.join(traceback.format_exception(*sys.exc_info()))
            # On Python3, the traceback is already a unicode
            if hasattr(tb_s, 'decode'):
                tb_s = tb_s.decode('utf-8', 'ignore')
            subject = self.raise_user_error('request_title',
                raise_exception=False)
            body = self.raise_user_error('request_body',
                (self.name, self.__url__, tb_s),
                raise_exception=False)

            from_addr = config.get('email', 'from')
            to_addr = self.request_user.email

            msg = MIMEText(body, _charset='utf-8')
            msg['To'] = to_addr
            msg['From'] = from_addr
            msg['Subject'] = Header(subject, 'utf-8')
            if not to_addr:
                logger.error(msg.as_string())
            else:
                sendmail(from_addr, to_addr, msg)

    @dualmethod
    @ModelView.button
    def run_once(cls, crons):
        pool = Pool()
        for cron in crons:
            if cron.args:
                args = literal_eval(cron.args)
            else:
                args = []
            Model = pool.get(cron.model)
            with Transaction().set_user(cron.user.id):
                getattr(Model, cron.function)(*args)

    @classmethod
    def run(cls, db_name):
        now = datetime.datetime.now()
        with Transaction().start(db_name, 0) as transaction:
            transaction.database.lock(transaction.connection, cls._table)
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
                            try:
                                cron.run_once()
                            except Exception:
                                transaction.rollback()
                                cron.send_error_message()
                        next_call += cls.get_delta(cron)
                        if number_calls > 0:
                            number_calls -= 1
                        first = False

                    cron.next_call = next_call
                    cron.number_calls = number_calls
                    if not number_calls:
                        cron.active = False
                    cron.save()
                    transaction.commit()
                except Exception:
                    transaction.rollback()
                    logger.error('Running cron %s', cron.id, exc_info=True)
        while transaction.tasks:
            task_id = transaction.tasks.pop()
            run_task(db_name, task_id)
