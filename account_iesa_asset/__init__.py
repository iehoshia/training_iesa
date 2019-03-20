# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .asset import *
from . import product

def register():
    Pool.register(
        CreateAssetStart, 
        CreateAssetForm, 
        CreateAssetEnd,
        product.ProductCategory, 
        module='account_iesa_asset', type_='model')
    Pool.register(
        CreateAsset,
        module='account_iesa_asset', type_='wizard')