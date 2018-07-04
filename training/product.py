#! -*- coding: utf8 -*-
# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.model import ModelView, fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

__all__ = ['Template']

class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'

    is_enrolment = fields.Boolean('Enrolment', states={
            'readonly': ~Eval('active', True),
            }, depends=['active'])