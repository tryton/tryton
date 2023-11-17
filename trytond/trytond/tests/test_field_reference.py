# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest

from trytond.model.exceptions import (
    DomainValidationError, RequiredValidationError)
from trytond.pool import Pool
from trytond.tests.test_tryton import activate_module, with_transaction


class FieldReferenceTestCase(unittest.TestCase):
    "Test Field Reference"

    @classmethod
    def setUpClass(cls):
        activate_module('tests')

    @with_transaction()
    def test_create(self):
        "Test create reference"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])

        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        self.assertEqual(reference.reference, target)

    @with_transaction()
    def test_create_without_default(self):
        "Test create reference without default"
        pool = Pool()
        Reference = pool.get('test.reference')

        reference, = Reference.create([{}])

        self.assertEqual(reference.reference, None)

    @with_transaction()
    def test_create_required_with_value(self):
        "Test create reference required with value"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference_required')
        target, = Target.create([{'name': "Target"}])

        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        self.assertEqual(reference.reference, target)

    @with_transaction()
    def test_create_required_without_value(self):
        "Test create reference required without value"
        pool = Pool()
        Reference = pool.get('test.reference_required')

        with self.assertRaises(RequiredValidationError):
            Reference.create([{}])

    @with_transaction()
    def test_create_required_with_none(self):
        "Test create reference required with none"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference_required')

        with self.assertRaises(RequiredValidationError):
            Reference.create([{
                        'reference': str(Target()),
                        }])

    @with_transaction()
    def test_create_required_with_negative(self):
        "Test create reference required with negative"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference_required')

        with self.assertRaises(RequiredValidationError):
            Reference.create([{
                        'reference': str(Target(id=-1)),
                        }])

    @with_transaction()
    def test_create_partial(self):
        "Test create reference partial"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])

        reference, = Reference.create([{
                    'reference': 'test.reference.target,',
                    }])

        self.assertEqual(reference.reference, 'test.reference.target,')

    @with_transaction()
    def test_create_negative(self):
        "Test create reference negative"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])

        reference, = Reference.create([{
                    'reference': 'test.reference.target,-1',
                    }])

        self.assertEqual(reference.reference, 'test.reference.target,-1')

    @with_transaction()
    def test_search_equals_string(self):
        "Test search reference equals string"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', '=', str(target)),
                ])

        self.assertListEqual(references, [reference])

    @with_transaction()
    def test_search_equals_tuple(self):
        "Test search reference equals tuple"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', '=', (Target.__name__, target.id)),
                ])

        self.assertListEqual(references, [reference])

    @with_transaction()
    def test_search_equals_list(self):
        "Test search reference equals list"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', '=', [Target.__name__, target.id]),
                ])

        self.assertListEqual(references, [reference])

    @with_transaction()
    def test_search_equals_none(self):
        "Test search reference equals None"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', '=', None),
                ])

        self.assertListEqual(references, [])

    @with_transaction()
    def test_search_non_equals_string(self):
        "Test search reference non equals string"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', '!=', str(target)),
                ])

        self.assertListEqual(references, [])

    @with_transaction()
    def test_search_non_equals_tuple(self):
        "Test search reference non equals tuple"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', '!=', (Target.__name__, target.id)),
                ])

        self.assertListEqual(references, [])

    @with_transaction()
    def test_search_non_equals_none(self):
        "Test search reference non equals None"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', '!=', None),
                ])

        self.assertListEqual(references, [reference])

    @with_transaction()
    def test_search_in_string(self):
        "Test search reference in string"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', 'in', [str(target)]),
                ])

        self.assertListEqual(references, [reference])

    @with_transaction()
    def test_search_in_tuple(self):
        "Test search reference in tuple"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', 'in', [(Target.__name__, target.id)]),
                ])

        self.assertListEqual(references, [reference])

    @with_transaction()
    def test_search_in_none(self):
        "Test search reference in [None]"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', 'in', [None]),
                ])

        self.assertListEqual(references, [])

    @with_transaction()
    def test_search_not_in_string(self):
        "Test search reference not in string"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', 'not in', [str(target)]),
                ])

        self.assertListEqual(references, [])

    @with_transaction()
    def test_search_not_in_tuple(self):
        "Test search reference not in tuple"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', 'not in', [(Target.__name__, target.id)]),
                ])

        self.assertListEqual(references, [])

    @with_transaction()
    def test_search_not_in_none(self):
        "Test search reference not in [None]"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference', 'not in', [None]),
                ])

        self.assertListEqual(references, [reference])

    @with_transaction()
    def test_search_join(self):
        "Test search reference join"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        references = Reference.search([
                ('reference.name', '=', "Target", Target.__name__),
                ])

        self.assertListEqual(references, [reference])

    @with_transaction()
    def test_write_string(self):
        "Test write reference string"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{}])

        Reference.write([reference], {
                'reference': str(target),
                })

        self.assertEqual(reference.reference, target)

    @with_transaction()
    def test_write_tuple(self):
        "Test write reference string"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{}])

        Reference.write([reference], {
                'reference': (Target.__name__, target.id),
                })

        self.assertEqual(reference.reference, target)

    @with_transaction()
    def test_write_none(self):
        "Test write reference None"
        pool = Pool()
        Target = pool.get('test.reference.target')
        Reference = pool.get('test.reference')
        target, = Target.create([{'name': "Target"}])
        reference, = Reference.create([{
                    'reference': str(target),
                    }])

        Reference.write([reference], {
                'reference': None
                })

        self.assertEqual(reference.reference, None)

    @with_transaction()
    def test_context_attribute(self):
        "Test context on reference attribute"
        pool = Pool()
        Reference = pool.get('test.reference_context')
        Target = pool.get('test.reference_context.target')

        target, = Target.create([{}])
        record, = Reference.create([{
                    'target': str(target),
                    }])

        self.assertEqual(record.target.context, 'foo')

    @with_transaction()
    def test_context_read(self):
        "Test context on reference read"
        pool = Pool()
        Reference = pool.get('test.reference_context')
        Target = pool.get('test.reference_context.target')

        target, = Target.create([{}])
        record, = Reference.create([{
                    'target': str(target),
                    }])
        data, = Reference.read([record.id], ['target.context'])

        self.assertEqual(data['target.']['context'], 'foo')

    @with_transaction()
    def test_context_read_multi(self):
        "Test context on reference read with value and None"
        pool = Pool()
        Reference = pool.get('test.reference_context')
        Target = pool.get('test.reference_context.target')

        target, = Target.create([{}])
        records = Reference.create([{
                    'target': str(target),
                    }, {
                    'target': None,
                    }])
        data = Reference.read([r.id for r in records], ['target.context'])

        self.assertEqual(data[0]['target.']['context'], 'foo')
        self.assertEqual(data[1]['target.'], None)

    @with_transaction()
    def test_context_set(self):
        "Test context on reference set"
        pool = Pool()
        Reference = pool.get('test.reference_context')
        Target = pool.get('test.reference_context.target')

        target, = Target.create([{}])
        record = Reference(target=str(target))

        self.assertEqual(record.target.context, 'foo')

    @with_transaction()
    def test_domain_valid(self):
        "Test reference with valid domain"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation')
        Target = pool.get('test.reference_domainvalidation.target')
        target = Target(value=42)
        target.save()

        reference, = Reference.create([{
                    'reference': str(target),
                    }])
        self.assertEqual(reference.reference, target)

    @with_transaction()
    def test_domain_invalid(self):
        "Test reference with invalid domain"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation')
        Target = pool.get('test.reference_domainvalidation.target')
        target = Target(value=1)
        target.save()

        reference = Reference(reference=target)
        with self.assertRaisesRegex(
                DomainValidationError,
                'The value "%s" for field "Reference" '
                'in record ".*" of "Reference Domain Validation"' %
                target.rec_name):
            reference.save()

    @with_transaction()
    def test_no_domain(self):
        "Test reference with no domain"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation')
        Target = pool.get('test.reference.target')
        target = Target(name="Test")
        target.save()

        reference, = Reference.create([{
                    'reference': str(target),
                    }])
        self.assertEqual(reference.reference, target)

    @with_transaction()
    def test_domain_none_value(self):
        "Test reference with domain and None value"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation')

        reference, = Reference.create([{
                    'reference': None,
                    }])
        self.assertEqual(reference.reference, None)

    @with_transaction()
    def test_domain_no_id_value(self):
        "Test reference with domain and no id"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation')

        reference, = Reference.create([{
                    'reference': 'test.reference.target,',
                    }])
        self.assertEqual(reference.reference, 'test.reference.target,')

    @with_transaction()
    def test_domain_negative_id_value(self):
        "Test reference with domain and negative id"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation')

        reference, = Reference.create([{
                    'reference': 'test.reference.target,-1',
                    }])
        self.assertEqual(reference.reference, 'test.reference.target,-1')

    @with_transaction()
    def test_domain_different_targets(self):
        "Test reference with domain and different targets"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation')
        Target1 = pool.get('test.reference.target')
        target1 = Target1(name="Test")
        target1.save()
        Target2 = pool.get('test.reference_domainvalidation.target')
        target2 = Target2(value=6)
        target2.save()

        references = Reference.create([{
                    'reference': str(target1),
                    }, {
                    'reference': str(target2),
                    }])
        self.assertEqual(len(references), 2)

    @with_transaction()
    def test_domain_pyson(self):
        "Test reference with pyson domain"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation_pyson')
        Target = pool.get('test.reference_domainvalidation.target')
        target = Target(value=42)
        target.save()

        reference, = Reference.create([{
                    'value': 1,
                    'reference': str(target),
                    }])
        self.assertEqual(reference.reference, target)

    @with_transaction()
    def test_domain_pyson_no_id_value(self):
        "Test reference with pyson domain and no id"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation_pyson')

        reference, = Reference.create([{
                    'reference': 'test.reference.target,',
                    }])
        self.assertEqual(reference.reference, 'test.reference.target,')

    @with_transaction()
    def test_domain_pyson_negative_id_value(self):
        "Test reference with pyson domain and negative id"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation_pyson')

        reference, = Reference.create([{
                    'reference': 'test.reference.target,-1',
                    }])
        self.assertEqual(reference.reference, 'test.reference.target,-1')

    @with_transaction()
    def test_domain_pyson_different_targets(self):
        "Test reference with pyson domain and different targets"
        pool = Pool()
        Reference = pool.get('test.reference_domainvalidation_pyson')
        Target1 = pool.get('test.reference.target')
        target1 = Target1(name="Test")
        target1.save()
        Target2 = pool.get('test.reference_domainvalidation.target')
        target2 = Target2(value=42)
        target2.save()

        references = Reference.create([{
                    'reference': str(target1),
                    }, {
                    'value': 1,
                    'reference': str(target2),
                    }])
        self.assertEqual(len(references), 2)
