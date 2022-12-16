# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from ..pool import Pool
from . import configuration
from . import translation
from . import sequence
from . import ui
from . import action
from . import model
from . import attachment
from . import note
from . import cron
from . import lang
from . import export
from . import rule
from . import module
from . import cache
from . import date
from . import trigger
from . import session
from . import queue
from . import calendar_
from . import message
from . import routes

__all__ = ['register', 'routes']


def register():
    Pool.register(
        configuration.Configuration,
        translation.Translation,
        translation.TranslationSetStart,
        translation.TranslationSetSucceed,
        translation.TranslationCleanStart,
        translation.TranslationCleanSucceed,
        translation.TranslationUpdateStart,
        translation.TranslationExportStart,
        translation.TranslationExportResult,
        sequence.SequenceType,
        sequence.Sequence,
        sequence.SequenceStrict,
        ui.menu.UIMenu,
        ui.menu.UIMenuFavorite,
        ui.view.View,
        ui.view.ShowViewStart,
        ui.view.ViewTreeWidth,
        ui.view.ViewTreeState,
        ui.view.ViewSearch,
        ui.icon.Icon,
        action.Action,
        action.ActionKeyword,
        action.ActionReport,
        action.ActionActWindow,
        action.ActionActWindowView,
        action.ActionActWindowDomain,
        action.ActionWizard,
        action.ActionURL,
        model.Model,
        model.ModelField,
        model.ModelAccess,
        model.ModelFieldAccess,
        model.ModelButton,
        model.ModelButtonRule,
        model.ModelButtonClick,
        model.ModelButtonReset,
        model.ModelData,
        model.PrintModelGraphStart,
        attachment.Attachment,
        note.Note,
        note.NoteRead,
        cron.Cron,
        lang.Lang,
        lang.LangConfigStart,
        export.Export,
        export.ExportLine,
        rule.RuleGroup,
        rule.Rule,
        module.Module,
        module.ModuleDependency,
        module.ModuleConfigWizardItem,
        module.ModuleConfigWizardFirst,
        module.ModuleConfigWizardOther,
        module.ModuleConfigWizardDone,
        module.ModuleActivateUpgradeStart,
        module.ModuleActivateUpgradeDone,
        cache.Cache,
        date.Date,
        trigger.Trigger,
        trigger.TriggerLog,
        session.Session,
        session.SessionWizard,
        queue.Queue,
        calendar_.Month,
        calendar_.Day,
        message.Message,
        module='ir', type_='model')
    Pool.register(
        translation.TranslationSet,
        translation.TranslationClean,
        translation.TranslationUpdate,
        translation.TranslationExport,
        translation.TranslationReport,
        ui.view.ShowView,
        model.PrintModelGraph,
        module.ModuleConfigWizard,
        module.ModuleActivateUpgrade,
        module.ModuleConfig,
        lang.LangConfig,
        module='ir', type_='wizard')
    Pool.register(
        model.ModelGraph,
        model.ModelWorkflowGraph,
        module='ir', type_='report')
