"""Verified release downloads and the portable Windows replacement helper.

No party input is used here. Only the repository's versioned GitHub release is
accepted, with its exact byte count and SHA-256 from the official update feed.
"""
import ctypes
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

MAX_BYTES=250*1024*1024
ASSET_HOSTS={'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}


def validate_release(info):
    version=info.get('version')
    if not isinstance(version,str) or not re.fullmatch(r'\d{1,5}\.\d{1,5}\.\d{1,5}',version):
        raise ValueError('Invalid release version')
    address=f'https://github.com/CoreosG/aniimo-tracker/releases/download/v{version}/AniimoTracker.exe'
    if info.get('download_url')!=address:raise ValueError('Unexpected release download address')
    digest=info.get('sha256')
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Missing release checksum')
    size=info.get('size')
    if type(size) is not int or not 2<=size<=MAX_BYTES:raise ValueError('Invalid release size')
    return address,digest,size


def asset_address(address):
    parsed=urlsplit(address)
    if parsed.scheme!='https' or parsed.hostname not in ASSET_HOSTS or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Unexpected download redirect')
    return address


class ReleaseRedirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        asset_address(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def verified_file(path,digest,size=None):
    path=Path(path)
    if size is not None and path.stat().st_size!=size:raise ValueError('Release size mismatch')
    checksum=hashlib.sha256()
    with path.open('rb') as source:
        if source.read(2)!=b'MZ':raise ValueError('Invalid Windows executable')
        source.seek(0)
        for chunk in iter(lambda:source.read(256*1024),b''):checksum.update(chunk)
    if checksum.hexdigest()!=digest:raise ValueError('Release checksum mismatch')
    return path


def download_release(info,destination,progress=None,opener=None):
    address,digest,size=validate_release(info)
    destination=Path(destination);partial=destination.with_suffix('.download')
    open_url=opener or build_opener(ReleaseRedirects()).open
    received=0;last_progress=0
    try:
        with open_url(Request(address,headers={'User-Agent':'AniimoTracker-Updater'}),timeout=20) as response,partial.open('wb') as output:
            asset_address(response.geturl())
            while True:
                chunk=response.read(256*1024)
                if not chunk:break
                received+=len(chunk)
                if received>size:raise ValueError('Release size mismatch')
                output.write(chunk)
                if progress and time.monotonic()-last_progress>.2:
                    progress(received,size);last_progress=time.monotonic()
        verified_file(partial,digest,size)
        partial.replace(destination)
        return destination
    finally:
        partial.unlink(missing_ok=True)


def replace_release(candidate,target,digest,launch):
    """Replace a stopped portable executable; preserve and restore its backup."""
    candidate,target=Path(candidate).resolve(),Path(target).resolve()
    if candidate==target or target.suffix.lower()!='.exe':raise ValueError('Invalid update target')
    verified_file(candidate,digest)
    temporary=target.with_name(target.name+'.new')
    backup=target.with_name(target.name+'.previous')
    try:
        shutil.copyfile(candidate,temporary)
        verified_file(temporary,digest)
        # The PyInstaller bootloader can hold the executable briefly after its
        # Python child exits. Retry file access without killing either process.
        deadline=time.monotonic()+20
        while True:
            try:
                shutil.copy2(target,backup)
                os.replace(temporary,target)
                break
            except PermissionError:
                if time.monotonic()>=deadline:raise
                time.sleep(.25)
        try:launch(target)
        except Exception:
            shutil.copy2(backup,target)
            raise
        return backup
    finally:
        temporary.unlink(missing_ok=True)


def wait_for_exit(pid):
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x100000,False,pid)
    if not handle:
        if ctypes.get_last_error()==87:return
        raise OSError('Cannot wait for the tracker to close')
    try:
        if kernel.WaitForSingleObject(handle,60000)!=0:raise TimeoutError('Tracker is still running')
    finally:kernel.CloseHandle(handle)


def start_update_helper(candidate,target,pid,digest):
    candidate=verified_file(candidate,digest)
    # Fail before closing the tracker if its folder cannot accept replacements.
    with tempfile.TemporaryFile(dir=Path(target).resolve().parent):pass
    return subprocess.Popen([str(candidate),'--apply-update',str(Path(target).resolve()),str(pid),digest],
                            creationflags=subprocess.CREATE_NO_WINDOW,
                            env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})


def run_helper(arguments):
    target=None;stopped=False
    def launch(path):
        subprocess.Popen([str(path)],creationflags=subprocess.CREATE_NO_WINDOW,
                         env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'})
    try:
        if len(arguments)!=3:raise ValueError('Invalid update arguments')
        target=Path(arguments[0]).resolve();pid=int(arguments[1]);digest=arguments[2]
        if pid<=0 or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Invalid update arguments')
        verified_file(sys.executable,digest)
        wait_for_exit(pid);stopped=True
        replace_release(sys.executable,target,digest,launch)
        return 0
    except Exception as error:
        ctypes.windll.user32.MessageBoxW(None,'Update could not finish. Your saved data is unchanged.\n'+str(error),'Aniimo Tracker update',0x10)
        if stopped and target and target.is_file():
            try:launch(target)
            except OSError:pass
        return 1
