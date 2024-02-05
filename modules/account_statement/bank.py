# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.i18n import gettext
from trytond.modules.bank.exceptions import AccountValidationError
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice


class Account(metaclass=PoolMeta):
    __name__ = 'bank.account'

    @classmethod
    def validate_fields(cls, accounts, field_names):
        super().validate_fields(accounts, field_names)
        cls.check_currency_statement_journal(accounts, field_names)

    @classmethod
    def check_currency_statement_journal(cls, accounts, field_names):
        pool = Pool()
        Journal = pool.get('account.statement.journal')
        if field_names and 'currency' not in field_names:
            return
        for sub_accounts in grouped_slice(accounts):
            sub_account_ids = [a.id for a in sub_accounts]
            journals = Journal.search([
                    ('bank_account', 'in', sub_account_ids),
                    ])
            for journal in journals:
                if (journal.currency != journal.bank_account.currency
                        and journal.bank_account.currency):
                    raise AccountValidationError(
                        gettext('account_statement.msg_bank_account_currency',
                            bank_account=journal.bank_account.rec_name,
                            currency=journal.currency.rec_name,
                            journal=journal.rec_name))
