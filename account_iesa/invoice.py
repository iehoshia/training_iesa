# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from collections import defaultdict, namedtuple
from itertools import combinations
import base64
import itertools

from sql import Literal, Null
from sql.aggregate import Count, Sum
from sql.conditionals import Coalesce, Case
from sql.functions import Round

from trytond.model import Workflow, ModelView, ModelSQL, fields, Check, \
    sequence_ordered, Unique
from trytond.report import Report
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from trytond import backend
from trytond.pyson import If, Eval, Bool
from trytond.tools import reduce_ids, grouped_slice
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.config import config

from trytond.modules.product import price_digits

class InvoiceLine(sequence_ordered(), ModelSQL, ModelView):
    'Invoice Line'
    __name__ = 'account.invoice.line'

    @classmethod
    def __setup__(cls):
        super(InvoiceLine, cls).__setup__()
        cls.unit_price.digits=(16,2)