# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import lazy_gettext
from trytond.model import fields
from trytond.pool import PoolMeta


class Company(metaclass=PoolMeta):
    __name__ = 'company.company'

    avatar_url = fields.Function(
        fields.Char(lazy_gettext('ir.msg_avatar_url')), 'get_avatar_url')

    def get_avatar_url(self, name):
        return self.party.avatar_url


class Employee(metaclass=PoolMeta):
    __name__ = 'company.employee'

    avatar_url = fields.Function(
        fields.Char(lazy_gettext('ir.msg_avatar_url')), 'get_avatar_url')

    def get_avatar_url(self, name):
        return self.party.avatar_url
