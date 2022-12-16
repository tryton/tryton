#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.backend import Database
from trytond.session import Session
from trytond.pool import Pool
from trytond.config import CONFIG
from trytond.transaction import Transaction
from trytond.exceptions import NotLogged
import time


_USER_CACHE = {}
_USER_TRY = {}

def login(dbname, loginname, password, cache=True):
    _USER_TRY.setdefault(dbname, {})
    _USER_TRY[dbname].setdefault(loginname, 0)
    with Transaction().start(dbname, 0) as transaction:
        database_list = Pool.database_list()
        pool = Pool(dbname)
        if not dbname in database_list:
            pool.init()
        user_obj = pool.get('res.user')
        user_id = user_obj.get_login(loginname, password)
        transaction.cursor.commit()
    if user_id:
        _USER_TRY[dbname][loginname] = 0
        if cache:
            _USER_CACHE.setdefault(dbname, {})
            _USER_CACHE[dbname].setdefault(user_id, [])
            session = Session(user_id)
            session.name = loginname
            _USER_CACHE[dbname][user_id].append(session)
            return (user_id, session.session)
        else:
            return user_id
    time.sleep(2 ** _USER_TRY[dbname][loginname])
    _USER_TRY[dbname][loginname] += 1
    return False

def logout(dbname, user, session):
    name = ''
    if user in _USER_CACHE.get(dbname, {}):
        for i, real_session \
                in enumerate(_USER_CACHE[dbname][user]):
            if real_session.session == session:
                name = real_session.name
                del _USER_CACHE[dbname][user][i]
                break
    return name

def check_super(passwd):
    if passwd == CONFIG['admin_passwd']:
        return True
    else:
        raise Exception('AccessDenied')

def check(dbname, user, session):
    if user == 0:
        raise Exception('AccessDenied')
    result = None
    now = time.time()
    timeout = int(CONFIG['session_timeout'])
    if user in _USER_CACHE.get(dbname, {}):
        to_del = []
        for i, real_session \
                in enumerate(_USER_CACHE[dbname][user]):
            if abs(real_session.timestamp - now) < timeout:
                if real_session.session == session:
                    result = real_session
            else:
                to_del.insert(0, i)
        for i in to_del:
            del _USER_CACHE[dbname][user][i]
    if result:
        return result
    raise NotLogged()

def get_connections(dbname, user):
    res = 0
    now = time.time()
    timeout = int(CONFIG['session_timeout'])
    if int(user) in _USER_CACHE.get(dbname, {}):
        for _, session in enumerate(_USER_CACHE[dbname][int(user)]):
            if abs(session.timestamp - now) < timeout:
                res += 1
    return res
