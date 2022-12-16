# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, fields
from trytond.pool import PoolMeta

from .mixin import MarketingAutomationMixin


class Party(MarketingAutomationMixin, metaclass=PoolMeta):
    __name__ = 'party.party'

    marketing_scenario_unsubscribed = fields.Many2Many(
        'party.party-unsubscribed-marketing.automation.scenario',
        'party', 'scenario', "Marketing Automation Scenario Unsubscribed")

    def get_marketing_party(self, name):
        return self.id

    @classmethod
    def search_marketing_party(cls, name, clause):
        _, operator, operand, *extra = clause[:3]
        nested = clause[0][len(name):]
        if not nested:
            if operator.endswith('where'):
                query = cls.search(operand, order=[], query=True)
                if operator.startswith('not'):
                    return [('id', 'not in', query)]
                else:
                    return [('id', 'in', query)]
            elif isinstance(operand, str):
                nested = 'rec_name'
            else:
                nested = 'id'
        else:
            nested = nested[1:]
        return [(nested, operator, operand, *extra)]


class PartyUnsubscribedScenario(ModelSQL):
    "Party Unsubscribed Scenario"
    __name__ = 'party.party-unsubscribed-marketing.automation.scenario'

    party = fields.Many2One(
        'party.party', "Party", required=True, ondelete='CASCADE')
    scenario = fields.Many2One(
        'marketing.automation.scenario', "Scenario",
        required=True, ondelete='CASCADE')
