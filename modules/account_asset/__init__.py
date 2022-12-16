# This file is part of Tryton.  The COPYRIGHT file at the top level of this
# repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import asset
from . import product
from . import invoice
from . import account
from . import purchase


def register():
    Pool.register(
        asset.Asset,
        asset.AssetLine,
        asset.AssetUpdateMove,
        asset.CreateMovesStart,
        asset.UpdateAssetStart,
        asset.UpdateAssetShowDepreciation,
        asset.PrintDepreciationTableStart,
        product.Category,
        product.CategoryAccount,
        product.Template,
        product.TemplateAccount,
        product.Product,
        invoice.InvoiceLine,
        account.Configuration,
        account.ConfigurationAssetSequence,
        account.Move,
        account.Period,
        module='account_asset', type_='model')
    Pool.register(
        purchase.PurchaseLine,
        module='account_asset', type_='model', depends=['purchase'])
    Pool.register(
        asset.CreateMoves,
        asset.UpdateAsset,
        asset.PrintDepreciationTable,
        module='account_asset', type_='wizard')
    Pool.register(
        asset.AssetDepreciationTable,
        module='account_asset', type_='report')
