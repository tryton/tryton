from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False",
}


class PartnerType(OSV):
    "Corporation Type"

    _name = 'partner.partner.type'
    _description = __doc__
    _order= 'name'
    name = fields.Char('Name', required=True, size=64)

PartnerType()


class Partner(OSV):
    "Partner"
    _description = __doc__
    _name = "partner.partner"
    _order = "name"

    name = fields.Char('Name', size=128, required=True, select=True,
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
    active = fields.Boolean('Active')

    def __init__(self):
        super(Partner, self).__init__()
        self._sql_constraints = [
            ('name_uniq', 'unique (name)',
             'The name of the partner must be unique!')
        ]

    def default_active(self, cursor, user, context=None):
        return 1

    def address_get(self, cursor, user, partner_id, types=None):
        """
        For each type in types, return the first matching address.
        Types are : 'type_invoice','type_delivery','type_contact'.
        """
        if not types:
            types = []
        res = {}
        partner = self.browse(cursor, user, partner_id)
        for address in partner.addresses:
            for type in types:
                if address[type] and not res.get(type):
                    res[type] = address.id

        return res

        cursor.execute('select type,id from res_partner_address where partner_id in ('+','.join(map(str,partner_ids))+')')
        res = cursor.fetchall()
        adr = dict(res)
        # get the id of the (first) default address if there is one,
        # otherwise get the id of the first address in the list
        if res:
            default_address = adr.get('default', res[0][1])
        else:
            default_address = False
        result = {}
        for a in adr_pref:
            result[a] = adr.get(a, default_address)
        return result

Partner()
