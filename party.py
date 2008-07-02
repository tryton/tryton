#This file is part of Tryton.  The COPYRIGHT file at the top level of this repository contains the full copyright notices and license terms.
from trytond.osv import fields, OSV
STATES = {
    'readonly': "active == False",
}

def mult_add(a, b):
    '''
    Sum each digits of the multiplication of a and b.
    '''
    mult = a * b
    res = 0
    for i in range(len(str(mult))):
        res += int(str(mult)[i])
    return res


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
    vat_country = fields.Selection([
        ('', ''),
        ('AT', 'AT'),
        ('BE', 'BE'),
        ('BG', 'BG'),
        ('CY', 'CY'),
        ('CZ', 'CZ'),
        ('DE', 'DE'),
        ('DK', 'DK'),
        ('EE', 'EE'),
        ('ES', 'ES'),
        ('FI', 'FI'),
        ('FR', 'FR'),
        ('GB', 'GB'),
        ('GR', 'GR'),
        ('EL', 'EL'),
        ('HU', 'HU'),
        ('IE', 'IE'),
        ('IT', 'IT'),
        ('LT', 'LT'),
        ('LU', 'LU'),
        ('LV', 'LV'),
        ('MT', 'MT'),
        ('NL', 'NL'),
        ('PL', 'PL'),
        ('PT', 'PT'),
        ('RO', 'RO'),
        ('SE', 'SE'),
        ('SI', 'SI'),
        ('SK', 'SK'),
        ], 'VAT Country', states=STATES,
        help="Setting VAT country will enable verification of the VAT number.")
    vat_code = fields.Function('get_vat_code', type='char', string="VAT Code")
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
        self._constraints += [
            ('check_vat',
                'Error! Wrong VAT number.', ['vat_number', 'vat_country']),
        ]
        self._order.insert(0, ('name', 'ASC'))

    def default_active(self, cursor, user, context=None):
        return True

    def get_vat_code(self, cursor, user, ids, name, arg, context=None):
        if not ids:
            return []
        res = {}
        for party in self.browse(cursor, user, ids, context=context):
            res[party.id] = party.vat_country + party.vat_number
        return res

    def create(self, cursor, user, values, context=None):
        values = values.copy()
        if not values.get('code'):
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

    def check_vat(self, cursor, user, ids):
        '''
        Check the VAT number depending of the country.
        http://sima-pc.com/nif.php
        '''
        for party in self.browse(cursor, user, ids):
            if not party.vat_number:
                continue
            if not getattr(self, 'check_vat_' + \
                    party.vat_country.lower())(party.vat_number):
                return False
        return True

    def check_vat_at(self, vat):
        '''
        Check Austria VAT number.
        '''
        if len(vat) != 9:
            return False
        if vat[0] != 'U':
            return False
        num = vat[1:]
        try:
            int(num)
        except:
            return False
        sum = int(num[0]) + mult_add(2, int(num[1])) + \
                int(num[2]) + mult_add(2, int(num[3])) + \
                int(num[4]) + mult_add(2, int(num[5])) + \
                int(num[6])
        check = 10 - ((sum + 4) % 10)
        if check == 10:
            check = 0
        if int(vat[-1:]) != check:
            return False
        return True

    def check_vat_be(self, vat):
        '''
        Check Belgium VAT number.
        '''
        if len(vat) != 10:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[-2:]) != \
                97 - (int(vat[:8]) % 97):
            return False
        return True

    def check_vat_bg(self, vat):
        '''
        Check Bulgaria VAT number.
        '''
        if len(vat) != 10:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[0]) in (2, 3) and \
                int(vat[1:2]) != 22:
            return False
        sum = 4 * int(vat[0]) + 3 * int(vat[1]) + 2 * int(vat[2]) + \
                7 * int(vat[3]) + 6 * int(vat[4]) + 5 * int(vat[5]) + \
                4 * int(vat[6]) + 3 * int(vat[7]) + 2 * int(vat[8])
        check = 11 - (sum % 11)
        if check == 11:
            check = 0
        if check == 10:
            return False
        if check != int(vat[9]):
            return False
        return True

    def check_vat_cy(self, vat):
        '''
        Check Cyprus VAT number.
        '''
        if len(vat) != 9:
            return False
        try:
            int(vat[:8])
        except:
            return False
        n0 = int(vat[0])
        n1 = int(vat[1])
        n2 = int(vat[2])
        n3 = int(vat[3])
        n4 = int(vat[4])
        n5 = int(vat[5])
        n6 = int(vat[6])
        n7 = int(vat[7])

        def conv(x):
            if x == 0:
                return 1
            elif x == 1:
                return 0
            elif x == 2:
                return 5
            elif x == 3:
                return 7
            elif x == 4:
                return 9
            elif x == 5:
                return 13
            elif x == 6:
                return 15
            elif x == 7:
                return 17
            elif x == 8:
                return 19
            elif x == 9:
                return 21
            return x
        n0 = conv(n0)
        n2 = conv(n2)
        n4 = conv(n4)
        n6 = conv(n6)

        sum = n0 + n1 + n2 + n3 + n4 + n5 + n6 + n7
        check = chr(sum % 26 + 65)
        if check != vat[8]:
            return False
        return True

    def check_vat_cz(self, vat):
        '''
        Check Czech Republic VAT number.
        '''
        if len(vat) not in (8, 9, 10):
            return False
        try:
            int(vat)
        except:
            return False

        if len(vat) == 8:
            if int(vat[0]) not in (0, 1, 2, 3, 4, 5, 6, 7, 8):
                return False
            sum = 8 * int(vat[0]) + 7 * int(vat[1]) + 6 * int(vat[2]) + \
                    5 * int(vat[3]) + 4 * int(vat[4]) + 3 * int(vat[5]) + \
                    2 * int(vat[6])
            check = 11 - (sum % 11)
            if check == 10:
                check = 0
            if check == 11:
                check = 1
            if check != int(vat[7]):
                return False
        elif len(vat) == 9 and int(vat[0]) == 6:
            sum = 8 * int(vat[1]) + 7 * int(vat[2]) + 6 * int(vat[3]) + \
                    5 * int(vat[4]) + 4 * int(vat[5]) + 3 * int(vat[6]) + \
                    2 * int(vat[7])
            check = 9 - ((11 - (sum % 11)) % 10)
            if check != int(vat[8]):
                return False
        elif len(vat) == 9:
            if int(vat[0:2]) > 53 and int(vat[0:2]) < 80:
                return False
            if int(vat[2:4]) < 1:
                return False
            if int(vat[2:4]) > 12 and int(vat[2:4]) < 51:
                return False
            if int(vat[2:4]) > 62:
                return False
            if int(vat[2:4]) in (2, 52) and int(vat[0:2]) % 4 > 0:
                if int(vat[4:6]) < 1:
                    return False
                if int(vat[4:6]) > 28:
                    return False
            if int(vat[2:4]) in (2, 52) and int(vat[0:2]) % 4 == 0:
                if int(vat[4:6]) < 1:
                    return False
                if int(vat[4:6]) > 29:
                    return False
            if int(vat[2:4]) in (4, 6, 9, 11, 54, 56, 59, 61):
                if int(vat[4:6]) < 1:
                    return False
                if int(vat[4:6]) > 30:
                    return False
            if int(vat[2:4]) in (1, 3, 5, 7, 8, 10, 12, 51,
                    53, 55, 57, 58, 60, 62):
                if int(vat[4:6]) < 1:
                    return False
                if int(vat[4:6]) > 31:
                    return False
        elif len(vat) == 10:
            if int(vat[0:2]) < 54:
                return False
            if int(vat[2:4]) < 1:
                return False
            if int(vat[2:4]) > 12 and int(vat[2:4]) < 51:
                return False
            if int(vat[2:4]) > 62:
                return False
            if int(vat[2:4]) in (2, 52) and int(vat[0:2]) % 4 > 0:
                if int(vat[4:6]) < 1:
                    return False
                if int(vat[4:6]) > 28:
                    return False
            if int(vat[2:4]) in (2, 52) and int(vat[0:2]) % 4 == 0:
                if int(vat[4:6]) < 1:
                    return False
                if int(vat[4:6]) > 29:
                    return False
            if int(vat[2:4]) in (4, 6, 9, 11, 54, 56, 59, 61):
                if int(vat[4:6]) < 1:
                    return False
                if int(vat[4:6]) > 30:
                    return False
            if int(vat[2:4]) in (1, 3, 5, 7, 8, 10, 12, 51,
                    53, 55, 57, 58, 60, 62):
                if int(vat[4:6]) < 1:
                    return False
                if int(vat[4:6]) > 31:
                    return False
            if (int(vat[0:2]) + int(vat[2:4]) + int(vat[4:6]) + int(vat[6:8]) +
                    int(vat[8:10])) % 11 != 0:
                return False
            if int(vat[0:10]) % 11 != 0:
                return False
        return True

    def check_vat_de(self, vat):
        '''
        Check Germany VAT number.
        '''
        if len(vat) != 9:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[0:7]) <= 0:
            return False
        sum = 0
        for i in range(8):
            sum = (2 * ((int(vat[i]) + sum + 9) % 10 + 1)) % 11
        check = 11 - sum
        if check == 10:
            check = 0
        if int(vat[8]) != check:
            return False
        return True

    def check_vat_dk(self, vat):
        '''
        Check Denmark VAT number.
        '''
        if len(vat) != 8:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[0]) <= 0:
            return False
        sum = 2 * int(vat[0]) + 7 * int(vat[1]) + 6 * int(vat[2]) + \
                5 * int(vat[3]) + 4 * int(vat[4]) + 3 * int(vat[5]) + \
                2 * int(vat[6]) + int(vat[7])
        if sum % 11 != 0:
            return False
        return True

    def check_vat_ee(self, vat):
        '''
        Check Estonia VAT number.
        '''
        if len(vat) != 9:
            return False
        try:
            int(vat)
        except:
            return False
        sum = 3 * int(vat[0]) + 7 * int(vat[1]) + 1 * int(vat[2]) + \
                3 * int(vat[3]) + 7 * int(vat[4]) + 1 * int(vat[5]) + \
                3 * int(vat[6]) + 7 * int(vat[7])
        check = 10 - (sum % 10)
        if check == 10:
            check = 0
        if check != int(vat[8]):
            return False
        return True

    def check_vat_es(self, vat):
        '''
        Check Spain VAT number.
        '''
        if len(vat) != 9:
            return False

        conv = {
            1: 'T',
            2: 'R',
            3: 'W',
            4: 'A',
            5: 'G',
            6: 'M',
            7: 'Y',
            8: 'F',
            9: 'P',
            10: 'D',
            11: 'X',
            12: 'B',
            13: 'N',
            14: 'J',
            15: 'Z',
            16: 'S',
            17: 'Q',
            18: 'V',
            19: 'H',
            20: 'L',
            21: 'C',
            22: 'K',
            23: 'E',
        }

        if vat[0] in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'):
            try:
                int(vat[1:])
            except:
                return False
            sum = mult_add(2, int(vat[1])) + int(vat[2]) + \
                    mult_add(2, int(vat[3])) + int(vat[4]) + \
                    mult_add(2, int(vat[5])) + int(vat[6]) + \
                    mult_add(2, int(vat[7]))
            check = 10 - (sum % 10)
            if check == 10:
                check = 0
            if check != int(vat[8]):
                return False
            return True
        elif vat[0] in ('N', 'P', 'Q', 'S'):
            try:
                int(vat[1:8])
            except:
                return False
            sum = mult_add(2, int(vat[1])) + int(vat[2]) + \
                    mult_add(2, int(vat[3])) + int(vat[4]) + \
                    mult_add(2, int(vat[5])) + int(vat[6]) + \
                    mult_add(2, int(vat[7]))
            check = 10 - (sum % 10)
            check = chr(check + 64)
            if check != vat[8]:
                return False
            return True
        elif vat[0] in ('K', 'L', 'M', 'X'):
            try:
                int(vat[1:8])
            except:
                return False
            check = 1 + (int(vat[1:8]) % 23)

            check = conv[check]
            if check != vat[8]:
                return False
            return True
        else:
            try:
                int(vat[:8])
            except:
                return False
            check = 1 + (int(vat[:8]) % 23)

            check = conv[check]
            if check != vat[8]:
                return False
            return True

    def check_vat_fi(self, vat):
        '''
        Check Finland VAT number.
        '''
        if len(vat) != 8:
            return False
        try:
            int(vat)
        except:
            return False
        sum = 7 * int(vat[0]) + 9 * int(vat[1]) + 10 * int(vat[2]) + \
                5 * int(vat[3]) + 8 * int(vat[4]) + 4 * int(vat[5]) + \
                2 * int(vat[6])
        check = 11 - (sum % 11)
        if check == 11:
            check = 0
        if check == 10:
            return False
        if check != int(vat[7]):
            return False
        return True

    def check_vat_fr(self, vat):
        '''
        Check France VAT number.
        '''
        if len(vat) != 11:
            return False

        try:
            int(vat[2:11])
        except:
            return False

        system = None
        try:
            int(vat[0:2])
            system = 'old'
        except:
            system = 'new'

        if system == 'old':
            check = ((int(vat[2:11]) * 100) + 12) % 97
            if check != int(vat[0:2]):
                return False
            return True
        else:
            conv = ['0', '1', '2', '3', '4', '5', '6', '7',
                '8', '9', 'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
                'J', 'K', 'L', 'M', 'N', 'P', 'Q', 'R', 'S', 'T',
                'U', 'V', 'W', 'X', 'Y', 'Z']
            if vat[0] not in conv \
                    or vat[1] not in conv:
                return False
            c1 = conv.index(vat[0])
            c2 = conv.index(vat[1])

            if c1 < 10:
                sum = c1 * 24 + c2 - 10
            else:
                sum = c1 * 34 + c2 - 100

            x = sum % 11
            sum = (int(sum) / 11) + 1
            y = (int(vat[2:11]) + sum) % 11
            if x != y:
                return False
            return True

    def check_vat_gb(self, vat):
        '''
        Check United Kingdom VAT number.
        '''

        if len(vat) == 5:
            try:
                int(vat[2:5])
            except:
                return False

            if vat[0:2] == 'GD':
                if int(vat[2:5]) >= 500:
                    return False
                return True
            if vat[0:2] == 'HA':
                if int(vat[2:5]) < 500:
                    return False
                return True
            return False
        elif len(vat) in (9, 10):
            try:
                int(vat)
            except:
                return False

            if int(vat[0:7]) < 1:
                return False
            if int(vat[0:7]) > 19999 and int(vat[0:7]) < 1000000:
                return False
            if int(vat[7:9]) > 97:
                return False
            if len(vat) == 10 and int(vat[9]) != 3:
                return False

            sum = 8 * int(vat[0]) + 7 * int(vat[1]) + 6 * int(vat[2]) + \
                    5 * int(vat[3]) + 4 * int(vat[4]) + 3 * int(vat[5]) + \
                    2 * int(vat[6]) + 10 * int(vat[7]) + int(vat[8])
            if sum % 97 != 0:
                return False
            return True
        elif len(vat) in (12, 13):
            try:
                int(vat)
            except:
                return False

            if int(vat[0:3]) not in (0, 1):
                return False

            if int(vat[3:10]) < 1:
                return False
            if int(vat[3:10]) > 19999 and int(vat[3:10]) < 1000000:
                return False
            if int(vat[10:12]) > 97:
                return False
            if len(vat) == 13 and int(vat[12]) != 3:
                return False

            sum = 8 * int(vat[3]) + 7 * int(vat[4]) + 6 * int(vat[5]) + \
                    5 * int(vat[6]) + 4 * int(vat[7]) + 3 * int(vat[8]) + \
                    2 * int(vat[9]) + 10 * int(vat[10]) + int(vat[11])
            if sum % 97 != 0:
                return False
            return True
        return False

    def check_vat_gr(self, vat):
        '''
        Check Greece VAT number.
        '''
        try:
            int(vat)
        except:
            return False
        if len(vat) == 8:
            sum = 128 * int(vat[0]) + 64 * int(vat[1]) + 32 * int(vat[2]) + \
                    16 * int(vat[3]) + 8 * int(vat[4]) + 4 * int(vat[5]) + \
                    2 * int(vat[6])
            check = sum % 11
            if check == 10:
                check = 0
            if check != int(vat[7]):
                return False
            return True
        elif len(vat) == 9:
            sum = 256 * int(vat[0]) + 128 * int(vat[1]) + 64 * int(vat[2]) + \
                    32 * int(vat[3]) + 16 * int(vat[4]) + 8 * int(vat[5]) + \
                    4 * int(vat[6]) + 2 * int(vat[7])
            check = sum % 11
            if check == 10:
                check = 0
            if check != int(vat[8]):
                return False
            return True
        return False

    def check_vat_el(self, vat):
        return self.check_vat_gr(vat)

    def check_vat_hu(self, vat):
        '''
        Check Hungary VAT number.
        '''
        if len(vat) != 8:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[0]) <= 0:
            return False
        sum = 9 * int(vat[0]) + 7 * int(vat[1]) + 3 * int(vat[2]) + \
                1 * int(vat[3]) + 9 * int(vat[4]) + 7 * int(vat[5]) + \
                3 * int(vat[6])
        check = 10 - (sum % 10)
        if check == 10:
            check = 0
        if check != int(vat[7]):
            return False
        return True

    def check_vat_ie(self, vat):
        '''
        Check Ireland VAT number.
        '''
        if len(vat) != 8:
            return False
        if (ord(vat[1]) >= 65 and ord(vat[1]) <= 90) \
                or vat[1] in ('+', '*'):
            try:
                int(vat[0])
                int(vat[2:7])
            except:
                return False

            if int(vat[0]) <= 6:
                return False

            sum = 7 * int(vat[2]) + 6 * int(vat[3]) + 5 * int(vat[4]) + \
                    4 * int(vat[5]) + 3 * int(vat[6]) + 2 * int(vat[0])
            check = sum % 23
            if check == 0:
                check = 'W'
            else:
                check = chr(check + 64)
            if check != vat[7]:
                return False
            return True
        else:
            try:
                int(vat[0:7])
            except:
                return False

            sum = 8 * int(vat[0]) + 7 * int(vat[1]) + 6 * int(vat[2]) + \
                    5 * int(vat[3]) + 4 * int(vat[4]) + 3 * int(vat[5]) + \
                    2 * int(vat[6])
            check = sum % 23
            if check == 0:
                check = 'W'
            else:
                check = chr(check + 64)
            if check != vat[7]:
                return False
            return True

    def check_vat_it(self, vat):
        '''
        Check Italy VAT number.
        '''
        if len(vat) != 11:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[0:7]) <= 0:
            return False
        if int(vat[7:10]) <= 0:
            return False
        if int(vat[7:10]) > 100 and int(vat[7:10]) < 120:
            return False
        if int(vat[7:10]) > 121:
            return False

        sum = int(vat[0]) + mult_add(2, int(vat[1])) + int(vat[2]) + \
                mult_add(2, int(vat[3])) + int(vat[4]) + \
                mult_add(2, int(vat[5])) + int(vat[6]) + \
                mult_add(2, int(vat[7])) + int(vat[8]) + \
                mult_add(2, int(vat[9]))
        check = 10 - (sum % 10)
        if check == 10:
            check = 0
        if check != int(vat[10]):
            return False
        return True

    def check_vat_lt(self, vat):
        '''
        Check Lithuania VAT number.
        '''
        try:
            int(vat)
        except:
            return False

        if len(vat) == 9:
            if int(vat[7]) != 1:
                return False
            sum = 1 * int(vat[0]) + 2 * int(vat[1]) + 3 * int(vat[2]) + \
                    4 * int(vat[3]) + 5 * int(vat[4]) + 6 * int(vat[5]) + \
                    7 * int(vat[6]) + 8 * int(vat[7])
            if sum % 11 == 10:
                sum = 3 * int(vat[0]) + 4 * int(vat[1]) + 5 * int(vat[2]) + \
                        6 * int(vat[3]) + 7 * int(vat[4]) + 8 * int(vat[5]) + \
                        9 * int(vat[6]) + 1 * int(vat[7])
            check = sum % 11
            if check == 10:
                check = 0
            if check != int(vat[8]):
                return False
            return True
        elif len(vat) == 12:
            if int(vat[10]) != 1:
                return False
            sum = 1 * int(vat[0]) + 2 * int(vat[1]) + 3 * int(vat[2]) + \
                    4 * int(vat[3]) + 5 * int(vat[4]) + 6 * int(vat[5]) + \
                    7 * int(vat[6]) + 8 * int(vat[7]) + 9 * int(vat[8]) + \
                    1 * int(vat[9]) + 2 * int(vat[10])
            if sum % 11 == 10:
                sum = 3 * int(vat[0]) + 4 * int(vat[1]) + 5 * int(vat[2]) + \
                        6 * int(vat[3]) + 7 * int(vat[4]) + 8 * int(vat[5]) + \
                        9 * int(vat[6]) + 1 * int(vat[7]) + 2 * int(vat[8]) + \
                        3 * int(vat[9]) + 4 * int(vat[10])
            check = sum % 11
            if check == 10:
                check = 0
            if check != int(vat[11]):
                return False
            return True
        return False

    def check_vat_lu(self, vat):
        '''
        Check Luxembourg VAT number.
        '''
        if len(vat) != 8:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[0:6]) <= 0:
            return False
        check = int(vat[0:6]) % 89
        if check != int(vat[6:8]):
            return False
        return True

    def check_vat_lv(self, vat):
        '''
        Check Latvia VAT number.
        '''
        if len(vat) != 11:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[0]) >= 4:
            sum = 9 * int(vat[0]) + 1 * int(vat[1]) + 4 * int(vat[2]) + \
                    8 * int(vat[3]) + 3 * int(vat[4]) + 10 * int(vat[5]) + \
                    2 * int(vat[6]) + 5 * int(vat[7]) + 7 * int(vat[8]) + \
                    6 * int(vat[9])
            if sum % 11 == 4 and int(vat[0]) == 9:
                sum = sum - 45
            if sum % 11 == 4:
                check = 4 - (sum % 11)
            elif sum % 11 > 4:
                check = 14 - (sum % 11)
            elif sum % 11 < 4:
                check = 3 - (sum % 11)
            if check != int(vat[10]):
                return False
            return True
        else:
            if int(vat[2:4]) == 2 and int(vat[4:6]) % 4 > 0:
                if int(vat[0:2]) < 1 or int(vat[0:2]) > 28:
                    return False
            if int(vat[2:4]) == 2 and int(vat[4:6]) % 4 == 0:
                if int(vat[0:2]) < 1 or int(vat[0:2]) > 29:
                    return False
            if int(vat[2:4]) in (4, 6, 9, 11):
                if int(vat[0:2]) < 1 or int(vat[0:2]) > 30:
                    return False
            if int(vat[2:4]) in (1, 3, 5, 7, 8, 10, 12):
                if int(vat[0:2]) < 1 or int(vat[0:2]) > 31:
                    return False
            if int(vat[2:4]) < 1 or int(vat[2:4]) > 12:
                return False
            return True

    def check_vat_mt(self, vat):
        '''
        Check Malta VAT number.
        '''
        if len(vat) != 8:
            return False
        try:
            int(vat)
        except:
            return False

        if int(vat[0:6]) < 100000:
            return False

        sum = 3 * int(vat[0]) + 4 * int(vat[1]) + 6 * int(vat[2]) + \
                7 * int(vat[3]) + 8 * int(vat[4]) + 9 * int(vat[5])
        check = 37 - (sum % 37)
        if check != int(vat[6:8]):
            return False
        return True

    def check_vat_nl(self, vat):
        '''
        Check Netherlands VAT number.
        '''
        if len(vat) != 12:
            return False
        try:
            int(vat[0:9])
            int(vat[10:12])
        except:
            return False
        if int(vat[0:8]) <= 0:
            return False
        if vat[9] != 'B':
            return False

        sum = 9 * int(vat[0]) + 8 * int(vat[1]) + 7 * int(vat[2]) + \
                6 * int(vat[3]) + 5 * int(vat[4]) + 4 * int(vat[5]) + \
                3 * int(vat[6]) + 2 * int(vat[7])

        check = sum % 11
        if check == 10:
            return False
        if check != int(vat[8]):
            return False
        return True

    def check_vat_pl(self, vat):
        '''
        Check Poland VAT number.
        '''
        if len(vat) != 10:
            return False
        try:
            int(vat)
        except:
            return False

        sum = 6 * int(vat[0]) + 5 * int(vat[1]) + 7 * int(vat[2]) + \
                2 * int(vat[3]) + 3 * int(vat[4]) + 4 * int(vat[5]) + \
                5 * int(vat[6]) + 6 * int(vat[7]) + 7 * int(vat[8])
        check = sum % 11
        if check == 10:
            return False
        if check != int(vat[9]):
            return False
        return True

    def check_vat_pt(self, vat):
        '''
        Check Portugal VAT number.
        '''
        if len(vat) != 9:
            return False
        try:
            int(vat)
        except:
            return False

        if int(vat[0]) <= 0:
            return False

        sum = 9 * int(vat[0]) + 8 * int(vat[1]) + 7 * int(vat[2]) + \
                6 * int(vat[3]) + 5 * int(vat[4]) + 4 * int(vat[5]) + \
                3 * int(vat[6]) + 2 * int(vat[7])
        check = 11 - (sum % 11)
        if check == 10:
            check = 0
        if check != int(vat[8]):
            return False
        return True

    def check_vat_ro(self, vat):
        '''
        Check Romania VAT number.
        '''
        try:
            int(vat)
        except:
            return False

        if len(vat) == 10:
            sum = 7 * int(vat[0]) + 5 * int(vat[1]) + 3 * int(vat[2]) + \
                    2 * int(vat[3]) + 1 * int(vat[4]) + 7 * int(vat[5]) + \
                    5 * int(vat[6]) + 3 * int(vat[7]) + 2 * int(vat[8])
            check = (sum * 10) % 11
            if check == 10:
                check = 0
            if check != int(vat[9]):
                return False
            return True
        elif len(vat) == 13:
            if int(vat[0]) not in (1, 2, 3, 4, 6):
                return False
            if int(vat[3:5]) < 1 or int(vat[3:5]) > 12:
                return False
            if int(vat[3:5]) == 2 and int(vat[1:3]) % 4 > 0:
                if int(vat[5:7]) < 1 or int(vat[5:7]) > 28:
                    return False
            if int(vat[3:5]) == 2 and int(vat[1:3]) % 4 == 0:
                if int(vat[5:7]) < 1 or int(vat[5:7]) > 29:
                    return False
            if int(vat[3:5]) in (4, 6, 9, 11):
                if int(vat[5:7]) < 1 or int(vat[5:7]) > 30:
                    return False
            if int(vat[3:5]) in (1, 3, 5, 7, 8, 10, 12):
                if int(vat[5:7]) < 1 or int(vat[5:7]) > 31:
                    return False

            sum = 2 * int(vat[0]) + 7 * int(vat[1]) + 9 * int(vat[2]) + \
                    1 * int(vat[3]) + 4 * int(vat[4]) + 6 * int(vat[5]) + \
                    3 * int(vat[6]) + 5 * int(vat[7]) + 8 * int(vat[8]) + \
                    2 * int(vat[9]) + 7 * int(vat[10]) + 9 * int(vat[11])
            check = sum % 11
            if check == 10:
                check = 1
            if check != int(vat[12]):
                return False
            return True
        return False

    def check_vat_se(self, vat):
        '''
        Check Sweden VAT number.
        '''
        if len(vat) != 12:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[9:11]) <= 0:
            return False

        sum = mult_add(2, int(vat[0])) + int(vat[1]) + \
                mult_add(2, int(vat[2])) + int(vat[3]) + \
                mult_add(2, int(vat[4])) + int(vat[5]) + \
                mult_add(2, int(vat[6])) + int(vat[7]) + \
                mult_add(2, int(vat[8]))
        check = 10 - (sum % 10)
        if check == 10:
            check = 0
        if check != int(vat[9]):
            return False
        return True

    def check_vat_si(self, vat):
        '''
        Check Slovenia VAT number.
        '''
        if len(vat) != 8:
            return False
        try:
            int(vat)
        except:
            return False
        if int(vat[0:7]) <= 999999:
            return False

        sum = 8 * int(vat[0]) + 7 * int(vat[1]) + 6 * int(vat[2]) + \
                5 * int(vat[3]) + 4 * int(vat[4]) + 3 * int(vat[5]) + \
                2 * int(vat[6])
        check = 11 - (sum % 11)
        if check == 10:
            check = 0
        if check == 11:
            check = 1
        if check != int(vat[7]):
            return False
        return True

    def check_vat_sk(self, vat):
        '''
        Check Slovakia VAT number.
        '''
        try:
            int(vat)
        except:
            return False
        if len(vat) not in(9, 10):
            return False

        if int(vat[0:2]) == 0 and len(vat) == 10:
            return True

        if len(vat) == 10:
            if int(vat[0:2]) < 54 or int(vat[0:2]) > 99:
                return False

        if len(vat) == 9:
            if int(vat[0:2]) > 53 :
                return False

        if int(vat[2:4]) < 1:
            return False
        if int(vat[2:4]) > 12 and int(vat[2:4]) < 51:
            return False
        if int(vat[2:4]) > 62:
            return False
        if int(vat[2:4]) in (2, 52) and int(vat[0:2]) % 4 > 0:
            if int(vat[4:6]) < 1 or int(vat[4:6]) > 28:
                return False
        if int(vat[2:4]) in (2, 52) and int(vat[0:2]) % 4 == 0:
            if int(vat[4:6]) < 1 or int(vat[4:6]) > 29:
                return False
        if int(vat[2:4]) in (4, 6, 9, 11, 54, 56, 59, 61):
            if int(vat[4:6]) < 1 or int(vat[4:6]) > 30:
                return False
        if int(vat[2:4]) in (1, 3, 5, 7, 8, 10, 12,
                51, 53, 55, 57, 58, 60, 62):
            if int(vat[4:6]) < 1 or int(vat[4:6]) > 31:
                return False
        return True

Party()
