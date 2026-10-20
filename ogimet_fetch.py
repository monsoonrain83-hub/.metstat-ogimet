"""دانلود خلاصهٔ روزانهٔ OGIMET (gsynres) برای پنجره‌های jobs.json.  مخزن: metstat-site
  python ogimet_fetch.py --jobs jobs.json --shard 0 --nshards 12 --out out --budget 330 [--skip done_prev.txt ...] [--limit N]
خروجی در out/: daily_<shard>.csv (ind,date,tmax,tmin,prec)  و  done_<shard>.txt (کلید کار + وضعیت).
- هر درخواست حداکثر ۵۰ روز برمی‌گرداند (آزموده در probe2). تاریخ‌ها در جدول فقط ماه/روزند؛ سال از تاریخ پایان پنجره استنباط می‌شود.
- صفحهٔ «stub» (۲۵ نویسه یا کم‌ردیف) یعنی محدودیت نرخ → صبر ۴۵/۶۰/۹۰ ث و تلاش دوباره؛ بعد از هر stub فاصلهٔ بین درخواست‌ها بیشتر می‌شود.
- فقط کارهای «ok» اجراهای قبلی (--skip) رد می‌شوند؛ empty/fail/skip دوباره امتحان می‌شوند. شارد = رتبهٔ ایستگاه mod nshards؛ ترتیب کارها: ایستگاه، جدید→قدیم.
- ایستگاهی که ۳ پنجرهٔ پیاپی خالی بدهد، پنجره‌های ۲ سال عقب‌تر را رد می‌کند (وضعیت skip).
- وضعیت: ok / empty (صفحهٔ بدون جدول داده، دوبار پیاپی) / fail (چند stub پیاپی؛ در اجرای بعد دوباره امتحان می‌شود).
- بارش: «0.0»→۰، «Tr»→۰٫۰۱ (اثر؛ شمرده می‌شود ولی عملاً صفر)، «----»/خالی→گمشده. دما: خالی/«----»→گمشده."""
import argparse, os, re, sys, time, json, io, datetime, urllib.request, urllib.error
URL = "https://www.ogimet.com/cgi-bin/gsynres?lang=en&ind={ind}&ndays={nd}&ano={y}&mes={m:02d}&day={d:02d}&hora=00&ord=REV&Send=Send"

def fetch(u):
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) metstat-ogimet"}), timeout=120)
        return r.status, r.read().decode("latin1")
    except urllib.error.HTTPError as e: return e.code, ""
    except Exception as e: return 0, ""

def num(x):
    x = str(x).strip()
    if x in ("", "nan", "----", "---", "--"): return None
    if x == "Tr": return 0.01
    try: return float(x)
    except ValueError: return None

def classify(t):
    """→ 'stub' (محدودیت نرخ، حتماً تکرار) | 'maybe' (صفحهٔ کوچک بدون جدول: یا stub یا ایستگاه بی‌داده؛ یک بار تکرار) | 'ok'"""
    n = len(re.findall(r"<tr", t, re.I))
    if "date" in t.lower() and n > 10: return "ok"
    return "stub" if (len(t) < 100 or 7000 <= len(t) <= 8500) else "maybe"

def parse(t, end):
    """جدول → فهرست (date, tmax, tmin, prec) با سال استنباط‌شده (ردیف‌ها نزولی از end)."""
    import pandas as pd
    tb = max(pd.read_html(io.StringIO(t)), key=lambda x: x.shape[0] * x.shape[1])
    cols = [tuple(str(x) for x in c) if isinstance(c, tuple) else (str(c), str(c)) for c in tb.columns]
    ix = lambda f: next(i for i, c in enumerate(cols) if f(c))
    ic, imx, imn, ip = ix(lambda c: c[0] == "Date"), ix(lambda c: c[1] == "Max"), ix(lambda c: c[1] == "Min"), ix(lambda c: c[0].startswith("Prec"))
    out = []; y = end.year; prev = (end.month, end.day); seen = set()
    for r in tb.itertuples(index=False):
        ds = str(r[ic]); m = re.match(r"(\d{1,2})/(\d{1,2})$", ds)
        if not m: continue
        mo, dd = int(m.group(1)), int(m.group(2))
        if (mo, dd) > prev: y -= 1                       # از ژانویه به دسامبر رسیدیم → سال قبل
        prev = (mo, dd)
        try: d = datetime.date(y, mo, dd)
        except ValueError: continue
        if d > end or d in seen: continue
        seen.add(d); out.append((d.isoformat(), num(r[imx]), num(r[imn]), num(r[ip])))
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--jobs", required=True); ap.add_argument("--shard", type=int, default=0); ap.add_argument("--nshards", type=int, default=1)
    ap.add_argument("--out", default="out"); ap.add_argument("--budget", type=float, default=330, help="دقیقه"); ap.add_argument("--skip", nargs="*", default=[]); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--gap", type=float, default=6.0, help="فاصلهٔ پایهٔ درخواست‌ها (ث)"); ap.add_argument("--deadn", type=int, default=3, help="بعد از N خالیِ پیاپی برای یک ایستگاه..."); ap.add_argument("--deadskip", type=int, default=730, help="...پنجره‌های تا این‌قدر روز عقب‌تر رد می‌شوند"); ap.add_argument("--html", help="(آزمون) به‌جای شبکه از این فایل HTML بخوان")
    a = ap.parse_args(); T0 = time.time(); os.makedirs(a.out, exist_ok=True)
    jobs = json.load(open(a.jobs)); key = lambda j: f"{j['ind']}|{j['end']}|{j['nd']}"
    done = set()
    for f in a.skip:
        for ln in open(f, encoding="utf8"):
            k, _, st = ln.strip().partition(" ")
            if st == "ok": done.add(k)
    rank = {ind: r for r, ind in enumerate(sorted({j["ind"] for j in jobs}))}            # شارد بر پایهٔ ایستگاه (تا قاعدهٔ «ایستگاه مرده» در یک شارد بماند)
    mine = [j for j in jobs if rank[j["ind"]] % a.nshards == a.shard and key(j) not in done]
    if a.limit: mine = mine[:a.limit]
    print(f"شارد {a.shard}/{a.nshards}: {len(mine)} کار (رد‌شده‌ها: {len(done)})", flush=True)
    fd = open(os.path.join(a.out, f"daily_{a.shard}.csv"), "a", encoding="utf8"); fl = open(os.path.join(a.out, f"done_{a.shard}.txt"), "a", encoding="utf8")
    gap = a.gap; stats = {"ok": 0, "empty": 0, "fail": 0, "skip": 0}; fails_in_row = 0; nsamp = [0]; emp = {}   # emp[ind] = (تعداد پیاپی خالی، تاریخ آخرین خالی)
    for n, j in enumerate(mine):
        if time.time() - T0 > a.budget * 60: print("⏹ سقف زمان", flush=True); break
        end = datetime.date.fromisoformat(j["end"])
        ce, le = emp.get(j["ind"], (0, None))
        if ce >= a.deadn and le and (le - end).days < a.deadskip:
            fl.write(f"{key(j)} skip\n"); stats["skip"] += 1; continue          # ایستگاه در این بازه گزارش نمی‌دهد؛ ۲ سال بعدتر دوباره امتحان می‌شود
        u = URL.format(ind=j["ind"], nd=j["nd"], y=end.year, m=end.month, d=end.day); st = "fail"; t = ""
        nmaybe = 0
        for w in (0, 45, 60, 90):
            if w: time.sleep(w); gap = min(gap * 1.5, 20)
            if a.html: code, t = 200, open(a.html, encoding="utf8").read()
            else: code, t = fetch(u)
            c = classify(t) if code == 200 else "stub"
            if c == "ok": st = "ok"; break
            if c == "maybe":
                nmaybe += 1
                if nsamp[0] < 5: nsamp[0] += 1; open(os.path.join(a.out, f"maybe_{a.shard}_{nsamp[0]}.html"), "w", encoding="utf8").write(f"<!-- {u} len={len(t)} -->\n" + t)
                if nmaybe >= 2: st = "empty"; break
        if st == "ok":
            try:
                rows = parse(t, end)
                for d, mx, mn, p in rows: fd.write(f"{j['ind']},{d},{'' if mx is None else mx},{'' if mn is None else mn},{'' if p is None else p}\n")
                fd.flush()
                if not rows: st = "empty"
            except Exception as e: print("  parse خطا", j, repr(e)[:150], flush=True); st = "fail"
        fl.write(f"{key(j)} {st}\n"); fl.flush(); stats[st] += 1
        if st == "empty": emp[j["ind"]] = (ce + 1, end)
        elif st == "ok": emp[j["ind"]] = (0, None)
        fails_in_row = fails_in_row + 1 if st == "fail" else 0
        if st == "ok": gap = max(a.gap, gap * 0.9)
        if fails_in_row >= 6: print("⏹ ۶ شکست پیاپی — احتمالاً مسدودی؛ توقف", flush=True); break
        if n % 25 == 0: print(f"  {n}/{len(mine)} {stats} gap={gap:.1f}s {(time.time()-T0)/60:.0f}min", flush=True)
        if a.html: break
        time.sleep(gap)
    print("پایان", stats, flush=True)
if __name__ == "__main__": main()
