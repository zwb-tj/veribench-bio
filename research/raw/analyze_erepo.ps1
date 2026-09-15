$ErrorActionPreference='Stop'
# Self-locate to this script's own directory.
# (Do NOT hardcode an absolute path: that makes the script runnable
#  only on the author's machine, and leaks their directory layout.)
$dir = $PSScriptRoot
$f="$dir\erepo_classifications.csv"

# --- EREPO: read, detect delimiter, aggregate ---
$sr = New-Object System.IO.StreamReader($f)
$header = $sr.ReadLine()
$delim = if($header.Contains("`t")){"`t"}else{","}
$cols = $header -split $delim
"ERE PO delimiter = $(if($delim -eq "`t"){'TAB'}else{'COMMA'})   ncols=$($cols.Count)"
for($i=0;$i -lt $cols.Count;$i++){ "  col[$i] = $($cols[$i])" }

$idxVarId = [array]::IndexOf($cols,'ClinVar Variation Id')
$idxGene  = [array]::IndexOf($cols,'HGNC Gene Symbol')
$idxMet   = [array]::IndexOf($cols,'Applied Evidence Codes (Met)')
$idxNot   = [array]::IndexOf($cols,'Applied Evidence Codes (Not Met)')
$idxAssert= [array]::IndexOf($cols,'Assertion')
$idxEP    = [array]::IndexOf($cols,'Expert Panel')
$idxPub   = [array]::IndexOf($cols,'Published Date')
$idxRetr  = [array]::IndexOf($cols,'Retracted')

$total=0; $withId=0; $withMet=0
$erepoIds = New-Object System.Collections.Generic.HashSet[string]
$erepoIdMet = New-Object System.Collections.Generic.HashSet[string]
$byYear=@{}
$assert=@{}
$line=$null
while(($line = $sr.ReadLine()) -ne $null){
  if([string]::IsNullOrWhiteSpace($line)){continue}
  $p = $line -split $delim
  if($p.Count -lt $cols.Count){continue}
  $total++
  $vid = $p[$idxVarId].Trim()
  $met = $p[$idxMet].Trim()
  $retr = $p[$idxRetr].Trim()
  $a = $p[$idxAssert].Trim()
  if($a){ if($assert.ContainsKey($a)){$assert[$a]++}else{$assert[$a]=1} }
  $pd = $p[$idxPub].Trim(); $yr = if($pd.Length -ge 4){$pd.Substring(0,4)}else{'?'}
  if($byYear.ContainsKey($yr)){$byYear[$yr]++}else{$byYear[$yr]=1}
  if($vid){
    $withId++
    [void]$erepoIds.Add($vid)
    if($met -and $retr -ne 'true'){ $withMet++; [void]$erepoIdMet.Add($vid) }
  }
}
$sr.Close()
"ERE PO rows total          = $total"
"  rows with ClinVar VarId  = $withId"
"  distinct ClinVar VarIds  = $($erepoIds.Count)"
"  distinct VarIds w/ Met codes & not retracted = $($erepoIdMet.Count)   (rows=$withMet)"
"--- EREPO published-year distribution ---"
$byYear.GetEnumerator() | Sort-Object Name | ForEach-Object { "  {0}  {1}" -f $_.Name,$_.Value }
"--- EREPO assertion distribution ---"
$assert.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "  {0,6}  {1}" -f $_.Value,$_.Key }

# --- step1 records -> measure_ids ---
$recs = Get-Content "$dir\step1_records.json" -Raw | ConvertFrom-Json
$uidToMid=@{}
foreach($r in $recs){
  $mids=@()
  foreach($vs in $r.variation_set){ if($vs.measure_id){ $mids += $vs.measure_id } }
  $uidToMid[$r.uid] = $mids
}
$allMids = New-Object System.Collections.Generic.HashSet[string]
foreach($k in $uidToMid.Keys){ foreach($m in $uidToMid[$k]){ [void]$allMids.Add($m) } }
"step1: $($recs.Count) VCV records -> $($allMids.Count) distinct VariationIDs"

# --- funnel sets from previous step (rebuild) ---
$cs = Get-Content "$dir\cspec_svis.json" -Raw | ConvertFrom-Json
$v  = Get-Content "$dir\clingen_validity.json" -Raw | ConvertFrom-Json
$csAll=New-Object System.Collections.Generic.HashSet[string]; $csRel=New-Object System.Collections.Generic.HashSet[string]
foreach($s in $cs.data){ foreach($rs in $s.ruleSets){ foreach($g in $rs.genes){ $sym=($g.'@id' -split 'query=')[-1]
  if($sym){[void]$csAll.Add($sym); if($s.status -eq 'Released' -or $s.status -eq 'Approved For Release'){[void]$csRel.Add($sym)}} } } }
$DS=New-Object System.Collections.Generic.HashSet[string]
foreach($row in $v.rows){ if($row.classification -in 'Definitive','Strong'){ [void]$DS.Add($row.symbol) } }

function Classify($recs,$useRel){
  $csSet = if($useRel){$csRel}else{$csAll}
  $sub=@()
  foreach($r in $recs){
    $gs=@($r.genes | ForEach-Object {$_.symbol})
    if(@($gs | Where-Object {$csSet.Contains($_)}).Count -eq 0){continue}
    if(@($gs | Where-Object {$DS.Contains($_)}).Count -eq 0){continue}
    $mids=@($r.variation_set | ForEach-Object {$_.measure_id})
    $hit = @($mids | Where-Object { $_ -and $erepoIdMet.Contains($_) }).Count -gt 0
    $sub += [pscustomobject]@{uid=$r.uid; genes=($gs -join '/'); cls=$r.germline_classification.description; mids=($mids -join ';'); erepo=$hit}
  }
  $sub
}
$s4 = Classify $recs $true
$s4e = $s4 | Where-Object {$_.erepo}
""
"=== FINAL FUNNEL (records) ==="
"S1 3-star & last_changed 2024-2026            : 3825"
"S2 + gene in CSpec VCEP scope                 : $(@($recs | Where-Object { $g=@($_.genes|%{$_.symbol}); @($g|?{$csAll.Contains($_)}).Count -gt 0 }).Count)"
"S3 + gene-disease validity Definitive/Strong  : $($s4.Count + 0)  [same gene filter, before Released]"
"S4 + CSpec publicly Released                  : $($s4.Count)"
"S5 + variant has PUBLIC ACMG criteria codes in ClinGen EREPO (set-F1 ready) : $(@($s4e).Count)"
""
"--- S5 by classification ---"
$s4e | Group-Object cls | Sort-Object Count -Descending | ForEach-Object { "  {0,5}  {1}" -f $_.Count,$_.Name }
"--- S5 by gene (top 25) ---"
$s4e | Group-Object genes | Sort-Object Count -Descending | Select-Object -First 25 | ForEach-Object { "  {0,5}  {1}" -f $_.Count,$_.Name }
"--- S4 but NOT in EREPO (criteria not public) : $(@($s4 | Where-Object {-not $_.erepo}).Count)"
$s4e | Export-Csv "$dir\funnel_S5_setF1_ready.csv" -NoTypeInformation -Encoding UTF8
"wrote funnel_S5_setF1_ready.csv"
