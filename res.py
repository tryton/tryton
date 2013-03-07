#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import ldap
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['User']
__metaclass__ = PoolMeta


class User:
    __name__ = 'res.user'

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._error_messages.update({
                'set_passwd_ldap_user': ('You can not set the password of ldap '
                    'user "%s".'),
                })

    @staticmethod
    def ldap_search_user(login, con, connection, attrs=None):
        '''
        Return the result of a ldap search for the login using the ldap
        connection con based on connection.
        The attributes values defined in attrs will be return.
        '''
        scope = {
            'base': ldap.SCOPE_BASE,
            'onelevel': ldap.SCOPE_ONELEVEL,
            'subtree': ldap.SCOPE_SUBTREE,
            }.get(connection.auth_scope)
        if connection.auth_require_filter:
            filter = '(&(%s=%s)%s)' % (connection.auth_uid, login,
                    connection.auth_require_filter)
        else:
            filter = '(%s=%s)' % (connection.auth_uid, login)

        result = con.search_s(connection.auth_base_dn or '', scope,
                    filter, attrs)
        if connection.active_directory:
            result = [x for x in result if x[0]]
        return result

    @classmethod
    def _check_passwd_ldap_user(cls, logins):
        Connection = Pool().get('ldap.connection')
        with Transaction().set_user(0):
            connection, = Connection.search([], limit=1)
        find = False
        try:
            con = ldap.initialize(connection.uri)
            if connection.active_directory:
                con.set_option(ldap.OPT_REFERRALS, 0)
            if connection.secure == 'tls':
                con.start_tls_s()
            if connection.bind_dn:
                con.simple_bind_s(connection.bind_dn, connection.bind_pass)
            for login in logins:
                if cls.ldap_search_user(login,
                        con, connection, attrs=[]):
                    find = True
                    break
        except Exception:
            pass
        if find:
            cls.raise_user_error('set_passwd_ldap_user', (login.rec_name,))

    @classmethod
    def create(cls, vlist):
        tocheck = []
        for values in vlist:
            if values.get('password') and 'login' in values:
                tocheck.append(values['login'])
        if tocheck:
            cls._check_passwd_ldap_user(tocheck)
        return super(User, cls).create(vlist)

    @classmethod
    def write(cls, users, values):
        if values.get('password'):
            logins = [x.login for x in users]
            cls._check_passwd_ldap_user(logins)
        super(User, cls).write(users, values)

    @classmethod
    def set_preferences(cls, values, old_password=False):
        Connection = Pool().get('ldap.connection')
        if 'password' in values:
            with Transaction().set_user(0):
                connection, = Connection.search([], limit=1)
            try:
                con = ldap.initialize(connection.uri)
                if connection.active_directory:
                    con.set_option(ldap.OPT_REFERRALS, 0)
                if connection.secure == 'tls':
                    con.start_tls_s()
                if connection.bind_dn:
                    con.simple_bind_s(connection.bind_dn, connection.bind_pass)
                user = cls(Transaction().user)
                [(dn, attrs)] = cls.ldap_search_user(user.login, con,
                    connection, attrs=[str(connection.auth_uid)])
                if con.simple_bind_s(dn, old_password):
                    con.passwd_s(dn, old_password, values['password'])
                    values = values.copy()
                    del values['password']
                else:
                    cls.raise_user_error('wrong_password')
            except Exception:
                pass
        super(User, cls).set_preferences(values, old_password=old_password)

    @classmethod
    def get_login(cls, login, password):
        Connection = Pool().get('ldap.connection')
        with Transaction().set_user(0):
            connection, = Connection.search([], limit=1)
        try:
            con = ldap.initialize(connection.uri)
            if connection.active_directory:
                con.set_option(ldap.OPT_REFERRALS, 0)
            if connection.secure == 'tls':
                con.start_tls_s()
            if connection.bind_dn:
                con.simple_bind_s(connection.bind_dn, connection.bind_pass)
            [(dn, attrs)] = cls.ldap_search_user(login, con, connection,
                attrs=[str(connection.auth_uid)])
            if password and con.simple_bind_s(dn, password):
                user_id, _, _ = cls._get_login(login)
                if user_id:
                    return user_id
                elif connection.auth_create_user:
                    user, = cls.create([{
                                'name': attrs.get(str(connection.auth_uid),
                                    [login])[0],
                                'login': login,
                                }])
                    return user.id
        except Exception:
            pass
        return super(User, cls).get_login(login, password)
