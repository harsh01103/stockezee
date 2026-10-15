"""Lightweight AST mutation tester: applies one operator/constant mutation at a time, runs the suite,
and reports killed vs survived mutants."""
import ast, copy, pathlib, subprocess, sys, shutil, collections

TARGETS = ["stockezee/indicators.py", "stockezee/screener.py", "stockezee/backtest.py", "stockezee/explain.py", "stockezee/data.py"]
SKIP_FUNCS = {"synthetic_ohlcv", "load_nse"}
CMP = {ast.Lt: ast.GtE, ast.Gt: ast.LtE, ast.LtE: ast.Gt, ast.GtE: ast.Lt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}


class Collect(ast.NodeVisitor):
    def __init__(self):
        self.sites = []
    def visit_Compare(self, n):
        if type(n.ops[0]) in CMP: self.sites.append(("cmp", n))
        self.generic_visit(n)
    def visit_BinOp(self, n):
        if type(n.op) in BIN: self.sites.append(("bin", n))
        self.generic_visit(n)
    def visit_JoinedStr(self, n):
        pass  # message text / format specs are not behaviour
    def visit_FunctionDef(self, n):
        if n.name in SKIP_FUNCS:
            return  # random-data generator and network loader are excluded
        self.generic_visit(n)
    def visit_Constant(self, n):
        if isinstance(n.value, (int, float)) and not isinstance(n.value, bool): self.sites.append(("const", n))


def apply(tree, idx):
    t = copy.deepcopy(tree); c = Collect(); c.visit(t)
    kind, node = c.sites[idx]
    if kind == "cmp": node.ops[0] = CMP[type(node.ops[0])]()
    elif kind == "bin": node.op = BIN[type(node.op)]()
    else: node.value = node.value + 1
    ast.fix_missing_locations(t)
    return ast.unparse(t), f"line {node.lineno}: {kind}"


def run_suite():
    r = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider"], capture_output=True, text=True)
    return r.returncode == 0


def main():
    stats = collections.OrderedDict(); survivors = []
    for f in TARGETS:
        p = pathlib.Path(f); orig = p.read_text(); tree = ast.parse(orig)
        c = Collect(); c.visit(tree); n = len(c.sites); killed = 0
        for i in range(n):
            src, desc = apply(tree, i)
            p.write_text(src)
            try:
                if run_suite(): survivors.append(f"{f} {desc}")
                else: killed += 1
            finally:
                p.write_text(orig)
        stats[f] = (n, killed)
        print(f"{f:28s} mutants={n:3d} killed={killed:3d} survived={n-killed:3d}")
    tot = sum(v[0] for v in stats.values()); kil = sum(v[1] for v in stats.values())
    print(f"\nTOTAL mutants={tot} killed={kil} survived={tot-kil} mutation score={100*kil/tot:.1f}%")
    if survivors:
        print("\nSurvivors:"); [print("  -", s) for s in survivors]


if __name__ == "__main__":
    main()
