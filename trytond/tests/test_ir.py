# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta
import datetime
import unittest

from trytond.pool import Pool
from trytond.transaction import Transaction
from .test_tryton import ModuleTestCase, with_transaction


class IrTestCase(ModuleTestCase):
    'Test ir module'
    module = 'ir'

    @with_transaction()
    def test_sequence_substitutions(self):
        'Test Sequence Substitutions'
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        SequenceType = pool.get('ir.sequence.type')
        Date = pool.get('ir.date')
        try:
            Group = pool.get('res.group')
            groups = Group.search([])
        except KeyError:
            groups = []

        sequence_type = SequenceType(name='Test', code='test', groups=groups)
        sequence_type.save()
        sequence = Sequence(name='Test Sequence', code='test')
        sequence.save()
        self.assertEqual(Sequence.get_id(sequence.id), '1')
        today = Date.today()
        sequence.prefix = '${year}'
        sequence.save()
        self.assertEqual(Sequence.get_id(sequence.id),
            '%s2' % str(today.year))
        next_year = today + relativedelta(years=1)
        with Transaction().set_context(date=next_year):
            self.assertEqual(Sequence.get_id(sequence.id),
                '%s3' % str(next_year.year))

    @with_transaction()
    def test_global_search(self):
        'Test Global Search'
        pool = Pool()
        Model = pool.get('ir.model')
        Model.global_search('User', 10)

    @with_transaction()
    def test_lang_strftime(self):
        "Test Lang.strftime"
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get('en')
        test_data = [
            (datetime.date(2016, 8, 3), '%d %B %Y', "03 August 2016"),
            (datetime.time(8, 20), '%I:%M %p', "08:20 AM"),
            (datetime.datetime(2018, 11, 1, 14, 30), '%a %d %b %Y %I:%M %p',
                "Thu 01 Nov 2018 02:30 PM"),
            (datetime.date(2018, 11, 1), '%x', "11/01/2018"),
            ]
        for date, format_, result in test_data:
            self.assertEqual(lang.strftime(date, format_), result)

    @with_transaction()
    def test_model_data_get_id(self):
        "Test ModelData.get_id"
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        User = pool.get('res.user')

        admin_id = ModelData.get_id('res', 'user_admin')
        admin, = User.search([('login', '=', 'admin')])

        self.assertEqual(admin_id, admin.id)

    @with_transaction()
    def test_model_data_get_id_dot(self):
        "Test ModelData.get_id with dot"
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        User = pool.get('res.user')

        admin_id = ModelData.get_id('res.user_admin')
        admin, = User.search([('login', '=', 'admin')])

        self.assertEqual(admin_id, admin.id)


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(IrTestCase)
