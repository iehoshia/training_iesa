# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime
from datetime import date

import operator
from functools import wraps
from collections import defaultdict

from dateutil.relativedelta import relativedelta
from sql import Column, Null, Window, Literal
from sql.aggregate import Sum, Max
from sql.conditionals import Coalesce, Case

from trytond.model import (ModelSingleton, DeactivableMixin, 
    ModelView, ModelSQL, DeactivableMixin, fields,
    Unique, Workflow, sequence_ordered) 
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.report import Report
from trytond.tools import reduce_ids, grouped_slice
from trytond.pyson import Eval, If, PYSONEncoder, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.report import Report

from trytond import backend

__all__ = [
    'ProductCategory',
    ]  
__metaclass__ = PoolMeta

class ProductCategory(ModelSQL, ModelView):
    'Product Category'
    __name__ = 'product.category'

    is_asset_category = fields.Boolean("Asset Category")

class CreateAssetForm(ModelSQL, ModelView):
    'Create Asset Start'
    __name__ = 'create.asset.form'
