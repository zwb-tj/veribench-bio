# gnomAD Bulk Data License — Findings

**Research question:** What is the ACTUAL data license / terms of use for gnomAD (Genome Aggregation Database, gnomad.broadinstitute.org) bulk data downloads?

**Researcher:** data-licensing research subagent
**Access date for all URLs below:** 2026-09-10 (approximate; single session)
**Tooling:** `web_search`, `web_fetch`, PowerShell `Invoke-WebRequest`

---

## 1. Verdict

# **IN WHITELIST**

The gnomAD Terms of Use — obtained as **primary source text** from both the gnomAD browser source repository and, independently, from the JavaScript bundle actually served by the live `gnomad.broadinstitute.org` website — state verbatim that the primary data are released under **CC0 1.0 Universal (Public Domain Dedication)**:

> "The primary data from the gnomAD exomes and genomes are available free of restrictions under the [Creative Commons Zero Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/). This means that you can use it for any purpose without legally having to give attribution."

CC0 is on the whitelist (CC0 / CC BY / public domain), so the **core gnomAD summary data qualifies as IN WHITELIST**.

### ⚠️ Mandatory caveats (read before relying on this verdict)

These do **not** change the core verdict, but they are real scoping conditions that a strict "CC0/CC-BY/public-domain only" whitelist must handle explicitly:

1. **Some annotation fields are NOT CC0.** The same primary terms page states that SpliceAI annotations are **CC BY-NC 4.0** (non-commercial). If the whitelist truly admits *only* CC0/CC BY/public-domain content, any gnomAD file/download that **bundles SpliceAI annotation columns must be excluded or those columns stripped**. This is a genuine partial exclusion scoped to specific annotation fields, not to the allele-frequency data.
2. **A no-reidentification condition is imposed on users.** "All users of gnomAD data agree to not attempt to reidentify participants." This is an ethical use condition, not a copyright/redistribution restriction. It does not block redistribution or commercial use, so it does not defeat CC0 status — but it is a term, and it should be recorded.
3. **Trademark / naming restriction.** Users are asked not to put "gnomAD"/"Genome Aggregation Database" in a tool's name or use the gnomAD logo without permission; gnomAD™ is a Broad Institute trademark. This restricts **branding/naming**, not data use or redistribution.
4. **The GitHub repository LICENSE files are MIT / BSD-3-Clause and apply to the SOFTWARE, not the data.** Do not cite the MIT license in `gnomad-browser` or `gnomad_methods` as the data license. (The AWS registry conflates these — see §2 secondary rows.)

---

## 2. Verbatim evidence table

| # | Source URL | Access date | Exact quoted text | Primary / Secondary |
|---|---|---|---|---|
| E1 | https://raw.githubusercontent.com/broadinstitute/gnomad-browser/86cc268b6ef6638a631cf53aae591987c2ac9a2d/browser/about/policies/terms.md (pinned commit; identical to `.../main/browser/about/policies/terms.md`) | 2026-09-10 | "The primary data from the gnomAD exomes and genomes are available free of restrictions under the [Creative Commons Zero Public Domain Dedication](https://creativecommons.org/publicdomain/zero/1.0/). This means that you can use it for any purpose without legally having to give attribution. However, we request that you actively acknowledge and give attribution to the gnomAD project, and link back to the relevant page, wherever possible. Attribution supports future efforts to release other data. It also reduces the amount of "orphaned data", helping retain links to authoritative sources." | **PRIMARY** — this file *is* the `termsContent` rendered by the site (see E4) |
| E2 | same file as E1 | 2026-09-10 | "All data here are released openly and publicly for the benefit of the wider biomedical community. You can freely download and search the data, and we encourage the use and publication of results generated from these data. **There are absolutely no restrictions or embargoes on the publication of results derived from gnomAD data**. However, we encourage you to [contact the consortium](mailto:gnomad@broadinstitute.org) before embarking on large-scale analyses to check if your proposed analysis overlaps with work currently underway by the gnomAD consortium. All users of gnomAD data agree to not attempt to reidentify participants." | **PRIMARY** |
| E3 | same file as E1 | 2026-09-10 | "Some annotations may have restrictions on usage. For instance, SpliceAI annotations have been computed by Illumina and are provided with permission under a CC BY NC 4.0 license for academic and non-commercial use [SpliceAI](https://github.com/Illumina/SpliceAI). It is the responsibility of users to abide by all relevant licensing requirements." | **PRIMARY** — the origin of caveat 1 |
| E3b | same file as E1 | 2026-09-10 | "Screenshots of the website may also be used without restriction. As with any use of gnomAD data, we request that you actively acknowledge and give attribution to the gnomAD project, and link back to the relevant page, wherever possible." | **PRIMARY** |
| E3c | same file as E1 | 2026-09-10 | "We request that developers integrating gnomAD data in their tools include a statement acknowledging the inclusion of gnomAD data (e.g., "This tool includes data from the gnomAD v4.1 release."). However, to avoid confusion and misattribution, we ask that you refrain from incorporating "gnomAD" or "Genome Aggregation Database'' into the name of your tool and from using the gnomAD logo without permission. gnomAD™ is a trademark owned by The Broad Institute, Inc." | **PRIMARY** — trademark clause, caveat 3 |
| E3d | same file as E1 | 2026-09-10 | Section heading: `## gnomAD™ Terms of use` | **PRIMARY** |
| E4 | https://gnomad.broadinstitute.org/js/190-883ccd4d11eceb0362e0.js (the live deployed chunk that renders the Policies page) | 2026-09-10 | Rendered HTML contains verbatim: `<h2>gnomAD™ Terms of use</h2>` … `<p>All data here are released openly and publicly for the benefit of the wider biomedical community…</p>` … `<p>The primary data from the gnomAD exomes and genomes are available free of restrictions under the <a href="https://creativecommons.org/publicdomain/zero/1.0/" target="_blank" rel="noopener noreferrer">Creative Commons Zero Public Domain Dedication</a>. This means that you can use it for any purpose without legally having to give attribution…</p>` | **PRIMARY (live site)** — independent confirmation that the *deployed* website serves exactly E1's text |
| E5 | https://raw.githubusercontent.com/broadinstitute/gnomad-browser/main/browser/src/PoliciesPage.tsx | 2026-09-10 | `import termsContent from '../about/policies/terms.md'` … `<MarkdownContent dangerouslySetInnerHTML={{ __html: termsContent.html }} />` | **PRIMARY** — proves the mapping from `terms.md` to the rendered Policies page |
| E6 | https://raw.githubusercontent.com/broadinstitute/gnomad-browser/main/browser/src/Routes.tsx | 2026-09-10 | `<Redirect from="/terms" to="/policies" />` and `<Route exact path="/policies" component={PoliciesPage} />` | **PRIMARY** — proves `/terms` redirects to `/policies`, so the canonical URL for the terms is **https://gnomad.broadinstitute.org/policies** |
| E7 | https://raw.githubusercontent.com/broadinstitute/gnomad-browser/main/LICENSE | 2026-09-10 | "MIT License / Copyright © 2017 Broad Institute and gnomAD Browser contributors" (full MIT text, 1102 bytes) | **PRIMARY but NOT the data license** — software license for the browser code only |
| E8 | https://raw.githubusercontent.com/broadinstitute/gnomad_methods/master/LICENSE | 2026-09-10 | "MIT License / Copyright (c) 2019 Konrad Karczewski, Laurent Francioli, Grace Tiao, Daniel MacArthur" | **PRIMARY but NOT the data license** — software license for the Python library |
| E9 | https://raw.githubusercontent.com/broadinstitute/gnomad_qc/main/LICENSE | 2026-09-10 | "BSD 3-Clause License / Copyright (c) 2022, Broad Institute of MIT and Harvard; Mass General Brigham" | **PRIMARY but NOT the data license** — software license for QC code |
| E10 | https://registry.opendata.aws/broad-gnomad/ | 2026-09-10 | "The summary data provided here are released for the benefit of the wider scientific community without restriction on use." | **SECONDARY / SECOND-HAND** (AWS-run registry, submitter-supplied description). Corroborates E1/E2 but is not the gnomAD terms themselves. |
| E11 | https://registry.opendata.aws/broad-gnomad/ | 2026-09-10 | License field reads: "MIT; terms of use" linking to `https://github.com/broadinstitute/gnomad_methods/blob/master/LICENSE` and `https://gnomad.broadinstitute.org/terms` | **SECONDARY / SECOND-HAND and MISLEADING** — the "MIT" here points at the *gnomad_methods software* license, not the data. Do not treat this as the data license. |
| E12 | https://raw.githubusercontent.com/awslabs/open-data-registry/main/datasets/broad-gnomad.yaml | 2026-09-10 | `License: "[MIT](https://github.com/broadinstitute/gnomad_methods/blob/master/LICENSE); [terms of use](https://gnomad.broadinstitute.org/terms)"` | **SECONDARY** — upstream YAML behind E10/E11; same software/data conflation |
| E13 | https://gnomad.broadinstitute.org/about | 2026-09-10 | (from repo `browser/about/about.md`, same route) "The full gnomAD datasets are released publicly via [download](/downloads) for the benefit of the wider biomedical community. For terms of use and other policies please see our [policy page](/policies)." | **PRIMARY** — confirms `/policies` is the normative terms location |
| E14 | https://gnomad.broadinstitute.org/news/2022-08-update-policies-page/ | 2026-09-10 | "The policies page, previously titled 'terms', has been updated to cover additional policies. New policies include, but are not limited to, data privacy, ethics, and open science." | **PRIMARY** — explains the `/terms` → `/policies` rename |
| E15 | https://raw.githubusercontent.com/broadinstitute/gnomad-browser/main/browser/help/faq/general/what-are-the-restrictions-on-data-usage.md | 2026-09-10 | "Please see our terms of use and other policies on our [policy page](/policies)." | **PRIMARY** — the FAQ defers to `/policies`; no independent license text |
| E16 | https://github.com/broadinstitute/gnomad-browser/commit/47d02a2883388273b99de5865fbadfdd5ff72120.patch | 2026-09-10 | `browser/about/policies/policies.md \| 2 +-` … "However, we ask that you refrain from using the name "gnomAD"/"Genome Aggregation Database" or the gnomAD logo without permission." | **PRIMARY** — shows the name/logo clause lineage (now lives in `terms.md` per E3c) |

### Distinction summary
- **PRIMARY (normative data-license text):** E1, E2, E3, E3b, E3c, E3d, E4 (deployed artifact), plus provenance proof E5, E6, E13, E14, E15, E16.
- **PRIMARY but software-only (do not use as data license):** E7, E8, E9.
- **SECONDARY / second-hand:** E10, E11, E12.

---

## 3. Routes tried and what each returned

| Route | Attempt | Result |
|---|---|---|
| 1a | `raw.githubusercontent.com/.../gnomad-browser/{main,master}/LICENSE` | **HTTP 200, MIT License (1102 bytes)** — software license only, says nothing about data |
| 1b | `.../main/LICENSE.md`, `.../main/LICENSE.txt` | HTTP 404 |
| 1c | `.../main/README.md` | HTTP 200 — README says "Licensed under the MIT license" and, critically, points to **"gnomAD Terms and Data Information" at `https://gnomad.broadinstitute.org/terms`** for *dataset citation/data* info. This is the lead that cracked the problem. |
| 1d | `gnomad_methods` / `gnomad_qc` LICENSE | MIT / BSD-3-Clause — software only |
| 1e | GitHub REST API (`/git/trees`, `/commits?path=...`, `/contents`) | **HTTP 403 on every call** — unauthenticated IP rate limit. Worked around via jsDelivr and the Atom feed. |
| 1f | **jsDelivr package API** (`data.jsdelivr.com/v1/packages/gh/broadinstitute/gnomad-browser@main?structure=flat`) | **HTTP 200 — full file listing (49 chunks + all source).** This is how `browser/about/policies/terms.md` was discovered. Highly effective GitHub-API substitute. |
| 1g | `raw.githubusercontent.com/.../browser/about/policies/terms.md` | **HTTP 200 — the primary terms text (3005 bytes). SUCCESS.** |
| 1h | `.../browser/about/about.md`, `.../browser/help/faq/general/what-are-the-restrictions-on-data-usage.md` | HTTP 200 — corroborating, defer to `/policies` |
| 2a | `Invoke-WebRequest https://gnomad.broadinstitute.org/policies`, `/terms`, `/about`, `/faq`, `/downloads` | **HTTP 200 but only the SPA shell** (~8.9 KB of `<div id="root">` and asset links, **zero policy text**). Confirms the original failure mode. Also **HTTP 429** on rapid successive requests — the site rate-limits; needs pacing. |
| 2b | Extract deployed JS bundles from the live HTML | Found `/js/bundle-747369138fd0dac372aa.js` (677,824 bytes) + webpack chunk map `o.u = e => "js/"+e+"-"+{...}[e]+".js"`, 49 chunks |
| 2c | Grep main bundle for policy text | Not present — `PoliciesPage` is `lazy()`-loaded into a separate chunk |
| 2d | **Download all 49 chunks, grep for "Creative Commons Zero"** | **HIT on `https://gnomad.broadinstitute.org/js/190-883ccd4d11eceb0362e0.js` (12,312 bytes).** Verbatim CC0 sentence recovered from the *live deployed site*. Many chunks returned 429 (rate limiting); the hit was found early, so coverage was sufficient. **SUCCESS — independent confirmation of E1.** |
| 2e | Broad Institute Terms of Use | Not needed — gnomAD has its own operative terms; not pursued further once primary text was found |
| 2f | Site source maps / static content / JSON API | Not needed — the compiled chunk (2d) already yielded the authoritative text. **No separate public JSON API for policy text exists**; the text is build-time-compiled markdown |
| 3 | `https://registry.opendata.aws/broad-gnomad/` | HTTP 200 — "released … **without restriction on use**"; License field "MIT; terms of use". **SECONDARY.** Also retrieved the upstream YAML E12 |
| 4 | gnomAD news post `2022-08-update-policies-page` | HTTP 200 — documents `/terms` → `/policies` rename; no license text itself |
| 5 | Verbatim original wording hunt | **SUCCESS — see E1/E2/E3/E4.** The actual wording is CC0, *not* CC BY 4.0 and *not* a redistribution ban. There is no embargo/redistribution restriction on the primary data |
| 6 | Nature release papers, data-availability statements | **NOT OBTAINED.** Europe PMC confirmed the v4 paper (Chen et al., *Nature* 625:92–100, 2024; PMID 38057664, PMCID PMC11629659) with `isOpenAccess: "N"`, `inEPMC: "Y"`. `.../PMC11629659/fullTextXML` → **HTTP 404**. `pmc.ncbi.nlm.nih.gov/articles/PMC11629659/` → **reCAPTCHA interstitial**. nature.com paywalled. Data-availability text therefore **unverified** (see §4) |
| 7 | Reachability as JSON / source maps / static files | Answered: **no JSON API**; text is markdown compiled into a lazy JS chunk. Reachable via (a) raw markdown in the repo and (b) the deployed chunk — both obtained |
| — | Wayback Machine (`archive.org/wayback/available`) | **HTTP 429** on both `/terms` and `/policies` — not obtained, but unnecessary given 2d |
| — | Pinned commit SHA | **Obtained via the Atom feed** `github.com/broadinstitute/gnomad-browser/commits/main/browser/about/policies/terms.md.atom`. Latest commit touching `terms.md`: **`86cc268b6ef6638a631cf53aae591987c2ac9a2d`** (2026-05-20T18:31:38Z). Verified: pinned raw URL is **byte-identical** to `main` (both 3005 bytes) |

### Key methodological finding
The gnomAD terms are **not** behind a JS-redaction problem in the usual sense — the text is **plain markdown committed to the public repo**, which is then compiled into a webpack chunk. Two independent routes therefore exist and both were exercised:

1. **Source route:** `browser/about/policies/terms.md` in `broadinstitute/gnomad-browser`.
2. **Deployed route:** chunk `js/190-883ccd4d11eceb0362e0.js` served by the live site.

Both yield the **same** CC0 text.

### Local evidence artifacts saved
（路径相对仓库根 `bio-eval/`）
- `research/raw/gnomad_terms.md.pinned-86cc268.txt` — verbatim terms text at the pinned commit
- `research/raw/gnomad_terms.md.main.txt` — verbatim terms text at `main` (byte-identical to pinned)
- `research/raw/gnomad_deployed_policies_chunk_excerpt.txt` — 3,000-char excerpt of the **deployed** JS chunk around the CC0 sentence

---

## 4. What could NOT be verified + reproduction instructions

### 4.1 NOT verified

1. **The Nature release papers' data-availability statements.** All three routes failed (Europe PMC full-text XML 404 because `isOpenAccess=N`; PMC HTML reCAPTCHA-gated; nature.com paywalled). The verdict therefore rests on gnomAD/Broad's own terms page, **not** on a peer-reviewed data-availability statement. This is acceptable because the terms page is the operative, normative document — but it means **no journal-level corroboration exists in this report.**
2. **The exact live HTML of `/policies` as a rendered DOM.** The site is a client-rendered SPA; no headless browser was available. Instead, the **deployed JS chunk** containing the compiled page content was retrieved and quoted (E4). This is a faithful and arguably stronger artifact than screenshotting the rendered DOM, but it is not literally "the page as a browser paints it."
3. **Whether every single gnomAD download file is free of NC-licensed annotations.** E3 proves that *some* annotations carry restrictions, naming SpliceAI/CC BY-NC 4.0 as an example ("For instance…", implying a non-exhaustive list). **Which specific files/columns on the /downloads page embed SpliceAI was NOT determined.** Per-file column inspection is required before a strict-whitelist ingestion.
4. **A pinned SHA for `policies.md`, `about.md`, or the downloads page.** Only `terms.md` was pinned (`86cc268…`).
5. **Archived snapshots** (Wayback) for change-over-time analysis — rate-limited, not obtained.
6. **Whether the pre-2022 `/terms` page differed materially** in license wording. The 2022 news post (E14) implies the page was reorganized; the CC0 claim's start date was **not** established. Only *current* terms were verified.

### 4.2 Step-by-step reproduction (anyone can follow)

**Fast path — get the normative text in under a minute (no browser, no JS):**

```powershell
# 1. Pinned, immutable primary source: the markdown that renders at /policies
Invoke-WebRequest -UseBasicParsing -Uri `
 'https://raw.githubusercontent.com/broadinstitute/gnomad-browser/86cc268b6ef6638a631cf53aae591987c2ac9a2d/browser/about/policies/terms.md' |
  Select-Object -ExpandProperty Content

# 2. Search the text for the operative license sentence
#    Expect: "available free of restrictions under the Creative Commons Zero Public Domain Dedication"
```

**Prove the mapping (that this file is what `/policies` renders):**

```powershell
# 3. Routes.tsx  -> /terms redirects to /policies
(Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/broadinstitute/gnomad-browser/main/browser/src/Routes.tsx').Content -split "`n" |
  Select-String 'terms|policies'
#    Expect: <Redirect from="/terms" to="/policies" />

# 4. PoliciesPage.tsx -> imports and renders terms.md
(Invoke-WebRequest -UseBasicParsing 'https://raw.githubusercontent.com/broadinstitute/gnomad-browser/main/browser/src/PoliciesPage.tsx').Content |
  Select-String 'termsContent|terms.md'
```

**Discover files when the GitHub API is rate-limited (403) — use jsDelivr:**

```powershell
# 5. Full recursive file listing of the repo, no auth, no rate limit
(Invoke-WebRequest -UseBasicParsing 'https://data.jsdelivr.com/v1/packages/gh/broadinstitute/gnomad-browser@main?structure=flat').Content |
  ConvertFrom-Json | Select-Object -ExpandProperty files |
  Where-Object { $_.name -match 'policies|terms|about' } | Select-Object name,size
```

**Verify against the LIVE deployed site (this is the step the previous attempt missed):**

```powershell
# 6. Fetch the SPA shell, extract the entry bundle and the webpack chunk map
$shell = (Invoke-WebRequest -UseBasicParsing -Headers @{'User-Agent'='Mozilla/5.0'} 'https://gnomad.broadinstitute.org/policies').Content
[regex]::Matches($shell,'src="([^"]*\.js)"') | ForEach-Object { $_.Groups[1].Value }
#    Expect something like: /js/bundle-<hash>.js

# 7. Download the entry bundle (NOTE: the site returns HTTP 429 if you hammer it - sleep between calls)
$b = (Invoke-WebRequest -UseBasicParsing -Headers @{'User-Agent'='Mozilla/5.0'} 'https://gnomad.broadinstitute.org/js/bundle-747369138fd0dac372aa.js').Content
#    The chunk map looks like: o.u=function(e){return"js/"+e+"-"+{61:"a4f2...",190:"883c...",...}[e]+".js"}

# 8. Extract the chunk map, then download chunks one at a time (SLEEP ~1s each) and grep
$map = [regex]::Match($b,'o\.u=function\(e\)\{return"js/"\+e\+"-"\+(\{.*?\})\[e\]\+"\.js"\}').Groups[1].Value
foreach($p in [regex]::Matches($map,'(\d+):"([0-9a-f]+)"')){
  $u = "https://gnomad.broadinstitute.org/js/$($p.Groups[1].Value)-$($p.Groups[2].Value).js"
  try {
    $c = (Invoke-WebRequest -UseBasicParsing -Headers @{'User-Agent'='Mozilla/5.0'} $u).Content
    if($c -match 'Creative Commons Zero'){ Write-Host "HIT: $u" }
  } catch { Write-Host "rate-limited/skip: $u" }
  Start-Sleep -Seconds 1   # <-- REQUIRED: site 429s without this
}
#    Verified hit as of 2026-09-10: https://gnomad.broadinstitute.org/js/190-883ccd4d11eceb0362e0.js
```

**Get commit history/SHAs without the rate-limited REST API (use the Atom feed):**

```powershell
# 9. Server-rendered Atom feed - lists commit SHAs touching a path
(Invoke-WebRequest -UseBasicParsing 'https://github.com/broadinstitute/gnomad-browser/commits/main/browser/about/policies/terms.md.atom').Content |
  Select-String -Pattern 'Grit::Commit/([0-9a-f]{40})' -AllMatches |
  ForEach-Object { $_.Matches.Groups[1].Value }
```

**Check the Nature papers (currently blocked — try these if you have access):**

```powershell
# 10. v4 paper: Chen et al., Nature 625:92-100 (2024); PMID 38057664; PMCID PMC11629659
#     Europe PMC REST metadata (worked): 
#       https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:%2210.1038/s41586-023-06045-0%22&resultType=core&format=json
#     Full-text XML (404'd for this article because isOpenAccess=N):
#       https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11629659/fullTextXML
#     PMC page (reCAPTCHA-gated in this session):
#       https://pmc.ncbi.nlm.nih.gov/articles/PMC11629659/
#     With institutional access, read the "Data availability" section of:
#       https://www.nature.com/articles/s41586-023-06045-0
#     Also relevant (v2 paper): https://www.nature.com/articles/s41586-020-2308-7
```

**Resolve caveat 3 (which files embed NC-licensed annotations):** download the gnomAD v4 sites VCF/TSV from `https://gnomad.broadinstitute.org/downloads`, inspect the header/INFO field definitions for `SpliceAI` (or `spliceai`) annotations, and confirm whether the distribution you intend to use contains them. Consult the per-file README on the downloads page. If SpliceAI columns are present, strip them for a strict CC0/CC-BY-only whitelist.

---

## 5. Practical bottom line for a whitelist pipeline

- **gnomAD summary/allele-frequency data (v2, v3, v4, SV, CNV, constraint, coverage): treat as CC0 — IN WHITELIST.** Attribution is *requested* (not legally required), and citing gnomAD is good practice.
- **Exclude or strip SpliceAI annotation columns**, which are CC BY-NC 4.0 (non-commercial) per the same primary terms page.
- **Do not** represent the license as MIT. MIT applies to `gnomad-browser`/`gnomad_methods` *source code*; the AWS registry's "License: MIT" field (E10–E12) is a secondary-source conflation and is misleading for data-licensing purposes.
- **Do not** name a product "gnomAD…" or use the gnomAD logo without permission (trademark).
- Canonical terms URL: **https://gnomad.broadinstitute.org/policies** (note: `/terms` now 302-redirects here).
