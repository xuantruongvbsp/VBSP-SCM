"""Check render() signatures for all tabs."""
import ast
import glob

for f in sorted(glob.glob("tabs/tab_*.py")):
    name = f.replace("\\","/").replace("tabs/","")
    try:
        with open(f, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
    except SyntaxError as e:
        print(f"  SYNTAX ERROR: {name}: {e}")
        continue

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "render":
            args = node.args
            pos_args = [a.arg for a in args.args]
            defaults = [None] * (len(args.args) - len(args.defaults)) + args.defaults
            tab_default = None
            for a, d in zip(args.args, defaults):
                if a.arg == "tab":
                    tab_default = d is not None
            marker = " [tab=MANDATORY]" if not tab_default else ""
            print(f"  {name}: render({', '.join(pos_args)}){marker}")
            break
    else:
        # Check for render_nhap_* functions
        has_nhap = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("render_nhap_"):
                has_nhap = True
        if has_nhap:
            print(f"  {name}: render_nhap_* (no render())")
