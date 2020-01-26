# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .configuration import *
from .bom import *
from .product import *
from .production import *
from .stock import *
from . import ir


def register():
    Pool.register(
        Configuration,
        ConfigurationProductionSequence,
        BOM,
        BOMInput,
        BOMOutput,
        BOMTree,
        OpenBOMTreeStart,
        OpenBOMTreeTree,
        Production,
        AssignFailed,
        Template,
        Product,
        ProductBom,
        ProductionLeadTime,
        Location,
        Move,
        ir.Cron,
        module='production', type_='model')
    Pool.register(
        Assign,
        OpenBOMTree,
        module='production', type_='wizard')
