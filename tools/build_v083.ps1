$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $root 'out\project-05-campaign-briefings-v076.md'
$outputPath = Join-Path $root 'out\project-06-faction-display-split-v083.md'
$expected = 'AADA45EA1708A80C8E7F504DADFA5D15CC82B51CE9743E8B70187DD013F17917'
if ((Get-FileHash -Algorithm SHA256 $sourcePath).Hash -ne $expected) { throw 'v076 source hash mismatch' }
$source = [IO.File]::ReadAllBytes($sourcePath)
$rom = [byte[]]$source.Clone()
if ([Convert]::ToHexString($rom[0x65C9..0x65CB]) -ne '149000') { throw 'faction pointer mismatch' }
$rom[0x65C9] = 0x02; $rom[0x65CA] = 0x33; $rom[0x65CB] = 0xF1

$code = [Collections.Generic.List[byte]]::new()
$labels = @{}
$branches = [Collections.Generic.List[object]]::new()
function Add-Hex([string]$hex) { foreach ($b in [Convert]::FromHexString(($hex -replace ' ',''))) { $code.Add($b) } }
function Add-Label([string]$name) { $labels[$name] = $code.Count }
function Add-Branch([byte]$opcode,[string]$target) { $code.Add($opcode); $code.Add(0); $branches.Add([pscustomobject]@{ Pos=$code.Count-1; Target=$target }) }
Add-Hex '78001818'
Add-Hex '0C380075C810'
Add-Branch 0x66 'normal'
$targets = @(
  @(0x00FFC811,'dok'), @(0x00FFC812,'blank'),
  @(0x00FFC813,'il'),  @(0x00FFC814,'blank'),
  @(0x00FFC815,'je'),  @(0x00FFC816,'blank'),
  @(0x00FFC817,'guk'), @(0x00FFC818,'blank')
)
foreach ($entry in $targets) {
  Add-Hex 'B1FC'
  $addr = [int]$entry[0]
  $code.Add([byte](($addr -shr 24) -band 0xFF)); $code.Add([byte](($addr -shr 16) -band 0xFF))
  $code.Add([byte](($addr -shr 8) -band 0xFF)); $code.Add([byte]($addr -band 0xFF))
  Add-Branch 0x67 ([string]$entry[1])
}
Add-Label 'normal'; Add-Hex '0C0400FD4E75'
foreach ($entry in @(@('dok',0x1D4),@('il',0x1D6),@('je',0x06F),@('guk',0x2E5),@('blank',0x014))) {
  Add-Label ([string]$entry[0]); Add-Hex '383C'
  $index=[int]$entry[1]; $code.Add([byte](($index -shr 8)-band 0xFF)); $code.Add([byte]($index-band 0xFF))
  Add-Branch 0x60 'normal'
}
foreach ($branch in $branches) {
  $disp = [int]$labels[$branch.Target] - ($branch.Pos + 1)
  if ($disp -lt -128 -or $disp -gt 127) { throw "branch range: $($branch.Target)" }
  $code[$branch.Pos] = [byte]($disp -band 0xFF)
}
$helper = $code.ToArray()
[Array]::Copy($helper,0,$rom,0x149400,$helper.Length)
$rom[0x18E]=0; $rom[0x18F]=0
$sum=0
for($i=0x200;$i -lt $rom.Length-1;$i+=2){$sum=($sum + (($rom[$i]-shl 8)-bor $rom[$i+1])) -band 0xFFFF}
$rom[0x18E]=[byte](($sum-shr 8)-band 0xFF);$rom[0x18F]=[byte]($sum-band 0xFF)
[IO.File]::WriteAllBytes($outputPath,$rom)
$report=[ordered]@{
 source=$sourcePath; source_sha256=$expected; output=$outputPath
 output_sha256=(Get-FileHash -Algorithm SHA256 $outputPath).Hash
 size=$rom.Length; checksum=('0x{0:X4}'-f$sum); helper=('0x149400'); helper_size=$helper.Length
 shared_faction_table='0x0233F1'; pregame_buffer='0xFFC810..0xFFC817'; pregame_text='독 일 제 국'
}
$report | ConvertTo-Json | Set-Content -Encoding utf8 "$outputPath.build.json"
$report | ConvertTo-Json
