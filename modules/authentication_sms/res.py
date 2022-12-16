# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging
import random

from trytond.config import config
from trytond.exceptions import LoginException
from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta, Pool
from trytond.tools import resolve

logger = logging.getLogger(__name__)


def send_sms(text, to):
    if config.has_option('authentication_sms', 'function'):
        func = resolve(config.get('authentication_sms', 'function'))
        if func:
            from_ = config.get('authentication_sms', 'from', default=None)
            return func(text, to, from_)
    logger.error('Could not send SMS to %s: "%s"', to, text)


class User(metaclass=PoolMeta):
    __name__ = 'res.user'
    mobile = fields.Char('Mobile',
        help='Phone number that supports receiving SMS.')

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._preferences_fields.append('mobile')

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
        msg = gettext('authentication_sms.msg_user_sms_code', login=login)
        raise LoginException('sms_code', msg, type='char')


class UserLoginSMSCode(ModelSQL):
    """SMS Code

    This class is separated from the res.user one in order to prevent locking
    the res.user table when in a long running process.
    """
    __name__ = 'res.user.login.sms_code'

    user_id = fields.Integer('User ID', select=True)
    user = fields.Function(fields.Many2One('res.user', 'User'), 'get_user')
    code = fields.Char('Code')

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
            text = gettext('authentication_sms.msg_sms_text',
                    name=name, code=record.code)
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
