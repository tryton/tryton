# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import unittest
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import suite as tryton_suite
from trytond.pool import Pool


class TestCase(ModuleTestCase):
    'Test Party relationship module'
    module = 'party_relationship'

    @with_transaction()
    def test_reverse_relationship(self):
        'Test reverse relationship'
        pool = Pool()
        Party = pool.get('party.party')
        RelationType = pool.get('party.relation.type')
        Relation = pool.get('party.relation')

        employee_of, = RelationType.create([{
                    'name': 'Employee of',
                    }])
        works_for, = RelationType.create([{
                    'name': 'Works for',
                    'reverse': employee_of.id,
                    }])
        RelationType.write([employee_of], {
                'reverse': works_for.id,
                })

        company, employee = Party.create([{
                    'name': 'Company',
                    }, {
                    'name': 'Employee',
                    }])

        Relation.create([{
                    'from_': company.id,
                    'to': employee.id,
                    'type': employee_of.id
                    }])
        company_relation, = company.relations
        employee_relation, = employee.relations
        self.assertEqual(company_relation.type, employee_of)
        self.assertEqual(company_relation.to, employee)
        self.assertEqual(employee_relation.type, works_for)
        self.assertEqual(employee_relation.to, company)

    @with_transaction()
    def test_without_reverse_relationship(self):
        'Test without reverse relationship'
        pool = Pool()
        Party = pool.get('party.party')
        RelationType = pool.get('party.relation.type')
        Relation = pool.get('party.relation')

        employee_of, = RelationType.create([{
                    'name': 'Employee of',
                    }])
        works_for, = RelationType.create([{
                    'name': 'Works for',
                    }])

        company, employee = Party.create([{
                    'name': 'Company',
                    }, {
                    'name': 'Employee',
                    }])

        Relation.create([{
                    'from_': company.id,
                    'to': employee.id,
                    'type': employee_of.id
                    }])
        company_relation, = company.relations
        self.assertEqual(len(employee.relations), 0)
        self.assertEqual(company_relation.type, employee_of)
        self.assertEqual(company_relation.to, employee)

    @with_transaction()
    def test_relation_all(self):
        'Test relation all'
        pool = Pool()
        Party = pool.get('party.party')
        RelationType = pool.get('party.relation.type')
        RelationAll = pool.get('party.relation.all')

        relation_type, reverse_relation_type = RelationType.create([{
                    'name': 'Relation',
                    }, {
                    'name': 'Reverse',
                    }])
        relation_type.reverse = reverse_relation_type
        relation_type.save()
        reverse_relation_type.reverse = relation_type
        reverse_relation_type.save()

        party1, party2, party3 = Party.create([{
                    'name': 'Party 1',
                    }, {
                    'name': 'Party 2',
                    }, {
                    'name': 'Party 3',
                    }])

        relation, = RelationAll.create([{
                    'from_': party1.id,
                    'to': party2.id,
                    'type': relation_type.id,
                    }])
        self.assertFalse(relation.id % 2)
        reverse_relation, = RelationAll.search([
                ('id', '!=', relation.id),
                ])
        self.assertTrue(reverse_relation.id % 2)
        self.assertEqual(relation.reverse_id, reverse_relation.id)
        self.assertEqual(reverse_relation.from_, party2)
        self.assertEqual(reverse_relation.to, party1)

        reverse_relation.from_ = party3
        reverse_relation.save()
        relation.save()  # clear cache
        self.assertEqual(reverse_relation.from_, party3)
        self.assertEqual(reverse_relation.to, party1)
        self.assertEqual(relation.from_, party1)
        self.assertEqual(relation.to, party3)

        reverse_relation.type = reverse_relation_type
        reverse_relation.save()
        self.assertEqual(reverse_relation.from_, party3)
        self.assertEqual(reverse_relation.to, party1)
        self.assertEqual(reverse_relation.type, reverse_relation_type)
        self.assertEqual(relation.from_, party1)
        self.assertEqual(relation.to, party3)
        self.assertEqual(relation.type, relation_type)

        relation.type = relation_type
        relation.save()
        self.assertEqual(reverse_relation.from_, party3)
        self.assertEqual(reverse_relation.to, party1)
        self.assertEqual(reverse_relation.type, reverse_relation_type)
        self.assertEqual(relation.from_, party1)
        self.assertEqual(relation.to, party3)
        self.assertEqual(relation.type, relation_type)

        reverse_relation.to = party2
        reverse_relation.save()
        relation.save()  # clear cache
        self.assertEqual(reverse_relation.from_, party3)
        self.assertEqual(reverse_relation.to, party2)
        self.assertEqual(relation.from_, party2)
        self.assertEqual(relation.to, party3)

        reverse_relation.from_ = party2
        reverse_relation.to = party1
        reverse_relation.save()
        relation.save()  # clear cache
        self.assertEqual(reverse_relation.from_, party2)
        self.assertEqual(reverse_relation.to, party1)
        self.assertEqual(relation.from_, party1)
        self.assertEqual(relation.to, party2)

        relation.from_ = party2
        relation.to = party1
        relation.save()
        reverse_relation.save()  # clear cache
        self.assertEqual(relation.from_, party2)
        self.assertEqual(relation.to, party1)
        self.assertEqual(reverse_relation.from_, party1)
        self.assertEqual(reverse_relation.to, party2)

        RelationAll.delete([reverse_relation])
        self.assertEqual(RelationAll.search([]), [])


def suite():
    suite = tryton_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCase))
    return suite
