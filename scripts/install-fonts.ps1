# SlideNote — PPTX 렌더링에 필요한 폰트 자동 설치
# 대상: Pretendard, Arimo, Roboto (현재 사용자 폴더에 설치, 관리자 불필요)
# 사용법: .\scripts\install-fonts.ps1

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$FontDir = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
$RegPath = "HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
$TmpDir  = Join-Path $env:TEMP "slidenote_fonts"

if (-not (Test-Path $FontDir)) { New-Item -ItemType Directory -Path $FontDir | Out-Null }
if (-not (Test-Path $TmpDir))  { New-Item -ItemType Directory -Path $TmpDir  | Out-Null }
if (-not (Test-Path $RegPath)) { New-Item -Path $RegPath -Force | Out-Null }

function Install-FontFile($ttfPath) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($ttfPath)
    $dest = Join-Path $FontDir ([System.IO.Path]::GetFileName($ttfPath))
    Copy-Item $ttfPath $dest -Force
    $ext  = [System.IO.Path]::GetExtension($ttfPath).ToLower()
    $type = if ($ext -eq '.otf') { '(OpenType)' } else { '(TrueType)' }
    Set-ItemProperty -Path $RegPath -Name "$name $type" -Value $dest
    Write-Host "  설치됨: $name"
}

# ── 1. Pretendard ──
if (Test-Path (Join-Path $FontDir "Pretendard-Regular.ttf")) {
    Write-Host "`n[1/3] Pretendard: 이미 설치됨, 건너뜀" -ForegroundColor Yellow
} else {
    Write-Host "`n[1/3] Pretendard 다운로드 (GitHub)..." -ForegroundColor Cyan
    $rel   = Invoke-RestMethod "https://api.github.com/repos/orioncactus/pretendard/releases/latest"
    $asset = $rel.assets | Where-Object { $_.name -match "\.zip$" } | Select-Object -First 1
    $zip   = Join-Path $TmpDir "pretendard.zip"
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
    $dir   = Join-Path $TmpDir "pretendard"
    Expand-Archive $zip $dir -Force
    $want  = @('Regular','Medium','Bold','ExtraBold','SemiBold')
    Get-ChildItem $dir -Recurse -Include "*.ttf","*.otf" | Where-Object {
        $b = $_.BaseName; $want | Where-Object { $b -match "Pretendard.*$_$" }
    } | Select-Object -Unique | ForEach-Object { Install-FontFile $_.FullName }
}

# ── GitHub API를 통한 폰트 다운로드 헬퍼 ──
function Get-GithubFont($repoPath, $destName) {
    $encoded = $repoPath -replace '\[', '%5B' -replace '\]', '%5D'
    $item = Invoke-RestMethod "https://api.github.com/repos/google/fonts/contents/$encoded"
    $dest = Join-Path $FontDir $destName
    Invoke-WebRequest $item.download_url -OutFile $dest
    $name = [System.IO.Path]::GetFileNameWithoutExtension($destName)
    Set-ItemProperty -Path $RegPath -Name "$name (TrueType)" -Value $dest
    Write-Host "  설치됨: $name"
}

# ── 2. Arimo (가변폰트) ──
if (Test-Path (Join-Path $FontDir "Arimo-Variable.ttf")) {
    Write-Host "`n[2/3] Arimo: 이미 설치됨, 건너뜀" -ForegroundColor Yellow
} else {
    Write-Host "`n[2/3] Arimo 다운로드 (GitHub API)..." -ForegroundColor Cyan
    Get-GithubFont "ofl/arimo/Arimo[wght].ttf"          "Arimo-Variable.ttf"
    Get-GithubFont "ofl/arimo/Arimo-Italic[wght].ttf"   "Arimo-Italic-Variable.ttf"
}

# ── 3. Roboto (가변폰트) ──
if (Test-Path (Join-Path $FontDir "Roboto-Variable.ttf")) {
    Write-Host "`n[3/3] Roboto: 이미 설치됨, 건너뜀" -ForegroundColor Yellow
} else {
    Write-Host "`n[3/3] Roboto 다운로드 (GitHub API)..." -ForegroundColor Cyan
    Get-GithubFont "ofl/roboto/Roboto[wdth,wght].ttf"        "Roboto-Variable.ttf"
    Get-GithubFont "ofl/roboto/Roboto-Italic[wdth,wght].ttf" "Roboto-Italic-Variable.ttf"
}

Remove-Item $TmpDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`n완료! PowerPoint를 재시작한 뒤 SlideNote에 파일을 다시 업로드하세요." -ForegroundColor Green
