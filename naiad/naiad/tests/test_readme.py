# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import doctest
import os
from unittest.mock import patch

import respx

from trytond.tests.test_tryton import DB_NAME, app

from .common import NaiadTestCase

here = os.path.dirname(__file__)
readme = os.path.normpath(os.path.join(here, '..', '..', 'README.rst'))
respx_mock = respx.mock(base_url=NaiadTestCase.base_url)
patcher = patch('trytond.res.user._send_email')


def doctest_setup(test):
    NaiadTestCase.setUpClass()
    os.environ['NAIAD_KEY'] = NaiadTestCase.key
    os.environ['NAIAD_URL'] = f'{NaiadTestCase.base_url}/{DB_NAME}'
    respx_mock.start()
    respx_mock.route().mock(side_effect=respx.WSGIHandler(app))
    patcher.start()


def doctest_teardown(test):
    patcher.stop()
    respx_mock.stop()
    NaiadTestCase.tearDownClass()


def load_tests(loader, tests, pattern):
    if os.path.isfile(readme):
        tests.addTest(doctest.DocFileSuite(
                readme, module_relative=False,
                setUp=doctest_setup, tearDown=doctest_teardown,
                encoding='utf-8',
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return tests
