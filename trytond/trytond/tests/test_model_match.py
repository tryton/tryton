# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest

from trytond.model import MatchMixin, fields


class Model(MatchMixin):
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        self._fields = {}
        for k, (f, v) in kwargs.items():
            setattr(self, k, v)
            self._fields[k] = f

    def __repr__(self):
        return f"Model(**{self._kwargs})"


class Target():
    def __init__(self, id):
        self.id = id

    def __repr__(self):
        return f"Target({self.id})"


class ModelMatchMixinTestCase(unittest.TestCase):
    "Test MatchMixin"

    def test_match(self):
        "Test match"
        for record, pattern, result in [
                (Model(f=(fields.Char("F"), 'foo')), {'f': 'foo'}, True),
                (Model(f=(fields.Char("F"), 'foo')), {'f': 'bar'}, False),
                (Model(f=(fields.Char("F"), 'foo')), {'f': None}, False),
                (Model(f=(fields.Char("F"), None)), {'f': 'foo'}, True),
                (Model(f=(fields.Char("F"), None)), {'f': None}, True),
                ]:
            with self.subTest(record=record, pattern=pattern):
                self.assertEqual(record.match(pattern), result)

    def test_match_none(self):
        "Test match with match_none"
        for record, pattern, result in [
                (Model(f=(fields.Char("F"), 'foo')), {'f': 'foo'}, True),
                (Model(f=(fields.Char("F"), 'foo')), {'f': 'bar'}, False),
                (Model(f=(fields.Char("F"), 'foo')), {'f': None}, False),
                (Model(f=(fields.Char("F"), None)), {'f': 'foo'}, False),
                (Model(f=(fields.Char("F"), None)), {'f': None}, True),
                ]:
            with self.subTest(record=record, pattern=pattern):
                self.assertEqual(
                    record.match(pattern, match_none=True), result)

    def test_match_many2one(self):
        "Test match many2one"
        for record, pattern, result in [
                (Model(f=(fields.Many2One(None, "F"), Target(42))),
                    {'f': 42}, True),
                (Model(f=(fields.Many2One(None, "F"), Target(42))),
                    {'f': 1}, False),
                (Model(f=(fields.Many2One(None, "F"), Target(42))),
                    {'f': 0}, False),
                (Model(f=(fields.Many2One(None, "F"), Target(42))),
                    {'f': None}, False),
                (Model(f=(fields.Many2One(None, "F"), None)),
                    {'f': 42}, True),
                (Model(f=(fields.Many2One(None, "F"), None)),
                    {'f': None}, True),
                ]:
            with self.subTest(record=record, pattern=pattern):
                self.assertEqual(record.match(pattern), result)

    def test_match_boolean(self):
        "Test match boolean"
        for record, pattern, result in [
                (Model(f=(fields.Boolean("F"), True)), {'f': True}, True),
                (Model(f=(fields.Boolean("F"), True)), {'f': False}, False),
                (Model(f=(fields.Boolean("F"), True)), {'f': None}, False),
                (Model(f=(fields.Boolean("F"), None)), {'f': True}, True),
                (Model(f=(fields.Boolean("F"), None)), {'f': None}, True),
                (Model(f=(fields.Boolean("F"), False)), {'f': None}, True),
                (Model(f=(fields.Boolean("F"), False)), {'f': False}, True),
                ]:
            with self.subTest(record=record, pattern=pattern):
                self.assertEqual(record.match(pattern), result)

    def test_match_multiple(self):
        "Test match multiple"
        for record, pattern, result in [
                (Model(
                        f1=(fields.Char("F1"), 'foo'),
                        f2=(fields.Char("F2"), 'bar')),
                    {'f1': 'foo'}, True),
                (Model(
                        f1=(fields.Char("F1"), 'foo'),
                        f2=(fields.Char("F2"), 'bar')),
                    {'f1': 'foo', 'f2': 'bar'}, True),
                (Model(
                        f1=(fields.Char("F1"), 'foo'),
                        f2=(fields.Char("F2"), 'bar')),
                    {'f1': 'foo', 'f2': 'foo'}, False),
                (Model(
                        f1=(fields.Char("F1"), 'foo'),
                        f2=(fields.Char("F2"), 'bar')),
                    {'f1': 'bar', 'f2': 'foo'}, False),
                (Model(
                        f1=(fields.Char("F1"), 'foo'),
                        f2=(fields.Char("F2"), 'bar')),
                    {'f1': 'bar'}, False),
                ]:
            with self.subTest(record=record, pattern=pattern):
                self.assertEqual(record.match(pattern), result)
