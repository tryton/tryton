# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction


class DocumentIncomingOcrTyplessTestCase(ModuleTestCase):
    "Test Document Incoming Ocr Typless module"
    module = 'document_incoming_ocr_typless'

    @with_transaction()
    def test_service_match(self):
        "Test Service match"
        pool = Pool()
        Service = pool.get('document.incoming.ocr.service')

        for service, pattern, result in [
                (Service(type='typless', source=None), {}, False),
                (Service(type='typless', source=None),
                    {'mime_type': 'application/pdf'}, True),
                (Service(type='typless', source=None),
                    {'mime_type': 'application/octet-stream'}, False),
                ]:
            with self.subTest(service=service, pattern=pattern):
                self.assertEqual(service.match(pattern), result)


del ModuleTestCase
