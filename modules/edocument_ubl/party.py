# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import re

from trytond.pool import PoolMeta

ISO6523_TYPES = {
    'fr_siren': '0002',
    'se_orgnr': '0007',
    'fr_siret': '0009',
    'fi_ytunnus': '0037',
    'ch_uid': '0183',
    'ee_registrikood': '0191',
    'is_kennitala': '0196',
    'lt_pvm': '0200',
    'be_businessid': '0208',
    'fi_associationid': '0212',
    'fi_vat': '0213',
    'lv_vat': '0218',
    'eu_vat': '0223',
    }

EAS_TYPES = {
    'fr_siren': '0002',
    'se_orgnr': '0007',
    'fr_siret': '0009',
    'fi_ytunnus': '0037',
    'ch_uid': '0183',
    'ee_registrikood': '0191',
    'is_kennitala': '0196',
    'lt_pvm': '0200',
    'be_businessid': '0208',
    'it_codicefiscale': '210',
    'fi_associationid': '0212',
    'fi_vat': '0213',
    'lv_vat': '0218',
    'hu_vat': '9910',
    'ad_vat': '9922',
    'al_vat': '9923',
    'be_vat': '9925',
    'bg_vat': '9926',
    'ch_vat': '9927',
    'cy_vat': '9928',
    'cz_vat': '9929',
    'de_vat': '9930',
    'ee_vat': '9931',
    'gb_vat': '9932',
    'gr_vat': '9933',
    'hr_vat': '9934',
    'ie_vat': '9935',
    'li_vat': '9936',
    'lt_vat': '9937',
    'lu_vat': '9938',
    'mc_vat': '9940',
    'me_vat': '9941',
    'mk_vat': '9942',
    'mt_vat': '9943',
    'nl_vat': '9944',
    'pl_vat': '9945',
    'pt_vat': '9946',
    'ro_vat': '9947',
    'rs_vat': '9948',
    'si_vat': '9949',
    'sk_vat': '9950',
    'sm_vat': '9951',
    'tr_vat': '9952',
    'va_vat': '9953',
    'fr_vat': '9957',
    'us_ein': '9959',
    }


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    @property
    def identifier_iso6523(self):
        for identifier in self.identifiers:
            if identifier.iso_6523:
                return identifier

    @property
    def identifier_eas(self):
        for identifier in self.identifiers:
            if identifier.eas:
                return identifier


class Identifier(metaclass=PoolMeta):
    __name__ = 'party.identifier'

    @property
    def iso_6523(self):
        return ISO6523_TYPES.get(self.type, '')

    @property
    def eas_code(self):
        return EAS_TYPES.get(self.type, '')

    @property
    def eas(self):
        if self.eas_code:
            if re.match(r'[a-z]{2}_vat', self.type):
                country = self.type[:2].replace('gr', 'el')
                return f'{country}{self.code}'.lower()
            else:
                return self.code

    @property
    def vatin(self):
        if re.match(r'[a-z]{2}_vat', self.type):
            country = self.type[:2].replace('gr', 'el')
            return f'{country}{self.code}'.lower()
