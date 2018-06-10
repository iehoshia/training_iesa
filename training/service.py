# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval

__all__ = ['Service']
 
class Service(ModelSQL, ModelView):
	'Service recurrence'
	__name__ = 'sale.subscription.service'

	#numero = fields.Numeric('Numero')

	@classmethod
	def __setup__(cls):
		super(Service, cls).__setup__()
		cls._order.insert(0, ('product.rec_name', 'ASC')) 
