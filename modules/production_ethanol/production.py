# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import defaultdict
from itertools import groupby

from sql import Null
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.tools import grouped_slice
from trytond.transaction import Transaction


class Production(metaclass=PoolMeta):
    __name__ = 'production'

    ethanol_volume = fields.Function(
        fields.Float(
            "Alcohol Volume", digits='ethanol_volume_unit',
            help="The volume of ethanol/alcohol gained or lost."),
        'get_ethanol_volume')
    ethanol_volume_unit = fields.Function(
        fields.Many2One('product.uom', "Alcohol Volume UoM"),
        'get_ethanol_volume_unit')

    @classmethod
    def get_ethanol_volume(cls, productions, name):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        configuration = Configuration(1)
        UoM = pool.get('product.uom')
        ModelData = pool.get('ir.model.data')
        Move = pool.get('stock.move')

        move = Move.__table__()
        cursor = Transaction().connection.cursor()

        liter = UoM(ModelData.get_id('product', 'uom_liter'))
        production = Coalesce(move.production_input, move.production_output)
        query = move.select(
            production,
            Coalesce(Sum(
                    move.internal_ethanol_volume,
                    filter_=move.production_output != Null), 0)
            - Coalesce(Sum(
                    move.internal_ethanol_volume,
                    filter_=move.production_input != Null), 0),
            group_by=[production])

        ethanol_volumes = defaultdict(int)
        for sub_productions in grouped_slice(productions):
            sub_production_ids = [p.id for p in sub_productions]
            query.where = (
                move.production_input.in_(sub_production_ids)
                | move.production_output.in_(sub_production_ids))
            cursor.execute(*query)
            ethanol_volumes.update(cursor)

        for company, production in groupby(
                productions, key=lambda p: p.company):
            uom = configuration.get_multivalue(
                'ethanol_volume_uom', company=company.id)
            for production in productions:
                ethanol_volumes[production.id] = UoM.compute_qty(
                    liter, ethanol_volumes[production.id], uom)
        return ethanol_volumes

    @classmethod
    def get_ethanol_volume_unit(cls, productions, name):
        pool = Pool()
        Configuration = pool.get('stock.configuration')
        configuration = Configuration(1)
        units = {}
        for company, productions in groupby(
                productions, key=lambda m: m.company):
            uom = configuration.get_multivalue(
                'ethanol_volume_uom', company=company.id)
            for production in productions:
                units[production.id] = uom.id
        return units
