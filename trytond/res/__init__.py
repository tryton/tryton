# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from ..pool import Pool

from .group import *
from .user import *
from .ir import *
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        Group,
        User,
        LoginAttempt,
        Group2,
        UserAction,
        UserGroup,
        Warning_,
        UserApplication,
        UserConfigStart,
        UIMenuGroup,
        ActionGroup,
        ModelFieldGroup,
        ModelButtonGroup,
        ModelButtonRule,
        ModelButtonClick,
        RuleGroupGroup,
        RuleGroupUser,
        Lang,
        SequenceType,
        SequenceTypeGroup,
        Sequence,
        SequenceStrict,
        ModuleConfigWizardItem,
        module='res', type_='model')
    Pool.register(
        UserConfig,
        module="res", type_='wizard')
