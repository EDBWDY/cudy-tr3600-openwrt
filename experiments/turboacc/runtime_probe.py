"""Isolated packet validation; no router access and no ARM toolchain rebuild."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
from runtime_vm import verify_runtime

HERE = Path(__file__).resolve().parent
lock = json.loads((HERE/'sources.json').read_text())

def download(url, target):
    with urllib.request.urlopen(url, timeout=120) as source, Path(target).open('wb') as output:
        while chunk := source.read(1024*1024): output.write(chunk)
    return target

def run(args, cwd):
    command = [str(arg) for arg in args]
    print('+', ' '.join(command), flush=True)
    result = subprocess.run(command, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode: print(result.stdout[-30000:], flush=True)
    result.check_returncode()

with tempfile.TemporaryDirectory(prefix='tcp-nat-vm-',dir=os.environ.get('RUNNER_TEMP')) as folder:
    build=Path(folder)
    archive=download(lock['kernel']['url'],build/'linux.tar.xz')
    with archive.open('rb') as source: digest=hashlib.file_digest(source,'sha256').hexdigest()
    if digest != lock['kernel']['sha256']: raise RuntimeError('Pinned kernel hash mismatch')
    verify_runtime(build,download,run)
