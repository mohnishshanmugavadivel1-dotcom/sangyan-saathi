"""Source-tree manifest (no git repository exists here, so the freeze is a per-file sha256 list plus one tree hash).
python3 -B eval/make_manifest.py <label> <out_file> [--append]
Tree hash = sha256 over the sorted lines 'sha256  relative/path' of every file under poc, v0_2, v0_3, rc (excluding results/, __pycache__, *.pyc, node_modules)."""
import hashlib, os, platform, subprocess, sys, datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
def walk():
    for top in ("poc", "v0_2", "v0_3", "rc"):
        for d, ds, fs in os.walk(os.path.join(ROOT, top)):
            ds[:] = sorted(x for x in ds if x not in ("__pycache__", "node_modules", ".cache") and not (top == "rc" and os.path.relpath(os.path.join(d, x), ROOT) == "rc/results"))
            for f in sorted(fs):
                if f.endswith(".pyc"): continue
                p = os.path.join(d, f); yield os.path.relpath(p, ROOT), hashlib.sha256(open(p, "rb").read()).hexdigest()
def main():
    label, out = sys.argv[1], sys.argv[2]; lines = ["%s  %s" % (h, p) for p, h in walk()]
    tree = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    eng = hashlib.sha256("\n".join(l for l in lines if "  rc/saathi_rc/" in l).encode()).hexdigest()
    head = ["# === %s ===" % label, "# created_utc: %s" % datetime.datetime.now(datetime.timezone.utc).isoformat(), "# python: %s" % sys.version.split()[0], "# platform: %s" % platform.platform(),
            "# vcs: none (not a git repository); freeze = per-file sha256 + tree hash", "# files: %d" % len(lines), "# TREE_SHA256: %s" % tree, "# ENGINE_SHA256 (rc/saathi_rc/ only): %s" % eng, "# command: python3 -B eval/make_manifest.py %s %s" % (label, out)]
    mode = "a" if "--append" in sys.argv else "w"
    with open(out, mode, encoding="utf-8") as f: f.write("\n".join(head + lines) + "\n\n")
    print(label, "tree", tree[:16], "engine", eng[:16], "files", len(lines))
main()
