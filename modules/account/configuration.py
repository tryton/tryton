# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.model import ModelView, ModelSQL, ModelSingleton, fields
from trytond.transaction import Transaction
from trytond.pyson import Eval, Id
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

tax_roundings = [
    ('document', 'Per Document'),
    ('line', 'Per Line'),
    ]


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Account Configuration'
    __name__ = 'account.configuration'
    default_account_receivable = fields.MultiValue(fields.Many2One(
            'account.account', "Default Account Receivable",
            domain=[
                ('closed', '!=', True),
                ('type.receivable', '=', True),
                ('party_required', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))
    default_account_payable = fields.MultiValue(fields.Many2One(
            'account.account', "Default Account Payable",
            domain=[
                ('closed', '!=', True),
                ('type.payable', '=', True),
                ('party_required', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]))
    default_customer_tax_rule = fields.MultiValue(fields.Many2One(
            'account.tax.rule', "Default Customer Tax Rule",
            domain=[
                ('company', '=', Eval('context', {}).get('company', -1)),
                ('kind', 'in', ['sale', 'both']),
                ],
            help="Default customer tax rule for new parties."))
    default_supplier_tax_rule = fields.MultiValue(fields.Many2One(
            'account.tax.rule', "Default Supplier Tax Rule",
            domain=[
                ('company', '=', Eval('context', {}).get('company', -1)),
                ('kind', 'in', ['purchase', 'both']),
                ],
            help="Default supplier tax rule for new parties."))
    tax_rounding = fields.MultiValue(fields.Selection(
            tax_roundings, "Tax Rounding"))
    reconciliation_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Reconciliation Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('account',
                        'sequence_type_account_move_reconciliation')),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'default_account_receivable', 'default_account_payable'}:
            return pool.get('account.configuration.default_account')
        if field in {'default_customer_tax_rule', 'default_supplier_tax_rule'}:
            return pool.get('account.configuration.default_tax_rule')
        if field == 'reconciliation_sequence':
            return pool.get('account.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_tax_rounding(cls, **pattern):
        return cls.multivalue_model('tax_rounding').default_tax_rounding()

    @classmethod
    def default_reconciliation_sequence(cls, **pattern):
        return cls.multivalue_model(
            'reconciliation_sequence').default_reconciliation_sequence()


class ConfigurationDefaultAccount(ModelSQL, CompanyValueMixin):
    "Account Configuration Default Account"
    __name__ = 'account.configuration.default_account'
    default_account_receivable = fields.Many2One(
        'account.account', "Default Account Receivable",
        domain=[
            ('type.receivable', '=', True),
            ('party_required', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])
    default_account_payable = fields.Many2One(
        'account.account', "Default Account Payable",
        domain=[
            ('type.payable', '=', True),
            ('party_required', '=', True),
            ('company', '=', Eval('company', -1)),
            ],
        depends=['company'])


class DefaultTaxRule(ModelSQL, CompanyValueMixin):
    "Account Configuration Default Tax Rule"
    __name__ = 'account.configuration.default_tax_rule'
    default_customer_tax_rule = fields.Many2One(
        'account.tax.rule', "Default Customer Tax Rule",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', 'in', ['sale', 'both']),
            ],
        depends=['company'])
    default_supplier_tax_rule = fields.Many2One(
        'account.tax.rule', "Default Supplier Tax Rule",
        domain=[
            ('company', '=', Eval('company', -1)),
            ('kind', 'in', ['purchase', 'both']),
            ],
        depends=['company'])


class ConfigurationTaxRounding(ModelSQL, CompanyValueMixin):
    'Account Configuration Tax Rounding'
    __name__ = 'account.configuration.tax_rounding'
    configuration = fields.Many2One('account.configuration', 'Configuration',
        required=True, ondelete='CASCADE',
        context={
            'company': Eval('company', -1),
            },
        depends=['company'])
    tax_rounding = fields.Selection(tax_roundings, 'Method', required=True)

    @classmethod
    def __register__(cls, module_name):
        sql_table = cls.__table__()
        cursor = Transaction().connection.cursor()

        super(ConfigurationTaxRounding, cls).__register__(module_name)

        table = cls.__table_handler__(module_name)

        # Migration from 4.2: rename method into tax_rounding
        if table.column_exist('method'):
            cursor.execute(*sql_table.update(
                    [sql_table.tax_rounding], [sql_table.method]))
            table.drop_column('method')

    @classmethod
    def default_tax_rounding(cls):
        return 'document'


class Sequence(ModelSQL, CompanyValueMixin):
    "Account Configuration Sequence"
    __name__ = 'account.configuration.sequence'
    reconciliation_sequence = fields.Many2One(
        'ir.sequence', "Reconciliation Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('sequence_type', '=',
                Id('account', 'sequence_type_account_move_reconciliation')),
            ],
        depends=['company'])

    @classmethod
    def default_reconciliation_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        try:
            return ModelData.get_id(
                'account', 'sequence_account_move_reconciliation')
        except KeyError:
            return None
