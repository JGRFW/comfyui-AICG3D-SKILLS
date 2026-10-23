# analyze_video.ps1
# 用法: .\analyze_video.ps1 -VideoPath "C:\path\to\video.mp4" -OutputDir "C:\path\to\frames"
# 输出: 元信息 + 镜头切点 + 自动按中点抽帧

param(
    [Parameter(Mandatory=$true)][string]$VideoPath,
    [Parameter(Mandatory=$true)][string]$OutputDir
)

if (-not (Test-Path $VideoPath)) { Write-Error "Video not found: $VideoPath"; exit 1 }
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Output "=== METADATA ==="
ffprobe -v error -show_entries format=duration -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate -of default=noprint_wrappers=1 $VideoPath

Write-Output "`n=== SCENE CUTS (seconds) ==="
$cuts = ffmpeg -hide_banner -i $VideoPath -vf "select='gt(scene,0.3)',showinfo" -f null - 2>&1 |
    Select-String "pts_time" |
    ForEach-Object { if ($_ -match "pts_time:([\d.]+)") { [double]$matches[1] } }

if ($cuts.Count -eq 0) {
    Write-Output "No cuts detected (single shot)"
    $cuts = @()
} else {
    $cuts | ForEach-Object { Write-Output ("{0:F3}" -f $_) }
}

# 计算每个镜头中点并抽帧
$dur = [double](ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $VideoPath)
$boundaries = @(0.0) + $cuts + @($dur)
Write-Output "`n=== EXTRACTED FRAMES (midpoints) ==="
for ($i = 0; $i -lt $boundaries.Count - 1; $i++) {
    $start = $boundaries[$i]
    $end = $boundaries[$i+1]
    $mid = ($start + $end) / 2
    $shotNum = $i + 1
    $outFile = Join-Path $OutputDir ("shot_{0:D2}_{1:F1}s.jpg" -f $shotNum, $mid)
    ffmpeg -hide_banner -loglevel error -ss $mid -i $VideoPath -frames:v 1 -q:v 2 $outFile -y
    Write-Output ("Shot {0:D2}: {1:F2}s-{2:F2}s (mid {3:F2}s) -> {4}" -f $shotNum, $start, $end, $mid, (Split-Path $outFile -Leaf))
    # 长镜头多抽一帧
    if ($end - $start -gt 3.0) {
        $mid2 = $start + ($end - $start) * 0.75
        $outFile2 = Join-Path $OutputDir ("shot_{0:D2}b_{1:F1}s.jpg" -f $shotNum, $mid2)
        ffmpeg -hide_banner -loglevel error -ss $mid2 -i $VideoPath -frames:v 1 -q:v 2 $outFile2 -y
        Write-Output ("  extra: {0:F2}s -> {1}" -f $mid2, (Split-Path $outFile2 -Leaf))
    }
}
Write-Output "`nDone. Total shots: $($boundaries.Count - 1), Duration: $($dur:F2)s"
