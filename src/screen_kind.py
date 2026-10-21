"""Conservative local OCR screen classification for one capture shortcut."""
import re
import unicodedata
from readings import rank_points_reading


def screen_kind(text):
    clean=unicodedata.normalize('NFKD',text.replace('−','-')).encode('ascii','ignore').decode().lower()
    clean=re.sub(r'\s+',' ',clean)
    matches=[]
    if re.search(r'invent[a-z]*rio|\binventory\b',clean) and re.search(r'cofre|mochila|equipment|equipamento|backpack',clean):
        matches.append('balance')
    if re.search(r'saque da partida|match loot|run loot|loot value',clean):
        matches.append('money')
    if rank_points_reading(text) is not None:
        matches.append('points')
    if len(matches)==1:return matches[0]
    if not matches and re.search(r'condicao de fuga|escape condition',clean):return 'gameplay'
    return None
