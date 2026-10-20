"""روزانهٔ OGIMET → ماهانهٔ جلالی با شمارنده‌ها.  python ogimet_aggregate.py <پوشه‌ها...> --out monthly.csv
ستون‌ها: ind,jy,jm,ndays,nmx,nmn,np,tmax,tmin,prec,ntr   (tmax/tmin میانگین روزانه‌ها؛ prec مجموع، «Tr» صفر شمرده می‌شود؛ هر میانگین/مجموع فقط روی روزهای موجود)
تصمیم دربارهٔ پذیرش ماه (≥۹۰٪ روزها و r≥۰٫۹ روی ماه‌های هم‌پوشان) در مرحلهٔ ادغام با اطلس گرفته می‌شود، نه این‌جا."""
import argparse, glob, os, collections, datetime
from jcal import g2j, jdays
ap = argparse.ArgumentParser(); ap.add_argument("dirs", nargs="+"); ap.add_argument("--out", default="monthly.csv"); a = ap.parse_args()
seen = {}
for d in a.dirs:
    for f in glob.glob(os.path.join(d, "**", "daily_*.csv"), recursive=True):
        for ln in open(f, encoding="utf8"):
            p = ln.rstrip("\n").split(",")
            if len(p) == 5: seen[(p[0], p[1])] = p
M = collections.defaultdict(lambda: [0, 0, 0, 0.0, 0.0, 0.0, 0])          # nmx,nmn,np,Σmx,Σmn,Σp,ntr
for (ind, ds), p in seen.items():
    y, m, _ = g2j(datetime.date.fromisoformat(ds)); r = M[(ind, y, m)]
    if p[2] != "": r[0] += 1; r[3] += float(p[2])
    if p[3] != "": r[1] += 1; r[4] += float(p[3])
    if p[4] != "":
        r[2] += 1; v = float(p[4])
        if abs(v - 0.01) < 1e-9: r[6] += 1
        else: r[5] += v
with open(a.out, "w", encoding="utf8") as o:
    o.write("ind,jy,jm,ndays,nmx,nmn,np,tmax,tmin,prec,ntr\n")
    for (ind, y, m), r in sorted(M.items()):
        f = lambda s, n, k=1: "" if n == 0 else f"{s/n:.{k}f}"
        o.write(f"{ind},{y},{m},{jdays(y,m)},{r[0]},{r[1]},{r[2]},{f(r[3],r[0])},{f(r[4],r[1])},{'' if r[2]==0 else round(r[5],1)},{r[6]}\n")
print("روزانه:", len(seen), "→ ماه-ایستگاه:", len(M), "→", a.out)
