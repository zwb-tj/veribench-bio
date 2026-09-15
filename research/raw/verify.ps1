$ErrorActionPreference='Stop'
# Self-locate to this script's own directory.
# (Do NOT hardcode an absolute path: that makes the script runnable
#  only on the author's machine, and leaks their directory layout.)
$dir = $PSScriptRoot

# ---------- EREPO ----------
$sr = New-Object System.IO.StreamReader("$dir\erepo_classifications.csv")
$null = $sr.ReadLine()
$erepoAll = New-Object System.Collections.Generic.HashSet[string]
$erepoMet = New-Object System.Collections.Generic.HashSet[string]
while(($line=$sr.ReadLine()) -ne $null){
  if([string]::IsNullOrWhiteSpace($line)){continue}
  $p = $line -split "`t"; if($p.Count -lt 20){continue}
  $v = $p[1].Trim(); if(-not $v){continue}
  [void]$erepoAll.Add($v)
  if($p[9].Trim() -and $p[17].Trim() -ne 'true'){ [void]$erepoMet.Add($v) }
}
$sr.Close()

# ---------- CSpec ----------
$cs = Get-Content "$dir\cspec_svis.json" -Raw | ConvertFrom-Json
$csAll=@{}; $csRel=@{}
foreach($s in $cs.data){
  $st = $s.status
  foreach($rs in $s.ruleSets){
    foreach($g in $rs.genes){
      $sym = ($g.'@id' -split 'query=')[-1]
      if(-not $sym){continue}
      $csAll[$sym] = $st
      if($st -eq 'Released' -or $st -eq 'Approved For Release'){ $csRel[$sym] = $st }
    }
  }
}
"CSpec distinct genes (all statuses) = $($csAll.Count)"
"CSpec distinct genes (Released+Approved) = $($csRel.Count)"

# ---------- ClinGen validity ----------
$v = Get-Content "$dir\clingen_validity.json" -Raw | ConvertFrom-Json
$DS=New-Object System.Collections.Generic.HashSet[string]
foreach($row in $v.rows){ if($row.classification -eq 'Definitive' -or $row.classification -eq 'Strong'){ [void]$DS.Add($row.symbol) } }
"ClinGen genes with >=1 Definitive/Strong = $($DS.Count)"

# ---------- step1 ----------
$recs = Get-Content "$dir\step1_records.json" -Raw | ConvertFrom-Json
$gseen=New-Object System.Collections.Generic.HashSet[string]
foreach($r in $recs){ foreach($g in $r.genes){ if($g.symbol){[void]$gseen.Add($g.symbol)} } }
"step1 distinct genes = $($gseen.Count)"
$inCs = @($gseen | Where-Object { $csAll.ContainsKey($_) })
$inCsRel = @($gseen | Where-Object { $csRel.ContainsKey($_) })
"step1 genes in CSpec-all      = $($inCs.Count)"
"step1 genes in CSpec-Released = $($inCsRel.Count)"
"step1 genes in CSpec-all AND Def/Strong = $(@($inCs | Where-Object { $DS.Contains($_) }).Count)"
"step1 genes NOT in CSpec-all = $(@($gseen | Where-Object { -not $csAll.ContainsKey($_) }).Count)"

# ---------- funnel ----------
$c = [ordered]@{S1=0;S2=0;S3=0;S4=0;S5=0}
$g2=New-Object System.Collections.Generic.HashSet[string]
$g3=New-Object System.Collections.Generic.HashSet[string]
$g4=New-Object System.Collections.Generic.HashSet[string]
$g5=New-Object System.Collections.Generic.HashSet[string]
foreach($r in $recs){
  $c.S1++
  $syms=@($r.genes | ForEach-Object {$_.symbol})
  $hasCs  = @($syms | Where-Object { $csAll.ContainsKey($_) }).Count -gt 0
  if(-not $hasCs){continue}
  $c.S2++; foreach($x in $syms){[void]$g2.Add($x)}
  $hasDS  = @($syms | Where-Object { $DS.Contains($_) }).Count -gt 0
  if(-not $hasDS){continue}
  $c.S3++; foreach($x in $syms){[void]$g3.Add($x)}
  $hasRel = @($syms | Where-Object { $csRel.ContainsKey($_) }).Count -gt 0
  if(-not $hasRel){continue}
  $c.S4++; foreach($x in $syms){[void]$g4.Add($x)}
  if(-not $erepoMet.Contains([string]$r.uid)){continue}
  $c.S5++; foreach($x in $syms){[void]$g5.Add($x)}
}
""
"================ FINAL FUNNEL ================"
"S1 3-star + CLINSIG_LAST_CHANGED 2024-2026            : $($c.S1)"
"S2 + gene in CSpec VCEP scope                         : $($c.S2)   (genes touched=$($g2.Count))"
"S3 + gene-disease validity Definitive/Strong          : $($c.S3)   (genes touched=$($g3.Count))"
"S4 + VCEP criteria spec Released/Approved             : $($c.S4)   (genes touched=$($g4.Count))"
"S5 + variant in ClinGen EREPO w/ public Met/NotMet    : $($c.S5)   (genes touched=$($g5.Count))"
""
"--- per-year union cross-check (2025-2026 slice) ---"
$u25=New-Object System.Collections.Generic.HashSet[string]
foreach($id in ($recs | Where-Object { $_.accession_version })){ }
"not recomputed here; see count log"
"--- S5 classification split ---"
$s5 = $recs | Where-Object { $erepoMet.Contains([string]$_.uid) }
$s5 | Group-Object { $_.germline_classification.description } | Sort-Object Count -Descending | ForEach-Object { "  {0,5}  {1}" -f $_.Count,$_.Name }
"  PLP_total = $(@($s5 | Where-Object { $_.germline_classification.description -like 'Pathogenic*' -or $_.germline_classification.description -like 'Likely pathogenic*' }).Count)"
"  VUS_total = $(@($s5 | Where-Object { $_.germline_classification.description -like 'Uncertain*' }).Count)"
"  BLB_total = $(@($s5 | Where-Object { $_.germline_classification.description -like 'Benign*' -or $_.germline_classification.description -like 'Likely benign*' }).Count)"
""
"--- top 15 genes in S5 ---"
$s5 | ForEach-Object { ($_.genes | ForEach-Object {$_.symbol}) -join '/' } | Group-Object | Sort-Object Count -Descending | Select-Object -First 15 | ForEach-Object { "  {0,5}  {1}" -f $_.Count,$_.Name }
