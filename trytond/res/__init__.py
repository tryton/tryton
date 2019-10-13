# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from ..pool import Pool

from .group import *
from .user import *
from . import ir
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        Group,
        User,
        LoginAttempt,
        UserAction,
        UserGroup,
        Warning_,
        UserApplication,
        UserConfigStart,
        ir.UIMenuGroup,
        ir.ActionGroup,
        ir.ModelButtonGroup,
        ir.ModelButtonRule,
        ir.ModelButtonClick,
        ir.RuleGroupGroup,
        ir.Lang,
        ir.SequenceType,
        ir.SequenceTypeGroup,
        ir.Sequence,
        ir.SequenceStrict,
        ir.ModuleConfigWizardItem,
        ir.Export,
        ir.Export_Group,
        ir.Export_Write_Group,
        module='res', type_='model')
    Pool.register(
        UserConfig,
        module="res", type_='wizard')
    Pool.register(
        EmailResetPassword,
        module='res', type_='report')
