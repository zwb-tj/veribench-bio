$ErrorActionPreference='Stop'
# Self-locate to this script's own directory.
# (Do NOT hardcode an absolute path: that makes the script runnable
#  only on the author's machine, and leaks their directory layout.)
$dir = $PSScriptRoot
$f="$dir\erepo_classifications.csv"

# --- load EREPO id sets ---
$sr = New-Object System.IO.StreamReader($f)
$cols = $sr.ReadLine() -split "`t"
$iId=1; $iMet=9; $iRetr=17; $iPub=16
$ids = New-Object System.Collections.Generic.HashSet[string]
$idsMet = New-Object System.Collections.Generic.HashSet[string]
while(($line = $sr.ReadLine()) -ne $null){
  if([string]::IsNullOrWhiteSpace($line)){continue}
  $p = $line -split "`t"
  if($p.Count -lt 20){continue}
  $v=$p[$iId].Trim(); if(-not $v){continue}
  [void]$ids.Add($v)
  if($p[$iMet].Trim() -and $p[$iRetr].Trim() -ne 'true'){ [void]$idsMet.Add($v) }
}
$sr.Close()
"ERE PO distinct VarIds = $($ids.Count) ; with Met codes = $($idsMet.Count)"

# --- verify uid semantics via known GJB2 variant (ClinVar VariationID 17000) ---
$s = (Invoke-RestMethod -Uri "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=clinvar&retmode=json&id=17000" -TimeoutSec 60).result.'17000'
"UID 17000 -> accession=$($s.accession_version) title=$($s.title)"
"  measure_ids = $(($s.variation_set | ForEach-Object {$_.measure_id}) -join ',')"

# --- step1 record uids and measure_ids ---
$recs = Get-Content "$dir\step1_records.json" -Raw | ConvertFrom-Json
$uids=New-Object System.Collections.Generic.HashSet[string]
$mids=New-Object System.Collections.Generic.HashSet[string]
foreach($r in $recs){ [void]$uids.Add([string]$r.uid); foreach($vs in $r.variation_set){ if($vs.measure_id){[void]$mids.Add([string]$vs.measure_id)} } }
"step1 uids=$($uids.Count)  step1 measure_ids=$($mids.Count)"

# numeric-shape comparison
$erepoBig = @($ids | Where-Object { [int64]$_ -ge 1000000 }).Count
$erepoSmall = @($ids | Where-Object { [int64]$_ -lt 1000000 }).Count
"ERE PO ids: >=1e6 -> $erepoBig ; <1e6 -> $erepoSmall"
$uidBig = @($uids | Where-Object { [int64]$_ -ge 1000000 }).Count
$midBig = @($mids | Where-Object { [int64]$_ -ge 1000000 }).Count
"step1 uids >=1e6 -> $uidBig ; step1 measure_ids >=1e6 -> $midBig"

# --- intersections, both ways ---
$a = @($uids | Where-Object { $ids.Contains($_) }).Count
$b = @($uids | Where-Object { $idsMet.Contains($_) }).Count
$c = @($mids | Where-Object { $ids.Contains($_) }).Count
$d = @($mids | Where-Object { $idsMet.Contains($_) }).Count
"step1 UID  in EREPO(all)      = $a"
"step1 UID  in EREPO(with Met) = $b   <== correct set-F1 intersection"
"step1 MID  in EREPO(all)      = $c"
"step1 MID  in EREPO(with Met) = $d   <== what I computed before (WRONG)"

# --- rebuild final funnel using UID ---
$cs = Get-Content "$dir\cspec_svis.json" -Raw | ConvertFrom-Json
$v  = Get-Content "$dir\clingen_validity.json" -Raw | ConvertFrom-Json
$csAll=New-Object System.Collections.Generic.HashSet[string]; $csRel=New-Object System.Collections.Generic.HashSet[string]
foreach($x in $cs.data){ foreach($rs in $x.ruleSets){ foreach($g in $rs.genes){ $sym=($g.'@id' -split 'query=')[-1]
  if($sym){[void]$csAll.Add($sym); if($x.status -in 'Released','Approved For Release'){[void]$csRel.Add($sym)}} } } }
$DS=New-Object System.Collections.Generic.HashSet[string]
foreach($row in $v.rows){ if($row.classification -in 'Definitive','Strong'){ [void]$DS.Add($row.symbol) } }

$s2=@(); $s3=@(); $s4=@(); $s5=@()
foreach($r in $recs){
  $gs=@($r.genes | ForEach-Object {$_.symbol})
  if(@($gs | Where-Object {$csAll.Contains($_)}).Count -eq 0){continue}
  $s2 += $r
  if(@($gs | Where-Object {$DS.Contains($_)}).Count -eq 0){continue}
  $s3 += $r
  if(@($gs | Where-Object {$csRel.Contains($_)}).Count -eq 0){continue}
  $s4 += $r
  if($idsMet.Contains([string]$r.uid)){ $s5 += $r }
}
""
"=== CORRECTED FUNNEL ==="
"S1 3-star & CLINSIG_LAST_CHANGED 2024-2026            : 3825   genes=207"
"S2 + gene in CSpec VCEP scope                          : $($s2.Count)   genes=$((@($s2|%{$_.genes|%{$_.symbol}})|Sort-Object -Unique).Count)"
"S3 + gene-disease validity Definitive or Strong        : $($s3.Count)   genes=$((@($s3|%{$_.genes|%{$_.symbol}})|Sort-Object -Unique).Count)"
"S4 + VCEP criteria spec publicly Released              : $($s4.Count)   genes=$((@($s4|%{$_.genes|%{$_.symbol}})|Sort-Object -Unique).Count)"
"S5 + variant in ClinGen EREPO with public Met/NotMet codes (set-F1 ready): $($s5.Count)   genes=$((@($s5|%{$_.genes|%{$_.symbol}})|Sort-Object -Unique).Count)"
""
"--- S5 by classification ---"
$s5 | Group-Object {$_.germline_classification.description} | Sort-Object Count -Descending | ForEach-Object { "  {0,5}  {1}" -f $_.Count,$_.Name }
"--- S5 by gene ---"
$s5 | Group-Object {($_.genes | ForEach-Object {$_.symbol}) -join '/'} | Sort-Object Count -Descending | ForEach-Object { "  {0,5}  {1}" -f $_.Count,$_.Name }
"--- S5 P/LP only : $(@($s5 | Where-Object {$_.germline_classification.description -like 'Pathogenic*' -or $_.germline_classification.description -like 'Likely pathogenic*'}).Count)"
$s5 | ForEach-Object { [pscustomobject]@{uid=$_.uid; accession=$_.accession_version; gene=(($_.genes|%{$_.symbol}) -join '/'); cls=$_.germline_classification.description; title=$_.title} } | Export-Csv "$dir\funnel_S5_setF1_ready.csv" -NoTypeInformation -Encoding UTF8
"wrote funnel_S5_setF1_ready.csv"
