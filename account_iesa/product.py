# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
import operator

from dateutil.relativedelta import relativedelta

from trytond.model import (
	ModelView, ModelSQL, fields, Unique, sequence_ordered)

from trytond.pyson import Eval, If, PYSONEncoder, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond import backend

__all__ = ['Template',
	'Service']
#__metaclass__ = PoolMeta

class Template(ModelView):
    'Product Template'
    __name__ = 'product.template'

    company = fields.Many2One('company.company','Company')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class Service(ModelSQL, ModelView):
    "Subscription Service"
    __name__ = 'sale.subscription.service'

    company = fields.Many2One('company.company','Company')

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') 