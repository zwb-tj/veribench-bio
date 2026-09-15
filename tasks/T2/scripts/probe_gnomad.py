"""Probe the gnomAD GraphQL API: confirm reachability + response shape.

We only ever request allele-frequency fields (CC0). We never request
in-silico predictor fields (SpliceAI = CC BY-NC 4.0, dbNSFP = CC BY-NC-ND).
"""
import json
import urllib.request
import urllib.error

ENDPOINT = "https://gnomad.broadinstitute.org/api"
UA = "VeriBench-Bio/0.1 (open evaluation dataset; allele-frequency only)"

# Minimal field set: identities + allele counts. No predictors, no annotations.
QUERY = """
query V($id: String!, $ds: DatasetId!) {
  variant(variantId: $id, dataset: $ds) {
    variant_id
    exome { ac an af }
    genome { ac an af }
    joint { ac an af populations { id ac an } }
  }
}
"""


def gql(query, variables=None):
    payload = {"query": query, "variables": variables or {}}
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


if __name__ == "__main__":
    for vid in ["1-55051215-G-GA", "13-32340390-C-T"]:
        try:
            out = gql(QUERY, {"id": vid, "ds": "gnomad_r4"})
            print("VID:", vid)
            print(json.dumps(out, indent=2)[:1500])
        except urllib.error.HTTPError as e:
            print("VID:", vid, "HTTPError", e.code, e.read().decode()[:500])
        except Exception as e:
            print("VID:", vid, "ERR", type(e).__name__, e)
        print("-" * 60)
