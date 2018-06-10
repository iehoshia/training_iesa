# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.model import ModelView, ModelSQL, fields, Check

__all__ = ['Move']

class Move(ModelSQL, ModelView):
    'Account Move'
    __name__ = 'account.move'

