# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pyson import Eval
from trytond.transaction import Transaction

__all__ = ['Invoice', 'InvoiceLine',
    'DepositRecall', 'DepositRecallStart']


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls._error_messages.update({
                'deposit_not_enough': (
                    'The account "%(account)s" for party "%(party)s" '
                    'has not enough deposit.'),
                })
        cls._buttons.update({
                'recall_deposit': {
                    'invisible': Eval('state') != 'draft',
                    'depends': ['state'],
                    },
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        cls.check_deposit(invoices)

    @classmethod
    @ModelView.button_action('account_deposit.wizard_recall_deposit')
    def recall_deposit(cls, invoices):
        pass

    def call_deposit(self, account, description):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        Currency = pool.get('currency.currency')

        balance = self.party.get_deposit_balance(account)
        balance = Currency.compute(
            account.company.currency, balance, self.currency)

        amount = 0
        if self.type.startswith('in'):
            if balance > 0 and self.total_amount > 0:
                amount = -min(balance, self.total_amount)
        else:
            if balance < 0 and self.total_amount > 0:
                amount = -min(-balance, self.total_amount)
        to_delete = []
        for line in self.lines:
            if line.account == account:
                to_delete.append(line)
        if amount < 0:
            line = self._get_deposit_recall_invoice_line(
                amount, account, description)
            line.sequence = max(l.sequence for l in self.lines)
            line.save()
        if to_delete:
            InvoiceLine.delete(to_delete)

    def _get_deposit_recall_invoice_line(self, amount, account, description):
        pool = Pool()
        Line = pool.get('account.invoice.line')

        line = Line(
            invoice=self,
            company=self.company,
            type='line',
            quantity=1,
            account=account,
            unit_price=amount,
            description=description,
            )
        # Set taxes
        line.on_change_account()
        return line

    @classmethod
    def check_deposit(cls, invoices):
        to_check = set()
        for invoice in invoices:
            for line in invoice.lines:
                if line.type != 'line':
                    continue
                if line.account.kind == 'deposit':
                    if ((invoice.type.endswith('invoice')
                            and line.amount < 0)
                            or (invoice.type.endswith('credit_note')
                                and line.amount > 0)):
                        sign = 1 if invoice.type.startswith('in') else -1
                        to_check.add((invoice.party, line.account, sign))

        for party, account, sign in to_check:
            if not party.check_deposit(account, sign):
                cls.raise_user_error('deposit_not_enough', {
                        'account': account.rec_name,
                        'party': party.rec_name,
                        })


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def _account_domain(cls, type_):
        domain = super(InvoiceLine, cls)._account_domain(type_)
        return domain + ['deposit']


class DepositRecall(Wizard):
    'Recall deposit on Invoice'
    __name__ = 'account.invoice.recall_deposit'
    start = StateView('account.invoice.recall_deposit.start',
        'account_deposit.recall_deposit_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Recall', 'recall', 'tryton-ok', default=True),
            ])
    recall = StateTransition()

    def default_start(self, fields):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoice = Invoice(Transaction().context['active_id'])

        return {
            'company': invoice.company.id,
            }

    def transition_recall(self):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoice = Invoice(Transaction().context['active_id'])
        invoice.call_deposit(self.start.account, self.start.description)
        return 'end'


class DepositRecallStart(ModelView):
    'Recall deposit on Invoice'
    __name__ = 'account.invoice.recall_deposit.start'
    company = fields.Many2One('company.company', 'Company', readonly=True)
    account = fields.Many2One('account.account', 'Account', required=True,
        domain=[
            ('kind', '=', 'deposit'),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    description = fields.Text('Description', required=True)
