# Run from the root of the reviewer repository during the paused rebase.
$ErrorActionPreference = 'Stop'
$path = Join-Path (Get-Location) 'README.md'
if (-not (Test-Path -LiteralPath $path)) { throw 'README.md not found. Run from C:\Users\iqran\reviewer.' }
$utf8 = [System.Text.UTF8Encoding]::new($false)
$content = [System.IO.File]::ReadAllText($path, $utf8)
$nl = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }

# Match only the two known conflict blocks; abort if either is missing.
$badgePattern = '(?m)^<<<<<<< HEAD\r?\n[\s\S]*?^>>>>>>>[^\r\n]*\r?\n'
$blocks = [regex]::Matches($content, $badgePattern)
if ($blocks.Count -ne 2) { throw "Expected 2 merge conflict blocks in README.md; found $($blocks.Count). No file changed." }
$top = $blocks[0].Value
$bottom = $blocks[1].Value
if ($top -notmatch 'tests-387' -or $top -notmatch 'tests-383' -or $bottom -notmatch '387 tests' -or $bottom -notmatch '383 tests') {
  throw 'Conflict blocks differ from the expected test-count conflicts. No file changed.'
}
$updated = $content.Replace($top, "[![Tests](https://img.shields.io/badge/tests-387-brightgreen.svg)](test/)${nl}")
$updated = $updated.Replace($bottom, "npm test              # 387 tests${nl}")

# Separate the startup repoId explanation from the following existing paragraph.
$paragraphPattern = '(The startup `--json` output does not include `repoId`:[^\r\n]*)(\r?\n)(A `repoId` is a random per-session handle)'
$updated = [regex]::Replace($updated, $paragraphPattern, ('$1' + $nl + $nl + '$3'))
if ($updated -match '(?m)^(<<<<<<<|=======|>>>>>>>)') { throw 'Conflict markers remain. No file changed.' }

$backup = Join-Path ([System.IO.Path]::GetTempPath()) ('reviewer-README-backup-' + [guid]::NewGuid().ToString('N') + '.md')
[System.IO.File]::WriteAllText($backup, $content, $utf8)
[System.IO.File]::WriteAllText($path, $updated, $utf8)
Write-Host 'README conflict blocks resolved; count set to 387.'
Write-Host "Backup saved as: $backup"
Write-Host 'Next: node --test test/readme.test.js'
