$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $root 'out\project-06-faction-display-split-v083.md'
$outputPath = Join-Path $root 'out\project-06-unit-command-march-v084.md'
$expected = '80930EBB0B63A11EDCFE329E512CB8D0ED58F47409EF9E5C7EB66011C6C65B24'
if ((Get-FileHash -Algorithm SHA256 $sourcePath).Hash -ne $expected) { throw 'v083 source hash mismatch' }

$rom = [IO.File]::ReadAllBytes($sourcePath)
$fontBase = 0x100000
$glyphBytes = 32
$sourceGlyph = 0x2C9 # verified custom glyph: 군
$targetGlyph = 0x0FF # 行軍 record (FD 02) references this slot
$sourceOffset = $fontBase + ($sourceGlyph * $glyphBytes)
$targetOffset = $fontBase + ($targetGlyph * $glyphBytes)
$before = [Convert]::ToHexString($rom[$targetOffset..($targetOffset + $glyphBytes - 1)])
[Array]::Copy($rom, $sourceOffset, $rom, $targetOffset, $glyphBytes)
$after = [Convert]::ToHexString($rom[$targetOffset..($targetOffset + $glyphBytes - 1)])
if ($before -eq $after) { throw 'target glyph did not change' }

$rom[0x18E] = 0; $rom[0x18F] = 0
$sum = 0
for ($i = 0x200; $i -lt $rom.Length - 1; $i += 2) {
  $sum = ($sum + (($rom[$i] -shl 8) -bor $rom[$i + 1])) -band 0xFFFF
}
$rom[0x18E] = [byte](($sum -shr 8) -band 0xFF)
$rom[0x18F] = [byte]($sum -band 0xFF)
[IO.File]::WriteAllBytes($outputPath, $rom)

$report = [ordered]@{
  source = $sourcePath
  source_sha256 = $expected
  output = $outputPath
  output_sha256 = (Get-FileHash -Algorithm SHA256 $outputPath).Hash
  size = $rom.Length
  checksum = ('0x{0:X4}' -f $sum)
  changed_glyph = '0x0FF'
  copied_from = '0x2C9'
  fixed_record = '行軍 (01 FD13 FD02) -> 행군'
  changed_payload_bytes = 32
}
$report | ConvertTo-Json | Set-Content -Encoding utf8 "$outputPath.build.json"
$report | ConvertTo-Json
