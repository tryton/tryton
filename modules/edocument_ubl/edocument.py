# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import mimetypes
import os
from base64 import b64encode
from itertools import groupby

import genshi
import genshi.template
# XXX fix: https://genshi.edgewall.org/ticket/582
from genshi.template.astutil import ASTCodeGenerator, ASTTransformer

from trytond.model import Model
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.tools import cached_property
from trytond.transaction import Transaction

if not hasattr(ASTCodeGenerator, 'visit_NameConstant'):
    def visit_NameConstant(self, node):
        if node.value is None:
            self._write('None')
        elif node.value is True:
            self._write('True')
        elif node.value is False:
            self._write('False')
        else:
            raise Exception("Unknown NameConstant %r" % (node.value,))
    ASTCodeGenerator.visit_NameConstant = visit_NameConstant
if not hasattr(ASTTransformer, 'visit_NameConstant'):
    # Re-use visit_Name because _clone is deleted
    ASTTransformer.visit_NameConstant = ASTTransformer.visit_Name

loader = genshi.template.TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'template'),
    auto_reload=True)


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class Invoice(Model):
    __name__ = 'edocument.ubl.invoice'
    __slots__ = ('invoice',)

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.__rpc__.update({
                'render': RPC(instantiate=0),
                })

    def __init__(self, invoice):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        super().__init__()
        if int(invoice) >= 0:
            invoice = Invoice(int(invoice))
            with Transaction().set_context(language=invoice.party_lang):
                self.invoice = invoice.__class__(int(invoice))
        else:
            self.invoice = invoice

    def render(self, template, specification=None):
        if self.invoice.state not in {'posted', 'paid'}:
            raise ValueError("Invoice must be posted")
        tmpl = self._get_template(template)
        if not tmpl:
            raise NotImplementedError
        return (tmpl.generate(this=self, specification=specification)
            .filter(remove_comment)
            .render()
            .encode('utf-8'))

    def _get_template(self, version):
        if self.invoice.sequence_type == 'credit_note':
            return loader.load(os.path.join(version, 'CreditNote.xml'))
        else:
            return loader.load(os.path.join(version, 'Invoice.xml'))

    @cached_property
    def type_code(self):
        if self.invoice.type == 'out':
            if self.invoice.sequence_type == 'credit_note':
                return '381'
            else:
                return '380'
        else:
            return '389'

    @property
    def additional_documents(self):
        pool = Pool()
        InvoiceReport = pool.get('account.invoice', type='report')
        oext, content, _, filename = InvoiceReport.execute(
            [self.invoice.id], {})
        filename = f'{filename}.{oext}'
        mimetype = mimetypes.guess_type(filename)[0]
        yield {
            'id': self.invoice.number,
            'type': 'binary',
            'binary': b64encode(content).decode(),
            'mimetype': mimetype,
            'filename': filename,
            }

    @cached_property
    def accounting_supplier_party(self):
        if self.invoice.type == 'out':
            return self.invoice.company.party
        else:
            return self.invoice.party

    @cached_property
    def accounting_supplier_address(self):
        if self.invoice.type == 'out':
            return self.invoice.company.party.address_get('invoice')
        else:
            return self.invoice.invoice_address

    @cached_property
    def accounting_supplier_tax_identifier(self):
        if self.invoice.type == 'out':
            return self.invoice.tax_identifier
        else:
            return self.invoice.party_tax_identifier

    @cached_property
    def accounting_customer_party(self):
        if self.invoice.type == 'out':
            return self.invoice.party
        else:
            return self.invoice.company.party

    @cached_property
    def accounting_customer_address(self):
        if self.invoice.type == 'out':
            return self.invoice.invoice_address
        else:
            return self.invoice.company.party.address_get('invoice')

    @cached_property
    def accounting_customer_tax_identifier(self):
        if self.invoice.type == 'out':
            return self.invoice.party_tax_identifier
        else:
            return self.invoice.tax_identifier

    @property
    def taxes(self):
        def key(line):
            return line.tax.group
        for group, lines in groupby(
                sorted(self.invoice.taxes, key=key), key=key):
            lines = list(lines)
            amount = sum(l.amount for l in lines)
            yield group, lines, amount

    @cached_property
    def lines(self):
        return [l for l in self.invoice.lines if l.type == 'line']
