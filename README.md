# LogoAdder

Windows desktop app for batch-adding a logo to images.

## Run from source

```powershell
python -m pip install -r requirements.txt
python LogoAdder.py
```

## Build EXE

```powershell
.\build_exe.ps1
```

The executable is created at:

```text
dist\LogoAdder.exe
```

The build bundles `myicon.ico` and `Title Logo.png`.
