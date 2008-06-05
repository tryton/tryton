from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False",
}


class PartyType(OSV):
    "Party Type"

    _name = 'relationship.party.type'
    _description = __doc__
    name = fields.Char('Name', required=True, size=None, translate=True)
    # TODO add into localisation modules: http://en.wikipedia.org/wiki/Types_of_companies

    def __init__(self):
        super(PartyType, self).__init__()
        self._order.insert(0, ('name', 'ASC'))

PartyType()


class Party(OSV):
    "Party"
    _description = __doc__
    _name = "relationship.party"

    name = fields.Char('Name', size=None, required=True, select=1,
           states=STATES)
    code = fields.Char('Code', size=None, required=True, select=1,
            readonly=True)
    type = fields.Many2One("relationship.party.type", "Type",
           states=STATES)
    lang = fields.Many2One("ir.lang", 'Language',
           states=STATES)
    vat_number = fields.Char('VAT Number',size=None,
            help="Value Added Tax number", states=STATES)
    website = fields.Char('Website',size=None,
           states=STATES)
    addresses = fields.One2Many('relationship.address', 'party',
           'Addresses',states=STATES)
    categories = fields.Many2Many(
            'relationship.category', 'relationship_category_rel',
            'party', 'category', 'Categories',
            states=STATES)
    active = fields.Boolean('Active', select=1)

    def __init__(self):
        super(Party, self).__init__()
        self._sql_constraints = [
            ('code_uniq', 'UNIQUE(code)',
             'The code of the party must be unique!')
        ]
        self._order.insert(0, ('name', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return 1

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        values['code'] = self.pool.get('ir.sequence').get(
                cursor, user, 'relationship.party')
        return super(Party, self).create(cursor, user, values,
                context=context)

    def address_get(self, cursor, user, party_id, type=None, context=None):
        """
        Try to find an address for the given type, if no type match
        the first address is return.
        """
        address_obj = self.pool.get("relationship.address")
        address_ids = address_obj.search(
            cursor, user, [("party","=",party_id),("active","=",True)],
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

Party()
