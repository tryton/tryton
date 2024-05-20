# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os

from trytond.tests.test_tryton import TEST_NETWORK, load_doc_tests


def load_tests(*args, **kwargs):
    if (not TEST_NETWORK
            or not (os.getenv('CHORUS_PISTE_CLIENT_ID')
                and os.getenv('CHORUS_PISTE_CLIENT_SECRET')
                and os.getenv('CHORUS_LOGIN')
                and os.getenv('CHORUS_PASSWORD')
                and os.getenv('CHORUS_COMPANY_SIRET')
                and os.getenv('CHORUS_CUSTOMER_SIRET'))):
        kwargs.setdefault('skips', set()).add(
            'scenario_account_fr_chorus_invoice.rst')
    return load_doc_tests(__name__, __file__, *args, **kwargs)
