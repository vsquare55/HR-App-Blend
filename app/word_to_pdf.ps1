param([string]$In, [string]$Out)
# Uses Microsoft Word (if installed) to save a .docx as a PDF so the app can show the real page.
$ErrorActionPreference = "Stop"
$word = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    # ConfirmConversions=false, ReadOnly=true, AddToRecentFiles=false
    $doc = $word.Documents.Open($In, $false, $true, $false)
    $doc.ExportAsFixedFormat($Out, 17)   # 17 = PDF
    $doc.Close($false)
    exit 0
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
finally {
    if ($word -ne $null) { try { $word.Quit() } catch {} }
}
