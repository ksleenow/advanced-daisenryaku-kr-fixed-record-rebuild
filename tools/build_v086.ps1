$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$sourcePath = Join-Path $root 'out\project-06-unit-names-faction-stats-v085.md'
$outputPath = Join-Path $root 'out\project-06-unit-names-faction-stats-v089.md'
$expected = 'C31A2C363958F317211EE446332ACB27450FEAFB1081EA6DAC52C6D810402CFC'
if ((Get-FileHash -Algorithm SHA256 $sourcePath).Hash -ne $expected) { throw 'v085 source hash mismatch' }
$rom = [IO.File]::ReadAllBytes($sourcePath)

# The renderer may copy the faction record through different buffers.  Do not
# assume an address: identify the exact German 9-byte record around A0, then
# replace only its eight visible cells while preserving draw count and spacing.
$code=[Collections.Generic.List[byte]]::new();$labels=@{};$branches=[Collections.Generic.List[object]]::new()
function Add-Hex([string]$hex){foreach($b in [Convert]::FromHexString(($hex-replace' ',''))){$code.Add($b)}}
function Add-Label([string]$name){$labels[$name]=$code.Count}
function Add-Branch([byte]$opcode,[string]$target){$code.Add($opcode);$code.Add(0);$branches.Add([pscustomobject]@{Pos=$code.Count-1;Target=$target})}
Add-Hex '78001818' # MOVEQ #0,D4 / MOVE.B (A0)+,D4 (original instructions)
$chars=@(
  @{Offset=1; Byte=0x75; Label='dok'},
  @{Offset=2; Byte=0x4A; Label='blank'},
  @{Offset=3; Byte=0x5A; Label='il'},
  @{Offset=4; Byte=0x14; Label='blank'},
  @{Offset=5; Byte=0x5B; Label='je'},
  @{Offset=6; Byte=0x4A; Label='blank'},
  @{Offset=7; Byte=0x52; Label='guk'},
  @{Offset=8; Byte=0x50; Label='blank'}
)
$glyph=@{dok=0x1D4;il=0x1D6;je=0x06F;guk=0x2E5;blank=0x014}
$n=0
foreach($ch in $chars){
    $next="next$n";$n++
    # CMPI.B immediate is encoded with a full extension word (00 xx).
    Add-Hex '0C0400';$code.Add([byte]$ch.Byte)
    Add-Branch 0x66 $next
    # Verify stable anchor bytes at record positions 1, 3, 5 and 7.
    foreach($anchor in @(@(1,0x75),@(3,0x5A),@(5,0x5B),@(7,0x52))){
      # A0 has already advanced one byte by MOVE.B (A0)+,D4.
      $disp=[int]$anchor[0]-[int]$ch.Offset-1
      Add-Hex '0C2800';$code.Add([byte]$anchor[1]);$code.Add([byte](($disp -shr 8) -band 0xFF));$code.Add([byte]($disp -band 0xFF))
      Add-Branch 0x66 $next
    }
    Add-Hex '383C';$idx=[int]$glyph[[string]$ch.Label];$code.Add([byte](($idx -shr 8) -band 0xFF));$code.Add([byte]($idx -band 0xFF))
    Add-Hex '0C0400FD4E75'
    Add-Label $next
}
Add-Label 'normal';Add-Hex '0C0400FD4E75'
foreach($branch in $branches){$disp=[int]$labels[$branch.Target]-($branch.Pos+1);if($disp -lt -128 -or $disp -gt 127){throw "branch range $($branch.Target): $disp"};$code[$branch.Pos]=[byte]($disp -band 0xFF)}
$helper=$code.ToArray()
if($helper.Length -gt 0x300){throw 'helper too large'}
[Array]::Clear($rom,0x149400,0x300)
[Array]::Copy($helper,0,$rom,0x149400,$helper.Length)

$rom[0x18E]=0;$rom[0x18F]=0;$sum=0
for($i=0x200;$i -lt $rom.Length-1;$i+=2){$sum=($sum+(([int]$rom[$i]*256)+[int]$rom[$i+1])) -band 0xFFFF}
$rom[0x18E]=[byte](($sum -shr 8) -band 0xFF);$rom[0x18F]=[byte]($sum -band 0xFF)
[IO.File]::WriteAllBytes($outputPath,$rom)
$report=[ordered]@{source=$sourcePath;source_sha256=$expected;output=$outputPath;output_sha256=(Get-FileHash -Algorithm SHA256 $outputPath).Hash;size=$rom.Length;checksum=('0x{0:X4}'-f$sum);helper_length=$helper.Length;fix='pregame country renderer traced exact-record-pattern mapping'}
$report|ConvertTo-Json|Set-Content -Encoding utf8 "$outputPath.build.json";$report|ConvertTo-Json
