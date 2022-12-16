#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from ..pool import Pool
from .group import *
from .user import *
from .request import *
from .ir import *


def register():
    Pool.register(
        Group,
        User,
        LoginAttempt,
        Group2,
        UserAction,
        UserGroup,
        Warning_,
        UserConfigStart,
        Request,
        RequestLink,
        RequestHistory,
        RequestReference,
        UIMenuGroup,
        ActionGroup,
        ModelFieldGroup,
        ModelButtonGroup,
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
