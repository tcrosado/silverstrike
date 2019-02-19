from . import dkb, dkb_visa, pc_mastercard, volksbank, custombank

IMPORTERS = [
    dkb,
    dkb_visa,
    pc_mastercard,
    volksbank,
    custombank,
]

IMPORTER_NAMES = [
    'DKB Giro',
    'DKB Visa',
    'PC MasterCard',
    'Volksbank',
    'CustomBank'
]

try:
    from . import ofx
    IMPORTERS.append(ofx)
    IMPORTER_NAMES.append('OFX Importer')
except ImportError:
    pass
