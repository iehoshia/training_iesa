# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

__all__ = ['Configuration', 'ConfigurationSequence']


class Configuration(metaclass=PoolMeta):
    'Sale Configuration'
    __name__ = 'sale.configuration'

    iesa_expense_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Expense IESA Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'account.iesa.expense'),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'iesa_expense_sequence':
            return pool.get('sale.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_iesa_expense_sequence(cls, **pattern):
        return cls.multivalue_model(
            'iesa_expense_sequence').default_iesa_expense_sequence()


class ConfigurationSequence(metaclass=PoolMeta):
    __name__ = 'sale.configuration.sequence'
    iesa_expense_sequence = fields.Many2One(
        'ir.sequence', "Expense IESA Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'account.iesa.expense'),
            ],
        depends=['company'])

    @classmethod
    def default_iesa_expense_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data') 
        try:
            model = ModelData.get_id(
                'account_expense', 'sequence_expense') 
            return model 
        except KeyError:
            return None