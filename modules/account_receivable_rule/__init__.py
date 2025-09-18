# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

__all__ = ['AccountRuleAbstract', 'AccountRuleAccountAbstract']


def __getattr__(name):
    if name in {'AccountRuleAbstract', 'AccountRuleAccountAbstract'}:
        from . import account
        return getattr(account, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
