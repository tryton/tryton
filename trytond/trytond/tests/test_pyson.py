#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
import datetime
from trytond import pyson


class PYSONTestCase(unittest.TestCase):
    '''
    Test PySON.
    '''

    def test0010Eval(self):
        '''
        Test pyson.Eval
        '''
        self.assert_(pyson.Eval('test').pyson() == {
            '__class__': 'Eval',
            'v': 'test',
            'd': '',
            })
        self.assert_(pyson.Eval('test', 'foo').pyson() == {
            '__class__': 'Eval',
            'v': 'test',
            'd': 'foo',
            })

        self.assert_(pyson.Eval('test', 'foo').types() == set([type('foo')]))
        self.assert_(pyson.Eval('test', 1).types() == set([type(1)]))

        eval = pyson.PYSONEncoder().encode(pyson.Eval('test', 0))
        self.assert_(pyson.PYSONDecoder({'test': 1}).decode(eval) == 1)
        self.assert_(pyson.PYSONDecoder().decode(eval) == 0)

    def test0020Not(self):
        '''
        Test pyson.Not
        '''
        self.assert_(pyson.Not(True).pyson() == {
            '__class__': 'Not',
            'v': True,
            })

        self.assertRaises(AssertionError, pyson.Not, 'foo')

        self.assert_(pyson.Not(True).types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.Not(True))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Not(False))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

    def test0030Bool(self):
        '''
        Test pyson.Bool
        '''
        self.assert_(pyson.Bool('test').pyson() == {
            '__class__': 'Bool',
            'v': 'test',
            })

        self.assert_(pyson.Bool('test').types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.Bool(True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool(False))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool('test'))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool(''))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool(1))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool(0))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool(['test']))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool([]))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool({'foo': 'bar'}))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Bool({}))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

    def test0040And(self):
        '''
        Test pyson.And
        '''
        self.assert_(pyson.And(True, False).pyson() == {
            '__class__': 'And',
            's': [True, False],
            })

        self.assertRaises(AssertionError, pyson.And, 'test', False)
        self.assertRaises(AssertionError, pyson.And, True, 'test')
        self.assertRaises(AssertionError, pyson.And, True, False, 'test')
        self.assertRaises(AssertionError, pyson.And, True)
        self.assertRaises(AssertionError, pyson.And)

        self.assert_(pyson.And(True, False).types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.And(True, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.And(True, True, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.And(True, False))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.And(False, True))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.And(False, False))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.And(False, False, False))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.And(True, False, False))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.And(False, True, False))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.And(False, False, True))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

    def test0050Or(self):
        '''
        Test pyson.Or
        '''
        self.assert_(pyson.Or(True, False).pyson() == {
            '__class__': 'Or',
            's': [True, False],
            })

        self.assertRaises(AssertionError, pyson.Or, 'test', False)
        self.assertRaises(AssertionError, pyson.Or, True, 'test')
        self.assertRaises(AssertionError, pyson.Or, True, False, 'test')
        self.assertRaises(AssertionError, pyson.Or, True)
        self.assertRaises(AssertionError, pyson.Or)

        self.assert_(pyson.Or(True, False).types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.Or(True, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Or(True, True, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Or(True, False))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Or(False, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Or(False, False))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Or(False, False, False))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Or(True, False, False))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Or(False, True, False))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Or(False, False, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

    def test0060Equal(self):
        '''
        Test pyson.Equal
        '''
        self.assert_(pyson.Equal('test', 'test').pyson() == {
            '__class__': 'Equal',
            's1': 'test',
            's2': 'test',
            })

        self.assertRaises(AssertionError, pyson.Equal, 'test', True)

        self.assert_(pyson.Equal('test', 'test').types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.Equal('test', 'test'))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Equal('foo', 'bar'))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

    def test0070Greater(self):
        '''
        Test pyson.Greater
        '''
        self.assert_(pyson.Greater(1, 0).pyson() == {
            '__class__': 'Greater',
            's1': 1,
            's2': 0,
            'e': False,
            })

        self.assertRaises(AssertionError, pyson.Greater, 'test', 0)
        self.assertRaises(AssertionError, pyson.Greater, 1, 'test')
        self.assertRaises(AssertionError, pyson.Greater, 1, 0, 'test')

        self.assert_(pyson.Greater(1, 0).types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.Greater(1, 0))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Greater(0, 1))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Greater(1, 0, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Greater(0, 1, True))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Greater(1, 1))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Greater(1, 1, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

    def test0080Less(self):
        '''
        Test pyson.Less
        '''
        self.assert_(pyson.Less(0, 1).pyson() == {
            '__class__': 'Less',
            's1': 0,
            's2': 1,
            'e': False,
            })

        self.assertRaises(AssertionError, pyson.Less, 'test', 1)
        self.assertRaises(AssertionError, pyson.Less, 0, 'test')
        self.assertRaises(AssertionError, pyson.Less, 0, 1, 'test')

        self.assert_(pyson.Less(0, 1).types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.Less(0, 1))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Less(1, 0))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Less(0, 1, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Less(1, 0, True))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Less(1, 1))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.Less(1, 1, True))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

    def test0090If(self):
        '''
        Test pyson.If
        '''
        self.assert_(pyson.If(True, 'foo', 'bar').pyson() == {
            '__class__': 'If',
            'c': True,
            't': 'foo',
            'e': 'bar',
            })

        self.assertRaises(AssertionError, pyson.If, 'test', 'foo', 'bar')
        self.assertRaises(AssertionError, pyson.If, True, 'foo', False)

        self.assertEqual(pyson.If(True, 'foo', 'bar').types(),
            set([type('foo')]))
        self.assert_(pyson.If(True, False, True).types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.If(True, 'foo', 'bar'))
        self.assert_(pyson.PYSONDecoder().decode(eval) == 'foo')

        eval = pyson.PYSONEncoder().encode(pyson.If(False, 'foo', 'bar'))
        self.assert_(pyson.PYSONDecoder().decode(eval) == 'bar')

    def test0100Get(self):
        '''
        Test pyson.Get
        '''
        self.assert_(pyson.Get({'foo': 'bar'}, 'foo', 'default').pyson() == {
            '__class__': 'Get',
            'v': {'foo': 'bar'},
            'k': 'foo',
            'd': 'default',
            })

        self.assertRaises(AssertionError, pyson.Get, 'test', 'foo', 'default')
        self.assertRaises(AssertionError, pyson.Get, {}, 1, 'default')

        self.assert_(pyson.Get({}, 'foo', 'default').types() == set([str]))
        self.assert_(pyson.Get({}, 'foo', True).types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.Get(
            {'foo': 'bar'}, 'foo', 'default'))
        self.assert_(pyson.PYSONDecoder().decode(eval) == 'bar')

        eval = pyson.PYSONEncoder().encode(pyson.Get(
            {'foo': 'bar'}, 'test', 'default'))
        self.assert_(pyson.PYSONDecoder().decode(eval) == 'default')

        eval = pyson.PYSONEncoder().encode(pyson.Get(
            {}, 'foo', 'default'))
        self.assert_(pyson.PYSONDecoder().decode(eval) == 'default')

    def test0110In(self):
        '''
        Test pyson.In
        '''
        self.assert_(pyson.In('foo', {'foo': 'bar'}).pyson() == {
            '__class__': 'In',
            'k': 'foo',
            'v': {'foo': 'bar'},
            })

        self.assertRaises(AssertionError, pyson.In, object(), {})
        self.assertRaises(AssertionError, pyson.In, 'test', 'foo')

        self.assert_(pyson.In('foo', {}).types() == set([bool]))

        eval = pyson.PYSONEncoder().encode(pyson.In('foo', {'foo': 'bar'}))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In('1', {1: 'bar'}))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In('test', {'foo': 'bar'}))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In('1', {2: 'bar'}))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In('test', {}))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In('foo', ['foo']))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In(1, [1]))
        self.assertTrue(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In('test', ['foo']))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In(1, [2]))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

        eval = pyson.PYSONEncoder().encode(pyson.In('test', []))
        self.assertFalse(pyson.PYSONDecoder().decode(eval))

    def test0120Date(self):
        '''
        Test pyson.Date
        '''
        self.assert_(pyson.Date(2010, 1, 12, -1, 12, -7).pyson() == {
            '__class__': 'Date',
            'y': 2010,
            'M': 1,
            'd': 12,
            'dy': -1,
            'dM': 12,
            'dd': -7
            })

        self.assertRaises(AssertionError, pyson.Date, 'test', 1, 12, -1, 12,
                -7)
        self.assertRaises(AssertionError, pyson.Date, 2010, 'test', 12, -1, 12,
                -7)
        self.assertRaises(AssertionError, pyson.Date, 2010, 1, 'test', -1, 12,
                -7)
        self.assertRaises(AssertionError, pyson.Date, 2010, 1, 12, 'test', 12,
                -7)
        self.assertRaises(AssertionError, pyson.Date, 2010, 1, 12, -1, 'test',
                -7)
        self.assertRaises(AssertionError, pyson.Date, 2010, 1, 12, -1, 12,
                'test')

        self.assert_(pyson.Date(2010, 1, 12, -1, 12, -7).types()
                == set([datetime.date]))

        eval = pyson.PYSONEncoder().encode(pyson.Date())
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.date.today())

        eval = pyson.PYSONEncoder().encode(pyson.Date(2010, 1, 12))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.date(2010, 1, 12))

        eval = pyson.PYSONEncoder().encode(pyson.Date(2010, 1, 12, -1))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.date(2009, 1, 12))

        eval = pyson.PYSONEncoder().encode(pyson.Date(2010, 1, 12, 0, 12))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.date(2011, 1, 12))

        eval = pyson.PYSONEncoder().encode(pyson.Date(2010, 1, 12, 0, 0, -7))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.date(2010, 1, 5))

        eval = pyson.PYSONEncoder().encode(datetime.date(2010, 2, 22))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.date(2010, 2, 22))

    def test0130DateTime(self):
        '''
        Test pyson.DateTime
        '''
        self.assert_(pyson.DateTime(2010, 1, 12, 10, 30, 20, 0,
            -1, 12, -7, 2, 15, 30, 1).pyson() == {
                '__class__': 'DateTime',
                'y': 2010,
                'M': 1,
                'd': 12,
                'h': 10,
                'm': 30,
                's': 20,
                'ms': 0,
                'dy': -1,
                'dM': 12,
                'dd': -7,
                'dh': 2,
                'dm': 15,
                'ds': 30,
                'dms': 1,
                })

        self.assertRaises(AssertionError, pyson.DateTime, 'test', 1, 12, 10,
                30, 20, 0, -1, 12, -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 'test', 12, 10,
                30, 20, 0, -1, 12, -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 'test', 10,
                30, 20, 0, -1, 12, -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 'test',
                30, 20, 0, -1, 12, -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10,
                'test', 20, 0, -1, 12, -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                'test', 0, -1, 12, -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                20, 'test', -1, 12, -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                20, 0, 'test', 12, -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                20, 0, -1, 'test', -7, 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                20, 0, -1, 12, 'test', 2, 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                20, 0, -1, 12, -7, 'test', 15, 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                20, 0, -1, 12, -7, 2, 'test', 30, 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                20, 0, -1, 12, -7, 2, 15, 'test', 1)
        self.assertRaises(AssertionError, pyson.DateTime, 2010, 1, 12, 10, 30,
                20, 0, -1, 12, -7, 2, 15, 30, 'test')

        self.assert_(pyson.DateTime(2010, 1, 12, 10, 30, 20, 0,
            -1, 12, -7, 2, 15, 30, 1).types() == set([datetime.datetime]))

        eval = pyson.PYSONEncoder().encode(pyson.DateTime(2010, 1, 12,
            10, 30, 20, 0))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2010, 1, 12, 10, 30, 20, 0))

        eval = pyson.PYSONEncoder().encode(pyson.DateTime(2010, 1, 12,
            10, 30, 20, 0, -1))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2009, 1, 12, 10, 30, 20, 0))

        eval = pyson.PYSONEncoder().encode(pyson.DateTime(2010, 1, 12,
            10, 30, 20, 0, 0, 12))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2011, 1, 12, 10, 30, 20, 0))

        eval = pyson.PYSONEncoder().encode(pyson.DateTime(2010, 1, 12,
            10, 30, 20, 0, 0, 0, -7))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2010, 1, 5, 10, 30, 20, 0))

        eval = pyson.PYSONEncoder().encode(pyson.DateTime(2010, 1, 12,
            10, 30, 20, 0, 0, 0, 0, 12))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2010, 1, 12, 22, 30, 20, 0))

        eval = pyson.PYSONEncoder().encode(pyson.DateTime(2010, 1, 12,
            10, 30, 20, 0, 0, 0, 0, 0, -30))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2010, 1, 12, 10, 0, 20, 0))

        eval = pyson.PYSONEncoder().encode(pyson.DateTime(2010, 1, 12,
            10, 30, 20, 0, 0, 0, 0, 0, 0, 30))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2010, 1, 12, 10, 30, 50, 0))

        eval = pyson.PYSONEncoder().encode(pyson.DateTime(2010, 1, 12,
            10, 30, 20, 0, 0, 0, 0, 0, 0, 0, 200))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2010, 1, 12, 10, 30, 20, 200))

        eval = pyson.PYSONEncoder().encode(datetime.datetime(
            2010, 2, 22, 10, 30, 20, 200))
        self.assert_(pyson.PYSONDecoder().decode(eval)
                == datetime.datetime(2010, 2, 22, 10, 30, 20, 200))

    def test0900Composite(self):
        '''
        Test Composite
        '''

        eval = pyson.PYSONEncoder().encode(['id', pyson.If(pyson.Not(
            pyson.In('company', pyson.Eval('context', {}))), '=', '!='),
            pyson.Get(pyson.Eval('context', {}), 'company', 0)])
        self.assert_(pyson.PYSONDecoder({'context': {'company': 1}}
            ).decode(eval) == ['id', '!=', 1])
        self.assert_(pyson.PYSONDecoder({'context': {}}
            ).decode(eval) == ['id', '=', 0])


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(PYSONTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
