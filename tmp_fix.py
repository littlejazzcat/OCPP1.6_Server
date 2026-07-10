import shutil
import zipfile
from pathlib import Path

def apply_update(_download_path, _latest_info):
    dist_root = Path(__file__).parent.parent / "dist"
    dist_new = Path(__file__).parent.parent / "dist_new"

    # 解压并找到实际目录
    if dist_new.exists():
        shutil.rmtree(dist_new, ignore_errors=True)
    with zipfile.ZipFile(_download_path, 'r') as zf:
        zf.extractall(dist_new)
    extracted_dir = dist_new
    for item in dist_new.iterdir():
        if item.is_dir() and 'ocppv16_server' in item.name:
            extracted_dir = item
            break
    target_dir = dist_root / 'ocppv16_server'

    # 生成 update.bat
    exe_name = "ocpp_server.exe"
    bat = dist_new / "update.bat"
    bat.write_text(f"""@echo off
chcp 65001 >nul
title Updating OCPP Server...
timeout /t 2 /nobreak >nul
taskkill /f /im {exe_name} >nul 2>&1
timeout /t 1 /nobreak >nul
xcopy /e /y "{extracted_dir}\\*" "{target_dir}\\" >nul
rmdir /s /q "{dist_new}" >nul
del "{_download_path}" >nul 2>&1
start "" "{target_dir / exe_name}"
del "%~f0" >nul 2>&1
""")

    # 启动 update.bat
    import subprocess
    subprocess.Popen(str(bat), shell=True)
    return True
print(apply_update.__doc__)
