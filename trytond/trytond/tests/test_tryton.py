#!/usr/bin/env python
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

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
        SOCK.send((None, None, None, 'common', 'db', 'create', DB_NAME,
            ADMIN_PASSWORD, 'en_US', PASSWORD))
        res = SOCK.receive()
        self.assert_(res)

    def test0020list(self):
        '''
        List databases.
        '''
        SOCK.send((None, None, None, 'common', 'db', 'list'))
        res = SOCK.receive()
        self.assert_(DB_NAME in res)

    def test0030login(self):
        '''
        Login.
        '''
        login()


class MPTTTestCase(unittest.TestCase):
    '''
    Test Modified Preorder Tree Traversal.
    '''

    def setUp(self):
        install_module('tests')
        self.mptt = RPCProxy('tests.mptt')

    def CheckTree(self, parent_id=False, left=0, right=0):
        child_ids = self.mptt.search([
            ('parent', '=', parent_id),
            ], 0, None, None, CONTEXT)
        childs = self.mptt.read(child_ids, ['left', 'right'], CONTEXT)
        childs.sort(lambda x, y: cmp(child_ids.index(x['id']),
            child_ids.index(y['id'])))
        for child in childs:
            assert child['left'] > left, \
                    'Record (%d): left %d <= parent left %d' % \
                    (child['id'], child['left'], left)
            assert child['left'] < child['right'], \
                    'Record (%d): left %d >= right %d' % \
                    (child['id'], child['left'], child['right'])
            assert right == 0 or child['right'] < right, \
                    'Record (%d): right %d >= parent right %d' % \
                    (child['id'], child['right'], right)
            self.CheckTree(child['id'], left=child['left'],
                    right=child['right'])
        next_left = 0
        for child in childs:
            assert child['left'] > next_left, \
                    'Record (%d): left %d <= next left %d' % \
                    (child['id'], child['left'], next_left)
            next_left = child['right']
        childs.reverse()
        previous_right = 0
        for child in childs:
            assert previous_right == 0 or child['right'] < previous_right, \
                    'Record (%d): right %d >= previous right %d' % \
                    (child['id'] , child['right'], previous_right)
            previous_right = child['left']

    def test0010create(self):
        '''
        Create tree.
        '''
        new_records = [False]
        for j in range(3):
            parent_records = new_records
            new_records = []
            k = 0
            for parent_record in parent_records:
                for i in range(3):
                    record_id = self.mptt.create({
                        'name': 'Test %d %d %d' % (j, k, i),
                        'parent': parent_record,
                        }, CONTEXT)
                    new_records.append(record_id)
                k += 1
        self.CheckTree()

    def test0020reorder(self):
        '''
        Re-order.
        '''
        def reorder(parent_id=False):
            record_ids = self.mptt.search([
                ('parent', '=', parent_id),
                ], CONTEXT)
            if not record_ids:
                return
            i = len(record_ids)
            for record_id in record_ids:
                self.mptt.write(record_id, {
                    'sequence': i,
                    }, CONTEXT)
                i -= 1
                self.CheckTree()
            i = 0
            for record_id in record_ids:
                self.mptt.write(record_id, {
                    'sequence': i,
                    }, CONTEXT)
                i += 1
                self.CheckTree()
            for record_id in record_ids:
                reorder(record_id)
        reorder()
        record_ids = self.mptt.search([], CONTEXT)
        self.mptt.write(record_ids, {
            'sequence': 0,
            }, CONTEXT)
        self.CheckTree()

    def test0030reparent(self):
        '''
        Re-parent.
        '''
        def reparent(parent_id=False):
            record_ids = self.mptt.search([
                ('parent', '=', parent_id),
                ], CONTEXT)
            if not record_ids:
                return
            for record_id in record_ids:
                for record2_id in record_ids:
                    if record_id != record2_id:
                        self.mptt.write(record_id, {
                            'parent': record2_id,
                            }, CONTEXT)
                        self.CheckTree()
                        self.mptt.write(record_id, {
                            'parent': parent_id,
                            }, CONTEXT)
                        self.CheckTree()
            for record_id in record_ids:
                reparent(record_id)
        reparent()

    def test0040delete(self):
        '''
        Delete.
        '''
        record_ids = self.mptt.search([], CONTEXT)
        for record_id in record_ids:
            if record_id % 2:
                self.mptt.delete(record_id, CONTEXT)
                self.CheckTree()
        record_ids = self.mptt.search([], CONTEXT)
        self.mptt.delete(record_ids[:len(record_ids)/2], CONTEXT)
        self.CheckTree()
        record_ids = self.mptt.search([], CONTEXT)
        self.mptt.delete(record_ids, CONTEXT)
        self.CheckTree()


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
        SOCK.send((DB_NAME, USER, SESSION, 'model', self.name, self.func_name) \
                + args)
        res = SOCK.receive()
        return res

def login():
    global USER, SESSION, CONTEXT
    SOCK.send((DB_NAME, USERNAME, PASSWORD, 'common', 'db', 'login'))
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

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'create'))
    wiz_id = SOCK.receive()

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'execute', wiz_id, {}, 'start',
        CONTEXT))
    SOCK.receive()

    SOCK.send((DB_NAME, USER, SESSION, 'wizard',
        'ir.module.module.install_upgrade', 'delete', wiz_id))
    SOCK.receive()

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(DBTestCase)

if __name__ == '__main__':
    suite = suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(MPTTTestCase))
    unittest.TextTestRunner(verbosity=2).run(suite)
    SOCK.disconnect()
