#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Connection']
__metaclass__ = PoolMeta


class Connection:
    __name__ = 'ldap.connection'

    auth_uid = fields.Char('UID', help='UID Attribute for authentication',
            required=True)
    auth_base_dn = fields.Char('Base DN', help='Base DN for authentication',
            required=True)
    auth_require_filter = fields.Char('Require Filter')
    auth_scope = fields.Selection([
        ('base', 'Base'),
        ('onelevel', 'OneLevel'),
        ('subtree', 'Subtree'),
        ], 'Scope', required=True)
    auth_create_user = fields.Boolean('Create User',
            help='Create user if not in database')

    @staticmethod
    def default_auth_uid():
        return 'uid'

    @staticmethod
    def default_auth_scope():
        return 'base'

    @staticmethod
    def default_auth_create_user():
        return False
