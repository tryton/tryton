# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelView
from trytond.pool import Pool


class TestMixin:
    pass


class TestSecondMixin:
    pass


class NotMixin:
    pass


def register(module):
    Pool.register_mixin(TestMixin, ModelView, module=module)
    Pool.register_mixin(TestSecondMixin, ModelView, module=module)
    Pool.register_mixin(NotMixin, ModelView, module='__wrong__')
