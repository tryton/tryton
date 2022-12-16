# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from unittest import TestCase

from proteus import config
from trytond.tests.test_tryton import create_db, db_exist


class ProteusTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        if not db_exist():
            create_db()

    def setUp(self):
        self.config = config.set_trytond()
