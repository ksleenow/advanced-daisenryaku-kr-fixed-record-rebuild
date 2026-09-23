$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $root 'out\project-06-unit-name-all-v082.md'
$outputPath = Join-Path $root 'out\project-06-unit-names-faction-stats-v085.md'
$expected = 'B26DF16274747ABD522E891366366F01ECC8BE5597B535D8F3C7AE98AE5691D4'
if ((Get-FileHash -Algorithm SHA256 $sourcePath).Hash -ne $expected) { throw 'v082 source hash mismatch' }
$rom = [IO.File]::ReadAllBytes($sourcePath)
if ([Convert]::ToHexString($rom[0x65C9..0x65CB]) -ne '149000') { throw 'faction pointer mismatch' }
$rom[0x65C9] = 0x02; $rom[0x65CA] = 0x33; $rom[0x65CB] = 0xF1

$code=[Collections.Generic.List[byte]]::new();$labels=@{};$branches=[Collections.Generic.List[object]]::new()
function Add-Hex([string]$hex){foreach($b in [Convert]::FromHexString(($hex-replace' ',''))){$code.Add($b)}}
function Add-Label([string]$name){$labels[$name]=$code.Count}
function Add-Branch([byte]$opcode,[string]$target){$code.Add($opcode);$code.Add(0);$branches.Add([pscustomobject]@{Pos=$code.Count-1;Target=$target})}
Add-Hex '78001818';Add-Hex '0C380075C810';Add-Branch 0x66 'normal'
$targets=@(@(0x00FFC811,'dok'),@(0x00FFC812,'blank'),@(0x00FFC813,'il'),@(0x00FFC814,'blank'),@(0x00FFC815,'je'),@(0x00FFC816,'blank'),@(0x00FFC817,'guk'),@(0x00FFC818,'blank'))
foreach($entry in $targets){Add-Hex 'B1FC';$addr=[int]$entry[0];$code.Add([byte](($addr-shr24)-band0xFF));$code.Add([byte](($addr-shr16)-band0xFF));$code.Add([byte](($addr-shr8)-band0xFF));$code.Add([byte]($addr-band0xFF));Add-Branch 0x67 ([string]$entry[1])}
Add-Label 'normal';Add-Hex '0C0400FD4E75'
foreach($entry in @(@('dok',0x1D4),@('il',0x1D6),@('je',0x06F),@('guk',0x2E5),@('blank',0x014))){Add-Label([string]$entry[0]);Add-Hex '383C';$idx=[int]$entry[1];$code.Add([byte](($idx-shr8)-band0xFF));$code.Add([byte]($idx-band0xFF));Add-Branch 0x60 'normal'}
foreach($branch in $branches){$disp=[int]$labels[$branch.Target]-($branch.Pos+1);if($disp-lt-128-or$disp-gt127){throw 'branch range'};$code[$branch.Pos]=[byte]($disp-band0xFF)}
$helper=$code.ToArray();[Array]::Copy($helper,0,$rom,0x149400,$helper.Length)

$fontBase=0x100000;$glyphBytes=32
foreach($copy in @(@(0x2C9,0x0FF),@(0x263,0x129))){$src=$fontBase+([int]$copy[0]*$glyphBytes);$dst=$fontBase+([int]$copy[1]*$glyphBytes);[Array]::Copy($rom,$src,$rom,$dst,$glyphBytes)}

$rom[0x18E]=0;$rom[0x18F]=0;$sum=0
for($i=0x200;$i-lt$rom.Length-1;$i+=2){$sum=($sum+(([int]$rom[$i]*256)+[int]$rom[$i+1]))-band0xFFFF}
$rom[0x18E]=[byte](($sum-shr8)-band0xFF);$rom[0x18F]=[byte]($sum-band0xFF)
[IO.File]::WriteAllBytes($outputPath,$rom)
$report=[ordered]@{source=$sourcePath;source_sha256=$expected;output=$outputPath;output_sha256=(Get-FileHash -Algorithm SHA256 $outputPath).Hash;size=$rom.Length;checksum=('0x{0:X4}'-f$sum);preserved='v077-v082 full unit-name work';fixes=@('8x8 faction table restored','pregame 독 일 제 국 isolated','行軍→행군','速度→속도')}
$report|ConvertTo-Json|Set-Content -Encoding utf8 "$outputPath.build.json";$report|ConvertTo-Json
