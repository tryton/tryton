# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction


class Reference(ModelSQL):
    __name__ = 'test.reference'
    reference = fields.Reference('Reference', selection=[
            (None, ''),
            ('test.reference.target', 'Target'),
            ])


class ReferenceTarget(ModelSQL):
    __name__ = 'test.reference.target'
    name = fields.Char('Name', required=True)


class ReferenceRequired(ModelSQL):
    __name__ = 'test.reference_required'
    reference = fields.Reference('Reference', selection=[
            (None, ''),
            ('test.reference.target', 'Target'),
            ], required=True)


class ReferenceContext(ModelSQL):
    __name__ = 'test.reference_context'
    target = fields.Reference("Reference", selection=[
            (None, ''),
            ('test.reference_context.target', "Target"),
            ], context={'test': 'foo'})


class ReferenceContextTarget(ModelSQL):
    __name__ = 'test.reference_context.target'
    context = fields.Function(fields.Char("context"), 'get_context')

    def get_context(self, name):
        context = Transaction().context
        return context.get('test')


class ReferenceDomainValidation(ModelSQL):
    __name__ = 'test.reference_domain_validation'
    reference = fields.Reference("Reference", selection=[
            (None, ''),
            ('test.reference.target', "Target"),
            ('test.reference_domain_validation.target', "Domain Target"),
            ],
        domain={
            'test.reference_domain_validation.target': [
                ('value', '>', 5),
                ],
            })


class ReferenceDomainValidationTarget(ModelSQL):
    __name__ = 'test.reference_domain_validation.target'
    value = fields.Integer("Value")


class ReferenceDomainValidationPYSON(ModelSQL):
    __name__ = 'test.reference_domain_validation_pyson'
    reference = fields.Reference("Reference", selection=[
            (None, ''),
            ('test.reference.target', "Target"),
            ('test.reference_domain_validation.target', "Domain Target"),
            ],
        domain={
            'test.reference_domain_validation.target': [
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
