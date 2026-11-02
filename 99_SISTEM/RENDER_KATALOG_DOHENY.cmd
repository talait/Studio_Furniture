@echo off
rem Seret (drag-drop) satu atau beberapa file produk .blend ke file ini.
rem Hasil: 04_HASIL_RENDER\Katalog_Doheny\<Produk>\ (HERO, FRONT, SIDE, LIFESTYLE, 2000x2500)
setlocal
set "BLENDER=C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
if defined BLENDER_EXE set "BLENDER=%BLENDER_EXE%"
if not exist "%BLENDER%" for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender 5.*") do if exist "%%D\blender.exe" set "BLENDER=%%D\blender.exe"
if not exist "%BLENDER%" for /f "delims=" %%B in ('where blender.exe 2^>nul') do set "BLENDER=%%B"
if not exist "%BLENDER%" (echo Blender 5.2 tidak ditemukan. Pasang Blender 5.2 atau isi BLENDER_EXE. & pause & exit /b 1)
set "ROOT=%~dp0.."
set "FINISH=natural_oak"
if "%~1"=="" (echo Seret file produk .blend ke file ini. & pause & exit /b)
:loop
if "%~1"=="" goto done
echo === Render katalog: %~n1 ===
"%BLENDER%" -b "%ROOT%\01_STUDIO\Studio_Katalog_Doheny.blend" --python "%ROOT%\99_SISTEM\katalog_doheny.py" -- "%~1" --finish %FINISH%
shift
goto loop
:done
start "" "%ROOT%\04_HASIL_RENDER\Katalog_Doheny"
pause
