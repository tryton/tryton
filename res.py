#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import ldap
from trytond.model import ModelView, ModelSQL
from trytond.transaction import Transaction
from trytond.pool import Pool


class User(ModelSQL, ModelView):
    _name = 'res.user'

    def __init__(self):
        super(User, self).__init__()
        self._error_messages.update({
            'set_passwd_ldap_user': \
                    'You can not set a password to a ldap user!',
            })

    def ldap_search_user(self, login, con, connection, attrs=None):
        '''
        Return the resule of a ldap search for the login

        :param login: the login
        :param con: the ldap connection
        :param connection: a BrowseRecord of ldap.connection
        :param attrs: a list of attribute to return
        :return: the ldap search result
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

    def _check_passwd_ldap_user(self, logins):
        connection_obj = Pool().get('ldap.connection')
        connection_ids = connection_obj.search([], limit=1)
        with Transaction().set_user(0):
            connection = connection_obj.browse(connection_ids[0])
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
                if self.ldap_search_user(login,
                        con, connection, attrs=[]):
                    find = True
        except Exception:
            pass
        if find:
            self.raise_user_error('set_passwd_ldap_user')

    def create(self, vals):
        if vals.get('password') and 'login' in vals:
            self._check_passwd_ldap_user([vals['login']])
        return super(User, self).create(vals)

    def write(self, ids, vals):
        if vals.get('password'):
            if isinstance(ids, (int, long)):
                ids2 = [ids]
            else:
                ids2 = ids
            logins = [x.login for x in self.browse(ids2)]
            self._check_passwd_ldap_user(logins)
        return super(User, self).write(ids, vals)

    def set_preferences(self, values, old_password=False):
        connection_obj = Pool().get('ldap.connection')
        if 'password' in values:
            connection_ids = connection_obj.search([], limit=1)
            with Transaction().set_user(0):
                connection = connection_obj.browse(connection_ids[0])
            try:
                con = ldap.initialize(connection.uri)
                if connection.active_directory:
                    con.set_option(ldap.OPT_REFERRALS, 0)
                if connection.secure == 'tls':
                    con.start_tls_s()
                if connection.bind_dn:
                    con.simple_bind_s(connection.bind_dn, connection.bind_pass)
                user = self.browse(Transaction().user)
                [(dn, attrs)] = self.ldap_search_user(user.login, con,
                        connection, attrs=[str(connection.auth_uid)])
                if con.simple_bind_s(dn, old_password):
                    con.passwd_s(dn, old_password, values['password'])
                    values = values.copy()
                    del values['password']
                else:
                    self.raise_user_error('wrong_password')
            except Exception:
                pass
        return super(User, self).set_preferences(values,
                old_password=old_password)

    def get_login(self, login, password):
        connection_obj = Pool().get('ldap.connection')
        connection_ids = connection_obj.search([], limit=1)
        with Transaction().set_user(0):
            connection = connection_obj.browse(connection_ids[0])
        try:
            con = ldap.initialize(connection.uri)
            if connection.active_directory:
                con.set_option(ldap.OPT_REFERRALS, 0)
            if connection.secure == 'tls':
                con.start_tls_s()
            if connection.bind_dn:
                con.simple_bind_s(connection.bind_dn, connection.bind_pass)
            [(dn, attrs)] = self.ldap_search_user(login, con, connection,
                    attrs=[str(connection.auth_uid)])
            if password and con.simple_bind_s(dn, password):
                user_id, _, _ = self._get_login(login)
                if user_id:
                    return user_id
                elif connection.auth_create_user:
                    user_id = self.create({
                        'name': attrs.get(str(connection.auth_uid),
                                [login])[0],
                        'login': login,
                        })
                    return user_id
        except Exception:
            pass
        return super(User, self).get_login(login, password)

User()
