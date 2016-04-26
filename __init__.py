# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .opportunity import *
from .configuration import *
from .sale import *
from .party import *
from .account import *
from .product import *
from .company import *


def register():
    Pool.register(
        SaleOpportunity,
        SaleOpportunityLine,
        SaleOpportunityEmployee,
        OpenSaleOpportunityEmployeeStart,
        SaleOpportunityMonthly,
        SaleOpportunityEmployeeMonthly,
        Configuration,
        Sale,
        Party,
        Address,
        PaymentTerm,
        PaymentTermLine,
        Template,
        Product,
        Company,
        Employee,
        module='sale_opportunity', type_='model')
    Pool.register(
        OpenSaleOpportunityEmployee,
        module='sale_opportunity', type_='wizard')
