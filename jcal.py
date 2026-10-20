# تبدیل جلالی↔میلادی (الگوریتم استاندارد jalaali؛ بدون وابستگی)
import datetime
_BR=[-61,9,38,199,426,686,756,818,1111,1181,1210,1635,2060,2097,2192,2262,2324,2394,2456,3178]
def _jalcal(jy):
    bl=len(_BR); gy=jy+621; leap_j=-14; jp=_BR[0]; jump=0
    for i in range(1,bl):
        jm=_BR[i]; jump=jm-jp
        if jy<jm: break
        leap_j+=jump//33*8+(jump%33)//4; jp=jm
    n=jy-jp; leap_j+=n//33*8+(n%33+3)//4
    if jump%33==4 and jump-n==4: leap_j+=1
    leap_g=gy//4-(gy//100+1)*3//4-150; march=20+leap_j-leap_g
    if jump-n<6: n=n-jump+(jump+4)//33*33
    leap=(((n+1)%33)-1)%4
    if leap==-1: leap=4
    return leap,gy,march
def j2g(jy,jm,jd):
    leap,gy,march=_jalcal(jy)
    return datetime.date(gy,3,march)+datetime.timedelta(days=(jm-1)*31-(jm//7)*(jm-7)+jd-1)
def jdays(jy,jm):
    if jm<=6: return 31
    if jm<=11: return 30
    return 30 if _jalcal(jy)[0]==0 else 29
def g2j(d):
    jy=d.year-621
    for y in (jy-1,jy,jy+1):
        s=j2g(y,1,1); nxt=j2g(y+1,1,1)
        if s<=d<nxt:
            k=(d-s).days; m=1
            while True:
                n=jdays(y,m)
                if k<n: return y,m,k+1
                k-=n; m+=1
