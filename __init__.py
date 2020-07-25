# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from . import configuration
from . import bom
from . import product
from . import production
from . import stock
from . import ir


def register():
    Pool.register(
        configuration.Configuration,
        configuration.ConfigurationProductionSequence,
        bom.BOM,
        bom.BOMInput,
        bom.BOMOutput,
        bom.BOMTree,
        bom.OpenBOMTreeStart,
        bom.OpenBOMTreeTree,
        production.Production,
        product.Template,
        product.Product,
        product.ProductBom,
        product.ProductionLeadTime,
        stock.Location,
        stock.Move,
        ir.Cron,
        module='production', type_='model')
    Pool.register(
        bom.OpenBOMTree,
        module='production', type_='wizard')
