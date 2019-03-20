#! -*- coding: utf8 -*-
# This file is part of the sale_pos module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.

from trytond.model import ModelView, fields, ModelSQL
from trytond.pool import PoolMeta, Pool
from trytond.pyson import If, Eval, Bool
from trytond.transaction import Transaction

__all__ = ['Template',
    'Category']

class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    is_enrolment = fields.Boolean('Enrolment', states={
            'readonly': ~Eval('active', True),
            }, depends=['active'])

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        cls.account_category.domain=['AND', 
                [('accounting', '=', True)],
                [('company', '=', Eval('context', {}).get('company', -1))],
            ]


class Category(metaclass=PoolMeta): 
    __name__ = 'product.category'

    company = fields.Many2One('company.company', 'Company', required=False,
        domain=[
            ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                Eval('context', {}).get('company', -1)),
            ]
    )

    @staticmethod
    def default_company():
        return Transaction().context.get('company')