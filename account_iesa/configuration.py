# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

__all__ = ['Configuration', 'ConfigurationSequence']


class Configuration:
    'Sale Configuration'
    __metaclass__ = PoolMeta
    __name__ = 'sale.configuration'

    iesa_payment_sequence = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Payment IESA Sequence", required=True,
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('code', '=', 'account.iesa.payment'),
                ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'iesa_payment_sequence':
            return pool.get('sale.configuration.sequence')
        return super(Configuration, cls).multivalue_model(field)

    @classmethod
    def default_iesa_payment_sequence(cls, **pattern):
        return cls.multivalue_model(
            'iesa_payment_sequence').default_iesa_payment_sequence()


class ConfigurationSequence:
    __metaclass__ = PoolMeta
    __name__ = 'sale.configuration.sequence'
    iesa_payment_sequence = fields.Many2One(
        'ir.sequence', "Payment IESA Sequence", required=True,
        domain=[
            ('company', 'in', [Eval('company', -1), None]),
            ('code', '=', 'account.iesa.payment'),
            ],
        depends=['company'])

    @classmethod
    def default_iesa_payment_sequence(cls):
        pool = Pool()
        ModelData = pool.get('ir.model.data') 
        try:
            return ModelData.get_id(
                'account_iesa', 'sequence_payment')
        except KeyError:
            return None