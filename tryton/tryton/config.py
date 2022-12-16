#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
"Options"
import ConfigParser
import optparse
import os
import gettext
from version import VERSION
import logging
import sys
import locale
import gtk
import site

from tryton.exceptions import TrytonError

_ = gettext.gettext


def get_home_dir():
    if os.name == 'nt':
        return os.path.join(os.environ['HOMEDRIVE'], os.environ['HOMEPATH']
            ).decode(sys.getfilesystemencoding()).encode('utf-8')
    return os.environ['HOME']


def get_config_dir():
    if os.name == 'nt':
        return os.path.join(os.environ['APPDATA'], '.config', 'tryton',
                VERSION.rsplit('.', 1)[0])
    return os.path.join(os.environ['HOME'], '.config', 'tryton',
            VERSION.rsplit('.', 1)[0])
if not os.path.isdir(get_config_dir()):
    os.makedirs(get_config_dir(), 0700)


class ConfigManager(object):
    "Config manager"

    def __init__(self):
        short_version = '.'.join(VERSION.split('.', 2)[:2])
        demo_server = 'demo%s.tryton.org' % short_version
        demo_database = 'demo%s' % short_version
        form_tab = 'left' if os.name != 'nt' else 'top'
        self.defaults = {
            'login.profile': demo_server,
            'login.login': 'demo',
            'login.server': demo_server,
            'login.port': '8000',
            'login.db': demo_database,
            'login.expanded': False,
            'tip.autostart': False,
            'tip.position': 0,
            'form.toolbar': True,
            'client.default_width': 900,
            'client.default_height': 750,
            'client.modepda': False,
            'client.toolbar': 'default',
            'client.form_tab': form_tab,
            'client.maximize': False,
            'client.save_width_height': True,
            'client.save_tree_state': True,
            'client.spellcheck': False,
            'client.default_path': get_home_dir(),
            'client.lang': locale.getdefaultlocale()[0],
            'client.language_direction': 'ltr',
            'client.email': '',
            'client.can_change_accelerators': False,
            'client.limit': 1000,
            'roundup.url': 'http://bugs.tryton.org/roundup/',
            'roundup.xmlrpc': 'roundup-xmlrpc.tryton.org',
            'menu.pane': 200,
            'menu.expanded': True,
        }
        self.config = {}
        self.options = {
            'login.host': True
        }
        self.arguments = []

    def parse(self):
        parser = optparse.OptionParser(version=("Tryton %s" % VERSION),
                usage="Usage: %prog [options] [url]")
        parser.add_option("-c", "--config", dest="config",
                help=_("specify alternate config file"))
        parser.add_option("-d", "--dev", action="store_true",
                default=False, dest="dev",
                help=_("development mode"))
        parser.add_option("-v", "--verbose", action="store_true",
                default=False, dest="verbose",
                help=_("logging everything at INFO level"))
        parser.add_option("-l", "--log-level", dest="log_level",
                help=_("specify the log level: "
                "DEBUG, INFO, WARNING, ERROR, CRITICAL"))
        parser.add_option("-u", "--user", dest="login",
                help=_("specify the login user"))
        parser.add_option("-p", "--port", dest="port",
                help=_("specify the server port"))
        parser.add_option("-s", "--server", dest="server",
                help=_("specify the server hostname"))
        opt, self.arguments = parser.parse_args()

        if len(self.arguments) > 1:
            raise TrytonError(_('Too much arguments'))

        if opt.config and not os.path.isfile(opt.config):
            raise TrytonError(_('File "%s" not found') % (opt.config,))
        self.rcfile = opt.config or os.path.join(
            get_config_dir(), 'tryton.conf')
        self.load()

        self.options['dev'] = opt.dev
        logging.basicConfig()
        loglevels = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
            }
        if not opt.log_level:
            if opt.verbose:
                opt.log_level = 'INFO'
            else:
                opt.log_level = 'ERROR'
        logging.getLogger().setLevel(loglevels[opt.log_level.upper()])

        for arg in ('login', 'port', 'server'):
            if getattr(opt, arg):
                self.options['login.' + arg] = getattr(opt, arg)

    def save(self):
        try:
            configparser = ConfigParser.ConfigParser()
            for entry in self.config.keys():
                if not len(entry.split('.')) == 2:
                    continue
                section, name = entry.split('.')
                if not configparser.has_section(section):
                    configparser.add_section(section)
                configparser.set(section, name, self.config[entry])
            configparser.write(open(self.rcfile, 'wb'))
        except IOError:
            logging.getLogger(__name__).warn(
                _('Unable to write config file %s!')
                % (self.rcfile,))
            return False
        return True

    def load(self):
        configparser = ConfigParser.ConfigParser()
        configparser.read([self.rcfile])
        for section in configparser.sections():
            for (name, value) in configparser.items(section):
                if value.lower() == 'true':
                    value = True
                elif value.lower() == 'false':
                    value = False
                if section == 'client' and name == 'limit':
                    # First convert to float to be backward compatible with old
                    # configuration
                    value = int(float(value))
                self.config[section + '.' + name] = value
        return True

    def __setitem__(self, key, value, config=True):
        self.options[key] = value
        if config:
            self.config[key] = value

    def __getitem__(self, key):
        return self.options.get(key, self.config.get(key,
            self.defaults.get(key)))

CONFIG = ConfigManager()
if (os.name == 'nt' and hasattr(sys, 'frozen')
        and os.path.basename(sys.executable) == 'tryton.exe'):
    CURRENT_DIR = os.path.dirname(unicode(sys.executable,
        sys.getfilesystemencoding()))
else:
    CURRENT_DIR = os.path.abspath(os.path.normpath(os.path.join(
        unicode(os.path.dirname(__file__), sys.getfilesystemencoding()),
        '..')))

for dir in [CURRENT_DIR, getattr(site, 'USER_BASE', sys.prefix), sys.prefix]:
    PIXMAPS_DIR = os.path.join(dir, 'share', 'pixmaps', 'tryton')
    if os.path.isdir(PIXMAPS_DIR):
        break

TRYTON_ICON = gtk.gdk.pixbuf_new_from_file(
        os.path.join(PIXMAPS_DIR, 'tryton-icon.png').encode('utf-8'))


def _data_dir():
    data_dir = os.path.join(CURRENT_DIR, 'share', 'tryton')
    if not os.path.isdir(data_dir):
        data_dir = os.path.join(sys.prefix, 'share', 'tryton')
    return data_dir
DATA_DIR = _data_dir()
