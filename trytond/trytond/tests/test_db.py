#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
import time
from trytond import pysocket

ADMIN_PASSWORD = 'admin'
HOST = '127.0.0.1'
PORT = '8070'
DB_NAME = 'test_' + str(int(time.time()))
USERNAME = 'admin'
PASSWORD = 'admin'
CONTEXT = {}
USER = None
SESSION = None

SOCK = pysocket.PySocket()
SOCK.connect(HOST, PORT)

class DBTestCase(unittest.TestCase):
    '''
    Test DB service.
    '''

    def test0010create(self):
        '''
        Create database.
        '''
        SOCK.send(('db', 'create', ADMIN_PASSWORD, DB_NAME, 'en_US', PASSWORD))
        res = SOCK.receive()
        self.assert_(res)

    def test0020list(self):
        '''
        List databases.
        '''
        SOCK.send(('db', 'list'))
        res = SOCK.receive()
        self.assert_(DB_NAME in res)

    def test0030login(self):
        '''
        Login.
        '''
        login()


class RPCProxy(object):

    def __init__(self, name):
        self.name = name
        self.__attrs = {}

    def __getattr__(self, attr):
        if attr not in self.__attrs:
            self.__attrs[attr] = RPCFunction(self.name, attr)
        return self.__attrs[attr]


class RPCFunction(object):

    def __init__(self, name, func_name):
        self.name = name
        self.func_name = func_name

    def __call__(self, *args):
        SOCK.send(('object', 'execute', DB_NAME, USER, SESSION, self.name,
            self.func_name) + args)
        res = SOCK.receive()
        return res

def login():
    global USER, SESSION, CONTEXT
    SOCK.send(('common', 'login', DB_NAME, USERNAME, PASSWORD))
    USER, SESSION = SOCK.receive()
    user = RPCProxy('res.user')
    context = user.get_preferences(True, {})
    for i in context:
        value = context[i]
        CONTEXT[i] = value

def install_module(name):
    module = RPCProxy('ir.module.module')
    module_ids = module.search([
        ('name', '=', name),
        ('state', '!=', 'installed'),
        ])

    if not module_ids:
        return

    module.button_install(module_ids, CONTEXT)

    SOCK.send(('wizard', 'create', DB_NAME, USER, SESSION,
        'ir.module.module.install_upgrade'))
    wiz_id = SOCK.receive()

    SOCK.send(('wizard', 'execute', DB_NAME, USER, SESSION, wiz_id, {},
        'start', CONTEXT))
    SOCK.receive()

    SOCK.send(('wizard', 'delete', DB_NAME, USER, SESSION, wiz_id))
    SOCK.receive()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(DBTestCase)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
    SOCK.disconnect()
