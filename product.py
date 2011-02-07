#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Not, Eval, Bool, Or, In, And


class Category(ModelSQL, ModelView):
    _name = 'product.category'

    account_stock = fields.Property(fields.Many2One('account.account',
        'Account Stock', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ], states={
            'invisible': Not(Bool(Eval('company'))),
        }))
    account_stock_supplier = fields.Property(fields.Many2One('account.account',
        'Account Stock Supplier', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ], states={
            'invisible': Not(Bool(Eval('company'))),
        }))
    account_stock_customer = fields.Property(fields.Many2One('account.account',
        'Account Stock Customer', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ], states={
            'invisible': Not(Bool(Eval('company'))),
        }))
    account_stock_lost_found = fields.Property(fields.Many2One(
        'account.account', 'Account Stock Lost and Found', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ], states={
            'invisible': Not(Bool(Eval('company'))),
        }))
    account_journal_stock_supplier = fields.Property(fields.Many2One(
        'account.journal', 'Journal Stock Supplier',
        states={
            'invisible': Not(Bool(Eval('company'))),
        }))
    account_journal_stock_customer = fields.Property(fields.Many2One(
        'account.journal', 'Journal Stock Customer',
        states={
            'invisible': Not(Bool(Eval('company'))),
        }))
    account_journal_stock_lost_found = fields.Property(fields.Many2One(
        'account.journal', 'Journal Stock Lost and Found',
        states={
            'invisible': Not(Bool(Eval('company'))),
        }))

Category()


class Template(ModelSQL, ModelView):
    _name = 'product.template'

    account_stock = fields.Property(fields.Many2One('account.account',
        'Account Stock', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ], states={
            'invisible': Or(Not(Bool(Eval('company'))),
                Bool(Eval('account_category'))),
            'required': And(In(Eval('type'), ['stockable', 'consumable']),
                Bool(Eval('company')),
                Not(Bool(Eval('account_category')))),
        }, help='This account will be used instead of the one defined '
        'on the category.', depends=['account_category']))
    account_stock_supplier = fields.Property(fields.Many2One('account.account',
        'Account Stock Supplier', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ], states={
            'invisible': Or(Not(Bool(Eval('company'))),
                Bool(Eval('account_category'))),
            'required': And(In(Eval('type'), ['stockable', 'consumable']),
                Bool(Eval('company')),
                Not(Bool(Eval('account_category')))),
        }, help='This account will be used instead of the one defined '
        'on the category.', depends=['account_category']))
    account_stock_customer = fields.Property(fields.Many2One('account.account',
        'Account Stock Customer', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ], states={
            'invisible': Or(Not(Bool(Eval('company'))),
                Bool(Eval('account_category'))),
            'required': And(In(Eval('type'), ['stockable', 'consumable']),
                Bool(Eval('company')),
                Not(Bool(Eval('account_category')))),
        }, help='This account will be used instead of the one defined '
        'on the category.', depends=['account_category']))
    account_stock_lost_found = fields.Property(fields.Many2One(
        'account.account', 'Account Stock Lost and Found', domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('company')),
        ], states={
            'invisible': Or(Not(Bool(Eval('company'))),
                Bool(Eval('account_category'))),
            'required': And(In(Eval('type'), ['stockable', 'consumable']),
                Bool(Eval('company')),
                Not(Bool(Eval('account_category')))),
        }, help='This account will be used instead of the one defined '
        'on the category.', depends=['account_category']))
    account_journal_stock_supplier = fields.Property(fields.Many2One(
        'account.journal', 'Account Journal Stock Supplier',
        states={
            'invisible': Or(Not(Bool(Eval('company'))),
                Bool(Eval('account_category'))),
            'required': And(In(Eval('type'), ['stockable', 'consumable']),
                Bool(Eval('company')),
                Not(Bool(Eval('account_category')))),
        }, help='This journal will be used instead of the one defined '
        'on the category.', depends=['account_category']))
    account_journal_stock_customer = fields.Property(fields.Many2One(
        'account.journal', 'Account Journal Stock Customer',
        states={
            'invisible': Or(Not(Bool(Eval('company'))),
                Bool(Eval('account_category'))),
            'required': And(In(Eval('type'), ['stockable', 'consumable']),
                Bool(Eval('company')),
                Not(Bool(Eval('account_category')))),
        }, help='This journal will be used instead of the one defined '
        'on the category.', depends=['account_category']))
    account_journal_stock_lost_found = fields.Property(fields.Many2One(
        'account.journal', 'Account Journal Stock Lost and Found',
        states={
            'invisible': Or(Not(Bool(Eval('company'))),
                Bool(Eval('account_category'))),
            'required': And(In(Eval('type'), ['stockable', 'consumable']),
                Bool(Eval('company')),
                Not(Bool(Eval('account_category')))),
        }, help='This journal will be used instead of the one defined '
        'on the category.', depends=['account_category']))
    account_stock_used = fields.Function(fields.Many2One('account.account',
        'Account Stock Used'), 'get_account')
    account_stock_supplier_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Supplier Used'), 'get_account')
    account_stock_customer_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Customer Used'), 'get_account')
    account_stock_lost_found_used = fields.Function(fields.Many2One(
        'account.account', 'Account Stock Lost and Found'), 'get_account')
    account_journal_stock_supplier_used = fields.Function(fields.Many2One(
        'account.journal', 'Journal Stock Supplier'), 'get_account')
    account_journal_stock_customer_used = fields.Function(fields.Many2One(
        'account.journal', 'Journal Stock Customer'), 'get_account')
    account_journal_stock_lost_found_used = fields.Function(fields.Many2One(
        'account.journal', 'Journal Stock Lost and Found'),
        'get_account')

Template()

