# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import group
from . import user
from . import ir
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        group.Group,
        user.User,
        user.LoginAttempt,
        user.UserAction,
        user.UserGroup,
        user.Warning_,
        user.UserApplication,
        user.UserConfigStart,
        ir.UIMenuGroup,
        ir.ActionGroup,
        ir.Action,
        ir.ActionReport,
        ir.ActionActWindow,
        ir.ActionWizard,
        ir.ActionURL,
        ir.ActionKeyword,
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
        user.UserConfig,
        module="res", type_='wizard')
    Pool.register(
        user.EmailResetPassword,
        module='res', type_='report')
