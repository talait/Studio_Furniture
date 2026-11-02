param([switch]$Lanjutkan)
$ErrorActionPreference='Stop'
$studioRoot=Split-Path -Parent $PSScriptRoot

# Blender: variabel BLENDER_EXE, lokasi standar 5.2, Blender 5.x terbaru di Program Files, lalu PATH.
function Find-Blender {
    if($env:BLENDER_EXE -and (Test-Path -LiteralPath $env:BLENDER_EXE)){return $env:BLENDER_EXE}
    $default=Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2\blender.exe'
    if(Test-Path -LiteralPath $default){return $default}
    $installed=Get-ChildItem -Path (Join-Path $env:ProgramFiles 'Blender Foundation') -Directory -Filter 'Blender 5.*' -ErrorAction SilentlyContinue |
        Sort-Object {[version]($_.Name -replace '^Blender ','')} -Descending |
        ForEach-Object {Join-Path $_.FullName 'blender.exe'} | Where-Object {Test-Path -LiteralPath $_} | Select-Object -First 1
    if($installed){return $installed}
    $found=Get-Command blender.exe -ErrorAction SilentlyContinue
    if($found){return $found.Source}
    throw 'Blender 5.2 tidak ditemukan. Pasang Blender 5.2, atau isi variabel lingkungan BLENDER_EXE dengan lokasi blender.exe.'
}

# Clone tanpa Git LFS (atau unduh ZIP dari GitHub) menghasilkan file .blend berisi teks penunjuk LFS, bukan file Blender.
function Assert-LfsFile([string]$path) {
    $head=[System.IO.File]::ReadAllBytes($path) | Select-Object -First 24
    if([System.Text.Encoding]::ASCII.GetString($head).StartsWith('version https://git-lfs')){
        throw ("File belum diunduh dari Git LFS: $path`n" +
               "Pasang Git LFS (https://git-lfs.com), lalu di folder Studio_Furniture jalankan:`n  git lfs install`n  git lfs pull`n" +
               "Jangan memakai 'Download ZIP' dari GitHub: ZIP tidak berisi file LFS.")
    }
}

$blender=Find-Blender
$template=Join-Path $studioRoot '01_STUDIO\Studio_Nakas.blend'
$startup=Join-Path $PSScriptRoot 'mulai_sesi.py'
if($Lanjutkan){
    Add-Type -AssemblyName System.Windows.Forms
    $picker=New-Object System.Windows.Forms.OpenFileDialog
    $picker.Title='Pilih proyek studio yang ingin dilanjutkan'
    $picker.InitialDirectory=Join-Path $studioRoot '03_PROYEK'
    $picker.Filter='Proyek Blender (*.blend)|*.blend'
    if($picker.ShowDialog() -ne [Windows.Forms.DialogResult]::OK){exit 0}
    $template=$picker.FileName
    $startup=Join-Path $PSScriptRoot 'lanjutkan_sesi.py'
}
if(-not (Test-Path -LiteralPath $template)){throw 'Template studio tidak ditemukan.'}
Assert-LfsFile $template
foreach($f in @('02_PRODUK\_FINISH\Finish_Library.blend','02_PRODUK\Nakas\Nakas_Oak_2Laci.blend')){
    $p=Join-Path $studioRoot $f
    if(Test-Path -LiteralPath $p){Assert-LfsFile $p}
}
New-Item -ItemType Directory -Force -Path (Join-Path $studioRoot '03_PROYEK'),(Join-Path $studioRoot '04_HASIL_RENDER') | Out-Null
Start-Process -FilePath $blender -ArgumentList @(('"'+$template+'"'),'--window-maximized','--python',('"'+$startup+'"')) -WindowStyle Normal
