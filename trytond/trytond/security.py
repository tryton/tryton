#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import pooler
from config import CONFIG
import sha
import time
import random

_USER_CACHE = {}
_USER_TRY = {}

def login(dbname, loginname, password, cache=True):
    _USER_TRY.setdefault(dbname, {})
    cursor = pooler.get_db(dbname).cursor()
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
                timestamp = time.time()
                session = str(random.random())
                _USER_CACHE[dbname].setdefault(user_id, [])
                _USER_CACHE[dbname][user_id].append((timestamp, session))
                return (user_id, session)
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
    if _USER_CACHE.get(dbname, {}).has_key(user):
        to_del = []
        for i, (timestamp, real_session) \
                in enumerate(_USER_CACHE[dbname][user]):
            if abs(timestamp - time.time()) < int(CONFIG['session_timeout']):
                if real_session == session:
                    if outdate_timeout:
                        _USER_CACHE[dbname][user][i] = \
                                (time.time(), real_session)
                    result = True
            else:
                to_del.insert(0, i)
        for i in to_del:
            del _USER_CACHE[dbname][user][i]
    if result:
        return True
    raise Exception('NotLogged')
