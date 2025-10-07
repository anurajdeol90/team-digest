import json, sys, collections

path = "out.json" if len(sys.argv) == 1 else sys.argv[1]
data = json.load(open(path, encoding="utf-8"))

def uniq(seq):
    seen = set(); out=[]
    for s in seq:
        k = s.strip().casefold()
        if k and k not in seen:
            out.append(s); seen.add(k)
    return out

actions = data.get("actions", [])
risks = data.get("risks", [])
deps = data.get("dependencies", [])

# 1) No raw JSON objects inside Risks/Dependencies
def looks_jsonish(s: str) -> bool:
    s = s.strip()
    return (s.startswith("{") and s.endswith("}")) or (('": "' in s) or ('": {' in s) or ('": [' in s))
no_json_in_risks = all(not looks_jsonish(s) for s in risks)
no_json_in_deps  = all(not looks_jsonish(s) for s in deps)

# 2) No duplicates (case-insensitive) in Risks/Dependencies
risks_unique = (len(risks) == len(uniq(risks)))
deps_unique  = (len(deps)  == len(uniq(deps)))

# 3) “Blocker detected.” only if there is no explicit blocker line
has_generic_blocker = any(s.strip().casefold() == "blocker detected." for s in risks+deps)
has_explicit_blocker = any("blocker" in s.lower() for s in risks+deps)
generic_ok = (not has_generic_blocker) or (has_generic_blocker and not has_explicit_blocker)

# 4) Action from Gamma should live in Actions (not in Risks)
gamma_action_in_actions = any("Communicate delay to stakeholders" in (a.get("title","")) for a in actions)
gamma_action_leaked = any("Communicate delay to stakeholders" in s for s in risks+deps)

# 5) If owner_map has AD -> Anuraj Deol, confirm mapping
owner_mapped = True
for a in actions:
    if a.get("title","").startswith("Update Alpha roadmap"):
        owner_mapped = (a.get("owner") == "Anuraj Deol")

checks = collections.OrderedDict([
    ("No JSON inside Risks", no_json_in_risks),
    ("No JSON inside Dependencies", no_json_in_deps),
    ("Risks are de-duplicated", risks_unique),
    ("Dependencies are de-duplicated", deps_unique),
    ("Generic blocker usage OK", generic_ok),
    ("Gamma action in Actions", gamma_action_in_actions),
    ("Gamma action NOT in Risks/Dependencies", not gamma_action_leaked),
    ("Owner map applied (AD -> Anuraj Deol)", owner_mapped),
])

failed = [k for k,v in checks.items() if not v]
for k,v in checks.items():
    print(("OK   " if v else "FAIL ") + k)

print("\nSummary:", "PASS ✅" if not failed else f"FAIL ❌ -> {', '.join(failed)}")
sys.exit(0 if not failed else 1)
