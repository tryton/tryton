# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import party

__all__ = ['register']


def register():
    Pool.register(
        party.Purpose,
        party.CaseStatus,
        party.Case,
        party.EventParty,
        party.EventContact,
        party.Event,
        module='party_communication', type_='model')
    Pool.register(
        module='party_communication', type_='wizard')
    Pool.register(
        module='party_communication', type_='report')
    Pool.register(
        party.Case_Invoice,
        module='party_communication', type_='model',
        depends=['account_invoice'])
    Pool.register(
        party.Case_Purchase,
        module='party_communication', type_='model', depends=['purchase'])
    Pool.register(
        party.Case_PurchaseRequestQuotation,
        module='party_communication', type_='model',
        depends=['purchase_request_quotation'])
    Pool.register(
        party.Case_Sale,
        module='party_communication', type_='model', depends=['sale'])
    Pool.register(
        party.Case_SaleComplaint,
        module='party_communication', type_='model',
        depends=['sale_complaint'])
    Pool.register(
        party.Case_SaleOpportunity,
        module='party_communication', type_='model',
        depends=['sale_opportunity'])
    Pool.register(
        party.Case_SaleSubscription,
        module='party_communication', type_='model',
        depends=['sale_subscription'])
