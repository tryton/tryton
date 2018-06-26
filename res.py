# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging
import random

from trytond.config import config
from trytond.exceptions import LoginException
from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.tools import resolve

__all__ = ['User', 'SMSCode']
logger = logging.getLogger(__name__)


def send_sms(text, to):
    assert len(text) <= 160, text
    if config.has_option('authentication_sms', 'function'):
        func = resolve(config.get('authentication_sms', 'function'))
        if func:
            from_ = config.get('authentication_sms', 'from', default=None)
            return func(text, to, from_)
    logger.error('Could not send SMS to %s: "%s"', to, text)


class User(metaclass=PoolMeta):
    __name__ = 'res.user'
    mobile = fields.Char('Mobile',
        help='Phone number that supports receiving SMS')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._preferences_fields.append('mobile')
        cls._error_messages.update({
                'wrong_mobile': 'Wrong mobile.',
                })

    @classmethod
    def set_preferences(cls, values, parameters):
        super(User, cls).set_preferences(values, parameters)
        user_id = Transaction().user
        user = cls(user_id)
        # Check new mobile
        if 'mobile' in values:
            # Use a new transaction to store the SMS code
            with Transaction().new_transaction() as transaction:
                # Force sending code to new mobile
                SMSCode.send(user_id, mobile=values['mobile'])
                try:
                    user_id = cls._login_sms(user.login, parameters)
                except LoginException:
                    transaction.commit()
                    raise
            if not user_id:
                cls.raise_user_error('wrong_mobile')

    @classmethod
    def _login_sms(cls, login, parameters):
        pool = Pool()
        SMSCode = pool.get('res.user.login.sms_code')
        user_id = cls._get_login(login)[0]
        if user_id:
            SMSCode.send(user_id)
        if 'sms_code' in parameters:
            code = parameters['sms_code']
            if not code:
                return
            if SMSCode.check(user_id, code):
                return user_id
        msg = SMSCode.fields_get(['code'])['code']['string']
        raise LoginException('sms_code', msg, type='char')

    @classmethod
    def _login_password_sms(cls, login, parameters):
        user_id = cls._login_password(login, parameters)
        if user_id:
            return cls._login_sms(login, parameters)


class SMSCode(ModelSQL):
    """SMS Code

    This class is separated from the res.user one in order to prevent locking
    the res.user table when in a long running process.
    """
    __name__ = 'res.user.login.sms_code'

    user_id = fields.Integer('User ID', select=True)
    user = fields.Function(fields.Many2One('res.user', 'User'), 'get_user')
    code = fields.Char('Code')

    @classmethod
    def __setup__(cls):
        super(SMSCode, cls).__setup__()
        cls._error_messages.update({
                'sms_text': '%(name)s code %(code)s',
                })

    @classmethod
    def default_code(cls):
        length = config.getint('authentication_sms', 'length', default=6)
        srandom = random.SystemRandom()
        return ''.join(str(srandom.randint(0, 9)) for _ in range(length))

    def get_user(self, name):
        return self.user_id

    @classmethod
    def get(cls, user, _now=None):
        if _now is None:
            _now = datetime.datetime.now()
        timeout = datetime.timedelta(
            seconds=config.getint('authentication_sms', 'ttl', default=5 * 60))
        records = cls.search([
                ('user_id', '=', user),
                ])
        for record in records:
            if abs(record.create_date - _now) < timeout:
                yield record
            else:
                cls.delete([record])

    @classmethod
    def send(cls, user, mobile=None):
        if not list(cls.get(user)) or mobile:
            record = cls(user_id=user)
            record.save()
            name = config.get('authentication_sms', 'name', default='Tryton')
            text = cls.raise_user_error(
                'sms_text', {
                    'name': name,
                    'code': record.code,
                    }, raise_exception=False)
            if mobile:
                send_sms(text, mobile)
            elif record.user.mobile:
                send_sms(text, record.user.mobile)

    @classmethod
    def check(cls, user, code):
        for record in cls.get(user):
            if record.code == code:
                cls.delete([record])
                return True
        return False
