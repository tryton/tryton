#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL
import ldap


class User(ModelSQL, ModelView):
    _name = 'res.user'

    def __init__(self):
        super(User, self).__init__()
        self._error_messages.update({
            'set_passwd_ldap_user': \
                    'You can not set a password to a ldap user!',
            })

    def ldap_search_user(self, cursor, user, login, con, connection,
            attrs=None, context=None):
        '''
        Return the resule of a ldap search for the login

        :param cursor: the database cursor
        :param user: the user id
        :param login: the login
        :param con: the ldap connection
        :param connection: a BrowseRecord of ldap.connection
        :param attrs: a list of attribute to return
        :param context: the context
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

    def _check_passwd_ldap_user(self, cursor, user, logins, context=None):
        connection_obj = self.pool.get('ldap.connection')
        connection_ids = connection_obj.search(cursor, 0, [], limit=1,
                context=context)
        connection = connection_obj.browse(cursor, 0, connection_ids[0],
                context=context)
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
                if self.ldap_search_user(cursor, user, login,
                        con, connection, attrs=[], context=context):
                    find = True
        except Exception:
            pass
        if find:
            self.raise_user_error(cursor, 'set_passwd_ldap_user',
                    context=context)

    def create(self, cursor, user, vals, context=None):
        if vals.get('password') and 'login' in vals:
            self._check_passwd_ldap_user(cursor, user, [vals['login']],
                    context=context)
        return super(User, self).create(cursor, user, vals, context=context)

    def write(self, cursor, user, ids, vals, context=None):
        if vals.get('password'):
            if isinstance(ids, (int, long)):
                ids2 = [ids]
            else:
                ids2 = ids
            logins = [x.login for x in self.browse(cursor, user, ids2,
                context=context)]
            self._check_passwd_ldap_user(cursor, user, logins, context=context)
        return super(User, self).write(cursor, user, ids, vals, context=context)

    def set_preferences(self, cursor, user_id, values, old_password=False,
            context=None):
        connection_obj = self.pool.get('ldap.connection')

        if 'password' in values:
            connection_ids = connection_obj.search(cursor, 0, [], limit=1,
                    context=context)
            connection = connection_obj.browse(cursor, 0, connection_ids[0],
                    context=context)
            try:
                con = ldap.initialize(connection.uri)
                if connection.active_directory:
                    con.set_option(ldap.OPT_REFERRALS, 0)
                if connection.secure == 'tls':
                    con.start_tls_s()
                if connection.bind_dn:
                    con.simple_bind_s(connection.bind_dn, connection.bind_pass)
                user = self.browse(cursor, user_id, user_id, context=context)
                [(dn, attrs)] = self.ldap_search_user(cursor, user_id,
                        user.login, con, connection,
                        attrs=[str(connection.auth_uid)], context=context)
                if con.simple_bind_s(dn, old_password):
                    con.passwd_s(dn, old_password, values['password'])
                    values = values.copy()
                    del values['password']
                else:
                    self.raise_user_error(cursor, 'wrong_password',
                            context=context)
            except Exception:
                pass
        return super(User, self).set_preferences(cursor, user_id, values,
                old_password=old_password, context=context)

    def get_login(self, cursor, user, login, password, context=None):
        connection_obj = self.pool.get('ldap.connection')
        connection_ids = connection_obj.search(cursor, 0, [], limit=1,
                context=context)
        connection = connection_obj.browse(cursor, 0, connection_ids[0],
                context=context)
        try:
            con = ldap.initialize(connection.uri)
            if connection.active_directory:
                con.set_option(ldap.OPT_REFERRALS, 0)
            if connection.secure == 'tls':
                con.start_tls_s()
            if connection.bind_dn:
                con.simple_bind_s(connection.bind_dn, connection.bind_pass)
            [(dn, attrs)] = self.ldap_search_user(cursor, user, login,
                    con, connection, attrs=[str(connection.auth_uid)],
                    context=context)
            if con.simple_bind_s(dn, password):
                user_id, _, _ = self._get_login(cursor, user, login,
                        context=context)
                if user_id:
                    return user_id
                elif connection.auth_create_user:
                    user_id = self.create(cursor, 0, {
                        'name': attrs.get(str(connection.auth_uid), [login])[0],
                        'login': login,
                        }, context=context)
                    return user_id
        except Exception:
            pass
        return super(User, self).get_login(cursor, user, login, password,
                context=context)

User()
