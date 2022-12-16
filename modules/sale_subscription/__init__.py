# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import configuration
from . import recurrence
from . import service
from . import subscription
from . import invoice
from . import party


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationSequence,
        recurrence.RecurrenceRuleSet,
        recurrence.RecurrenceRule,
        service.Service,
        subscription.Subscription,
        subscription.Line,
        subscription.LineConsumption,
        subscription.CreateLineConsumptionStart,
        subscription.CreateSubscriptionInvoiceStart,
        invoice.InvoiceLine,
        module='sale_subscription', type_='model')
    Pool.register(
        subscription.CreateLineConsumption,
        subscription.CreateSubscriptionInvoice,
        party.PartyReplace,
        party.PartyErase,
        module='sale_subscription', type_='wizard')
    Pool.register(
        module='sale_subscription', type_='report')
