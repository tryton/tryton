# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import group, ir, routes, user

__all__ = ['register', 'routes']


def register():
    Pool.register(
        group.Group,
        user.User,
        user.LoginAttempt,
        user.UserDevice,
        user.UserAction,
        user.UserGroup,
        user.Warning_,
        user.UserApplication,
        user.UserConfigStart,
        ir.UIMenu,
        ir.UIMenuGroup,
        ir.ActionGroup,
        ir.Action,
        ir.ActionReport,
        ir.ActionActWindow,
        ir.ActionWizard,
        ir.ActionURL,
        ir.ActionKeyword,
        ir.ModelButton,
        ir.ModelButtonGroup,
        ir.ModelButtonRule,
        ir.ModelButtonClick,
        ir.RuleGroup,
        ir.RuleGroupGroup,
        ir.Rule,
        ir.SequenceType,
        ir.SequenceTypeGroup,
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
