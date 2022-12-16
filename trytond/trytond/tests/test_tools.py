# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import unittest
import datetime
import sql
import sql.operators

from trytond.tools import reduce_ids, safe_eval, datetime_strftime, \
    reduce_domain


class ToolsTestCase(unittest.TestCase):
    'Test tools'
    table = sql.Table('test')

    def test0000reduce_ids_empty(self):
        'Test reduce_ids empty list'
        self.assertEqual(reduce_ids(self.table.id, []), sql.Literal(False))

    def test0010reduce_ids_continue(self):
        'Test reduce_ids continue list'
        self.assertEqual(reduce_ids(self.table.id, range(10)),
            sql.operators.Or(((self.table.id >= 0) & (self.table.id <= 9),)))

    def test0020reduce_ids_one_hole(self):
        'Test reduce_ids continue list with one hole'
        self.assertEqual(reduce_ids(self.table.id, range(10) + range(20, 30)),
            ((self.table.id >= 0) & (self.table.id <= 9))
            | ((self.table.id >= 20) & (self.table.id <= 29)))

    def test0030reduce_ids_short_continue(self):
        'Test reduce_ids short continue list'
        self.assertEqual(reduce_ids(self.table.id, range(4)),
            sql.operators.Or((self.table.id.in_(range(4)),)))

    def test0040reduce_ids_complex(self):
        'Test reduce_ids complex list'
        self.assertEqual(reduce_ids(self.table.id,
                range(10) + range(25, 30) + range(15, 20)),
            (((self.table.id >= 0) & (self.table.id <= 14))
                | (self.table.id.in_(range(25, 30)))))

    def test0050reduce_ids_complex_small_continue(self):
        'Test reduce_ids complex list with small continue'
        self.assertEqual(reduce_ids(self.table.id,
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 18, 19, 21]),
            (((self.table.id >= 1) & (self.table.id <= 12))
                | (self.table.id.in_([15, 18, 19, 21]))))

    def test0055reduce_ids_float(self):
        'Test reduce_ids with integer as float'
        self.assertEqual(reduce_ids(self.table.id,
                [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0,
                    15.0, 18.0, 19.0, 21.0]),
            (((self.table.id >= 1.0) & (self.table.id <= 12.0))
                | (self.table.id.in_([15.0, 18.0, 19.0, 21.0]))))
        self.assertRaises(AssertionError, reduce_ids, self.table.id, [1.1])

    def test0060safe_eval_builtin(self):
        'Attempt to access a unsafe builtin'
        self.assertRaises(NameError, safe_eval, "open('test.txt', 'w')")

    def test0061safe_eval_getattr(self):
        'Attempt to get arround direct attr access'
        self.assertRaises(NameError, safe_eval, "getattr(int, 'real')")

    def test0062safe_eval_func_globals(self):
        'Attempt to access global enviroment where fun was defined'
        self.assertRaises(SyntaxError, safe_eval,
                "def x(): pass; print x.func_globals")

    def test0063safe_eval_lowlevel(self):
        "Lowlevel tricks to access 'object'"
        self.assertRaises(ValueError, safe_eval,
                "().__class__.mro()[1].__subclasses__()")

    def test0070datetime_strftime(self):
        'Test datetime_strftime'
        self.assert_(datetime_strftime(datetime.date(2005, 3, 2),
            '%Y-%m-%d'), '2005-03-02')
        self.assert_(datetime_strftime(datetime.date(1805, 3, 2),
            '%Y-%m-%d'), '1805-03-02')

    def test_reduce_domain(self):
        'Test reduce_domain'
        clause = ('x', '=', 'x')
        tests = (
            ([clause], ['AND', clause]),
            ([clause, [clause]], ['AND', clause, clause]),
            (['AND', clause, [clause]], ['AND', clause, clause]),
            ([clause, ['AND', clause]], ['AND', clause, clause]),
            ([clause, ['AND', clause, clause]],
                ['AND', clause, clause, clause]),
            (['AND', clause, ['AND', clause]], ['AND', clause, clause]),
            ([[[clause]]], ['AND', clause]),
            (['OR', clause], ['OR', clause]),
            (['OR', clause, [clause]], ['OR', clause, ['AND', clause]]),
            (['OR', clause, [clause, clause]],
                ['OR', clause, ['AND', clause, clause]]),
            (['OR', clause, ['OR', clause]], ['OR', clause, clause]),
            (['OR', clause, [clause, ['OR', clause, clause]]],
                ['OR', clause, ['AND', clause, ['OR', clause, clause]]]),
            (['OR', [clause]], ['OR', ['AND', clause]]),
            ([], []),
            (['OR', clause, []], ['OR', clause, []]),
            (['AND', clause, []], ['AND', clause, []]),
        )
        for i, j in tests:
            self.assertEqual(reduce_domain(i), j,
                    '%s -> %s != %s' % (i, reduce_domain(i), j))


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in (ToolsTestCase,):
        suite.addTests(func(testcase))
    return suite
