from trytond.osv import fields, OSV

STATES = {
    'readonly': "active == False",
}

class UomCategory(OSV):
    'Product uom category'
    _name = 'product.uom.category'
    _description = __doc__
    _order = 'name'
    name = fields.Char('Name', size=64, required=True)
    uoms = fields.One2Many('product.uom', 'category', 'Unit of Measures')

UomCategory()


class Uom(OSV):
    'Unit of measure'
    _name = 'product.uom'
    _description = __doc__
    _order = 'name'
    name = fields.Char('Name', size=64, required=True, states=STATES,)
    symbol = fields.Char('Symbol', size=10, required=True, states=STATES,)
    category = fields.Many2One('product.uom.category', 'UOM Category',
                               required=True, ondelete='cascade',
                               states=STATES,)
    rate = fields.Float('Rate', digits=(12, 6), required=True,
                        on_change = ['rate'],states=STATES,
                        help='The coefficient for the formula:\n' \
                            '1 (base unit) = coef (this unit)')
    factor = fields.Float('Factor', digits=(12, 6), states=STATES,
                          on_change = ['factor'], required=True,
                          help='The coefficient for the formula:\n' \
                              'coef (base unit) = 1 (this unit)')
    rounding = fields.Float('Rounding Precision', digits=(12, 6),
                              required=True, states=STATES,)
    active = fields.Boolean('Active')

    def default_rate(self, cursor, user, context=None):
        return 1.0

    def default_factor(self, cursor, user, context=None):
        return 1.0

    def default_active(self, cursor, user, context=None):
        return 1

    def default_rounding(self, cursor, user, context=None):
        return 0.01

    def on_change_factor(self, cursor, user, ids, value, context=None):
        if value.get('factor', 0.0) == 0.0:
            return {'rate': 0.0}
        return {'rate': round(1.0/value['factor'], 6)}

    def on_change_rate(self, cursor, user, ids, value, context=None):
        if value.get('rate', 0.0) == 0.0:
            return {'factor': 0.0}
        return {'factor': round(1.0/value['rate'], 6)}


    def __init__(self):
        super(Uom, self).__init__()
        self._sql_constraints += [
            ('non_zero_rate_factor', 'CHECK((rate != 0.0) or (factor != 0.0))',
                'Rate and factor can not be both equal to zero.')
        ]


    @staticmethod
    def round(number, precision=1.0):
        return round(number/precision)*precision

    @staticmethod
    def check_factor_and_rate(values):
        factor = None
        rate = None
        if ('factor' not in values) and ('rate' not in values):
            return values
        elif 'factor' in values and 'rate' in values:
            if values['rate'] == 0.0 and values['factor'] == 0.0:
                return values
            elif values['factor'] != 0.0 and \
                    values['rate'] != 0.0:
                if values['rate'] == round(1.0/values['factor'], 6) or \
                        values['factor'] == round(1.0/values['rate'], 6):
                    return values
                else:
                    factor = round(1.0/values['rate'], 6)
            elif values['rate'] != 0.0 and \
                    values['factor'] != round(1.0/values['rate'], 6):
                factor = round(1.0/values['rate'], 6)
            elif values['factor'] != 0.0 and \
                    values['rate'] != round(1.0/values['factor'], 6):
                rate = round(1.0/values['factor'], 6)
            else:
                return values
        elif 'rate' in values:
            if values['rate'] != 0.0:
                factor = round(1.0/values['rate'], 6)
            else:
                factor = 0.0
        elif 'factor' in values:
            if values['factor'] != 0.0:
                rate = round(1.0/values['factor'], 6)
            else:
                rate = 0.0

        if rate != None or factor != None:
            values = values.copy()
            if rate != None: values['rate'] = rate
            if factor != None: values['factor'] = factor
        return values

    def create(self, cursor, user, values, context=None):
        values = self.check_factor_and_rate(values)
        return super(Uom, self).create(cursor, user, values, context)

    def write(self, cursor, user, ids, values, context=None):
        values = self.check_factor_and_rate(values)
        return super(Uom, self).write(cursor, user, ids, values, context)

    def compute_qty(self, cursor, user, from_uom, qty, to_uom=False):
        """
        Convert quantity for given uom's. from_uom and to_uom should
        be browse records.
        """
        if not from_uom or not qty or not to_uom:
            return qty
        if from_uom.category.id <> to_uom.category.id:
            return qty
        if from_uom.factor >= 1.0: # Choose the more precise field.
            amount = qty * from_uom.factor
        else:
            amount = qty / from_uom.rate
        if to_uom:
            if to_uom.factor >= 1.0:
                amount = self.round(amount / to_uom.factor, to_uom.rounding)
            else:
                amount = self.round(amount * to_uom.rate, to_uom.rounding)
        return amount

    def compute_price(self, cursor, user, from_uom, price, to_uom=False):
        """
        Convert price for given uom's. from_uom and to_uom should be
        browse records.
        """
        if not from_uom or not price or not to_uom:
            return price
        if from_uom.category.id <> to_uom.category.id:
            return price
        if from_uom.factor >= 1.0:
            new_price = float(price) / from_uom.factor
        else:
            new_price = float(price) * from_uom.rate

        if to_uom.factor >= 1.0:
            new_price = new_price * to_uom.factor
        else:
            new_price = new_price / to_uom.rate

        return new_price

Uom()
