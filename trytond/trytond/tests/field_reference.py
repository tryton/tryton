# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Reference(ModelSQL):
    'Reference'
    __name__ = 'test.reference'
    reference = fields.Reference('Reference', selection=[
            (None, ''),
            ('test.reference.target', 'Target'),
            ])


class ReferenceTarget(ModelSQL):
    'Reference Target'
    __name__ = 'test.reference.target'
    name = fields.Char('Name', required=True)


class ReferenceRequired(ModelSQL):
    'Reference Required'
    __name__ = 'test.reference_required'
    reference = fields.Reference('Reference', selection=[
            (None, ''),
            ('test.reference.target', 'Target'),
            ], required=True)


class ReferenceContext(ModelSQL):
    "Reference Context"
    __name__ = 'test.reference_context'
    target = fields.Reference("Reference", selection=[
            (None, ''),
            ('test.reference_context.target', "Target"),
            ], context={'test': 'foo'})


class ReferenceContextTarget(ModelSQL):
    "Reference Context Target"
    __name__ = 'test.reference_context.target'
    context = fields.Function(fields.Char("context"), 'get_context')

    def get_context(self, name):
        context = Transaction().context
        return context.get('test')


class ReferenceDomainValidation(ModelSQL):
    "Reference Domain Validation"
    __name__ = 'test.reference_domainvalidation'
    reference = fields.Reference("Reference", selection=[
            (None, ''),
            ('test.reference.target', "Target"),
            ('test.reference_domainvalidation.target', "Domain Target"),
            ],
        domain={
            'test.reference_domainvalidation.target': [
                ('value', '>', 5),
                ],
            })


class ReferenceDomainValidationTarget(ModelSQL):
    "Reference Domain Validation Target"
    __name__ = 'test.reference_domainvalidation.target'
    value = fields.Integer("Value")


class ReferenceDomainValidationPYSON(ModelSQL):
    "Reference Domain Validation"
    __name__ = 'test.reference_domainvalidation_pyson'
    reference = fields.Reference("Reference", selection=[
            (None, ''),
            ('test.reference.target', "Target"),
            ('test.reference_domainvalidation.target', "Domain Target"),
            ],
        domain={
            'test.reference_domainvalidation.target': [
                ('value', '>', Eval('value')),
                ],
            },
        depends=['value'])
    value = fields.Integer("Value")


def register(module):
    Pool.register(
        Reference,
        ReferenceTarget,
        ReferenceRequired,
        ReferenceContext,
        ReferenceContextTarget,
        ReferenceDomainValidation,
        ReferenceDomainValidationTarget,
        ReferenceDomainValidationPYSON,
        module=module, type_='model')
