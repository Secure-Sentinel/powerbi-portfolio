# -*- coding: utf-8 -*-
"""Depo tutarlilik denetimi — Power BI Desktop'i acmadan.

Bir .pbip'i acmadan once bozulmus olabilecek her seyi kontrol eder:
  * CSV basliklari ile M tip donusum listesi birebir mi
  * modelin veri kolonlari CSV'de var mi
  * iliski / sortByColumn / hiyerarsi / varyasyon referanslari cozuluyor mu
  * DAX icinde gecen 'Tablo'[Kolon] referanslari modelde var mi
  * report.json'daki alan referanslari modelde var mi (en kritik denetim)
  * kaynak (resource) referanslari dosyada var mi
"""
import csv, glob, json, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
hata_sayisi = 0
uyari_sayisi = 0


def hata(m):
    global hata_sayisi
    hata_sayisi += 1
    print('   HATA  ', m)


def uyari(m):
    global uyari_sayisi
    uyari_sayisi += 1
    print('   uyarı ', m)


def csv_basliklari(yol):
    with open(yol, encoding='utf-8', newline='') as f:
        return next(csv.reader(f))


def denetle(slug):
    print('=' * 78)
    print(slug)
    kok = os.path.join(REPO, slug)
    bim_yol = glob.glob(os.path.join(kok, '*.SemanticModel', 'model.bim'))[0]
    rep_yol = glob.glob(os.path.join(kok, '*.Report', 'report.json'))[0]
    m = json.load(open(bim_yol, encoding='utf-8'))['model']
    rapor = json.load(open(rep_yol, encoding='utf-8'))

    # ---- model envanteri
    kolonlar = {}      # tablo -> {kolon: tip}
    olculer = {}       # tablo -> set(olcu)
    tum_olculer = set()
    hiyerarsiler = {}  # (tablo, hiyerarsi)
    for t in m['tables']:
        kolonlar[t['name']] = {c['name']: c for c in t['columns']}
        olculer[t['name']] = {x['name'] for x in t.get('measures', [])}
        tum_olculer |= olculer[t['name']]
        for h in t.get('hierarchies', []):
            hiyerarsiler[(t['name'], h['name'])] = [l['column'] for l in h['levels']]
    iliski_adlari = {r['name'] for r in m.get('relationships', [])}

    # ---- 1) CSV <-> M tip listesi ve model kolonlari
    for t in m['tables']:
        src = t['partitions'][0]['source']
        if src['type'] != 'm':
            continue
        ifade = src['expression']
        mm = re.search(r'Veri\("([^"]+)"\)', ifade)
        if not mm:
            continue
        dosya = os.path.join(kok, 'data', mm.group(1))
        if not os.path.isfile(dosya):
            hata(f'{t["name"]}: CSV yok -> {mm.group(1)}')
            continue
        basliklar = csv_basliklari(dosya)
        m_kolonlar = re.findall(r'\{"((?:[^"\\]|\\.)*)",\s*[^}]+\}', ifade)
        if m_kolonlar != basliklar:
            eksik = [c for c in m_kolonlar if c not in basliklar]
            fazla = [c for c in basliklar if c not in m_kolonlar]
            if eksik or fazla:
                hata(f'{t["name"]}: M/CSV kolon uyuşmazlığı '
                     f'M-de-var-CSV-de-yok={eksik} CSV-de-var-M-de-yok={fazla}')
            else:
                uyari(f'{t["name"]}: kolon sırası farklı (sorun değil)')
        # modelin veri kolonlari CSV'de olmali
        for ad, c in kolonlar[t['name']].items():
            if c.get('type') in (None, 'data') and 'sourceColumn' in c:
                if c['sourceColumn'] not in basliklar:
                    hata(f'{t["name"]}[{ad}]: sourceColumn CSV başlıklarında yok '
                         f'({c["sourceColumn"]})')

    # ---- 2) iliskiler
    for r in m.get('relationships', []):
        for tb, kl in ((r['fromTable'], r['fromColumn']), (r['toTable'], r['toColumn'])):
            if tb not in kolonlar:
                hata(f'ilişki {r["name"]}: tablo yok {tb}')
            elif kl not in kolonlar[tb]:
                hata(f'ilişki {r["name"]}: kolon yok {tb}[{kl}]')

    # ---- 3) sortByColumn / hiyerarsi / varyasyon
    for t in m['tables']:
        for c in t['columns']:
            sb = c.get('sortByColumn')
            if sb and sb not in kolonlar[t['name']]:
                hata(f'{t["name"]}[{c["name"]}]: sortByColumn yok ({sb})')
            for v in c.get('variations', []):
                if v.get('relationship') not in iliski_adlali_set(iliski_adlari):
                    hata(f'{t["name"]}[{c["name"]}]: varyasyon ilişkisi yok '
                         f'({v.get("relationship")})')
                dh = v.get('defaultHierarchy') or {}
                if dh and (dh.get('table'), dh.get('hierarchy')) not in hiyerarsiler:
                    hata(f'{t["name"]}[{c["name"]}]: varyasyon hiyerarşisi yok ({dh})')
        for h in t.get('hierarchies', []):
            for l in h['levels']:
                if l['column'] not in kolonlar[t['name']]:
                    hata(f'{t["name"]}.{h["name"]}: seviye kolonu yok ({l["column"]})')

    # ---- 4) DAX referanslari
    dax_kaynaklari = []
    for t in m['tables']:
        for ms in t.get('measures', []):
            dax_kaynaklari.append((f'{t["name"]}[{ms["name"]}] (ölçü)', ms['expression']))
        for c in t['columns']:
            if c.get('type') == 'calculated':
                dax_kaynaklari.append((f'{t["name"]}[{c["name"]}] (hesap kolonu)',
                                       c.get('expression') or ''))
        src = t['partitions'][0]['source']
        if src['type'] == 'calculated':
            dax_kaynaklari.append((f'{t["name"]} (hesap tablosu)', src['expression']))

    for etiket, dax in dax_kaynaklari:
        dax = re.sub(r'--[^\n]*', '', dax)      # satır yorumları
        dax = re.sub(r'/\*.*?\*/', '', dax, flags=re.S)
        for tb, kl in re.findall(r"'([^']+)'\[([^\]]+)\]", dax):
            if tb not in kolonlar:
                hata(f'{etiket}: DAX tablosu yok \'{tb}\'')
            elif kl not in kolonlar[tb] and kl not in olculer.get(tb, set()):
                hata(f'{etiket}: DAX kolonu yok \'{tb}\'[{kl}]')
        for tb, kl in re.findall(r'(?<![\'\w])(\w+)\[([^\]]+)\]', dax):
            if tb in kolonlar:
                if kl not in kolonlar[tb] and kl not in olculer.get(tb, set()):
                    hata(f'{etiket}: DAX kolonu yok {tb}[{kl}]')

    # ---- 5) report.json alan referanslari
    metin = json.dumps(rapor, ensure_ascii=False)
    ent_prop = set()
    for blob in re.finditer(
            r'\{\\"(?:Column|Measure)\\":\{\\"Expression\\":\{\\"SourceRef\\":'
            r'\{\\"Entity\\":\\"([^"\\]+)\\"\}\},\\"Property\\":\\"([^"\\]+)\\"', metin):
        ent_prop.add((blob.group(1), blob.group(2)))
    # ayrica ac(ilmis) config bloklari icinde duz JSON olarak
    def gez(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ('config', 'filters', 'query', 'dataTransforms') and isinstance(v, str):
                    try:
                        gez(json.loads(v))
                    except Exception:
                        pass
                else:
                    gez(v)
        elif isinstance(o, list):
            for v in o:
                gez(v)

    toplanan = []

    def topla(o, alias=None):
        """SourceRef alias -> Entity eslemesini de kurarak alan referanslarini topla."""
        if isinstance(o, dict):
            harita = {}
            if 'From' in o and isinstance(o['From'], list):
                for f in o['From']:
                    if isinstance(f, dict) and 'Name' in f and 'Entity' in f:
                        harita[f['Name']] = f['Entity']
            if harita:
                alias = dict(alias or {}, **harita)
            for kind in ('Column', 'Measure'):
                c = o.get(kind)
                if isinstance(c, dict) and 'Property' in c:
                    sr = ((c.get('Expression') or {}).get('SourceRef') or {})
                    ent = sr.get('Entity') or (alias or {}).get(sr.get('Source'))
                    if ent:
                        toplanan.append((ent, c['Property'], kind))
            for v in o.values():
                if isinstance(v, str) and v.strip().startswith(('{', '[')):
                    try:
                        topla(json.loads(v), alias)
                        continue
                    except Exception:
                        pass
                topla(v, alias)
        elif isinstance(o, list):
            for v in o:
                topla(v, alias)

    # Orijinal raporda da bulunan, kopyala-yapistirdan kalan olu bicimlendirme
    # secicileri (dataPoint.selector.scopeId). Power BI eslesmeyen seciciyi
    # sessizce yok sayar; modelde karsiligi olmamasi normaldir.
    OLU_REFERANSLAR = {
        ('STOK', 'GRUP_ADI'), ('SIPARIS', 'Musteri Tipi'),
        ('SATINALMA_SIPARIS', 'Termine Kalan Gün (Düz)'),
    }
    topla(rapor)
    goruldu = set()
    for ent, prop, kind in toplanan:
        if (ent, prop, kind) in goruldu:
            continue
        goruldu.add((ent, prop, kind))
        if (ent, prop) in OLU_REFERANSLAR and ent not in kolonlar:
            uyari(f'report.json: ölü biçimlendirme seçicisi {ent}[{prop}] '
                  '(orijinalinde de var, Power BI yok sayar)')
            continue
        if ent not in kolonlar:
            hata(f'report.json: tablo yok {ent} ({prop})')
        elif prop not in kolonlar[ent] and prop not in olculer.get(ent, set()):
            hata(f'report.json: alan yok {ent}[{prop}] ({kind})')

    # ---- 6) kaynak dosyalari
    res_dir = os.path.join(os.path.dirname(rep_yol), 'StaticResources', 'RegisteredResources')
    mevcut = set(os.listdir(res_dir)) if os.path.isdir(res_dir) else set()
    istenen = set(re.findall(r'\\"ItemName\\":\s?\\"([^"\\]+)\\"', metin))
    istenen |= set(re.findall(r'"ItemName":\s?"([^"]+)"', metin))
    for i in istenen:
        if i not in mevcut:
            hata(f'kaynak dosya yok: {i}')
    for pkg in rapor.get('resourcePackages', []):
        for it in pkg.get('resourcePackage', {}).get('items', []):
            if pkg['resourcePackage']['type'] == 1 and it['name'] not in mevcut:
                hata(f'resourcePackage kaydı dosyasız: {it["name"]}')

    print(f'   {len(goruldu)} rapor alan referansı, {len(dax_kaynaklari)} DAX ifadesi, '
          f'{len(istenen)} kaynak referansı denetlendi')


def iliski_adlali_set(s):
    return s


if __name__ == '__main__':
    print(f'Depo: {REPO}')
    print()
    for slug in sorted(os.listdir(REPO)):
        if re.match(r'^0\d-', slug):
            denetle(slug)
    print('=' * 78)
    print(f'Toplam: {hata_sayisi} hata, {uyari_sayisi} uyarı')
    sys.exit(1 if hata_sayisi else 0)
