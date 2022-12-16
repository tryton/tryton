#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

import sys, os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import unittest
from decimal import Decimal
from trytond.protocols.datatype import Float

class ProtocolsDatatypeFloatTestCase(unittest.TestCase):
    '''
    Test Float.
    '''
    def test_abs(self):
        '''
        Test absolute Float
        '''
        self.assertEqual(abs(Float('-1.0')), Float('1.0'))
        self.assert_(isinstance(abs(Float('-1.0')), Float))

    def test_Float_add_Decimal(self):
        '''
        Test addition between Float and Decimal
        '''
        self.assertEqual(Float('1.0') + Decimal('1.0'), Decimal('2.0'))

    def test_Float_add_float(self):
        '''
        Test addition between Float and float
        '''
        self.assertEqual(Float('1.0') + 1.0, 2.0)

    def test_Decimal_radd__Float(self):
        '''
        Test right addition between Float and Decimal
        '''
        self.assertEqual(Decimal('1.0') + Float('1.0'), Decimal('2.0'))

    def test_float_radd__Float(self):
        '''
        Test right addition between Float and float
        '''
        self.assertEqual(1.0 + Float('1.0'), 2.0)

    def test_Float_div_Decimal(self):
        '''
        Test division between Float and Decimal
        '''
        self.assertEqual(Float('1.0') / Decimal('1.0'), Decimal('1.0'))

    def test_Float_div_float(self):
        '''
        Test division between Float and float
        '''
        self.assertEqual(Float('1.0') / 1.0, 1.0)

    def test_Decimal_rdiv_Float(self):
        '''
        Test right division between Float and Decimal
        '''
        self.assertEqual(Decimal('1.0') / Float('1.0'), Decimal('1.0'))

    def test_float_rdiv_Float(self):
        '''
        Test right division between Float and float
        '''
        self.assertEqual(1.0 / Float('1.0'), 1.0)

    def test_Float_divmod_Decimal(self):
        '''
        Test divmod between Float and Decimal
        '''
        self.assertEqual(divmod(Float('2.1'), Decimal('20.5')),
                divmod(Decimal('2.1'), Decimal('20.5')))

    def test_Float_divmod_float(self):
        '''
        Test divmod between Float and float
        '''
        self.assertEqual(divmod(Float('2.1'), 20.5), divmod(2.1, 20.5))

    def test_Decimal_rdivmod_float(self):
        '''
        Test right divmod between Float and Decimal
        '''
        self.assertEqual(divmod(Decimal('2.1'), Float('20.5')),
                divmod(Decimal('2.1'), Decimal('20.5')))

    def test_float_rdivmod_Float(self):
        '''
        Test right divmod between Float and float
        '''
        self.assertEqual(divmod(2.1, Float('20.5')), divmod(2.1, 20.5))

    def test_Float_eq_Decimal(self):
        '''
        Test equal between Float and Decimal
        '''
        self.assert_(Float('1.1') == Decimal('1.1'))
        self.assertFalse(Float('1.1') == Decimal('1.0'))

    def test_Float_eq_float(self):
        '''
        Test equal between Float and float
        '''
        self.assert_(Float('1.1') == 1.1)
        self.assertFalse(Float('1.1') == 1.0)

    def test_Decimal_eq_Float(self):
        '''
        Test equal between Decimal and Float
        '''
        self.assert_(Decimal('1.1') == Float('1.1'))
        self.assertFalse(Decimal('1.1') == Float('1.0'))

    def test_float_eq_Float(self):
        '''
        Test equal between float and Decimal
        '''
        self.assert_(1.1 == Float('1.1'))
        self.assertFalse(1.1 == Float('1.0'))

    def test_Float_floordiv_Decimal(self):
        '''
        Test floordiv between Float and Decimal
        '''
        self.assertEqual(Float('2.5') // Decimal('2.1'), Decimal('1'))

    def test_Float_floordiv_float(self):
        '''
        Test floordiv between Float and float
        '''
        self.assertEqual(Float('2.5') // 2.1, 1.0)

    def test_Decimal_rfloordiv_Float(self):
        '''
        Test rfloordiv between Decimal and Float
        '''
        self.assertEqual(Decimal('2.5') // Float('2.1'), Decimal('1'))

    def test_float_rfloordiv_Float(self):
        '''
        Test rfloordiv between float and Float
        '''
        self.assertEqual(2.5 // Float('2.1'), 1.0)

    def test_Float_format(self):
        '''
        Test format Float
        '''
        # For Python < 2.6
        if hasattr(__builtins__, 'format'):
            self.assertEqual(format(Float('1.1'), '.32f'),
                    '1.10000000000000000000000000000000')

    def test_Float_ge_Decimal(self):
        '''
        Test ge between Float and Decimal
        '''
        self.assert_(Float('1.5') >= Decimal('1.1'))
        self.assertFalse(Float('1.1') >= Decimal('1.5'))

    def test_Float_ge_float(self):
        '''
        Test ge between Float and float
        '''
        self.assert_(Float('1.5') >= 1.1)
        self.assertFalse(Float('1.1') >= 1.5)

    def test_Float_gt_Decimal(self):
        '''
        Test gt between Float and Decimal
        '''
        self.assert_(Float('1.5') > Decimal('1.1'))
        self.assertFalse(Float('1.1') > Decimal('1.5'))

    def test_Float_gt_float(self):
        '''
        Test gt between Float and float
        '''
        self.assert_(Float('1.5') > 1.1)
        self.assertFalse(Float('1.1') > 1.5)

    def test_Float_le_Decimal(self):
        '''
        Test le between Float and Decimal
        '''
        self.assert_(Float('1.1') <= Decimal('1.5'))
        self.assertFalse(Float('1.5') <= Decimal('1.1'))

    def test_Float_le_float(self):
        '''
        Test le between Float and float
        '''
        self.assert_(Float('1.1') <= 1.5)
        self.assertFalse(Float('1.5') <= 1.1)

    def test_Float_lt_Decimal(self):
        '''
        Test lt between Float and Decimal
        '''
        self.assert_(Float('1.1') < Decimal('1.5'))
        self.assertFalse(Float('1.5') < Decimal('1.1'))

    def test_Float_lt_float(self):
        '''
        Test lt between Float and float
        '''
        self.assert_(Float('1.1') < 1.5)
        self.assertFalse(Float('1.5') < 1.1)

    def test_Float_mod_Decimal(self):
        '''
        Test modulo between Float and Decimal
        '''
        self.assertEqual(Float('2.1') % Decimal('20.5'),
                Decimal('2.1') % Decimal('20.5'))

    def test_Float_mod_float(self):
        '''
        Test modulo between Float and float
        '''
        self.assertEqual(Float('2.1') % 20.5, 2.1 % 20.5)

    def test_Decimal_rmod_Float(self):
        '''
        Test right modulo between Decimal and Float
        '''
        self.assertEqual(Decimal('2.1') % Float('20.5'),
                Decimal('2.1') % Decimal('20.5'))

    def test_float_rmod_Float(self):
        '''
        Test right modulo between float and Float
        '''
        self.assertEqual(2.1 % Float('20.5'), 2.1 % 20.5)

    def test_Float_mul_Decimal(self):
        '''
        Test multiplication between Float and Decimal
        '''
        self.assertEqual(Float('1.5') * Decimal('1.2'), Decimal('1.8'))

    def test_Float_mul_float(self):
        '''
        Test multiplication between Float and float
        '''
        self.assertEqual(Float('1.5') * 1.2, 1.5 * 1.2)

    def test_Decimal_rmul_Float(self):
        '''
        Test right multiplication between Decimal and Float
        '''
        self.assertEqual(Decimal('1.5') * Float('1.2'), Decimal('1.8'))

    def test_float_rmul_Float(self):
        '''
        Test right multiplication between float and Float
        '''
        self.assertEqual(1.5 * Float('1.2'), 1.5 * 1.2)

    def test_Float_ne_Decimal(self):
        '''
        Test not equal between Float and Decimal
        '''
        self.assert_(Float('1.1') != Decimal('1.2'))
        self.assertFalse(Float('1.1') != Decimal('1.1'))

    def test_Float_ne_float(self):
        '''
        Test not equal between Float and float
        '''
        self.assert_(Float('1.1') != 1.2)
        self.assertFalse(Float('1.1') != 1.1)

    def test_Decimal_ne_Float(self):
        '''
        Test not equal between Decimal and Float
        '''
        self.assert_(Decimal('1.1') != Float('1.2'))
        self.assertFalse(Decimal('1.1') != Float('1.1'))

    def test_float_ne_Float(self):
        '''
        Test not equal between float and Decimal
        '''
        self.assert_(1.1 != Float('1.2'))
        self.assertFalse(1.1 != Float('1.1'))

    def test_neg(self):
        '''
        Test negative Float
        '''
        self.assertEqual(-Float('1.0'), Float('-1.0'))
        self.assert_(isinstance(-Float('1.0'), Float))

    def test_nonzero(self):
        '''
        Test non zero Float
        '''
        self.assert_(Float('1.0') != 0)
        self.assertFalse(Float('0.0') != 0)

    def test_pos(self):
        '''
        Test positive Float
        '''
        self.assertEqual(+Float('1.0'), Float('1.0'))
        self.assert_(isinstance(+Float('1.0'), Float))

    def test_Float_pow_Decimal(self):
        '''
        Test pow between Float and Decimal
        '''
        self.assertEqual(Float('2.5') ** Decimal('2.0'), Decimal('6.25'))

    def test_Float_pow_float(self):
        '''
        Test pow between Float and float
        '''
        self.assertEqual(Float('2.5') ** 2.0, 6.25)

    def test_Decimal_rpow_float(self):
        '''
        Test right pow between Decimal and Float
        '''
        self.assertEqual(Decimal('2.5') ** Float('2.0'), Decimal('6.25'))

    def test_float_rpow_Float(self):
        '''
        Test right pow between Float and float
        '''
        self.assert_(2.5 ** Float('2.0'), 6.25)

    def test_Float_sub_Decimal(self):
        '''
        Test substration between Float and Decimal
        '''
        self.assertEqual(Float('2.5') - Decimal('1.2'), Decimal('1.3'))

    def test_Float_sub_float(self):
        '''
        Test substraction between Float and float
        '''
        self.assertEqual(Float('2.5') - 1.2, 1.3)

    def test_Decimal_rsub_Float(self):
        '''
        Test right substraction between Decimal and Float
        '''
        self.assertEqual(Decimal('2.5') - Float('1.2'), Decimal('1.3'))

    def test_float_rsub_Float(self):
        '''
        Test right substraction between float and Float
        '''
        self.assertEqual(2.5 - Float('1.2'), 1.3)

    def test_Decimal_only_Method(self):
        '''
        Test Decimal only method
        '''
        self.assertEqual(Float('1.5').quantize(Decimal('1')), Decimal('2'))

    def test_float_only_Method(self):
        '''
        Test float only method
        '''
        # For Python < 2.6
        if hasattr(float, 'hex'):
            self.assertEqual(Float('1.5').hex(), '0x1.8000000000000p+0')

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(ProtocolsDatatypeFloatTestCase)

if __name__ == '__main__':
    suite = suite()
    unittest.TextTestRunner(verbosity=2).run(suite)
