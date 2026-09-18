# -*- coding: utf-8 -*-
"""
صغاري VIP — المزامنة التلقائية (Sync Daemon)
يعمل في الخلفية ويراقب الموردين الصينيين؛ أي منتج جديد يُضاف تلقائيًا إلى products.js
التشغيل:
  python sync.py            → وضع المراقبة الدائم (كل 30 دقيقة افتراضيًا)
  python sync.py --once     → مزامنة واحدة الآن ثم يتوقف
الأتمتة الكاملة: mode = "api" + مفتاح CJ في config.json
"""
import json, csv, time, os, sys, urllib.request, hashlib

def get_api_key(cfg):
    return os.environ.get('CJ_API_KEY') or cfg['api']['api_key']

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line); open('sync.log','a',encoding='utf-8').write(line+'\n')

def price(cost, ship, cfg):
    return round((cost+ship)*cfg['usd_to_sar']*(1+cfg['margin_pct']/100)+cfg['fixed_fee_sar'])

def load_products():
    try:
        raw = open('products.js',encoding='utf-8').read()
        return json.loads(raw[raw.index('['):raw.rindex(']')+1])
    except Exception:
        return []

def save_products(prods):
    open('products.js','w',encoding='utf-8').write('window.PRODUCTS_EXTERNAL = '+json.dumps(prods,ensure_ascii=False,indent=1)+';\n')

def known_urls(prods):
    return {p.get('supplier') for p in prods}

def fetch_from_api(cfg, existing):
    """وضع API: جلب مباشر من CJ Dropshipping — المزامنة التلقائية الحقيقية"""
    key = get_api_key(cfg)
    if not key or 'PUT_YOUR' in key:
        log('لا يوجد مفتاح API — فعّل الوضع اليدوي أو أضف المفتاح'); return []
    req = urllib.request.Request(cfg['api']['endpoint_products'],
        data=json.dumps({'pageNum':1,'pageSize':100,'categoryId':'kids'}).encode(),
        headers={'Content-Type':'application/json','CJ-Access-Token':key})
    data = json.loads(urllib.request.urlopen(req,timeout=30).read())
    seen = known_urls(existing); new = []
    for it in data.get('data',[]):
        url = it.get('productUrl','')
        if url in seen: continue
        c = float(it.get('sellPrice',0))
        p = price(c,4.0,cfg)
        new.append({'id':len(existing)+len(new)+1,'name':it.get('productNameEn','منتج جديد'),
            'cat':'مستورد تلقائي','supplier':url,'cost':c,'ship':4.0,
            'price':p,'old':round(p*1.4),'emoji':'🛍️','bg':'linear-gradient(135deg,#eee,#f8f8f8)'})
        seen.add(url)
    return new

def fetch_from_watchlist(cfg, existing):
    """وضع المراقبة: اقرأ sources.csv — أضف أي صف جديد يظهر فيه تلقائيًا"""
    seen = known_urls(existing); new = []
    if not os.path.exists('sources.csv'): return []
    with open('sources.csv',encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if row['supplier_url'] in seen: continue
            c,s = float(row['product_cost_usd']),float(row['shipping_usd'])
            p = price(c,s,cfg)
            new.append({'id':len(existing)+len(new)+1,'name':row['name'],'cat':row['category'],
                'supplier':row['supplier_url'],'cost':c,'ship':s,'price':p,'old':round(p*1.4),
                'emoji':row['emoji'],'bg':row['bg']})
            seen.add(row['supplier_url'])
    return new

def run_once(cfg):
    prods = load_products()
    new = fetch_from_api(cfg,prods) if cfg['sync']['mode']=='api' else fetch_from_watchlist(cfg,prods)
    if new and cfg['sync']['auto_publish']:
        save_products(prods+new)
        log(f'تم نشر {len(new)} منتجًا جديدًا تلقائيًا')
    else:
        log('لا جديد — المتجر محدّث')

if __name__=='__main__':
    cfg = json.load(open('config.json',encoding='utf-8'))
    log('بدء المزامنة التلقائية')
    if '--once' in sys.argv:
        run_once(cfg); sys.exit(0)
    while True:
        run_once(cfg)
        time.sleep(cfg['sync']['interval_minutes']*60)
