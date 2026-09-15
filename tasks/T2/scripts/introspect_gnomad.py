"""Introspect gnomAD GraphQL schema for Variant + population frequency types."""
import json
import urllib.request

ENDPOINT = "https://gnomad.broadinstitute.org/api"
UA = "VeriBench-Bio/0.1 (open evaluation dataset; allele-frequency only)"


def gql(query, variables=None):
    payload = {"query": query, "variables": variables or {}}
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


INTROSPECT = """
query T($name: String!) {
  __type(name: $name) {
    name
    kind
    fields { name type { name kind ofType { name kind ofType { name kind } } } }
  }
}
"""

for t in [
    "Variant",
    "VariantDetailsSequencingTypeData",
    "VariantDetailsJointSequencingTypeData",
    "VariantPopulation",
    "VariantDetailsPopulation",
]:
    try:
        out = gql(INTROSPECT, {"name": t})
        ty = out.get("data", {}).get("__type")
        print("==", t, "==")
        if not ty:
            print("  (not found)", json.dumps(out)[:300])
            continue
        for f in ty["fields"]:
            def fmt(x):
                if not x:
                    return "?"
                if x.get("name"):
                    return x["name"]
                return fmt(x.get("ofType"))
            print("   ", f["name"], ":", fmt(f["type"]))
    except Exception as e:
        print("==", t, "ERR", type(e).__name__, str(e)[:300])
    print()
