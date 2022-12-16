# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.pool import Pool

from ..exceptions import InvalidBIC


class BankTestCase(ModuleTestCase):
    'Test Bank module'
    module = 'bank'

    @with_transaction()
    def test_bic_validation(self):
        "Test BIC validation"
        pool = Pool()
        Party = pool.get('party.party')
        Bank = pool.get('bank')

        party = Party(name='Test')
        party.save()
        bank = Bank(party=party)
        bank.save()

        bank.bic = 'ABNA BE 2A'
        bank.bic = bank.on_change_with_bic()
        self.assertEqual(bank.bic, 'ABNABE2A')

        bank.save()

        with self.assertRaises(InvalidBIC):
            bank.bic = 'foo'
            bank.save()

    @with_transaction()
    def test_iban_format(self):
        'Test IBAN format'
        pool = Pool()
        Party = pool.get('party.party')
        Bank = pool.get('bank')
        Account = pool.get('bank.account')
        Number = pool.get('bank.account.number')

        party = Party(name='Test')
        party.save()
        bank = Bank(party=party)
        bank.save()
        account, = Account.create([{
                    'bank': bank.id,
                    'numbers': [('create', [{
                                    'type': 'iban',
                                    'number': 'BE82068896274468',
                                    }, {
                                    'type': 'other',
                                    'number': 'not IBAN',
                                    }])],
                    }])

        iban_number, other_number = account.numbers
        self.assertEqual(iban_number.type, 'iban')
        self.assertEqual(other_number.type, 'other')

        # Test format on create
        self.assertEqual(iban_number.number, 'BE82 0688 9627 4468')
        self.assertEqual(other_number.number, 'not IBAN')

        # Test format on write
        iban_number.number = 'BE82068896274468'
        iban_number.type = 'iban'
        iban_number.save()
        self.assertEqual(iban_number.number, 'BE82 0688 9627 4468')

        other_number.number = 'still not IBAN'
        other_number.save()
        self.assertEqual(other_number.number, 'still not IBAN')

        Number.write([iban_number, other_number], {
                'number': 'BE82068896274468',
                })
        self.assertEqual(iban_number.number, 'BE82 0688 9627 4468')
        self.assertEqual(other_number.number, 'BE82068896274468')


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            BankTestCase))
    return suite
