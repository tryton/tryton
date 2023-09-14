# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.modules.company.tests import CompanyTestMixin
from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class DocumentIncomingOcrTestCase(CompanyTestMixin, ModuleTestCase):
    "Test Document Incoming Ocr module"
    module = 'document_incoming_ocr'

    @with_transaction()
    def test_service_match(self):
        "Test Service match"
        pool = Pool()
        Service = pool.get('document.incoming.ocr.service')

        for service, pattern, result in [
                (Service(source=None), {}, True),
                (Service(source='test'), {}, False),
                (Service(source='test'), {'source': 'test'}, True),
                (Service(source='test'), {'source': None}, False),
                (Service(source='test'), {'source': 'test source'}, True),
                (Service(source='Test'), {'source': 'test'}, False),
                (Service(source='(?i)test'), {'source': 'Test'}, True),
                (Service(source='test$'), {'source': 'test source'}, False),
                (Service(source='test$'), {'source': 'source test'}, True),
                ]:
            with self.subTest(service=service, pattern=pattern):
                self.assertEqual(service.match(pattern), result)


del ModuleTestCase
