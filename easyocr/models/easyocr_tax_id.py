# Copyright 2026 EasySoft Tech S.L. <https://easysoft.es>
# License LGPL-3 (see LICENSE file).

"""Telling whether two tax numbers, or two vendor names, are the same one.

No model lives here, for the same reason as in easyocr_values: these are plain
functions the document needs and the tests call directly, and a module without
models cannot reorder the registry.

It is the port of what the module this comes from does on its unattended path
(the webhook), where nobody looks at the vendor before the bill is made. A tax
number arrives in many shapes ("ES B-12345678", "B12345678", "CIF: B12345678"),
the OCR misreads a character now and then, and a vendor's name carries a legal
form the paper may print or not. Matching on the exact text created the same
vendor twice; these functions are what the lookup compares instead.
"""

import re
import unicodedata

# VAT prefixes a tax number can carry: the VIES list plus the usual non-EU ones.
VAT_COUNTRY_PREFIXES = (
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'EL', 'ES', 'FI', 'FR', 'HR',
    'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI',
    'SK', 'XI', 'GB', 'CH', 'NO',
)

# A label stuck to the number. No Spanish id starts with these letters, so a real
# number is never cut.
TAX_ID_LABEL = re.compile(r'^(NIFIVA|NIF|CIF|NIE|DNI|VATNO|VAT|IVA|TVA|USTIDNR)([A-Z0-9]{5,})$')

SPAIN_NAMES = ('ES', 'ESP', 'ESPANA', 'SPAIN', 'ESPAGNE', 'SPANIEN', 'SPAGNA', 'ESPANHA', 'ESPANYA')

DNI_LETTERS = 'TRWAGMYFPDXBNJZSQVHLCKE'

# Legal forms dropped from the end of a vendor name before comparing it.
LEGAL_FORMS = (
    'SL', 'SA', 'SLU', 'SAU', 'SLL', 'SLP', 'SLNE', 'SC', 'SCP', 'SCOOP', 'COOP', 'CB',
    'AIE', 'SRL', 'SAS', 'SARL', 'SPA', 'SNC', 'GMBH', 'AG', 'KG', 'BV', 'NV', 'LTD',
    'LIMITED', 'PLC', 'LLC', 'LLP', 'INC', 'CORP', 'CORPORATION', 'CO', 'COMPANY', 'LDA',
    'UNIPESSOAL', 'SOCIEDADLIMITADA', 'SOCIEDADANONIMA', 'UNIPERSONAL',
)

# What two amounts of one paper may differ by and still be the same amount.
TOTALS_TOLERANCE = 0.05


def normalize_tax_id(value):
    """Upper case, with everything that is not a letter or a digit gone."""
    return re.sub(r'[^A-Z0-9]', '', unaccent(value or '').upper())


def unaccent(text):
    """The text without its accents: "Ñandú" gives "Nandu"."""
    decomposed = unicodedata.normalize('NFKD', str(text or ''))
    return ''.join(char for char in decomposed if not unicodedata.combining(char))


def split_tax_id(value):
    """The tax number as (normalized, country prefix, bare number).

    The prefix is only taken as one when it is a known VAT prefix and what is
    left carries a digit, so a bare number that happens to start with two
    letters is left alone.
    """
    norm = normalize_tax_id(value)
    label = TAX_ID_LABEL.match(norm)
    if label and re.search(r'[0-9]', label.group(2)):
        norm = label.group(2)
    country, bare = '', norm
    prefixed = re.match(r'^([A-Z]{2})([A-Z0-9]+)$', norm)
    if (len(norm) > 4 and prefixed and prefixed.group(1) in VAT_COUNTRY_PREFIXES
            and re.search(r'[0-9]', prefixed.group(2))):
        country, bare = prefixed.group(1), prefixed.group(2)
    return norm, country, bare


def spanish_tax_id_type(bare):
    """'dni', 'nie', 'klm', 'cif', or '' when it does not have a Spanish shape."""
    bare = bare or ''
    if re.match(r'^[0-9]{8}[A-Z]$', bare):
        return 'dni'
    if re.match(r'^[XYZ][0-9]{7}[A-Z]$', bare):
        return 'nie'
    if re.match(r'^[KLM][0-9]{7}[A-Z]$', bare):
        return 'klm'
    if re.match(r'^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$', bare):
        return 'cif'
    return ''


def is_valid_spanish_tax_id(bare):
    """Whether a bare Spanish DNI, NIE, K/L/M NIF or CIF has the right control."""
    bare = bare or ''
    kind = spanish_tax_id_type(bare)
    if kind == 'dni':
        return bare[8] == DNI_LETTERS[int(bare[:8]) % 23]
    if kind == 'nie':
        number = {'X': '0', 'Y': '1', 'Z': '2'}[bare[0]] + bare[1:8]
        return bare[8] == DNI_LETTERS[int(number) % 23]
    if kind == 'klm':
        return bare[8] == DNI_LETTERS[int(bare[1:8]) % 23]
    if kind == 'cif':
        total = 0
        for position in range(1, 8):
            digit = int(bare[position])
            if position % 2 == 1:
                digit *= 2
                digit = digit // 10 + digit % 10
            total += digit
        control = (10 - total % 10) % 10
        # Some kinds of entity print a digit and others a letter: same value.
        return bare[8] in (str(control), 'JABCDEFGHI'[control])
    return False


def is_spain(country):
    """Whether a country read from a paper, code or name, is Spain."""
    text = re.sub(r'[^A-Z]', '', unaccent(country or '').upper())
    return bool(text) and text in SPAIN_NAMES


def tax_id_looks_invalid(value, vendor_country='', own_country=''):
    """Whether a tax number read by the OCR is certainly wrong.

    Only Spanish numbers can be told: they carry a control character. One is
    taken as Spanish when it has the ES prefix, or when it has none, has the
    length of a Spanish one and nothing says the vendor is foreign (its country
    is Spain, or was not read and the company itself is Spanish). Nine
    characters without a letter are not a Spanish shape at all: that is a
    foreign number read without its prefix, and it is not judged.
    """
    norm, country, bare = split_tax_id(value)
    if not norm:
        return False
    if country == 'ES':
        return not is_valid_spanish_tax_id(bare)
    if country:
        return False
    if (vendor_country or '').strip():
        looks_spanish = is_spain(vendor_country)
    else:
        looks_spanish = (own_country or '').upper() == 'ES'
    if not looks_spanish or len(bare) != 9 or not re.search(r'[A-Z]', bare):
        return False
    return not is_valid_spanish_tax_id(bare)


def tax_id_variants(value):
    """Every form under which the same tax number may be stored, normalized.

    "ESB12345678" also gives "B12345678", and a bare Spanish number also gives
    its ES form, so either side may carry the prefix. The bare number is only
    offered for ES and EL: for any other country it is short enough to be some
    other country's number. A DNI without its leading zero is offered with it,
    and the other way round, only as a search form: the number read is never
    rewritten, since seven digits and a letter is also an old Irish VAT number.
    """
    norm, country, bare = split_tax_id(value)
    if not norm:
        return []
    variants = [norm]
    if country in ('', 'ES', 'EL'):
        variants.append(bare)
    if not country and spanish_tax_id_type(bare):
        variants.append('ES' + bare)
    if country == 'EL':
        variants.append('GR' + bare)
    if country in ('', 'ES'):
        if re.match(r'^[0-9]{7}[A-Z]$', bare):
            variants += ['0' + bare, 'ES0' + bare]
        elif re.match(r'^0[0-9]{7}[A-Z]$', bare):
            variants += [bare[1:], 'ES' + bare[1:]]
    # Below five characters a match is noise, not an identity.
    unique = []
    for variant in variants:
        if len(variant) >= 5 and variant not in unique:
            unique.append(variant)
    return unique


def tax_id_key(value):
    """What two tax numbers are compared by: the bare number, DNI zero included."""
    _norm, country, bare = split_tax_id(value)
    if country in ('', 'ES') and re.match(r'^[0-9]{7}[A-Z]$', bare):
        return '0' + bare
    return bare


def name_key(name):
    """The name in capitals, unaccented, with anything else turned into spaces."""
    key = re.sub(r'[^A-Z0-9]+', ' ', unaccent(name or '').upper())
    return ' '.join(key.split())


def name_core(name):
    """The vendor name without its trailing legal form, run together.

    "ACME, S.L." and "Acme SL" both give "ACME". Only trailing words are dropped,
    and never the whole name. Single letters are joined first, because "S.L."
    is "S L" once the dots are gone.
    """
    key = name_key(name)
    if not key:
        return ''
    tokens = key.split(' ')
    while len(tokens) > 1:
        last = tokens[-1]
        if last in LEGAL_FORMS:
            tokens.pop()
            continue
        run = []
        index = len(tokens) - 1
        while index > 0 and len(tokens[index]) == 1:
            run.insert(0, tokens[index])
            index -= 1
        if len(run) >= 2 and ''.join(run) in LEGAL_FORMS:
            tokens = tokens[:len(tokens) - len(run)]
            continue
        if len(tokens) > 2 and tokens[-2] + last in LEGAL_FORMS:
            tokens = tokens[:-2]
            continue
        break
    return ''.join(tokens)


def header_totals_mismatch(base, tax, total, surcharge=0.0, withholding=0.0,
                           tolerance=TOTALS_TOLERANCE):
    """What base + tax + surcharge - withholding comes to, when it is not the total.

    None when the amounts add up, and also when one of them was not read: an
    amount nobody read cannot be checked. The withholding is accepted both taken
    off and not, because the paper may print the total before or after it.
    """
    if base is None or tax is None or total is None:
        return None
    if abs(base) < 0.005 or abs(total) < 0.005:
        return None
    surcharge = surcharge or 0.0
    withholding = abs(withholding or 0.0)
    with_withholding = base + tax + surcharge - withholding
    without_withholding = base + tax + surcharge
    if (abs(with_withholding - total) <= tolerance
            or abs(without_withholding - total) <= tolerance):
        return None
    return round(with_withholding, 2)
