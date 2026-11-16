"""Write the (model, L, W) multiset delta between the composed pll_top LVS
reference and the deck's extracted netlist, with the drawn-segment
decomposition of every delta -- the artifact behind
``lvs-20261116/PROOF-lvs.md``'s "every delta is accounted for" table.

Usage: python3 make-signature-delta.py <reference.spice> <extracted.cir> > out.txt
(plain stdlib; no repo imports -- the parsing rules are documented inline).
"""

import re
import sys
from collections import Counter


def parse(path: str) -> Counter:
    """(model, L_um, W_um) -> count. M= cards multiply; nf= counts fingers
    only in extracted files (the deck writes one card per finger there);
    continuation lines are joined first."""
    devs: Counter = Counter()
    text = re.sub(r"\n\+\s*", " ", open(path).read())
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("*", ".", "+")):
            continue
        toks = line.split()
        if not re.match(r"^[MRC]", toks[0]):
            continue
        model = next((t for t in toks if re.match(r"^(pfet_03v3|nfet_03v3|cap_|ppolyf)", t)), None)
        if model is None:
            continue
        w = re.search(r"\bW=([0-9.]+)", line, re.I)
        l = re.search(r"\bL=([0-9.]+)", line, re.I)
        key = (model, float(l.group(1)) if l else 0.0, float(w.group(1)) if w else 0.0)
        m = re.search(r"\sM=(\d+)", line)
        nf = re.search(r"\bnf=(\d+)", line)
        mult = int(m.group(1)) if m else (int(nf.group(1)) if nf else 1)
        devs[key] += mult
    return devs


def main() -> None:
    ref = parse(sys.argv[1])
    ext = parse(sys.argv[2])
    print(f"reference devices (M= multiplied): {sum(ref.values())}")
    print(f"extracted devices:                 {sum(ext.values())}")
    print()
    print("== extracted-only (model, L_um, W_um) ==")
    for k in sorted(set(ext) - set(ref)):
        print(f"  {ext[k]:4d} x {k}")
    print()
    print("== reference-only (model, L_um, W_um) ==")
    for k in sorted(set(ref) - set(ext)):
        print(f"  {ref[k]:4d} x {k}")
    print()
    print("== count deltas on shared signatures ==")
    for k in sorted(set(ref) & set(ext)):
        if ext[k] != ref[k]:
            print(f"  {k}: ref {ref[k]} vs ext {ext[k]} (delta {ext[k]-ref[k]:+d})")
    print()
    print("== drawn-segment decomposition check ==")
    print("MOSFET reference-only cards: does an extracted-only signature of exactly")
    print("size/N exist, with count(ext) == count(ref)*N?  Caps: the deck writes the")
    print("extracted ones in A/P form (W=L=0), so a match is model + equal count.")
    pool = Counter(ext)
    accounted = 0
    ok = True
    for k in sorted(set(ref) - set(ext)):
        model, l_um, w_um = k
        n_ref = ref[k]
        found = None
        if model.startswith("cap_mim_"):
            # the known #753 finding, not a decomposition failure: the drawn
            # option-A MIM cap is absent from the extracted netlist entirely
            print(f"  {n_ref} x {k}  ->  absent from the extracted netlist (the #753 MIM finding)")
            accounted += n_ref
            continue
        if model.startswith("cap_"):
            # the deck writes extracted caps in A/P form (W=L=0): a match is
            # same model + equal device count
            ek = (model, 0.0, 0.0)
            if pool.get(ek, 0) == n_ref:
                print(f"  {n_ref} x {k}  ->  {n_ref} x {ek} (A/P form, count equal)  OK")
                pool[ek] -= n_ref
                accounted += n_ref
                continue
            print(f"  {n_ref} x {k}  ->  no equal-count A/P-form extracted counterpart  FAIL")
            ok = False
            continue
        for n in range(2, 65):
            ek = (model, l_um, round(w_um / n, 6))
            if pool.get(ek, 0) >= n_ref * n and abs(ek[2] * n - w_um) < 0.05:
                found = (n, ek, pool[ek])
                break
        if found:
            n, ek, have = found
            print(f"  {n_ref} x {k}  ->  {n_ref*n} x {ek}  (extracted pool has {have})  OK")
            pool[ek] -= n_ref * n
            accounted += n_ref
        elif model.startswith("cap_mim_"):
            # the known #753 finding, not a decomposition failure: the drawn
            # option-A MIM cap is absent from the extracted netlist entirely
            print(f"  {n_ref} x {k}  ->  absent from the extracted netlist (the #753 MIM finding)")
            accounted += n_ref
        else:
            print(f"  {n_ref} x {k}  ->  NO decomposing signature found  FAIL")
            ok = False
    print()
    print("== shared-signature count-delta reconciliation ==")
    print("Signatures both sides carry but in different counts: does an extracted")
    print("surplus of size W pair with a reference deficit of size N*W (drawn folds")
    print("of the same card)?")
    ok2 = True
    deltas = {k: ext[k] - ref[k] for k in set(ref) & set(ext) if ext[k] != ref[k]}
    consumed: set = set()
    for k in sorted(deltas):
        d = deltas[k]
        if d >= 0:
            continue  # surpluses are resolved from the deficit side below
        model, l_um, w_um = k
        deficit = -d
        found = False
        for n in range(2, 65):
            ek = (model, l_um, round(w_um / n, 6))
            if ek in deltas and deltas[ek] == deficit * n and abs(ek[2] * n - w_um) < 0.05:
                print(f"  {deficit} x {k}  ->  {deficit*n} x {ek} (each drawn as {n} segments)  OK")
                consumed.add(k)
                consumed.add(ek)
                found = True
                break
        if not found:
            print(f"  {k}: deficit {deficit}, no fold-consistent surplus signature  FAIL")
            ok2 = False
    for k in sorted(deltas):
        if k not in consumed and deltas[k] > 0:
            print(f"  {k}: extracted surplus {deltas[k]}, no reference card consumed -- FAIL")
            ok2 = False
    if not deltas:
        print("  (no shared-signature count deltas)")
    print()
    print(f"reference-only cards accounted for: {accounted}; residual extracted-only after decomposition:")
    residual = {k: v for k, v in pool.items() if v and k not in ref}
    if residual:
        for k, v in sorted(residual.items()):
            print(f"  {v:4d} x {k}")
    else:
        print("  none")
    print()
    mim = ref.get(("cap_mim_2f0_m2m3_noshield", 31.4, 31.4), 0)
    print("VERDICT:", end=" ")
    if ok and ok2 and residual == {} and mim:
        print("every delta accounted for: folded-MOSFET cards pair with their drawn")
        print("fingers, caps match in A/P form, and the single true residual is the")
        print("option-A MIM cap, which the variant-D deck (mim_option=B) does not")
        print("extract at all -- see PROOF-lvs.md.")
    else:
        print("UNEXPLAINED deltas remain -- see the tables above.")


if __name__ == "__main__":
    main()
