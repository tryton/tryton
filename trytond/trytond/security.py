#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.backend import Database
from trytond.session import Session
from config import CONFIG
try:
    import hashlib
except ImportError:
    hashlib = None
    import sha
import time


_USER_CACHE = {}
_USER_TRY = {}

def login(dbname, loginname, password, cache=True):
    _USER_TRY.setdefault(dbname, {})
    database = Database(dbname).connect()
    cursor = database.cursor()
    if hashlib:
        password_sha = hashlib.sha1(password).hexdigest()
    else:
        password_sha = sha.new(password).hexdigest()
    cursor.execute('SELECT id, password, active FROM res_user '
        'WHERE login = %s', (loginname,))
    if cursor.rowcount:
        res = cursor.fetchone()
        cursor.close()
        user_id = res[0]
        if user_id == 0:
            return False
        _USER_TRY[dbname].setdefault(user_id, 0)
        if res[1] == password_sha and res[2]:
            _USER_TRY[dbname][user_id] = 0
            if cache:
                _USER_CACHE.setdefault(dbname, {})
                _USER_CACHE[dbname].setdefault(user_id, [])
                session = Session(user_id)
                _USER_CACHE[dbname][user_id].append(session)
                return (user_id, session.session)
            else:
                return user_id
        time.sleep(2 ** _USER_TRY[dbname][user_id])
        _USER_TRY[dbname][user_id] += 1
        return False
    cursor.close()
    _USER_TRY[dbname].setdefault(0, 0)
    time.sleep(2 ** _USER_TRY[dbname][0])
    _USER_TRY[dbname][0] += 1
    return False

def check_super(passwd):
    if passwd == CONFIG['admin_passwd']:
        return True
    else:
        raise Exception('AccessDenied')

def check(dbname, user, session, outdate_timeout=True):
    if user == 0:
        raise Exception('AccessDenied')
    result = False
    now = time.time()
    timeout = int(CONFIG['session_timeout'])
    if _USER_CACHE.get(dbname, {}).has_key(user):
        to_del = []
        for i, real_session \
                in enumerate(_USER_CACHE[dbname][user]):
            if abs(real_session.timestamp - now) < timeout:
                if real_session.session == session:
                    if outdate_timeout:
                        real_session.reset_timestamp()
                    result = real_session
            else:
                to_del.insert(0, i)
        for i in to_del:
            del _USER_CACHE[dbname][user][i]
    if result:
        return result
    raise Exception('NotLogged')
