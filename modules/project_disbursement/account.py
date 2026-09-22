# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from functools import wraps

from trytond.model import ModelView, Workflow, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    default_account_disbursement = fields.MultiValue(fields.Many2One(
            'account.account', "Default Account Disbursement",
            domain=[
                ('closed', '!=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'default_account_disbursement':
            return pool.get('account.configuration.default_account')
        return super().multivalue_model(field)


class ConfigurationDefaultAccount(metaclass=PoolMeta):
    __name__ = 'account.configuration.default_account'

    default_account_disbursement = fields.Many2One(
        'account.account', "Default Account Disbursement",
        domain=[
            ('closed', '!=', True),
            ('company', '=', Eval('company', -1)),
            ])


def AccountTypeMixin(template=False):

    class Mixin:
        __slots__ = ()
        disbursement = fields.Boolean(
            "Disbursement",
            domain=[
                If(Eval('statement') != 'balance',
                    ('disbursement', '=', False), ()),
                ],
            states={
                'invisible': (Eval('statement') != 'balance'),
                })

    if not template:
        for fname in dir(Mixin):
            field = getattr(Mixin, fname)
            if not isinstance(field, fields.Field):
                continue
            field.states['editable'] = (
                ~Eval('template', None) | Eval('template_override', False))
    return Mixin


class AccountTypeTemplate(AccountTypeMixin(template=True), metaclass=PoolMeta):
    __name__ = 'account.account.type.template'

    def _get_type_value(self, type=None):
        values = super()._get_type_value(type=type)
        if not type or type.disbursement != self.disbursement:
            values['disbursement'] = self.disbursement
        return values


class AccountType(AccountTypeMixin(), metaclass=PoolMeta):
    __name__ = 'account.account.type'


def process_disbursement(func):
    @wraps(func)
    def wrapper(cls, payments):
        pool = Pool()
        Disbursement = pool.get('project.disbursement')
        transaction = Transaction()
        context = transaction.context

        func(cls, payments)

        to_process = set()
        for payment in payments:
            if (isinstance(payment.origin, Disbursement)
                    and payment.origin.id >= 0):
                to_process.add(payment.origin)
        if to_process:
            with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)):
                Disbursement.__queue__.process(to_process)
    return wrapper


class Payment(metaclass=PoolMeta):
    __name__ = 'account.payment'

    @classmethod
    def _get_origin(cls):
        return [*super()._get_origin(), 'project.disbursement']

    @classmethod
    @ModelView.button
    @Workflow.transition('succeeded')
    @process_disbursement
    def succeed(cls, payments):
        super().succeed(payments)

    @classmethod
    @ModelView.button
    @Workflow.transition('failed')
    @process_disbursement
    def fail(cls, payments):
        super().fail(payments)


class StatementLine(metaclass=PoolMeta):
    __name__ = 'account.statement.line'

    @fields.depends(methods=['payment'])
    def on_change_related_to(self):
        pool = Pool()
        Disbursement = pool.get('project.disbursement')
        super().on_change_related_to()
        if self.payment:
            if isinstance(self.payment.origin, Disbursement):
                disbursement = self.payment.origin
                self.account = disbursement.account


class InvoiceLine(metaclass=PoolMeta):
    __name__ = 'account.invoice.line'

    @classmethod
    def _account_domain(cls, type_):
        domain = super()._account_domain(type_)
        if type_ == 'out':
            domain.append(('type.disbursement', '=', True))
        return domain

    @classmethod
    def _get_origin(cls):
        return [*super()._get_origin(), 'project.disbursement']

    def get_move_lines(self):
        pool = Pool()
        Disbursement = pool.get('project.disbursement')
        lines = super().get_move_lines()
        if isinstance(self.origin, Disbursement) and self.origin.id >= 0:
            disbursement = self.origin
            for line in lines:
                if line.account.party_required:
                    line.party = disbursement.payee
        return lines
