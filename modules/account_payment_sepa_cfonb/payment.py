# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os

import genshi
import genshi.template

from trytond.pool import PoolMeta
from trytond.modules.account_payment_sepa import payment as sepa_payment


class Journal(metaclass=PoolMeta):
    __name__ = 'account.payment.journal'

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        payable_flavor_cfonb = ('pain.001.001.03-cfonb',
            'pain.001.001.03 CFONB')
        receivable_flavor_cfonb = ('pain.008.001.02-cfonb',
            'pain.008.001.02 CFONB')
        for flavor, field in [
                (payable_flavor_cfonb, cls.sepa_payable_flavor),
                (receivable_flavor_cfonb, cls.sepa_receivable_flavor),
                ]:
            if flavor not in field.selection:
                field.selection.append(flavor)


loader = genshi.template.TemplateLoader([
        os.path.join(os.path.dirname(__file__), 'template'),
        os.path.join(
            os.path.dirname(
                sepa_payment.__file__), 'template'),
        ], auto_reload=True)


class Group(metaclass=PoolMeta):
    __name__ = 'account.payment.group'

    def get_sepa_template(self):
        if (self.kind == 'payable'
                and self.journal.sepa_payable_flavor.endswith('-cfonb')):
            return loader.load('%s.xml' % self.journal.sepa_payable_flavor)
        if (self.kind == 'receivable'
                and self.journal.sepa_receivable_flavor.endswith('-cfonb')):
            return loader.load('%s.xml' % self.journal.sepa_receivable_flavor)
        return super(Group, self).get_sepa_template()
