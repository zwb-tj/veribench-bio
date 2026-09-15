$ErrorActionPreference='Stop'
# Self-locate to this script's own directory.
# (Do NOT hardcode an absolute path: that makes the script runnable
#  only on the author's machine, and leaks their directory layout.)
$dir = $PSScriptRoot
$base='https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=clinvar&retmode=json&term='
function C($t){
  for($i=1;$i -le 3;$i++){
    try{ return [int](Invoke-RestMethod -Uri ($base+[uri]::EscapeDataString($t)) -TimeoutSec 60).esearchresult.count }
    catch{ Start-Sleep -Seconds 2 }
  }
  return -1
}
$cs = Get-Content "$dir\cspec_svis.json" -Raw | ConvertFrom-Json
$v  = Get-Content "$dir\clingen_validity.json" -Raw | ConvertFrom-Json
$DS=New-Object System.Collections.Generic.HashSet[string]
foreach($row in $v.rows){ if($row.classification -in 'Definitive','Strong'){ [void]$DS.Add($row.symbol) } }
$genes=@{}
foreach($s in $cs.data){ $rel = ($s.status -in 'Released','Approved For Release')
  foreach($rs in $s.ruleSets){ foreach($g in $rs.genes){ $sym=($g.'@id' -split 'query=')[-1]; if($sym){ $genes[$sym]=$rel } } } }

$yrs='("2024"[CLINSIG_LAST_CHANGED] OR "2025"[CLINSIG_LAST_CHANGED] OR "2026"[CLINSIG_LAST_CHANGED])'
$conf='"criteria provided, conflicting classifications"[Review Status]'
$ep3='"reviewed by expert panel"[Review Status]'
$rows=@()
$n=0
foreach($g in ($genes.Keys | Sort-Object)){
  $n++
  $c3 = C ("$g[gene] AND $ep3 AND $yrs")
  Start-Sleep -Milliseconds 380
  $cc = C ("$g[gene] AND $conf AND $yrs")
  Start-Sleep -Milliseconds 380
  $rows += [pscustomobject]@{gene=$g; released=$genes[$g]; defstrong=$DS.Contains($g); three_star=$c3; one_star_conflicting=$cc}
  if($n % 20 -eq 0){ Write-Host "  ...$n genes" }
}
$rows | Export-Csv "$dir\pergene_counts.csv" -NoTypeInformation -Encoding UTF8
"queried genes: $($rows.Count)"
""
"=== per-gene cross-check (may double-count multi-gene variants) ==="
"3-star 2024-2026, sum over CSpec genes (all)        = $(($rows | Measure-Object three_star -Sum).Sum)"
"1-star conflicting 2024-2026, sum over CSpec genes   = $(($rows | Measure-Object one_star_conflicting -Sum).Sum)"
$r2 = $rows | Where-Object { $_.defstrong }
"  ...restricted to Definitive/Strong genes          = $(($r2 | Measure-Object one_star_conflicting -Sum).Sum)"
$r3 = $rows | Where-Object { $_.released -and $_.defstrong }
"  ...restricted to Released+Def/Strong genes        = $(($r3 | Measure-Object one_star_conflicting -Sum).Sum)"
""
"--- top 20 genes by 1-star conflicting count ---"
$rows | Sort-Object one_star_conflicting -Descending | Select-Object -First 20 | ForEach-Object { "  {0,7}  {1}" -f $_.one_star_conflicting,$_.gene }
