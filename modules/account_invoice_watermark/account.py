# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from io import BytesIO

from PyPDF2 import PdfFileReader, PdfFileWriter

from trytond.pool import Pool, PoolMeta
from trytond.report import Report
from trytond.transaction import Transaction


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def _execute(cls, records, header, data, action):
        pool = Pool()
        Watermark = pool.get('account.invoice.watermark', type='report')
        format_, data = super()._execute(records, header, data, action)
        if format_ == 'pdf':
            invoice, = records
            report_id = cls.get_report_id(invoice)
            if report_id is not None:
                if invoice.party.lang:
                    language = invoice.party.lang.code
                else:
                    language = Transaction().language
                with Transaction().set_context(language=language):
                    _, watermark, _, _ = Watermark.execute([invoice.id], {
                            'action_id': report_id,
                            })
                data = cls.merge(data, watermark)
        return format_, data

    @classmethod
    def get_report_id(cls, invoice):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        if invoice.state == 'paid':
            return ModelData.get_id(
                'account_invoice_watermark', 'report_invoice_watermark_paid')
        elif invoice.state == 'draft':
            return ModelData.get_id(
                'account_invoice_watermark', 'report_invoice_watermark_draft')

    @classmethod
    def merge(cls, invoice, watermark):
        output = PdfFileWriter()
        invoice = PdfFileReader(BytesIO(invoice))
        watermark = PdfFileReader(BytesIO(watermark)).getPage(0)
        for i in range(invoice.getNumPages()):
            page = invoice.getPage(i)
            page.mergePage(watermark)
            output.addPage(page)
        data = BytesIO()
        output.write(data)
        return data.getvalue()


class InvoiceWatermark(Report):
    __name__ = 'account.invoice.watermark'
