#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import copy

from trytond.model import Model
from trytond.pyson import Eval


class Configuration(Model):
    _name = 'party.configuration'

    def __init__(self):
        super(Configuration, self).__init__()

        self.party_sequence = copy.copy(self.party_sequence)
        self.party_sequence.domain = copy.copy(self.party_sequence.domain)
        self.party_sequence.domain = [
            self.party_sequence.domain,
            ('company', 'in', [Eval('context', {}).get('company'), None])]

Configuration()
