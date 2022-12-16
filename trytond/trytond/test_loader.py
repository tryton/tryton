# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from unittest import TestLoader


class Loader(TestLoader):

    def loadTestsFromModule(self, module):
        return module.suite()
