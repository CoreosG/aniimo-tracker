"""Editable shortcuts with keyboard-layout-aware character keys."""
import ctypes

DEFAULT_SHORTCUTS=dict(capture='Ctrl+Shift+F8',save='Ctrl+Shift+F9',overlay=';',move='',watch='',clear='Ctrl+Shift+F10',map='M',close_map='Esc')
LABELS=dict(capture='Capture screen',save='Save ready run',overlay='Toggle overlay',move='Move / lock overlay',watch='Toggle map tracking (pause/resume)',clear='Clear empty result draft',map='Game map key',close_map='Game close-map key')
GLOBAL_ACTIONS=('capture','save','clear')
ACTION_IDS=dict(capture=1,save=2,clear=3,overlay=5,move=6,watch=7)
MODIFIERS={'ctrl':2,'control':2,'shift':4,'alt':1,'win':8,'windows':8}
NAMED={'esc':27,'escape':27,'space':32,'enter':13,'return':13,'tab':9,'backspace':8,'delete':46,'insert':45,'home':36,'end':35,'pageup':33,'pagedown':34,'left':37,'up':38,'right':39,'down':40}


class ObservedKeyTaps:
    """Merge native timestamps and sampled edges without losing short taps.

    A late native event belongs to a sampled edge only when its timestamp is
    inside that edge's sampling interval, so rapid separate taps stay separate.
    """
    def __init__(self):
        self.down=False
        self.sampled_at=None
        self.hooks=[]
        self.polls=[]

    def presses(self,hook_times,down,now):
        self.hooks=[t for t in self.hooks if now-t<2]
        self.polls=[p for p in self.polls if now-p[1]<2]
        count=0
        for stamp in hook_times:
            partner=next((p for p in self.polls if p[0]<=stamp<=p[1]),None)
            if partner is not None:self.polls.remove(partner)
            else:
                self.hooks.append(stamp);count+=1
        if down and not self.down:
            low=(self.sampled_at if self.sampled_at is not None else now-.25)-.025
            high=now+.025
            partner=next((t for t in self.hooks if low<=t<=high),None)
            if partner is not None:self.hooks.remove(partner)
            else:
                self.polls.append((low,high));count+=1
        self.down,self.sampled_at=bool(down),now
        return count


def resolve_character(char):
    f=ctypes.windll.user32.VkKeyScanW
    f.argtypes=[ctypes.c_wchar];f.restype=ctypes.c_short
    value=f(char)
    if value==-1:raise ValueError(f'Key {char!r} is unavailable on this keyboard layout.')
    native=value>>8
    return value&255, (4 if native&1 else 0)|(2 if native&2 else 0)|(1 if native&4 else 0)


def compile_shortcuts(values,resolve_char=None):
    resolve_char=resolve_char or resolve_character
    compiled={};used={}
    for action,default in DEFAULT_SHORTCUTS.items():
        text=values.get(action,default).strip()
        if not text:
            compiled[action]=None;continue
        parts=text.split('+')
        if text=='+':parts=['plus']
        mods=0
        for token in parts[:-1]:
            if token.strip().lower() not in MODIFIERS:raise ValueError(f'{LABELS[action]}: use a key or a combination such as Ctrl+Shift+F8.')
            mods|=MODIFIERS[token.strip().lower()]
        key=parts[-1].strip();name=key.lower()
        if name=='plus':
            vk,implicit=resolve_char('+');mods|=implicit
        elif name in NAMED:vk=NAMED[name]
        elif name.startswith('f') and name[1:].isdigit() and 1<=int(name[1:])<=24:vk=111+int(name[1:])
        elif len(key)==1:
            # Letter case is a label choice, not an implicit Shift modifier.
            vk,implicit=resolve_char(key.lower() if key.isalpha() else key)
            mods|=implicit
        else:raise ValueError(f'{LABELS[action]}: unknown key {key!r}.')
        binding=(vk,mods)
        if binding in used:raise ValueError(f'{LABELS[action]} conflicts with {LABELS[used[binding]]}. Choose different shortcuts.')
        used[binding]=action;compiled[action]=binding
    return compiled


def matching_actions(bindings,vk,mods,in_game):
    if not in_game:return []
    return [action for action,binding in bindings.items() if action not in GLOBAL_ACTIONS and binding and binding[0]==vk and
        (mods&binding[1]==binding[1] if action in ('map','close_map') else mods==binding[1])]
