# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from operator import attrgetter

from num2words import num2words

from trytond.i18n import gettext
from trytond.model import ModelView, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Id, If
from trytond.report import Report
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from .exceptions import CheckNumberError


class PaymentJournal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'

    check_sequence = fields.Many2One(
        'ir.sequence.strict', "Check Sequence",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('sequence_type', '=',
                Id('account_payment_check',
                    'sequence_type_account_payment_check')),
            ('prefix', '=', ''),
            ('suffix', '=', ''),
            ('type', '=', 'incremental'),
            ('number_increment', '=', 1),
            ],
        states={
            'invisible': Eval('process_method') != 'check',
            },
        help="Leave empty for manual numbering.")
    check_max_number = fields.Integer(
        "Maximum Check Number",
        states={
            'invisible': Eval('process_method') != 'check',
            },
        help="The highest check number allowed for this journal.")
    check_format = fields.Many2One(
        'ir.action.report', "Check Format", ondelete='RESTRICT',
        domain=[
            ('model', '=', 'account.payment'),
            ('report_name', '=', 'account.payment.check'),
            ],
        states={
            'invisible': Eval('process_method') != 'check',
            },
        help="The report layout for printing checks.")

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.process_method.selection.append(('check', "Check"))


class PaymentGroup(metaclass=PoolMeta):
    __name__ = 'account.payment.group'

    check_printed = fields.Boolean(
        "Check Printed", readonly=True,
        states={
            'invisible': (
                (Eval('process_method') != 'check')
                | (Eval('kind') != 'payable')),
            })

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update(
            check_print={
                'invisible': (
                    (Eval('process_method') != 'check')
                    | (Eval('kind') != 'payable')
                    | Eval('check_printed')),
                'depends': ['process_method', 'kind', 'check_printed'],
                },
            )

    def process_check(self):
        pass

    @classmethod
    @ModelView.button_action(
        'account_payment_check.account_payment_check_print')
    def check_print(cls, groups):
        pass


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    check_printed = fields.Function(
        fields.Boolean("Check Printed"),
        'get_check_printed')
    check_number = fields.Char(
        "Check Number",
        states={
            'readonly': Eval('state') != 'draft',
            'invisible': Eval('process_method') != 'check',
            'required': If(Eval('kind') == 'receivable',
                Eval('state') != 'draft',
                Eval('check_printed', False),
                ),
            })

    def get_check_printed(self, name):
        return self.group.check_printed if self.group else None

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//page[id="check"]', 'states', {
                    'invisible': Eval('process_method') != 'check',
                    }),
            ]

    @classmethod
    def process_method_with_group(cls):
        return super().process_method_with_group() + ['check']


class PaymentCheckPrint(Wizard):
    __name__ = 'account.payment.check.print'

    start = StateTransition()
    number = StateView(
        'account.payment.check.print.number',
        'account_payment_check.account_payment_check_print_number_view_form', [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Print", 'print_', 'tryton-print'),
            ])
    print_ = StateAction(
        'account_payment_check.report_account_payment_check_print')

    def transition_start(self):
        if (self.record.process_method != 'check'
                or self.record.check_printed):
            return 'end'
        elif not self.record.journal.check_sequence:
            return 'number'
        else:
            return 'print_'

    def do_print_(self, action):
        pool = Pool()
        Payment = pool.get('account.payment')

        payments = self.record.payments
        sequence = self.record.journal.check_sequence
        if sequence:
            for payment, number in zip(
                    payments, sequence.get_many(len(payments))):
                payment.check_number = number
        else:
            padding = len(self.number.start_number)
            start_number = int(self.number.start_number)
            for number, payment in enumerate(payments, start_number):
                payment.check_number = f'{number:0>{padding}d}'

        if max_number := self.record.journal.check_max_number:
            if max_number < max(
                    map(int, map(attrgetter('check_number'), payments))):
                raise CheckNumberError(gettext(
                        'account_payment_check.'
                        'msg_payment_group_journal_max_number',
                        group=self.record.rec_name,
                        journal=self.record.journal.rec_name,
                        ))
        Payment.save(payments)
        self.record.check_printed = True
        self.record.save()

        if self.record.journal.check_format:
            action.update(
                self.record.journal.check_format.action.get_action_value())
        return action, {'ids': list(map(int, payments))}


class PaymentCheckPrintNumber(ModelView):
    __name__ = 'account.payment.check.print.number'

    start_number = fields.Char("Start Number", required=True)


class PaymentCheck(Report):
    __name__ = 'account.payment.check'

    @classmethod
    def get_context(cls, records, header, data):
        context = super().get_context(records, header, data)
        context['num2words'] = cls.num2words
        return context

    @classmethod
    def num2words(cls, number, lang=None, **kwargs):
        if lang is None:
            lang = Transaction().language
        try:
            return num2words(number, lang=lang, **kwargs)
        except NotImplementedError:
            return num2words(number, **kwargs)


class StatementRule(metaclass=PoolMeta):
    __name__ = 'account.statement.rule'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.description.help += "\n'check'"


class StatementRuleLine(metaclass=PoolMeta):
    __name__ = 'account.statement.rule.line'

    @classmethod
    def _get_payment_check_domain(cls, number, origin):
        return [
            ('check_number', '=', number),
            ('company', '=', origin.company.id),
            ('currency', '=', origin.currency.id),
            ('state', 'in', ['processing', 'succeeded', 'failed']),
            ]

    def _get_payment(self, origin, keywords, party=None, amount=0):
        pool = Pool()
        Payment = pool.get('account.payment')

        payment = super()._get_payment(
            origin, keywords, party=party, amount=amount)

        if keywords.get('check'):
            domain = self._get_payment_check_domain(keywords['check'], origin)
            if party:
                domain.append(('party', '=', party.id))
            if amount > 0:
                domain.append(('kind', '=', 'receivable'))
            elif amount < 0:
                domain.append(('kind', '=', 'payable'))
            payments = Payment.search(domain)
            if len(payments) == 1:
                payment, = payments
        return payment
