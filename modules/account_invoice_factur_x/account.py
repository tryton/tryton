# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from io import BytesIO

import facturx
from lxml import etree

from trytond.i18n import gettext
from trytond.model import ModelSQL, fields
from trytond.modules.account_invoice.exceptions import InvoiceReportError
from trytond.modules.company.model import CompanyValueMixin
from trytond.pool import Pool, PoolMeta

PROFILES = [
    (None, ""),
    ('urn:cen.eu:en16931:2017', "EN 16931"),
    ('urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended',
        "EXTENDED"),
    ('urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic',
        "BASIC"),
    ('urn:factur-x.eu:1p0:basicwl', "BASIC WL"),
    ('urn:factur-x.eu:1p0:minimum', "Minimum"),
    ]


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    default_factur_x_profile = fields.MultiValue(fields.Selection(
            PROFILES, "Default Factur-X Profile", sort=False,
            help="Leave this field empty if you do want to include Factur-X."))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'default_factur_x_profile':
            return pool.get('account.configuration.factur_x')
        return super().multivalue_model(field)


class ConfigurationFacturX(ModelSQL, CompanyValueMixin):
    __name__ = 'account.configuration.factur_x'

    default_factur_x_profile = fields.Selection(
        PROFILES, "Default Factur-X Profile")


class InvoiceReport(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def store(cls, invoice, format_, data):
        profile = invoice.party.get_multivalue(
            'factur_x_profile', company=invoice.company.id)
        if profile:
            if format_ != 'pdf':
                raise InvoiceReportError(gettext(
                        'account_invoice_factur_x.msg_invoice_pdf_factur_x',
                        invoice=invoice.rec_name))
            data = cls.add_factur_x(invoice, profile, data)
        return super().store(invoice, format_, data)

    @classmethod
    def add_factur_x(cls, invoice, profile, pdf):
        "Add Factur-X objects to PDF"
        pool = Pool()
        EInvoice = pool.get('edocument.uncefact.invoice')

        pdf = BytesIO(pdf)
        level = profile.split(':')[-1]
        einvoice = EInvoice(invoice).render(
            '16B-CII', exchange_context=profile)
        tree = etree.parse(
            BytesIO(einvoice),
            etree.XMLParser(remove_blank_text=True))
        for elem in tree.iter('*'):
            if elem.text is not None:
                elem.text = elem.text.strip()
            if elem.tail is not None:
                elem.tail = elem.tail.strip()
        einvoice = etree.tostring(
            tree, encoding='utf-8', xml_declaration=True,
            pretty_print=True)
        facturx.generate_from_file(
            pdf,
            einvoice,
            flavor='factur-x',
            level=level,
            check_xsd=True,
            check_schematron=False,  # requires a running saxon-server
            pdf_metadata=cls.factur_x_metadata(invoice),
            lang=invoice.party.lang.code if invoice.party.lang else None,
            attachments={
                n: {'filedata': v}
                for n, v in cls.factur_x_attachments(invoice)},
            )
        return pdf.getvalue()

    @classmethod
    def factur_x_metadata(cls, invoice):
        return {
            'author': invoice.company.party.name,
            'keywords': ', '.join([invoice.type_name, 'Factur-X']),
            'title': invoice.rec_name,
            'subject': invoice.description,
            }

    @classmethod
    def factur_x_attachments(cls, invoice):
        yield from ()
