# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from .asset import *
from .product import *
from .invoice import *
from .account import *
from .purchase import *


def register():
    Pool.register(
        Asset,
        AssetLine,
        AssetUpdateMove,
        CreateMovesStart,
        UpdateAssetStart,
        UpdateAssetShowDepreciation,
        PrintDepreciationTableStart,
        Category,
        Template,
        Product,
        InvoiceLine,
        Configuration,
        Move,
        PurchaseLine,
        module='account_asset', type_='model')
    Pool.register(
        CreateMoves,
        UpdateAsset,
        PrintDepreciationTable,
        module='account_asset', type_='wizard')
    Pool.register(
        AssetDepreciationTable,
        module='account_asset', type_='report')
