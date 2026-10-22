"""Single-use update handoff, encrypted for the current Windows user by DPAPI."""
import ctypes
from ctypes import wintypes
import json
import time


class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data,unprotect=False):
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));target=Blob()
    function=ctypes.windll.crypt32.CryptUnprotectData if unprotect else ctypes.windll.crypt32.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):raise OSError('Windows could not protect the party handoff')
    try:return ctypes.string_at(target.data,target.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes=[ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(target.data)


def save(path,session):
    payload=json.dumps(dict(session,expires=time.time()+60)).encode('utf-8')
    if len(payload)>8192:raise ValueError('Party handoff too large')
    temporary=path.with_suffix('.tmp')
    temporary.write_bytes(_crypt(payload));temporary.replace(path)


def consume(path):
    try:
        with path.open('rb') as stream:encrypted=stream.read(16385)
        if len(encrypted)>16384:return None
        value=json.loads(_crypt(encrypted,True))
        if not isinstance(value,dict) or not time.time()<=value.get('expires',0)<=time.time()+60:return None
        return value
    except (OSError,ValueError,TypeError):return None
    finally:
        try:path.unlink(missing_ok=True)
        except OSError:pass
