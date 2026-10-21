"""Conservative parsing for OCR and abbreviated inventory currency."""
import re
from decimal import Decimal, InvalidOperation

DEFAULT_REGIONS = dict(money=[.028,.345,.166,.417], points=[.861,.559,.907,.594],
                       balance=[.792,.042,.851,.084], lifetime=[.722,.559,.818,.593])


def parse_amount(text):
    text = text.strip().replace('\u00a0', ' ')
    match = re.fullmatch(r'\+?([\d][\d., ]*?)\s*([KkMmBb]?)', text)
    if not match:
        raise ValueError('Enter a whole number or a currency abbreviation such as 9637.5 K.')
    number, suffix = match.groups()
    number = number.replace(' ', '')
    if suffix:
        if ',' in number and '.' in number:
            raise ValueError('Use one decimal separator before K/M/B.')
        number = number.replace(',', '.')
    else:
        if re.fullmatch(r'\d{1,3}(?:,\d{3})+', number) or re.fullmatch(r'\d{1,3}(?:\.\d{3})+', number):
            number = number.replace(',', '').replace('.', '')
        elif not number.isdigit():
            raise ValueError('A decimal currency value needs a K, M or B suffix.')
    try:
        value = Decimal(number) * {'':1, 'K':1000, 'M':1000000, 'B':1000000000}[suffix.upper()]
    except InvalidOperation:
        raise ValueError('Unrecognized number.') from None
    if value != value.to_integral_value():
        raise ValueError('The result must be a whole number of coins or points.')
    return int(value)


def parse_points(text):
    text = text.strip().replace('−', '-')
    if text.startswith('-'):
        magnitude = text[1:].strip()
        if not magnitude or not magnitude[0].isdigit():
            raise ValueError('Use one minus sign before the points lost.')
        return -parse_amount(magnitude)
    return parse_amount(text)


def single_points(text):
    matches = re.findall(r'(?<![\w.,+−-])[+−-]?\s*\d+(?:(?:[.,]\d+)|(?:[ \u00a0]\d{3}))*(?:[ \u00a0]*[KkMmBb])?(?![\w.,])', text)
    if len(matches) != 1:
        return None
    try:
        return parse_points(matches[0])
    except ValueError:
        return None


def rank_points_reading(text):
    """A signed change on a ranking result, separate from lifetime totals."""
    if not re.search(r'\b(?:imperador\s+dos\s+ovos|egg\s+emperor)\b',text,re.I) or lifetime_reading(text) is None:
        return None
    changes=re.findall(r'(?<![\w.,+−-])[+−-]\s*\d+(?:[.,]\d{3})*(?![\w.,])',text)
    if len(changes)!=1:return None
    try:return parse_points(changes[0])
    except ValueError:return None


def single_amount(text):
    if re.search(r'[-−]\s*\d', text):
        return None
    # Windows OCR can read the fractional zero as O. Only repair it inside
    # an otherwise numeric abbreviation with an explicit currency multiplier.
    text = re.sub(r'(?<!\w)(\d+[.,][\dOo]+)(\s*[KkMmBb])\b',
                  lambda m:m[1].replace('O','0').replace('o','0')+m[2],text)
    matches = re.findall(r'(?<![\w.,])\+?\d+(?:(?:[.,]\d+)|(?:[ \u00a0]\d{3}))*(?:[ \u00a0]*[KkMmBb])?(?![\w.,])', text)
    if len(matches) != 1:
        return None
    try:
        return parse_amount(matches[0])
    except ValueError:
        return None


def loot_reading(text, allow_unlabelled=False):
    """Read the value immediately following a loot heading, never other stats."""
    lines=[line.strip() for line in text.splitlines() if line.strip()]
    values=[]
    for index,line in enumerate(lines):
        match=re.search(r'\b(?:saque\s+da\s+partida|match\s+loot|run\s+loot|loot\s+value)\b',line,re.I)
        if not match:
            continue
        value=line[match.end():].strip(' :')
        if not value and index+1<len(lines):
            value=lines[index+1]
        try:
            values.append(parse_amount(value))
        except ValueError:
            values.append(None)
    if values:
        return values[0] if len(values)==1 else None
    if allow_unlabelled and not re.search(r'\b(?:derrotas|defeats)\b',text,re.I):
        return single_amount(text)
    return None


def lifetime_reading(text):
    match = re.search(r'([\d., ]+)\s*/\s*([\d., ]+)', text)
    if match:
        try:
            total, next_threshold = (parse_amount(v) for v in match.groups())
            return total, next_threshold
        except ValueError:
            pass
    return None
