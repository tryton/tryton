# -*- coding: utf-8 -*-
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
import urllib.parse

from trytond.tests.test_tryton import activate_module, with_transaction
from trytond.transaction import Transaction
from trytond.model import ModelView
from trytond.pool import Pool
from trytond.url import http_host, HOSTNAME

from .mixin import TestMixin, TestSecondMixin, NotMixin, ReportMixin


class UrlTestCase(unittest.TestCase):
    "Test URL generation"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def testModelURL(self):
        "Test model URLs"
        pool = Pool()
        UrlObject = pool.get('test.urlobject')
        db_name = Transaction().database.name

        self.assertEqual(UrlObject.__url__,
            'tryton://%s/%s/model/test.urlobject' % (
                HOSTNAME, urllib.parse.quote(db_name)))

        self.assertEqual(UrlObject(1).__url__,
            'tryton://%s/%s/model/test.urlobject/1' % (
                HOSTNAME, urllib.parse.quote(db_name)))

    @with_transaction()
    def testModelHref(self):
        "Test model href"
        pool = Pool()
        UrlObject = pool.get('test.urlobject')
        db_name = Transaction().database.name

        self.assertEqual(UrlObject.__href__,
            '%s/#%s/model/test.urlobject' % (
                http_host(), urllib.parse.quote(db_name)))

        self.assertEqual(UrlObject(1).__href__,
            '%s/#%s/model/test.urlobject/1' % (
                http_host(), urllib.parse.quote(db_name)))

    @with_transaction()
    def testWizardURL(self):
        "Test wizard URLs"
        pool = Pool()
        UrlWizard = pool.get('test.test_wizard', type='wizard')
        db_name = Transaction().database.name

        self.assertEqual(UrlWizard.__url__,
            'tryton://%s/%s/wizard/test.test_wizard' % (
                HOSTNAME, urllib.parse.quote(db_name)))

    @with_transaction()
    def testWizardHref(self):
        "Test wizard href"
        pool = Pool()
        UrlWizard = pool.get('test.test_wizard', type='wizard')
        db_name = Transaction().database.name

        self.assertEqual(UrlWizard.__href__,
            '%s/#%s/wizard/test.test_wizard' % (
                http_host(), urllib.parse.quote(db_name)))


class MixinTestCase(unittest.TestCase):
    "Test Mixin"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_mixin_on_modelview(self):
        "Test all ModelView and only ModelView are subclass of TestMixin"
        for _, model in Pool().iterobject():
            self.assertEqual(
                issubclass(model, ModelView),
                issubclass(model, TestMixin))

    @with_transaction()
    def test_second_mixin_on_modelview(self):
        "Test all ModelView and only ModelView are subclass of TestSecondMixin"
        for _, model in Pool().iterobject():
            self.assertEqual(
                issubclass(model, ModelView),
                issubclass(model, TestSecondMixin))

    @with_transaction()
    def test_no_mixin(self):
        "Test any model are subclass of NotMixin"
        for _, model in Pool().iterobject():
            self.assertFalse(issubclass(model, NotMixin))

    @with_transaction()
    def test_report_mixin(self):
        "Test mixin applies on default report"
        pool = Pool()
        Report = pool.get('test.report.mixin', type='report')

        self.assertTrue(issubclass(Report, ReportMixin))


class DeactivableMixinTestCase(unittest.TestCase):
    "Test DeactivableMixin"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_deactivable_default_active(self):
        pool = Pool()
        Deactivable = pool.get('test.deactivable.modelsql')

        deactivable = Deactivable()
        deactivable.save()

        self.assertEqual(deactivable.active, True)

    @with_transaction()
    def test_search_deactivable(self):
        pool = Pool()
        Deactivable = pool.get('test.deactivable.modelsql')

        active = Deactivable()
        active.save()
        inactive = Deactivable()
        inactive.active = False
        inactive.save()

        for domain, founds in [
                ([], [active]),
                ([('active', '=', False)], [inactive]),
                ([('active', 'in', [True, False])], [active, inactive]),
                ]:
            self.assertListEqual(Deactivable.search(domain), founds)


def suite():
    func = unittest.TestLoader().loadTestsFromTestCase
    suite = unittest.TestSuite()
    for testcase in [UrlTestCase, MixinTestCase, DeactivableMixinTestCase]:
        suite.addTests(func(testcase))
    return suite
