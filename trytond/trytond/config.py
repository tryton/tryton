#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import sys
try:
    import cdecimal
    # Use cdecimal globally
    if 'decimal' not in sys.modules:
        sys.modules['decimal'] = cdecimal
except ImportError:
    import decimal
    sys.modules['cdecimal'] = decimal
import os
import ConfigParser
import time


def get_hostname(netloc):
    if '[' in netloc and ']' in netloc:
        return netloc.split(']')[0][1:]
    elif ':' in netloc:
        return netloc.split(':')[0]
    else:
        return netloc


def get_port(netloc, protocol):
    netloc = netloc.split(']')[-1]
    if ':' in netloc:
        return int(netloc.split(':')[1])
    else:
        return {
            'jsonrpc': 8000,
            'xmlrpc': 8069,
            'webdav': 8080,
        }.get(protocol)


class ConfigManager(object):
    def __init__(self, fname=None):
        self.options = {
            'jsonrpc': [('localhost', 8000)],
            'ssl_jsonrpc': False,
            'hostname_jsonrpc': None,
            'xmlrpc': [],
            'ssl_xmlrpc': False,
            'jsondata_path': '/var/www/localhost/tryton',
            'webdav': [],
            'ssl_webdav': False,
            'hostname_webdav': None,
            'db_type': 'postgresql',
            'db_host': False,
            'db_port': False,
            'db_name': False,
            'db_user': False,
            'db_password': False,
            'db_minconn': 1,
            'db_maxconn': 64,
            'pg_path': None,
            'admin_passwd': 'admin',
            'verbose': False,
            'debug_mode': False,
            'pidfile': None,
            'logfile': None,
            'privatekey': '/etc/ssl/trytond/server.key',
            'certificate': '/etc/ssl/trytond/server.pem',
            'smtp_server': 'localhost',
            'smtp_port': 25,
            'smtp_ssl': False,
            'smtp_tls': False,
            'smtp_user': False,
            'smtp_password': False,
            'data_path': '/var/lib/trytond',
            'multi_server': False,
            'session_timeout': 600,
            'auto_reload': True,
            'prevent_dblist': False,
            'init': {},
            'update': {},
            'cron': True,
            'unoconv': 'pipe,name=trytond;urp;StarOffice.ComponentContext',
            'retry': 5,
            'language': 'en_US',
            'timezone': time.tzname[0] or time.tzname[1],
        }
        self.configfile = None

    def set_timezone(self):
        os.environ['TZ'] = self.get('timezone')
        if hasattr(time, 'tzset'):
            time.tzset()

    def update_cmdline(self, cmdline_options):
        self.options.update(cmdline_options)

        # Verify that we want to log or not,
        # if not the output will go to stdout
        if self.options['logfile'] in ('None', 'False'):
            self.options['logfile'] = False
        # the same for the pidfile
        if self.options['pidfile'] in ('None', 'False'):
            self.options['pidfile'] = False
        if self.options['data_path'] in ('None', 'False'):
            self.options['data_path'] = False

    def update_etc(self, configfile=None):
        if configfile is None:
            prefixdir = os.path.abspath(os.path.normpath(os.path.join(
                os.path.dirname(sys.prefix), '..')))
            configfile = os.path.join(prefixdir, 'etc', 'trytond.conf')
            if not os.path.isfile(configfile):
                configdir = os.path.abspath(os.path.normpath(os.path.join(
                    os.path.dirname(__file__), '..')))
                configfile = os.path.join(configdir, 'etc', 'trytond.conf')
            if not os.path.isfile(configfile):
                configfile = None

        self.configfile = configfile
        if not self.configfile:
            return

        parser = ConfigParser.ConfigParser()
        with open(self.configfile) as fp:
            parser.readfp(fp)
        for (name, value) in parser.items('options'):
            if value == 'True' or value == 'true':
                value = True
            if value == 'False' or value == 'false':
                value = False
            if name in ('xmlrpc', 'jsonrpc', 'webdav') and value:
                value = [(get_hostname(netloc).replace('*', ''),
                    get_port(netloc, name)) for netloc in value.split(',')]
            self.options[name] = value

    def get(self, key, default=None):
        return self.options.get(key, default)

    def __setitem__(self, key, value):
        self.options[key] = value

    def __getitem__(self, key):
        return self.options[key]

CONFIG = ConfigManager()
