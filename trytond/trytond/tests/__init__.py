# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

try:
    import pkg_resources
except ImportError:
    pkg_resources = None


from ..pool import Pool
from .test import *
from .model import *
from .modelview import *
from .mptt import *
from .import_data import *
from .export_data import *
from .trigger import *
from .access import *
from .wizard import *
from .workflow import *
from .copy_ import *
from history import *
from .field_context import *
from . import multivalue


def register():
    Pool.register(
        Boolean,
        BooleanDefault,
        Integer,
        IntegerDefault,
        IntegerRequired,
        IntegerDomain,
        Float,
        FloatDefault,
        FloatRequired,
        FloatDigits,
        Numeric,
        NumericDefault,
        NumericRequired,
        NumericDigits,
        Char,
        CharDefault,
        CharRequired,
        CharSize,
        CharTranslate,
        Text,
        TextDefault,
        TextRequired,
        TextSize,
        TextTranslate,
        Date,
        DateDefault,
        DateRequired,
        DateTime,
        DateTimeDefault,
        DateTimeRequired,
        DateTimeFormat,
        Time,
        TimeDefault,
        TimeRequired,
        TimeFormat,
        TimeDelta,
        TimeDeltaDefault,
        TimeDeltaRequired,
        One2One,
        One2OneTarget,
        One2OneRelation,
        One2OneRequired,
        One2OneRequiredRelation,
        One2OneDomain,
        One2OneDomainRelation,
        One2Many,
        One2ManyTarget,
        One2ManyRequired,
        One2ManyRequiredTarget,
        One2ManyReference,
        One2ManyReferenceTarget,
        One2ManySize,
        One2ManySizeTarget,
        One2ManySizePYSON,
        One2ManySizePYSONTarget,
        One2ManyFilter,
        One2ManyFilterTarget,
        One2ManyFilterDomain,
        One2ManyFilterDomainTarget,
        Many2Many,
        Many2ManyTarget,
        Many2ManyRelation,
        Many2ManyRequired,
        Many2ManyRequiredTarget,
        Many2ManyRequiredRelation,
        Many2ManyReference,
        Many2ManyReferenceTarget,
        Many2ManyReferenceRelation,
        Many2ManySize,
        Many2ManySizeTarget,
        Many2ManySizeRelation,
        Many2ManyTree,
        Many2ManyTreeRelation,
        Many2ManyFilter,
        Many2ManyFilterTarget,
        Many2ManyFilterRelation,
        Many2ManyFilterDomain,
        Many2ManyFilterDomainTarget,
        Many2ManyFilterDomainRelation,
        Reference,
        ReferenceTarget,
        ReferenceRequired,
        Selection,
        SelectionRequired,
        DictSchema,
        Dict,
        DictDefault,
        DictRequired,
        DictJSONB,
        Binary,
        BinaryDefault,
        BinaryRequired,
        BinaryFileStorage,
        Model,
        ModelParent,
        ModelChild,
        ModelChildChild,
        Singleton,
        URLObject,
        ModelStorage,
        ModelStorageRequired,
        ModelStorageContext,
        ModelSQLRequiredField,
        ModelSQLTimestamp,
        ModelSQLFieldSet,
        Model4Union1,
        Model4Union2,
        Model4Union3,
        Model4Union4,
        Union,
        UnionUnion,
        Model4UnionTree1,
        Model4UnionTree2,
        UnionTree,
        SequenceOrderedModel,
        ModelViewChangedValues,
        ModelViewChangedValuesTarget,
        ModelViewButton,
        ModelViewRPC,
        ModelViewEmptyPage,
        MPTT,
        ImportDataBoolean,
        ImportDataInteger,
        ImportDataIntegerRequired,
        ImportDataFloat,
        ImportDataFloatRequired,
        ImportDataNumeric,
        ImportDataNumericRequired,
        ImportDataChar,
        ImportDataText,
        ImportDataDate,
        ImportDataDateTime,
        ImportDataSelection,
        ImportDataMany2OneTarget,
        ImportDataMany2One,
        ImportDataMany2ManyTarget,
        ImportDataMany2Many,
        ImportDataMany2ManyRelation,
        ImportDataOne2Many,
        ImportDataOne2ManyTarget,
        ImportDataReferenceSelection,
        ImportDataReference,
        ExportDataTarget,
        ExportData,
        ExportDataTarget2,
        ExportDataRelation,
        Triggered,
        TriggerAction,
        TestAccess,
        TestWizardStart,
        WorkflowedModel,
        CopyOne2Many,
        CopyOne2ManyTarget,
        CopyOne2ManyReference,
        CopyOne2ManyReferenceTarget,
        CopyMany2Many,
        CopyMany2ManyTarget,
        CopyMany2ManyRelation,
        CopyMany2ManyReference,
        CopyMany2ManyReferenceTarget,
        CopyMany2ManyReferenceRelation,
        Many2OneTarget,
        Many2OneDomainValidation,
        Many2OneOrderBy,
        Many2OneSearch,
        Many2OneTree,
        Many2OneMPTT,
        Many2OneNoForeignKey,
        Many2OneTargetStorage,
        TestHistory,
        TestHistoryLine,
        FieldContextChild,
        FieldContextParent,
        NullOrder,
        module='tests', type_='model')
    Pool.register(
        TestWizard,
        module='tests', type_='wizard')

    multivalue.register('tests')

    if pkg_resources is not None:
        entry_points = pkg_resources.iter_entry_points('trytond.tests')
        for test_ep in entry_points:
            test_module = test_ep.load()
            if hasattr(test_module, 'register'):
                test_module.register('tests')


def suite():
    from .test_tryton import all_suite
    return all_suite()
