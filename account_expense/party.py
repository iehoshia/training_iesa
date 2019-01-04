#! -*- coding: utf8 -*-
# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date
from decimal import Decimal 
from io import BytesIO
from trytond.model import ModelView, fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.pyson import If, Eval, Bool, PYSONEncoder, Not
from trytond.transaction import Transaction

__all__ = ['Party']
__metaclass__ = PoolMeta

class Party(ModelSQL, ModelView):
    __name__ = 'party.party'

    is_provider= fields.Boolean('Provider')