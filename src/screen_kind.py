"""Conservative local OCR screen classification for one capture shortcut."""
import re
import unicodedata


def screen_kind(text):
    clean=unicodedata.normalize('NFKD',text.replace('−','-')).encode('ascii','ignore').decode().lower()
    clean=re.sub(r'\s+',' ',clean)
    matches=[]
    if re.search(r'invent[a-z]*rio|\binventory\b',clean) and re.search(r'cofre|mochila|equipment|equipamento|backpack',clean):
        matches.append('balance')
    if re.search(r'saque da partida|match loot|run loot|loot value',clean):
        matches.append('money')
    if re.search(r'imperador dos ovos|egg emperor',clean) and re.search(r'\d[\d., ]*/\s*\d',clean) and re.search(r'[+-]\s*\d',clean):
        matches.append('points')
    if len(matches)==1:return matches[0]
    if not matches and re.search(r'condicao de fuga|escape condition',clean):return 'gameplay'
    return None
