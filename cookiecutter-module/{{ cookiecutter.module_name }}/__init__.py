{% if not cookiecutter.prefix -%}
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

{% endif -%}
from trytond.pool import Pool

__all__ = ['register']


def register():
    Pool.register(
        module='{{ cookiecutter.module_name }}', type_='model')
    Pool.register(
        module='{{ cookiecutter.module_name }}', type_='wizard')
    Pool.register(
        module='{{ cookiecutter.module_name }}', type_='report')
