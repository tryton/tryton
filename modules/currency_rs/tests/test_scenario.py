# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import os

from trytond.tests.test_tryton import load_doc_tests

if (os.getenv('NBS_RS_USERNAME')
        and os.getenv('NBS_RS_PASSWORD')
        and os.getenv('NBS_RS_LICENSE_ID')):
    def load_tests(*args, **kwargs):
        return load_doc_tests(__name__, __file__, *args, **kwargs)
