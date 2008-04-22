from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False",
}


class PartnerType(OSV):
    "Partner Type"

    _name = 'partner.partner.type'
    _description = __doc__
    name = fields.Char('Name', required=True, size=None, translate=True)
    # TODO add into localisation modules: http://en.wikipedia.org/wiki/Types_of_companies

    def __init__(self):
        super(PartnerType, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

PartnerType()


class Partner(OSV):
    "Partner"
    _description = __doc__
    _name = "partner.partner"

    name = fields.Char('Name', size=128, required=True, select=1,
           states=STATES)
    type = fields.Many2One("partner.partner.type", "Type",
           states=STATES)
    lang = fields.Many2One("ir.lang", 'Language',
           states=STATES)
    vat = fields.Char('VAT',size=32 ,help="Value Added Tax number",
           states=STATES)
    website = fields.Char('Website',size=64,
           states=STATES)
    addresses = fields.One2Many('partner.address', 'partner',
           'Addresses',states=STATES)
    categories = fields.Many2Many(
            'partner.category', 'partner_category_rel',
            'partner', 'category', 'Categories',
            states=STATES)
    active = fields.Boolean('Active', select=1)

    def __init__(self):
        super(Partner, self).__init__()
        self._sql_constraints = [
            ('name_uniq', 'unique (name)',
             'The name of the partner must be unique!')
        ]
        self._order.insert(0, ('name', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return 1

    def address_get(self, cursor, user, partner_id, type=None, context=None):
        """
        Try to find an address for the given type, if no type match
        the first address is return.
        """
        address_obj = self.pool.get("partner.address")
        address_ids = address_obj.search(
            cursor, user, [("partner","=",partner_id),("active","=",True)],
            order=[('sequence', 'ASC'), ('id', 'ASC')], context=context)
        if not address_ids:
            return False
        default_address = address_ids[0]
        if not type:
            return default_address
        for address in address_obj.browse(cursor, user, address_ids,
                context=context):
            if address[type]:
                    return address.id
        return default_address

Partner()
