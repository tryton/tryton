#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
# -*- coding: utf-8 -*-
"""
Miscelleanous tools used by tryton
"""
import os, time, sys
import inspect
from trytond.config import CONFIG
import socket
import zipfile
from trytond import pooler
from threading import Lock
import logging
try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

def find_in_path(name):
    if os.name == "nt":
        sep = ';'
    else:
        sep = ':'
    path = [directory for directory in os.environ['PATH'].split(sep)
            if os.path.isdir(directory)]
    for directory in path:
        val = os.path.join(directory, name)
        if os.path.isfile(val) or os.path.islink(val):
            return val
    return None

def find_pg_tool(name):
    if CONFIG['pg_path'] and CONFIG['pg_path'] != 'None':
        return os.path.join(CONFIG['pg_path'], name)
    else:
        return find_in_path(name)

def exec_pg_command(name, *args):
    prog = find_pg_tool(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    args2 = (os.path.basename(prog),) + args
    return os.spawnv(os.P_WAIT, prog, args2)

def exec_pg_command_pipe(name, *args):
    prog = find_pg_tool(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    if os.name == "nt":
        cmd = '"' + prog + '" ' + ' '.join(args)
    else:
        cmd = prog + ' ' + ' '.join(args)
    return os.popen2(cmd, 'b')

def exec_command_pipe(name, *args):
    prog = find_in_path(name)
    if not prog:
        raise Exception('Couldn\'t find %s' % name)
    if os.name == "nt":
        cmd = '"'+prog+'" '+' '.join(args)
    else:
        cmd = prog+' '+' '.join(args)
    return os.popen2(cmd, 'b')

def file_open(name, mode="r", subdir='modules'):
    """Open a file from the root dir, using a subdir folder."""
    from trytond.modules import EGG_MODULES
    root_path = os.path.dirname(os.path.dirname(__file__))

    name3 = False
    if subdir == 'modules':
        module_name = name.split(os.sep)[0]
        if module_name in EGG_MODULES:
            ep = EGG_MODULES[module_name]
            mod_path = os.path.join(ep.dist.location,
                    *ep.module_name.split('.')[:-1])
            name3 = os.path.join(mod_path, name)

    if subdir:
        if subdir == 'modules'\
                and (name.startswith('ir' + os.sep) \
                    or name.startswith('workflow' + os.sep) \
                    or name.startswith('res' + os.sep) \
                    or name.startswith('webdav' + os.sep)):
            name = os.path.join(root_path, name)
        else:
            name = os.path.join(root_path, subdir, name)
    else:
        name = os.path.join(root_path, name)

    # Check for a zipfile in the path
    head = name
    zipname = False
    name2 = False
    while True:
        head, tail = os.path.split(head)
        if not tail:
            break
        if zipname:
            zipname = os.path.join(tail, zipname)
        else:
            zipname = tail
        if zipfile.is_zipfile(head+'.zip'):
            zfile = zipfile.ZipFile(head+'.zip')
            try:
                return StringIO.StringIO(zfile.read(os.path.join(
                    os.path.basename(head), zipname).replace(
                        os.sep, '/')))
            except:
                name2 = os.path.normpath(os.path.join(head + '.zip', zipname))
    for i in (name2, name, name3):
        if i and os.path.isfile(i):
            return file(i, mode)

    raise IOError, 'File not found : '+str(name)

def email_send(email_from, email_to, subject, body, email_cc=None,
        email_bcc=None, reply_to=False, tinycrm=False):
    """Send an email."""
    if not email_cc:
        email_cc = []
    if not email_bcc:
        email_bcc = []
    import smtplib
    from email.MIMEText import MIMEText
    from email.Header import Header
    from email.Utils import formatdate, COMMASPACE

    msg = MIMEText(body or '', _charset='utf-8')
    msg['Subject'] = Header(subject.decode('utf8'), 'utf-8')
    msg['From'] = email_from
    del msg['Reply-To']
    if reply_to:
        msg['Reply-To'] = msg['From']+', '+reply_to
    msg['To'] = COMMASPACE.join(email_to)
    if email_cc:
        msg['Cc'] = COMMASPACE.join(email_cc)
    if email_bcc:
        msg['Bcc'] = COMMASPACE.join(email_bcc)
    msg['Date'] = formatdate(localtime=True)
    if tinycrm:
        msg['Message-Id'] = '<' + str(time.time()) + '-tinycrm-' + \
                str(tinycrm) + '@' + socket.gethostname() + '>'
    try:
        smtp = smtplib.SMTP()
        smtp.connect(CONFIG['smtp_server'])
        if CONFIG['smtp_user'] or CONFIG['smtp_password']:
            smtp.login(CONFIG['smtp_user'], CONFIG['smtp_password'])
        smtp.sendmail(email_from, email_to + email_cc + email_bcc,
                msg.as_string())
        smtp.quit()
    except Exception, exp:
        logging.getLogger("web-service").error(str(exp))
    return True

def email_send_attach(email_from, email_to, subject, body, email_cc=None,
        email_bcc=None, reply_to=False, attach=None,
        tinycrm=False):
    """Send an email."""
    if not email_cc:
        email_cc = []
    if not email_bcc:
        email_bcc = []
    if not attach:
        attach = []
    import smtplib
    from email.MIMEText import MIMEText
    from email.MIMEBase import MIMEBase
    from email.MIMEMultipart import MIMEMultipart
    from email.Header import Header
    from email.Utils import formatdate, COMMASPACE
    from email import Encoders

    msg = MIMEMultipart()

    msg['Subject'] = Header(subject.decode('utf8'), 'utf-8')
    msg['From'] = email_from
    del msg['Reply-To']
    if reply_to:
        msg['Reply-To'] = reply_to
    msg['To'] = COMMASPACE.join(email_to)
    if email_cc:
        msg['Cc'] = COMMASPACE.join(email_cc)
    if email_bcc:
        msg['Bcc'] = COMMASPACE.join(email_bcc)
    if tinycrm:
        msg['Message-Id'] = '<' + str(time.time()) + '-tinycrm-' + \
                str(tinycrm) + '@' + socket.gethostname()+'>'
    msg['Date'] = formatdate(localtime=True)
    msg.attach( MIMEText(body or '', _charset='utf-8') )
    for (fname, fcontent) in attach:
        part = MIMEBase('application', "octet-stream")
        part.set_payload( fcontent )
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                'attachment; filename="%s"' % (fname,))
        msg.attach(part)
    try:
        smtp = smtplib.SMTP()
        smtp.connect(CONFIG['smtp_server'])
        if CONFIG['smtp_user'] or CONFIG['smtp_password']:
            smtp.login(CONFIG['smtp_user'], CONFIG['smtp_password'])
        smtp.sendmail(email_from, email_to + email_cc + email_bcc,
                msg.as_string())
        smtp.quit()
    except Exception, exp:
        logging.getLogger("web-service").error(str(exp))

    return True

def sms_send(user, password, api_id, text, to):
    "text must be latin-1 encoded"
    import urllib
    params = urllib.urlencode({
        'user': user,
        'password': password,
        'api_id': api_id,
        'text': text,
        'to':to,
        })
    #urllib.urlopen("http://api.clickatell.com/http/sendmsg", params)
    urllib.urlopen("http://196.7.150.220/http/sendmsg", params)
    return True

def find_language_context(args):
    res = 'en_US'
    for arg in args:
        if isinstance(arg, dict):
            res = arg.get('language', 'en_US')
    return res


class Cache(object):
    """
    Use it as a decorator of the function you plan to cache
    Timeout: 0 = no timeout, otherwise in seconds
    """
    _cache_instance = []
    _resets = {}
    _resets_lock = Lock()

    def __init__(self, name, timeout=3600, max_len=1024):
        self.timeout = timeout
        self.max_len = max_len
        self._cache = {}
        self._cache_instance.append(self)
        self.name = name
        self.timestamp = None
        self.lock = Lock()

    def __call__(self, function):
        arg_names = inspect.getargspec(function)[0][2:]

        def cached_result(self2, cursor=None, *args, **kwargs):
            result = None
            if isinstance(cursor, basestring):
                Cache.reset(cursor, self.name)
                self.lock.acquire()
                try:
                    self._cache[cursor] = {}
                finally:
                    self.lock.release()
                return True
            # Update named arguments with positional argument values
            kwargs.update(dict(zip(arg_names, args)))
            kwargs = kwargs.items()
            kwargs.sort()

            self.lock.acquire()
            try:
                self._cache.setdefault(cursor.dbname, {})
            finally:
                self.lock.release()

            lower = None
            self.lock.acquire()
            try:
                if len(self._cache[cursor.dbname]) > self.max_len:
                    mintime = time.time() - self.timeout
                    for key in self._cache[cursor.dbname].keys():
                        last_time = self._cache[cursor.dbname][key][1]
                        if mintime > last_time:
                            del self._cache[cursor.dbname][key]
                        else:
                            if not lower or lower[1] > last_time:
                                lower = (key, last_time)
                if len(self._cache[cursor.dbname]) > self.max_len and lower:
                    del self._cache[cursor.dbname][lower[0]]
            finally:
                self.lock.release()

            # Work out key as a tuple of ('argname', value) pairs
            key = (id(self2), str(kwargs))

            # Check cache and return cached value if possible
            self.lock.acquire()
            try:
                if key in self._cache[cursor.dbname]:
                    (value, last_time) = self._cache[cursor.dbname][key]
                    mintime = time.time() - self.timeout
                    if self.timeout <= 0 or mintime <= last_time:
                        result = value
            finally:
                self.lock.release()

            if not result:
                # Work out new value, cache it and return it
                # Should copy() this value to avoid futur modf of the cacle ?
                result = function(self2, cursor, **dict(kwargs))

                self.lock.acquire()
                try:
                    self._cache[cursor.dbname][key] = (result, time.time())
                finally:
                    self.lock.release()
            return result

        return cached_result

    @staticmethod
    def clean(dbname):
        if not CONFIG['multi_server']:
            return
        cursor = pooler.get_db(dbname).cursor()
        try:
            cursor.execute('SELECT "timestamp", "name" FROM ir_cache')
            timestamps = {}
            for timestamp, name in cursor.fetchall():
                timestamps[name] = timestamp
        finally:
            cursor.commit()
            cursor.close()
        for obj in Cache._cache_instance:
            if obj.name in timestamps:
                if not obj.timestamp or timestamps[obj.name] > obj.timestamp:
                    obj.timestamp = timestamps[obj.name]
                    obj.lock.acquire()
                    try:
                        obj._cache[dbname] = {}
                    finally:
                        obj.lock.release()

    @staticmethod
    def reset(dbname, name):
        if not CONFIG['multi_server']:
            return
        Cache._resets_lock.acquire()
        try:
            Cache._resets.setdefault(dbname, set())
            Cache._resets[dbname].add(name)
        finally:
            Cache._resets_lock.release()
        return

    @staticmethod
    def resets(dbname):
        if not CONFIG['multi_server']:
            return
        cursor = pooler.get_db(dbname).cursor()
        Cache._resets_lock.acquire()
        Cache._resets.setdefault(dbname, set())
        try:
            for name in Cache._resets[dbname]:
                cursor.execute('SELECT name FROM ir_cache WHERE name = %s',
                            (name,))
                if cursor.rowcount:
                    cursor.execute('UPDATE ir_cache SET "timestamp" = now() '\
                            'WHERE name = %s', (name,))
                else:
                    cursor.execute('INSERT INTO ir_cache ("timestamp", "name") ' \
                            'VALUES (now(), %s)', (name,))
            Cache._resets[dbname].clear()
        finally:
            cursor.commit()
            cursor.close()
            Cache._resets_lock.release()


def mod10r(number):
    """
    Recursive mod10

    :param number: a number
    :return: the same number completed with the recursive modulo base 10
    """
    codec = [0, 9, 4, 6, 8, 2, 7, 1, 3, 5]
    report = 0
    result = ""
    for digit in number:
        result += digit
        if digit.isdigit():
            report = codec[ (int(digit) + report) % 10 ]
    return result + str((10 - report) % 10)
