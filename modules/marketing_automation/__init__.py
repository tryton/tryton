# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool

from . import (
    ir, marketing_automation, marketing_automation_reporting, party, routes,
    sale, web)

__all__ = ['register', 'routes']


def register():
    Pool.register(
        ir.Cron,
        ir.Email,
        marketing_automation.Scenario,
        marketing_automation.Activity,
        marketing_automation.Record,
        marketing_automation.RecordActivity,
        marketing_automation_reporting.Context,
        marketing_automation_reporting.Scenario,
        marketing_automation_reporting.Activity,
        party.Party,
        party.PartyUnsubscribedScenario,
        web.ShortenedURL,
        module='marketing_automation', type_='model')
    Pool.register(
        sale.Sale,
        module='marketing_automation', type_='model',
        depends=['sale'])
    Pool.register(
        marketing_automation.Unsubscribe,
        module='marketing_automation', type_='report')
