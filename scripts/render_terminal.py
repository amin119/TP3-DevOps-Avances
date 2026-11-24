"""Transforme une sortie de commande (fichier texte) en page HTML style « terminal »,
pour en faire une capture d'écran (Playwright) à insérer dans le rapport.

Usage : python scripts/render_terminal.py results/term-01-cluster.txt "Titre" > out.html
"""
import html
import re
import sys

src, title = sys.argv[1], sys.argv[2]
lines = open(src, encoding="utf-8", errors="replace").read().rstrip("\n").split("\n")

out = []
for ln in lines:
    e = html.escape(ln)
    if ln.startswith("$ "):
        e = f'<span class="p">$</span> <span class="c">{html.escape(ln[2:])}</span>'
    else:
        e = re.sub(r"\b(Running|CONFIRMED|successfully|up|Ready|HTTP 200)\b", r'<span class="ok">\1</span>', e)
        e = re.sub(r"(level=ERROR|HTTP 50\d|erreurs HTTP\s+: [1-9][\d.]* %)", r'<span class="err">\1</span>', e)
        e = re.sub(r"^(#.*)$", r'<span class="cm">\1</span>', e)
        e = re.sub(r"^(http_(?:server|client)_request_duration_seconds_\w+)", r'<span class="m">\1</span>', e)
        e = re.sub(r"(p99[^:]*:\s*[\d.]+ ms|p\(99\)=[\d.]+\w+)", r'<span class="hl">\1</span>', e)
    out.append(e)

print(f"""<!doctype html><html><head><meta charset="utf-8"><style>
html{{zoom:1.5}} body{{margin:0;background:#fff;padding:14px;font-family:'Cascadia Mono','Consolas',monospace}}
.win{{display:inline-block;min-width:900px;max-width:1500px;border-radius:9px;overflow:hidden;
     box-shadow:0 6px 22px rgba(0,0,0,.25);background:#1e1f29}}
.bar{{background:#2d2f3b;padding:8px 12px;display:flex;align-items:center;gap:7px}}
.d{{width:12px;height:12px;border-radius:50%}}
.t{{color:#c9cbd6;font:13px 'Segoe UI',sans-serif;margin-left:10px}}
pre{{margin:0;padding:14px 18px;color:#e6e6e6;font-size:13.5px;line-height:1.42;white-space:pre-wrap;word-break:break-all}}
.p{{color:#50fa7b;font-weight:bold}} .c{{color:#f1fa8c}} .ok{{color:#50fa7b}} .err{{color:#ff5555;font-weight:bold}}
.cm{{color:#6272a4}} .m{{color:#8be9fd}} .hl{{color:#ffb86c;font-weight:bold}}
</style></head><body><div class="win"><div class="bar"><span class="d" style="background:#ff5f56"></span>
<span class="d" style="background:#ffbd2e"></span><span class="d" style="background:#27c93f"></span>
<span class="t">{html.escape(title)}</span></div><pre>{chr(10).join(out)}</pre></div></body></html>""")
