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


UomCategory()


class Uom(OSV):
    'Unit of measure'
    _name = 'product.uom'
    _description = __doc__
    _order = 'name'
    name = fields.Char('Name', size=64, required=True, states=STATES,)
    category = fields.Many2One('product.uom.category', 'UOM Category',
                               required=True, ondelete='cascade',
                               states=STATES,)
    rate = fields.Float('Rate', digits=(12, 6), required=True,
                        on_change = ['rate'],states=STATES,
                        help='The coefficient for the formula:\n' \
                            '1 (base unit) = coef (this unit)')
    factor = fields.Function("_factor", fnct_inv="_factor_inv",
                             digits=(12, 6),states=STATES,
                             method=True, string='Factor',
                             on_change = ['factor'],
                             help='The coefficient for the formula:\n' \
                                 'coef (base unit) = 1 (this unit)')
    factor_data = fields.Float('Factor', digits=(12, 6), states=STATES,)
    rounding = fields.Float('Rounding Precision', digits=(16, 3),
                            required=True,states=STATES,)
    active = fields.Boolean('Active')

    def _factor(self, cursor, user, ids, name, arg, context):
        res = {}
        for uom in self.browse(cursor, user, ids, context=context):
            if uom.rate:
                if uom.factor_data:
                    res[uom.id] = uom.factor_data
                else:
                    res[uom.id] = round(1 / uom.rate, 6)
            else:
                res[uom.id] = 0.0
        return res

    def _factor_inv(self, cursor, user, id, name, value, arg, context=None):
        if context and 'read_delta' in context:
            context = context.copy()
            del context['read_delta']

        if value:
            data = 0.0
            if round(1 / round(1/value, 6), 6) != value:
                data = value
            self.write(cursor, user, id, {
                'rate': round(1/value, 6),
                'factor_data': data,
                }, context=context)
        else:
            self.write(cursor, user, id, {
                'rate': 0.0,
                'factor_data': 0.0,
                }, context=context)

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
            return {'value': {'rate': 0}}
        return {'rate': round(1/value['factor'], 6)}

    def on_change_rate(self, cursor, user, ids, value, context=None):
        if value.get('rate', 0.0) == 0.0:
            return {'value': {'factor': 0}}
        return {'factor': round(1/value['rate'], 6)}


    def _compute_qty(self, cursor, user, from_uom_id, qty, to_uom=False):
        """
        Convert quantity for given uom's. from_uom and to_uom should
        be browse records.
        """
        if not from_uom or not qty or not to_uom:
            return qty
        if from_uom.category.id <> to_uom.category.id:
            return qty
        if from_uom.factor_data:
            amount = qty * from_uom.factor_data
        else:
            amount = qty / from_uom.factor
        if to_uom:
            if to_uom.factor_data:
                amount = rounding(amount / to_uom.factor_data, to_uom.rounding)
            else:
                amount = rounding(amount * to_uom.factor, to_uom.rounding)
        return amount

    def _compute_price(self, cursor, user, from_uom, price, to_uom=False):
        """
        Convert price for given uom's. from_uom and to_uom should be
        browse records.
        """
        if not from_uom or not price or not to_uom:
            return price
        if from_uom.category.id <> to_uom.category.id:
            return price
        if from_uom.factor_data:
            new_price = float(price) / from_uom.factor_data
        else:
            new_price = float(price) * from_uom.factor

        if to_uom.factor_data:
            new_price = new_price * to_uom.factor_data
        else:
            new_price = new_price / to_uom.factor

        return new_price

Uom()
