# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import functools
import os

import genshi
import genshi.template

from trytond.model import Model
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.tools import cached_property
from trytond.transaction import Transaction

# XXX fix: https://genshi.edgewall.org/ticket/582
from genshi.template.astutil import ASTCodeGenerator, ASTTransformer
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


def has_goods_assets(func):
    @functools.wraps(func)
    def wrapper(self):
        if any(l.product.type in {'goods', 'assets'}
                for l in self.invoice.lines if l.product):
            return func(self)
    return wrapper


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class Invoice(Model):
    "EDocument UN/CEFACT Invoice"
    __name__ = 'edocument.uncefact.invoice'
    __no_slots__ = True  # to work with cached_property

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.__rpc__.update({
                'render': RPC(instantiate=0),
                })

    def __init__(self, invoice):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if int(invoice) >= 0:
            invoice = Invoice(int(invoice))
            with Transaction().set_context(language=invoice.party_lang):
                self.invoice = invoice.__class__(int(invoice))
        else:
            self.invoice = invoice

    def render(self, template):
        if self.invoice.state not in {'posted', 'paid'}:
            raise ValueError("Invoice must be posted")
        tmpl = self._get_template(template)
        if not tmpl:
            raise NotImplementedError
        return (tmpl.generate(this=self)
            .filter(remove_comment)
            .render()
            .encode('utf-8'))

    def _get_template(self, version):
        return loader.load(os.path.join(version, 'CrossIndustryInvoice.xml'))

    @cached_property
    def type_code(self):
        if self.invoice.type == 'out':
            if all(l.amount < 0 for l in self.lines if l.product):
                return '381'
            else:
                return '380'
        else:
            if all(l.amount < 0 for l in self.lines if l.product):
                return '261'
            else:
                return '389'

    @cached_property
    def type_sign(self):
        "The sign of the quantity depending of the type code"
        if self.type_code in {'381', '261'}:
            return -1
        return 1

    @cached_property
    def lines(self):
        return [l for l in self.invoice.lines if l.type == 'line']

    @cached_property
    def seller_trade_party(self):
        if self.invoice.type == 'out':
            return self.invoice.company.party
        else:
            return self.invoice.party

    @cached_property
    def seller_trade_address(self):
        if self.invoice.type == 'out':
            return self.invoice.company.party.address_get('invoice')
        else:
            return self.invoice.invoice_address

    @cached_property
    def seller_trade_tax_identifier(self):
        if self.invoice.type == 'out':
            return self.invoice.tax_identifier
        else:
            return self.invoice.party_tax_identifier

    @cached_property
    def buyer_trade_party(self):
        if self.invoice.type == 'out':
            return self.invoice.party
        else:
            return self.invoice.company.party

    @cached_property
    def buyer_trade_address(self):
        if self.invoice.type == 'out':
            return self.invoice.invoice_address
        else:
            return None

    @cached_property
    def buyer_trade_tax_identifier(self):
        if self.invoice.type == 'out':
            return self.invoice.party_tax_identifier
        else:
            return self.invoice.tax_identifier

    @cached_property
    @has_goods_assets
    def ship_to_trade_party(self):
        if self.invoice.type == 'out':
            if getattr(self.invoice, 'sales'):
                sale = self.invoice.sales[0]  # XXX
                if sale.shipment_party != self.buyer_trade_party:
                    return sale.shipment_party
        else:
            if self.invoice.purchases:
                purchase = self.invoice.purchases[0]  # XXX
                address = purchase.warehouse.address
                if (address and address.party != self.buyer_trade_party):
                    return address.party

    @cached_property
    @has_goods_assets
    def ship_to_trade_address(self):
        if self.invoice.type == 'out':
            if getattr(self.invoice, 'sales'):
                sale = self.invoice.sales[0]  # XXX
                if sale.shipment_party != self.buyer_trade_party:
                    return sale.shipment_address
        else:
            if getattr(self.invoice, 'purchases'):
                purchase = self.invoice.purchases[0]  # XXX
                address = purchase.warehouse.address
                if (address and address.party != self.buyer_trade_party):
                    return address

    @cached_property
    @has_goods_assets
    def ship_from_trade_party(self):
        if self.invoice.type == 'out':
            if getattr(self.invoice, 'sales'):
                sale = self.invoice.sales[0]  # XXX
                address = sale.warehouse.address
                if address and address.party != self.seller_trade_party:
                    return address.shipment_party

    @cached_property
    @has_goods_assets
    def ship_from_trade_address(self):
        if self.invoice.type == 'out':
            if getattr(self.invoice, 'sales'):
                sale = self.invoice.sales[0]  # XXX
                address = sale.warehouse.address
                if address and address.party != self.seller_trade_party:
                    return address

    @cached_property
    def payment_reference(self):
        return self.invoice.number

    @classmethod
    def party_legal_ids(cls, party, address):
        return []
