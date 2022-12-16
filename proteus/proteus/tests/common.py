# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from unittest import TestCase

from trytond.tests.test_tryton import db_exist, create_db

from proteus import config


class ProteusTestCase(TestCase):

    def setUp(self):
        if not db_exist():
            create_db()
        self.config = config.set_trytond()
