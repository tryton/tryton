# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import fields
from trytond.pool import PoolMeta


class UoM(metaclass=PoolMeta):
    __name__ = 'product.uom'

    ups_code = fields.Selection([
            ('BA', "Barrel"),
            ('BE', "Bundle"),
            ('BG', "Bag"),
            ('BH', "Bunch"),
            ('BOX', "Box"),
            ('BT', "Bolt"),
            ('BU', "Butt"),
            ('CI', "Canister"),
            ('CM', "Centimeter"),
            ('CON', "Container"),
            ('CR', "Crate"),
            ('CS', "Case"),
            ('CT', "Carton"),
            ('CY', "Cylinder"),
            ('DOZ', "Dozen"),
            ('EA', "Each"),
            ('EN', "Envelope"),
            ('FT', "Feet"),
            ('KG', "Kilogram"),
            ('KGS', "Kilograms"),
            ('LB', "Pound"),
            ('LBS', "Pounds"),
            ('L', "Liter"),
            ('M', "Meter"),
            ('NMB', "Number"),
            ('PA', "Packet"),
            ('PAL', "Pallet"),
            ('PC', "Piece"),
            ('PCS', "Pieces"),
            ('PF', "Proof Liters"),
            ('PKG', "Package"),
            ('PR', "Pair"),
            ('PRS', "Pairs"),
            ('RL', "Roll"),
            ('SET', "Set"),
            ('SME', "Square Meters"),
            ('SYD', "Square Yards"),
            ('TU', "Tube"),
            ('YD', "Yard"),
            ('OTH', "Other"),
            ], "UPS Code", required=True)

    @classmethod
    def default_ups_code(cls):
        return 'OTH'
