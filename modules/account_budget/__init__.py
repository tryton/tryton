# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = [
    'BudgetMixin', 'BudgetLineMixin',
    'CopyBudgetMixin', 'CopyBudgetStartMixin',
    ]


def __getattr__(name):
    if name in __all__:
        from . import account
        return getattr(account, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
