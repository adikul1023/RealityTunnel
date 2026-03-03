Add-Type -AssemblyName System.Drawing

function New-Frame([int]$size) {
    $bmp = New-Object System.Drawing.Bitmap($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g   = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode   = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
    $g.Clear([System.Drawing.Color]::Transparent)

    $cx = $size / 2.0; $cy = $size / 2.0
    $r  = [Math]::Max(2, [int]($size * 0.18)); $r2 = $r * 2

    # --- rounded square bg ---
    $bgPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $bgPath.AddArc(0, 0, $r2, $r2, 180, 90)
    $bgPath.AddArc($size-$r2, 0, $r2, $r2, 270, 90)
    $bgPath.AddArc($size-$r2, $size-$r2, $r2, $r2, 0, 90)
    $bgPath.AddArc(0, $size-$r2, $r2, $r2, 90, 90)
    $bgPath.CloseFigure()

    $bgBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Rectangle(0, 0, $size, $size)),
        [System.Drawing.Color]::FromArgb(255, 10, 8, 30),
        [System.Drawing.Color]::FromArgb(255, 40, 18, 76),
        [System.Drawing.Drawing2D.LinearGradientMode]::ForwardDiagonal)
    $g.FillPath($bgBrush, $bgPath)
    $bgBrush.Dispose(); $bgPath.Dispose()

    # --- glow ring outer ---
    $pad = [int]($size * 0.10); $rsz = $size - $pad * 2
    $pw  = [float]([Math]::Max(1.0, $size * 0.055))
    $gp  = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(60, 30, 140, 255), ($pw * 3.5))
    $g.DrawEllipse($gp, $pad, $pad, $rsz, $rsz); $gp.Dispose()

    # --- main ring ---
    $rp = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(230, 0, 155, 255), $pw)
    $g.DrawEllipse($rp, $pad, $pad, $rsz, $rsz); $rp.Dispose()

    # --- shield ---
    $sw = [float]($size * 0.42); $sh = [float]($size * 0.50)
    $sx = [float]($cx - $sw / 2); $sy = [float]($cy - $sh * 0.55)

    $pts = [System.Drawing.PointF[]]@(
        [System.Drawing.PointF]::new([float]$cx,           [float]$sy),
        [System.Drawing.PointF]::new([float]($sx + $sw),   [float]($sy + $sh * 0.27)),
        [System.Drawing.PointF]::new([float]($sx + $sw),   [float]($sy + $sh * 0.63)),
        [System.Drawing.PointF]::new([float]$cx,           [float]($sy + $sh)),
        [System.Drawing.PointF]::new([float]$sx,           [float]($sy + $sh * 0.63)),
        [System.Drawing.PointF]::new([float]$sx,           [float]($sy + $sh * 0.27))
    )

    if ($size -ge 24) {
        $sf = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
            (New-Object System.Drawing.RectangleF($sx, $sy, $sw, $sh)),
            [System.Drawing.Color]::FromArgb(215, 0, 95, 210),
            [System.Drawing.Color]::FromArgb(215, 70, 0, 190),
            [System.Drawing.Drawing2D.LinearGradientMode]::Vertical)
        $g.FillPolygon($sf, $pts); $sf.Dispose()

        $sp = New-Object System.Drawing.Pen(
            [System.Drawing.Color]::FromArgb(255, 130, 215, 255),
            [float]([Math]::Max(1.0, $size * 0.04)))
        $g.DrawPolygon($sp, $pts); $sp.Dispose()

        if ($size -ge 32) {
            # checkmark inside shield
            $tw = [float]($sw * 0.54); $th = [float]($sh * 0.36)
            $tx = [float]($cx - $tw / 2); $ty = [float]($sy + $sh * 0.34)
            $tk = [System.Drawing.PointF[]]@(
                [System.Drawing.PointF]::new($tx,             $ty + $th * 0.50),
                [System.Drawing.PointF]::new($tx + $tw * 0.37,$ty + $th),
                [System.Drawing.PointF]::new($tx + $tw,       $ty)
            )
            $tpw = [float]([Math]::Max(1.5, $size * 0.055))
            $tp  = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(255, 200, 240, 255), $tpw)
            $tp.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
            $tp.EndCap   = [System.Drawing.Drawing2D.LineCap]::Round
            $tp.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
            $g.DrawLines($tp, $tk); $tp.Dispose()
        }
    } else {
        $db = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 0, 155, 255))
        $ds = [int]($size * 0.46)
        $g.FillEllipse($db, [int]($cx - $ds/2), [int]($cy - $ds/2), $ds, $ds)
        $db.Dispose()
    }

    $g.Dispose()
    return $bmp
}

function Write-Ico([string]$outPath, [int[]]$sizes) {
    # Use string keys to avoid PowerShell ordered-dict integer-index ambiguity
    $pngs = @{}
    foreach ($sz in $sizes) {
        $bmp  = New-Frame $sz
        $ms   = New-Object System.IO.MemoryStream
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $pngs["s$sz"] = $ms.ToArray()
        $ms.Close(); $bmp.Dispose()
        Write-Host "  Rendered $sz x $sz  ($($pngs["s$sz"].Length) bytes)"
    }

    $fs = [System.IO.File]::Create($outPath)
    $bw = New-Object System.IO.BinaryWriter($fs)

    # ICONDIR
    $bw.Write([uint16]0)
    $bw.Write([uint16]1)
    $bw.Write([uint16]$sizes.Count)

    # ICONDIRENTRY[]
    $offset = [uint32](6 + $sizes.Count * 16)
    foreach ($sz in $sizes) {
        $imgByte = if ($sz -ge 256) { [byte]0 } else { [byte]$sz }
        $bw.Write($imgByte); $bw.Write($imgByte)
        $bw.Write([byte]0);  $bw.Write([byte]0)
        $bw.Write([uint16]1); $bw.Write([uint16]32)
        $bw.Write([uint32]$pngs["s$sz"].Length)
        $bw.Write($offset)
        $offset += [uint32]$pngs["s$sz"].Length
    }

    foreach ($sz in $sizes) { $bw.Write($pngs["s$sz"]) }

    $bw.Close(); $fs.Close()
    Write-Host "Saved: $outPath  ($((Get-Item $outPath).Length) bytes total)"
}

Write-Ico "D:\My projects\VPN\OverREALITY\app.ico" @(16, 32, 48, 256)
