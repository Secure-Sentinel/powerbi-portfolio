#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Firma A.Ş. — sentetik (sahte) veri üreteci
====================================================

Bu depodaki dört Power BI raporunu besleyen CSV dosyalarını üretir. Üretilen
veri tamamen kurgudur; Test Firma A.Ş. diye bir firma yoktur. Amaç,
raporların modelleme ve DAX kurgusunu gerçek bir üretim/satış verisi olmadan
gösterebilmektir.

Veri, kurgusal bir üretim işletmesini modeller:

    stok kartları -> siparişler -> sevkiyat/fatura (ciro) -> ödeme planı
    tedarikçiler  -> satın alma siparişleri -> mal kabul -> cari bakiye
    iş emirleri   -> makine/vardiya kayıtları -> duruş & arıza -> OEE

Kullanım
--------
    python tools/veri_uret.py                 # bugüne göre üret
    python tools/veri_uret.py --bugun 2026-07-30
    python tools/veri_uret.py --olcek 0.4     # daha küçük veri seti

Aynı --bugun ve --olcek ile her çalıştırma birebir aynı çıktıyı verir
(sabit tohum: RASTGELE_TOHUM).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import math
import os
import random
from collections import defaultdict

RASTGELE_TOHUM = 20260730
# Cari bakiyelerin ne kadarı ters tarafta durur (bkz. Uretec.bakiye_uret)
TERS_BAKIYE_ORANI = 0.12
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# rapor klasörü -> hangi tabloların CSV'si oraya yazılacak
RAPOR_KLASORLERI = {
    'scada': '01-scada-uretim-izleme',
    'yurtici': '02-departman-ticaret-analizi',
    'satinalma': '03-satin-alma-analizi',
    'urun': '04-urun-kalip-analizi',
}

# --------------------------------------------------------------------------
# Sözlükler — teknik terimler gerçek üretim diliyle, kimlikler tamamen kurgu
# --------------------------------------------------------------------------

SEKILLER = [
    # (AD1, KOD_1, ağırlık)
    ('Yuvarlak Kutu', 'SK01', 34),
    ('Yuvarlak-Sivama Kutu', 'SK02', 12),
    ('Kare Kutu', 'SK03', 10),
    ('Dikdortgen Kutu', 'SK04', 11),
    ('Oval Kutu', 'SK05', 6),
    ('Altıgen Kutu', 'SK06', 3),
    ('Sekizgen Kutu', 'SK07', 3),
    ('Sekilli Kutu', 'SK08', 4),
    ('Kalp Kutu', 'SK09', 2),
    ('Koseli Sivama Kutu', 'SK10', 4),
    ('Tepsi', 'SK11', 3),
    ('Kapak', 'SK12', 3),
    ('Sadece Dip', 'SK13', 2),
    ('Sadece Kapak', 'SK14', 1),
    ('Tel Mekanizmali Kutu', 'SK15', 1),
    ('Plaka-Bardak Alti', 'SK16', 1),
]

# Kalıp kodları: "<en>-<yükseklik>" / "DIA-<çap>" / "Y<en>-<yükseklik>"
# (yükseklik mm). Raporda kalıp kırılımının temeli bu koddur.
KALIPLAR = [
    ('DIA-050', 'Yuvarlak Kutu', 55), ('DIA-068', 'Yuvarlak-Sivama Kutu', 72),
    ('DIA-092', 'Yuvarlak Kutu', 99), ('DIA-148', 'Yuvarlak Kutu', 153),
    ('078-095', 'Yuvarlak Kutu', 100), ('094-050', 'Yuvarlak Kutu', 45),
    ('120-105', 'Yuvarlak Kutu', 110), ('Y120-105', 'Yuvarlak Kutu', 110),
    ('145-095', 'Dikdortgen Kutu', 100), ('158-175', 'Yuvarlak Kutu', 180),
    ('185-115', 'Dikdortgen Kutu', 110), ('210-080', 'Koseli Sivama Kutu', 75),
    ('210-255', 'Yuvarlak Kutu', 260), ('225-165', 'Kare Kutu', 160),
    ('245-175', 'Yuvarlak Kutu', 180), ('255-205', 'Yuvarlak Kutu', 210),
    ('295-165', 'Oval Kutu', 160), ('325-125', 'Tepsi', 120),
    ('125-085', 'Altıgen Kutu', 90), ('135-145', 'Sekizgen Kutu', 140),
    ('160-090', 'Kalp Kutu', 85), ('175-205', 'Sekilli Kutu', 200),
    ('090-065', 'Kapak', 60), ('205-050', 'Plaka-Bardak Alti', 45),
]

KULLANIM_ALANI = [('KA1', 'Gıda'), ('KA2', 'Boya-Kimya'), ('KA3', 'Kozmetik'),
                  ('KA4', 'Hediyelik'), ('KA5', 'Endüstriyel'), ('KA6', 'Bal-Reçel')]
BASKI_TIPI = [('B1', 'Litografi'), ('B2', 'Vernikli'), ('B3', 'Ham Teneke'), ('B4', 'Mat Lak')]
PARCA_SAYISI = [('P2', '2 Parça'), ('P3', '3 Parça')]
KAPAK_TIPI = [('K1', 'Geçme Kapak'), ('K2', 'Vidalı Kapak'), ('K3', 'Kolay Açılır'), ('K4', 'Kapaksız')]

HAMMADDELER = [
    ('Teneke Sac 0,18mm', 'KG'), ('Teneke Sac 0,20mm', 'KG'), ('Teneke Sac 0,22mm', 'KG'),
    ('Krom Sac 0,25mm', 'KG'), ('Beyaz Vernik', 'KG'), ('Altın Vernik', 'KG'),
    ('Ofset Mürekkep Cyan', 'KG'), ('Ofset Mürekkep Magenta', 'KG'),
    ('Ofset Mürekkep Sarı', 'KG'), ('Ofset Mürekkep Siyah', 'KG'),
    ('Conta Bileşimi', 'KG'), ('Tiner', 'LT'), ('Kalıp Yağı', 'LT'),
    ('Lehim Teli', 'KG'), ('Astar Boya', 'KG'), ('Koruyucu Film', 'MT'),
]
DIGER_MALZEME = [
    ('Oluklu Koli 40x30x25', 'ADET'), ('Oluklu Koli 60x40x30', 'ADET'),
    ('Streç Film 500mm', 'RULO'), ('Ahşap Palet 80x120', 'ADET'),
    ('Etiket Rulo 100x50', 'RULO'), ('Bant 48mm', 'ADET'),
    ('Ara Karton', 'ADET'), ('Çember 12mm', 'RULO'),
    ('Kalıp Yedek Zımba', 'ADET'), ('Hidrolik Filtre', 'ADET'),
    ('Rulman 6205', 'ADET'), ('Yağlama Gresi', 'KG'),
]

# Kurgusal firma adları: uydurma kökler + sektör + tüzel ek
FIRMA_KOKLERI = [
    'Ardıçlı', 'Berkant', 'Çınaraltı', 'Denizcan', 'Efelik', 'Fidanlık', 'Gökbayır',
    'Halkalıtaş', 'Irmakkent', 'Jalezade', 'Kavaklıdere', 'Lodoslu', 'Marmarist',
    'Narlıcan', 'Ovacıklı', 'Pınarbaşlı', 'Rüzgarlı', 'Sakarcan', 'Şafaklı',
    'Tuzlalı', 'Uğurcan', 'Ünlüoğlu', 'Vadiköy', 'Yaylalı', 'Zeytinburcu',
    'Akkavak', 'Bozkırlı', 'Cevizli', 'Dörtyollu', 'Erikçi', 'Ferahlı',
    'Gümüşdere', 'Hisarlı', 'İncirli', 'Kartallı', 'Leylakçı', 'Mercanlı',
    'Nilüferli', 'Orhanlı', 'Poyrazlı', 'Sarıçam', 'Toprakçı', 'Umutlu',
    'Vişneli', 'Yıldızcan', 'Zümrütlü', 'Alaçatı', 'Bahçelik', 'Cumbalı', 'Dalyanlı',
]
FIRMA_SEKTOR_EKI = ['Gıda', 'Konserve', 'Boya', 'Kimya', 'Kozmetik', 'Zeytin', 'Bal',
                    'Reçel', 'Çay', 'Kahve', 'Şekerleme', 'Bisküvi', 'Ambalaj',
                    'Endüstri', 'Makine', 'Tarım', 'Süt', 'Salça', 'Turşu', 'Baharat']
FIRMA_TUZEL = ['San. ve Tic. A.Ş.', 'Ltd. Şti.', 'A.Ş.', 'San. Tic. Ltd. Şti.',
               'Gıda San. A.Ş.', 'Koll. Şti.']
YABANCI_FIRMA = ['Nordwind', 'Bluewater', 'Casa Verde', 'Stellamar', 'Grünfeld',
                 'Vantel', 'Orionis', 'Larkspur', 'Meridian', 'Fjordholm',
                 'Terravita', 'Solheim', 'Brightcan', 'Nordtin', 'Aurelia']
YABANCI_EKI = ['Foods GmbH', 'Trading B.V.', 'S.p.A.', 'Ltd.', 'S.A.', 'A/S', 'Oy']

SEKTORLER = ['Gıda', 'Boya-Kimya', 'Kozmetik', 'Zeytin-Zeytinyağı', 'Bal-Reçel',
             'Hediyelik', 'Endüstriyel', 'Süt Ürünleri', 'Baharat']
SEKTOR2 = ['Marka Sahibi', 'Fason Üretici', 'Toptancı', 'İhracatçı', 'Zincir Market']
BOLGELER = ['Marmara', 'İç Anadolu', 'Ege', 'Akdeniz', 'Karadeniz', 'Güneydoğu', 'Doğu Anadolu']
ILLER = ['İstanbul', 'Kocaeli', 'Bursa', 'Ankara', 'Konya', 'İzmir', 'Manisa', 'Aydın',
         'Antalya', 'Mersin', 'Adana', 'Samsun', 'Trabzon', 'Ordu', 'Gaziantep',
         'Şanlıurfa', 'Kayseri', 'Eskişehir', 'Tekirdağ', 'Balıkesir', 'Denizli']
ULKELER = [('DE', 'ALMANYA'), ('NL', 'HOLLANDA'), ('IT', 'İTALYA'), ('FR', 'FRANSA'),
           ('GB', 'İNGİLTERE'), ('DK', 'DANİMARKA'), ('SE', 'İSVEÇ'), ('PL', 'POLONYA'),
           ('SA', 'SUUDİ ARABİSTAN'), ('AE', 'BAE'), ('IQ', 'IRAK'), ('RO', 'ROMANYA')]

# Satış temsilcileri (kurgusal, kısaltılmış ad)
TEMSILCILER = [
    ('Selim K.', 'YURT_ICI', 'YURTICI'), ('Nurhan T.', 'YURT_ICI', 'YURTICI'),
    ('Bahar Ö.', 'YURT_ICI', 'YURTICI'), ('Cem A.', 'YURT_ICI', 'YURTICI'),
    ('Deniz Y.', 'YURT_DISI', 'YURTDISI'), ('Elif S.', 'YURT_DISI', 'YURTDISI'),
    ('Kaan M.', 'BASKILI', 'BASKILI'), ('Pelin R.', 'BASKILI', 'BASKILI'),
]

ODEME_TIPLERI = [
    # (ODEKOD, açıklama, peşinat oranı, vade günü, taksit ofsetleri)
    ('OD01', 'Peşin', 1.00, 0, [0]),
    ('OD02', '30 Gün Vadeli', 0.00, 30, [30]),
    ('OD03', '60 Gün Vadeli', 0.00, 60, [60]),
    ('OD04', '90 Gün Vadeli', 0.00, 90, [90]),
    ('OD05', '%30 Peşin + 60 Gün', 0.30, 60, [0, 60]),
    ('OD06', '%50 Peşin + 45 Gün', 0.50, 45, [0, 45]),
    ('OD07', '120 Gün Vadeli', 0.00, 120, [60, 120]),
    ('OD08', 'Akreditif', 0.20, 75, [0, 45, 90]),
]

TESLIM_YERLERI = ['Fabrika Teslim', 'Müşteri Deposu', 'Liman Teslim (FOB)',
                  'CIF Teslim', 'Antrepo']

# ---- Üretim tarafı: makine parkı (SCADA raporundaki kart filtreleriyle aynı) ----
MAKINELER = [
    # (DEMIR_KODU, DEMIR_ISMI, ISTKODU, ISTISIM)
    ('PRS-01', 'PRES 01 · 63 TON EKSANTRİK', 'PRS', 'PRES'),
    ('PRS-02', 'PRES 02 · 63 TON EKSANTRİK', 'PRS', 'PRES'),
    ('PRS-03', 'PRES 03 · 80 TON EKSANTRİK', 'PRS', 'PRES'),
    ('PRS-04', 'PRES 04 · 80 TON EKSANTRİK', 'PRS', 'PRES'),
    ('PRS-05', 'PRES 05 · 100 TON EKSANTRİK', 'PRS', 'PRES'),
    ('PRS-06', 'PRES 06 · 40 TON SIVAMA', 'PRS', 'PRES'),
    ('PRS-07', 'PRES 07 · 40 TON SIVAMA', 'PRS', 'PRES'),
    ('PRS-08', 'PRES 08 · 63 TON SIVAMA', 'PRS', 'PRES'),
    ('PRS-09', 'PRES 09 · 63 TON SIVAMA', 'PRS', 'PRES'),
    ('PRS-10', 'PRES 10 · 100 TON DERİN ÇEKME', 'PRS', 'PRES'),
    ('PRS-11', 'PRES 11 · 25 TON KAPAK', 'PRS', 'PRES'),
    ('PRS-12', 'PRES 12 · 25 TON KAPAK', 'PRS', 'PRES'),
    ('PRS-13', 'PRES 13 · 35 TON KAPAK', 'PRS', 'PRES'),
    ('PRS-14', 'PRES 14 · 35 TON DİP', 'PRS', 'PRES'),
    ('PRS-15', 'PRES 15 · 35 TON DİP', 'PRS', 'PRES'),
    ('PRS-16', 'PRES 16 · 16 TON KULP', 'PRS', 'PRES'),
    ('PRS-17', 'PRES 17 · 16 TON KULP', 'PRS', 'PRES'),
    ('PRS-18', 'PRES 18 · 20 TON HALKA', 'PRS', 'PRES'),
    ('PRS-19', 'PRES 19 · 20 TON HALKA', 'PRS', 'PRES'),
    ('PRS-20', 'PRES 20 · 45 TON ÇOK KADEMELİ', 'PRS', 'PRES'),
    ('PRS-21', 'PRES 21 · 45 TON ÇOK KADEMELİ', 'PRS', 'PRES'),
    ('PRS-22', 'PRES 22 · 60 TON TRANSFER', 'PRS', 'PRES'),
    ('PRS-23', 'PVC KAPLAMA HATTI 01', 'PRS', 'PRES'),
    ('KSM-01', 'KESİM HATTI 01 · GİYOTİN', 'KSM', 'KESIM'),
    ('KSM-02', 'KESİM HATTI 02 · GİYOTİN', 'KSM', 'KESIM'),
    ('KSM-03', 'KESİM HATTI 03 · DİLİMLEME', 'KSM', 'KESIM'),
    ('KSM-04', 'KESİM HATTI 04 · DİLİMLEME', 'KSM', 'KESIM'),
    ('KSM-05', 'KESİM HATTI 06 · KÖŞE KESME', 'KSM', 'KESIM'),
    ('KSM-06', 'KESİM HATTI 07 · KÖŞE KESME', 'KSM', 'KESIM'),
    ('MTB-01', 'OFSET BASKI 01 · 4 RENK', 'MTB', 'MATBAA'),
    ('MTB-02', 'OFSET BASKI 02 · 4 RENK', 'MTB', 'MATBAA'),
    ('MTB-03', 'OFSET BASKI 03 · 2 RENK + VERNİK', 'MTB', 'MATBAA'),
    ('MNT-01', 'MONTAJ HATTI 01 · OTOMATİK', 'MNT', 'MONTAJ'),
    ('MNT-02', 'MONTAJ HATTI 02 · OTOMATİK', 'MNT', 'MONTAJ'),
    ('MNT-03', 'MONTAJ HATTI 03 · OTOMATİK', 'MNT', 'MONTAJ'),
    ('MNT-04', 'MONTAJ HATTI 04 · YARI OTOMATİK', 'MNT', 'MONTAJ'),
    ('MNT-05', 'MONTAJ HATTI 05 · YARI OTOMATİK', 'MNT', 'MONTAJ'),
    ('MNT-06', 'MONTAJ HATTI 06 · YARI OTOMATİK', 'MNT', 'MONTAJ'),
    ('MNT-07', 'MONTAJ HATTI 08 · SIVAMA', 'MNT', 'MONTAJ'),
    ('MNT-08', 'MONTAJ HATTI 09 · SIVAMA', 'MNT', 'MONTAJ'),
    ('MNT-09', 'MONTAJ HATTI 10 · KAPAK', 'MNT', 'MONTAJ'),
    ('MNT-10', 'MONTAJ HATTI 11 · KAPAK', 'MNT', 'MONTAJ'),
    ('MNT-11', 'MONTAJ HATTI 13 · ÖZEL ŞEKİL', 'MNT', 'MONTAJ'),
    ('MNT-12', 'MONTAJ HATTI 14 · ÖZEL ŞEKİL', 'MNT', 'MONTAJ'),
    ('DJT-01', 'DİJİTAL BASKI 01', 'DJT', 'DIJITAL'),
    ('DJT-02', 'DİJİTAL BASKI 02', 'DJT', 'DIJITAL'),
    ('MNT-13', 'MANUEL SARIM 01', 'MNT', 'MONTAJ'),
    ('MNT-14', 'MANUEL SARIM 02', 'MNT', 'MONTAJ'),
]

# Puantaj / vardiya grupları (SCADA dilimleyicileriyle aynı değerler)
CALISMA_GRUPLARI = ['PRES', 'KESİM', 'MATBAA', 'DİJİTAL', 'MONTAJ',
                    'MONTAJ_USTA', 'MONTAJ_MEYDAN']

GOREVLER = [('BANT_LIDERI', 'BANT LİDERİ'), ('SEKILLENDIRME', 'ŞEKİLLENDİRME'),
            ('KALITECI', 'KALİTECİ'), ('PAKETLEMECI', 'PAKETLEMECİ'),
            ('PRES_OPR', 'PRES OPERATÖRÜ'), ('PRES_ISTIFLEYICI', 'PRES İSTİFLEYİCİ'),
            ('MAKAS_OPR', 'MAKAS OPERATÖRÜ'), ('BASKI_OPR', 'BASKI OPERATÖRÜ')]

ARIZA_TIPLERI = [
    ('AR01', 'Kalıp Değişimi', 34), ('AR02', 'Elektrik Arızası', 8),
    ('AR03', 'Mekanik Arıza', 12), ('AR04', 'Hidrolik Kaçak', 5),
    ('AR05', 'Ayar / Numune Onayı', 14), ('AR06', 'Malzeme Bekleme', 10),
    ('AR07', 'Sac Sıkışması', 7), ('AR08', 'Planlı Bakım', 6),
    ('AR09', 'Vardiya Devri', 8), ('AR10', 'Enerji Kesintisi', 2),
    ('AR11', 'Kalite Duruşu', 6), ('AR12', 'Personel Yetersizliği', 4),
]

AKTIVITELER = [('A01', 'HAZIRLIK'), ('A02', 'ISLEM'), ('A03', 'DURMA')]

ISLEM_DURUMLARI = ['ISLEM', 'HAZIRLIK', 'ARIZA/DURUŞ', 'PASIF', 'TAMAMLANDI', 'KAPATILDI']

DURUM_KODLARI = [('10', 'PLANLANDI'), ('20', 'ÜRETİMDE'), ('30', 'TAMAMLANDI'),
                 ('40', 'KAPATILDI'), ('50', 'İPTAL')]

# --------------------------------------------------------------------------
# Yardımcılar
# --------------------------------------------------------------------------


def agirlikli_sec(rnd, secenekler):
    """[(deger, agirlik), ...] listesinden ağırlıklı seçim."""
    toplam = sum(a for _, a in secenekler)
    r = rnd.random() * toplam
    for deger, a in secenekler:
        r -= a
        if r <= 0:
            return deger
    return secenekler[-1][0]


# Dolar kuru çıpaları (yıl, ay) -> kur. Aradaki günler doğrusal enterpolasyon.
KUR_CIPALARI = [
    (2012, 1, 1.85), (2014, 1, 2.20), (2016, 1, 2.95), (2018, 1, 3.78),
    (2019, 1, 5.30), (2020, 1, 5.95), (2021, 1, 7.40), (2022, 1, 13.50),
    (2022, 7, 17.35), (2023, 1, 18.80), (2023, 7, 26.10), (2024, 1, 29.80),
    (2024, 7, 32.90), (2025, 1, 35.60), (2025, 7, 40.20), (2026, 1, 44.10),
    (2026, 7, 47.60), (2027, 1, 51.00), (2030, 12, 62.00),
]


def kur(tarih):
    """Verilen tarih için kurgusal USD/TRY kuru."""
    x = tarih.year * 12 + tarih.month
    onceki = KUR_CIPALARI[0]
    for c in KUR_CIPALARI:
        cx = c[0] * 12 + c[1]
        if cx >= x:
            px = onceki[0] * 12 + onceki[1]
            if cx == px:
                return c[2]
            t = (x - px) / (cx - px)
            return round(onceki[2] + (c[2] - onceki[2]) * t, 4)
        onceki = c
    return KUR_CIPALARI[-1][2]


def is_gunu_mu(d):
    return d.weekday() < 5


def hafta_no(d):
    return d.isocalendar()[1]


def csv_yaz(yol, basliklar, satirlar):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter=',', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        w.writerow(basliklar)
        for s in satirlar:
            w.writerow([bicimle(s.get(b)) for b in basliklar])
    print(f'   {os.path.relpath(yol, KOK):68s} {len(satirlar):>8,} satır')


def bicimle(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, dt.datetime):
        return v.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(v, dt.date):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return f'{v:.4f}'.rstrip('0').rstrip('.')
    return str(v)


# --------------------------------------------------------------------------
# Ana üretim
# --------------------------------------------------------------------------


class Uretec:
    def __init__(self, bugun, olcek):
        self.bugun = bugun
        self.olcek = olcek
        self.rnd = random.Random(RASTGELE_TOHUM)
        self.veri_basi = dt.date(bugun.year - 3, 1, 2)   # ~3,5 yıl ticari veri
        self.uretim_basi = bugun - dt.timedelta(days=400)  # üretim tarafı 400 gün

    # ---------------------------------------------------------------- stok
    def stok_uret(self):
        rnd = self.rnd
        self.stok = []
        self.mamul = []
        self.hammadde = []
        self.diger = []

        mamul_sayisi = max(60, int(330 * self.olcek))
        for i in range(mamul_sayisi):
            kalip, sekil_varsayilan, yukseklik = rnd.choice(KALIPLAR)
            # kalıbın doğal şekli çoğunlukla korunur, %15 sapma (ERP gerçeği)
            if rnd.random() < 0.15:
                ad1 = agirlikli_sec(rnd, [(a, w) for a, _, w in SEKILLER])
            else:
                ad1 = sekil_varsayilan
            kod1 = next(k for a, k, _ in SEKILLER if a == ad1)
            ka_kod, ka_ad = rnd.choice(KULLANIM_ALANI)
            b_kod, b_ad = rnd.choice(BASKI_TIPI)
            p_kod, p_ad = rnd.choice(PARCA_SAYISI)
            k_kod, k_ad = rnd.choice(KAPAK_TIPI)
            kod = f'M{i + 1:05d}'
            olcu = kalip.replace('DIA-', 'Ø')
            adi = f'{ad1.upper()} {olcu} {b_ad.upper()} {p_ad.upper()}'
            ing = (f'{ad1.replace("Kutu", "Tin").replace("Sivama", "Drawn")} '
                   f'{olcu} {b_ad} {p_ad.replace("Parça", "pc")}')
            koli_adet = rnd.choice([12, 24, 48, 60, 100])
            s = {
                'STOK_KODU': kod, 'STOK_ADI': adi,
                'GRUP_KODU': '01', 'GRUP_ADI': 'Mamul',
                'KOD_1': kod1, 'AD1': ad1,
                'KOD_2': ka_kod, 'AD2': ka_ad,
                'KOD_3': kalip, 'AD3': f'Kalıp {kalip}',
                'KOD_4': b_kod, 'AD4': b_ad,
                'KOD_5': p_kod, 'AD5': p_ad,
                'INGISIM': ing,
                'KT_YUKSEKLIK': float(yukseklik),
                'OLCU_BR1': 'ADET', 'OLCU_BR2': 'KOLİ', 'OLCU_BR3': 'PALET',
                'BIRIM2_CARPAN': float(koli_adet),
                'BIRIM3_CARPAN': float(koli_adet * rnd.choice([20, 24, 30])),
                '_kapak': k_ad,
                '_yukseklik': yukseklik,
                '_taban_fiyat': round(rnd.uniform(0.9, 14.0) * (1 + yukseklik / 320), 3),
            }
            s['BIRIM_MALIYET'] = round(s['_taban_fiyat'] * rnd.uniform(0.55, 0.78), 4)
            self.stok.append(s)
            self.mamul.append(s)

        for i, (ad, br) in enumerate(HAMMADDELER):
            s = {'STOK_KODU': f'H{i + 1:05d}', 'STOK_ADI': ad.upper(),
                 'GRUP_KODU': '02', 'GRUP_ADI': 'Hammadde',
                 'KOD_1': 'HM', 'AD1': 'Hammadde',
                 'KOD_2': 'HM1', 'AD2': 'Sac' if 'Sac' in ad else 'Kimyasal',
                 'KOD_3': '', 'AD3': '', 'KOD_4': '', 'AD4': '', 'KOD_5': '', 'AD5': '',
                 'INGISIM': ad, 'KT_YUKSEKLIK': None,
                 'OLCU_BR1': br, 'OLCU_BR2': 'TON' if br == 'KG' else br, 'OLCU_BR3': '',
                 'BIRIM2_CARPAN': 1000.0 if br == 'KG' else 1.0, 'BIRIM3_CARPAN': None,
                 'BIRIM_MALIYET': round(self.rnd.uniform(12, 78), 3),
                 '_taban_fiyat': round(self.rnd.uniform(14, 96), 3)}
            self.stok.append(s)
            self.hammadde.append(s)

        for i, (ad, br) in enumerate(DIGER_MALZEME):
            s = {'STOK_KODU': f'D{i + 1:05d}', 'STOK_ADI': ad.upper(),
                 'GRUP_KODU': '03', 'GRUP_ADI': 'DIGER',
                 'KOD_1': 'DG', 'AD1': 'Diğer',
                 'KOD_2': 'DG1', 'AD2': 'Yardımcı Malzeme',
                 'KOD_3': '', 'AD3': '', 'KOD_4': '', 'AD4': '', 'KOD_5': '', 'AD5': '',
                 'INGISIM': ad, 'KT_YUKSEKLIK': None,
                 'OLCU_BR1': br, 'OLCU_BR2': br, 'OLCU_BR3': '',
                 'BIRIM2_CARPAN': 1.0, 'BIRIM3_CARPAN': None,
                 'BIRIM_MALIYET': round(self.rnd.uniform(2, 240), 3),
                 '_taban_fiyat': round(self.rnd.uniform(3, 300), 3)}
            self.stok.append(s)
            self.diger.append(s)

        # ciro/adet dağılımı çarpık olsun: az sayıda ürün cironun çoğunu yapsın
        for i, s in enumerate(self.mamul):
            s['_populerlik'] = 1.0 / (i * 0.35 + 1.0) ** 1.35
        print(f'   stok: {len(self.stok)} kart ({len(self.mamul)} mamul)')

    # ---------------------------------------------------------------- cari
    def cari_uret(self):
        rnd = self.rnd
        self.cari = []
        kullanilan = set()

        def ad_uret(yabanci=False):
            for _ in range(200):
                if yabanci:
                    ad = f'{rnd.choice(YABANCI_FIRMA)} {rnd.choice(YABANCI_EKI)}'
                else:
                    ad = (f'{rnd.choice(FIRMA_KOKLERI)} {rnd.choice(FIRMA_SEKTOR_EKI)} '
                          f'{rnd.choice(FIRMA_TUZEL)}')
                if ad not in kullanilan:
                    kullanilan.add(ad)
                    return ad
            return ad

        musteri_sayisi = max(40, int(140 * self.olcek))
        tedarikci_sayisi = max(15, int(55 * self.olcek))

        for i in range(musteri_sayisi):
            # %72 yurtiçi, %18 yurtdışı, %10 BASKILI (stoktan baskılı satış iş kolu)
            r = rnd.random()
            if r < 0.72:
                dept, grup = 'YURTICI', 'YURT_ICI'
            elif r < 0.90:
                dept, grup = 'YURTDISI', 'YURT_DISI'
            else:
                dept, grup = 'BASKILI', 'BASKILI'
            yabanci = dept == 'YURTDISI'
            if yabanci:
                uk, ua = rnd.choice(ULKELER)
                yer = ua.title()
                bolge = 'Avrupa' if uk not in ('SA', 'AE', 'IQ') else 'Ortadoğu'
            else:
                uk, ua = 'TR', 'TÜRKİYE'
                yer = rnd.choice(ILLER)
                bolge = rnd.choice(BOLGELER)
            temsilci = rnd.choice([t for t in TEMSILCILER if t[2] == dept] or TEMSILCILER)
            self.cari.append({
                'CARI_KOD': f'120.01.{i + 1:04d}', 'CARI_AD': ad_uret(yabanci),
                'ULKE_KODU': uk, 'ULKEADI': ua,
                'GRUP_KODU': 'MG1' if not yabanci else 'MG2',
                'SEKTOR': rnd.choice(SEKTORLER), 'RAPOR_KODU1': f'R1-{rnd.randint(1, 9)}',
                'BOLGE': bolge, 'RAPOR_KODU2': f'R2-{rnd.randint(1, 6)}',
                'SEKTOR2': rnd.choice(SEKTOR2), 'RAPOR_KODU3': f'R3-{rnd.randint(1, 4)}',
                'CARI_TEMSILCI': temsilci[0], 'DEPARTMAN': dept,
                'CARI_TIPI': 'MUSTERI', 'MUSTERI_YERI': yer,
                '_temsilci': temsilci[0], '_temsilci_grup': temsilci[1],
                '_buyukluk': 1.0 / (i * 0.28 + 1.0) ** 1.2,
            })

        for i in range(tedarikci_sayisi):
            yabanci = rnd.random() < 0.22
            if yabanci:
                uk, ua = rnd.choice(ULKELER)
                yer, bolge = ua.title(), 'Avrupa'
            else:
                uk, ua = 'TR', 'TÜRKİYE'
                yer, bolge = rnd.choice(ILLER), rnd.choice(BOLGELER)
            self.cari.append({
                'CARI_KOD': f'320.01.{i + 1:04d}', 'CARI_AD': ad_uret(yabanci),
                'ULKE_KODU': uk, 'ULKEADI': ua, 'GRUP_KODU': 'TG1',
                'SEKTOR': 'Endüstriyel', 'RAPOR_KODU1': f'R1-{rnd.randint(1, 9)}',
                'BOLGE': bolge, 'RAPOR_KODU2': f'R2-{rnd.randint(1, 6)}',
                'SEKTOR2': 'Tedarikçi', 'RAPOR_KODU3': 'R3-1',
                'CARI_TEMSILCI': 'Satın Alma', 'DEPARTMAN': 'SATINALMA',
                'CARI_TIPI': 'TEDARIKCI', 'MUSTERI_YERI': yer,
                '_buyukluk': 1.0 / (i * 0.3 + 1.0) ** 1.1,
            })
        self.musteriler = [c for c in self.cari if c['CARI_TIPI'] == 'MUSTERI']
        self.tedarikciler = [c for c in self.cari if c['CARI_TIPI'] == 'TEDARIKCI']
        print(f'   cari: {len(self.musteriler)} müşteri, {len(self.tedarikciler)} tedarikçi')

    # ------------------------------------------------------------ siparis
    def siparis_uret(self):
        """Sipariş satırları + ödeme planı + sevkiyat/fatura (ciro)."""
        rnd = self.rnd
        self.siparis = []
        self.siparis_odeme = []
        self.ciro = []
        inckey = 100000
        ciro_fis = 500000
        musteri_sayac = defaultdict(int)
        fis_sayac = defaultdict(int)

        gun = self.veri_basi
        hedef_gunluk = 6.5 * self.olcek
        while gun <= self.bugun:
            if not is_gunu_mu(gun):
                gun += dt.timedelta(days=1)
                continue
            # mevsimsellik: son çeyrek yoğun, ağustos düşük
            mevsim = {1: .85, 2: .9, 3: 1.0, 4: 1.05, 5: 1.1, 6: 1.05,
                      7: .95, 8: .7, 9: 1.1, 10: 1.2, 11: 1.25, 12: 1.05}[gun.month]
            buyume = 1.0 + (gun - self.veri_basi).days / 1400.0
            adet = max(0, int(rnd.gauss(hedef_gunluk * mevsim * buyume, 2.2)))
            for _ in range(adet):
                musteri = agirlikli_sec(rnd, [(c, c['_buyukluk']) for c in self.musteriler])
                musteri_sayac[musteri['CARI_KOD']] += 1
                kacinci = musteri_sayac[musteri['CARI_KOD']]
                odeme = rnd.choice(ODEME_TIPLERI)
                # fiş no: stok satışı / baskılı stok satışı / üretim siparişi
                r = rnd.random()
                onek = 'STKB' if r < 0.06 else ('STK' if r < 0.18 else 'SIP')
                fis_sayac[onek] += 1
                fisno = f'{onek}{gun.year % 100:02d}{fis_sayac[onek]:06d}'
                satir_sayisi = agirlikli_sec(rnd, [(1, 55), (2, 25), (3, 12), (4, 6), (5, 2)])
                kur_g = kur(gun)
                for sira in range(1, satir_sayisi + 1):
                    urun = agirlikli_sec(rnd, [(s, s['_populerlik']) for s in self.mamul])
                    koli = urun['BIRIM2_CARPAN'] or 24
                    miktar = float(rnd.choice([6, 12, 20, 30, 50, 80, 120, 200]) * koli)
                    fiyat_tl = round(urun['_taban_fiyat'] * kur_g *
                                     rnd.uniform(0.92, 1.18), 4)
                    tutar_tl = miktar * fiyat_tl
                    tutar_usd = round(tutar_tl / kur_g, 4)
                    # sevkiyat durumu: eski siparişler kapanmış olur
                    gecen = (self.bugun - gun).days
                    if gecen > 120:
                        oran = 1.0 if rnd.random() < 0.94 else rnd.uniform(0.5, 0.99)
                    elif gecen > 45:
                        oran = 1.0 if rnd.random() < 0.7 else rnd.uniform(0.2, 0.95)
                    else:
                        oran = rnd.choice([0.0, 0.0, 0.25, 0.5, 0.75, 1.0])
                    gonderilen = round(miktar * oran, 2)
                    kalan = round(miktar - gonderilen, 2)
                    inckey += 1
                    kayit = {
                        'INCKEYNO': inckey, 'STHAR_TARIH': gun, 'FISNO': fisno, 'SIRA': sira,
                        'STOK_KODU': urun['STOK_KODU'], 'STHAR_CARIKOD': musteri['CARI_KOD'],
                        'STHAR_GCMIK': miktar, 'STHAR_NF': fiyat_tl,
                        'GONDERILEN': gonderilen, 'KALAN': kalan,
                        'SIPARIS_TEMSILCI': musteri['_temsilci'],
                        'DEPARTMAN': musteri['_temsilci_grup'],
                        'STHAR_GCKOD': '1', 'DOLAR_KURU': kur_g,
                        'STHAR_KOD1': urun['KOD_1'], 'STHAR_KOD2': urun['KOD_2'],
                        'TUTAR_USD': tutar_usd,
                        'DURUM': 'ACIK' if kalan > 0.5 else 'KAPALI',
                        'YIL': gun.year, 'AY': gun.month, 'HAFTA': hafta_no(gun),
                        'ODEKOD': odeme[0], 'ODEME_ACIKLAMA': odeme[1],
                        'PESINAT_ORANI': odeme[2], 'VADE_GUNU': odeme[3],
                        'PESIN_TUTAR': round(tutar_usd * odeme[2], 4),
                        'VADELI_TUTAR': round(tutar_usd * (1 - odeme[2]), 4),
                        'RPT': 1 if rnd.random() < 0.78 else 0,
                        'KACINCI_SIPARIS': kacinci,
                        'MUSTERI_SIP_NO': f'PO-{rnd.randint(10000, 99999)}',
                        'TESLIM_YERI': rnd.choice(TESLIM_YERLERI),
                        'EK_ACIKLAMA_1': urun['_kapak'],
                        'EK_ACIKLAMA_2': f'{int(koli)} adet/koli',
                        'EK_ACIKLAMA_3_MALZEME': rnd.choice(
                            ['Teneke 0,18mm', 'Teneke 0,20mm', 'Teneke 0,22mm', 'Krom 0,25mm']),
                        'EK_ACIKLAMA_4': rnd.choice(['Paletli', 'Kolili', 'Dökme']),
                        'EK_ACIKLAMA_5': rnd.choice(['', '', 'Numune onaylı', 'Acil']),
                        '_urun': urun, '_musteri': musteri, '_gonderilen': gonderilen,
                        '_fiyat': fiyat_tl,
                    }
                    self.siparis.append(kayit)
                    self._odeme_plani_ekle(kayit, odeme)
                    if gonderilen > 0:
                        ciro_fis += 1
                        self._ciro_ekle(kayit, ciro_fis)
            gun += dt.timedelta(days=1)
        print(f'   sipariş: {len(self.siparis)} satır, ciro: {len(self.ciro)} satır, '
              f'ödeme planı: {len(self.siparis_odeme)} satır')

    def _odeme_plani_ekle(self, sip, odeme):
        rnd = self.rnd
        ofsetler = odeme[4]
        n = len(ofsetler)
        oranlar = ([odeme[2]] + [(1 - odeme[2]) / (n - 1)] * (n - 1)) if n > 1 else [1.0]
        tutar_tl = sip['STHAR_GCMIK'] * sip['STHAR_NF']
        for i, ofset in enumerate(ofsetler):
            oran = round(oranlar[i], 4)
            od_tarih = sip['STHAR_TARIH'] + dt.timedelta(days=ofset)
            net_tl = round(tutar_tl * oran, 4)
            kdvli_tl = round(net_tl * 1.20, 4)
            k = sip['DOLAR_KURU']
            self.siparis_odeme.append({
                'INCKEYNO': sip['INCKEYNO'], 'FISNO': sip['FISNO'], 'SIRA': sip['SIRA'],
                'STHAR_TARIH': sip['STHAR_TARIH'], 'ODEKOD': odeme[0],
                'OFSET': ofset, 'ORAN': oran, 'ODEME_TARIHI': od_tarih,
                'ODEME_TUTARI_TL': net_tl, 'ODEME_TUTAR_USD': round(net_tl / k, 4),
                'KDV_ORANI': 0.20,
                'ODEME_TUTARI_KDVLI_TL': kdvli_tl,
                'ODEME_TUTARI_KDVLI_USD': round(kdvli_tl / k, 4),
                'BIRIM_FIYAT_TL': sip['STHAR_NF'],
                'BIRIM_FIYAT_USD': round(sip['STHAR_NF'] / k, 6),
                'ODEME_TUTARI_NET_TL': net_tl,
                'ODEME_TUTARI_NET_USD': round(net_tl / k, 4),
            })

    def _ciro_ekle(self, sip, fis):
        """Sevk edilen miktar için fatura satırı (ciro)."""
        rnd = self.rnd
        gecikme = rnd.randint(3, 45)
        f_tarih = min(sip['STHAR_TARIH'] + dt.timedelta(days=gecikme), self.bugun)
        k = kur(f_tarih)
        miktar = sip['_gonderilen']
        urun = sip['_urun']
        musteri = sip['_musteri']
        koli = urun['BIRIM2_CARPAN'] or 24
        fiyat = round(sip['_fiyat'] * rnd.uniform(0.99, 1.03), 4)
        self.ciro.append({
            'STOK_KODU': urun['STOK_KODU'], 'STHAR_CARIKOD': musteri['CARI_KOD'],
            'FISNO': f'FT{f_tarih.year % 100:02d}{fis:06d}', 'STHAR_TARIH': f_tarih,
            'STHAR_GCMIK': miktar, 'STHAR_GCMIK2': round(miktar / koli, 2),
            'STHAR_NF': fiyat, 'STHAR_GCKOD': '4', 'DOLAR_KURU': k,
            'TUTAR_USD': round(miktar * fiyat / k, 4),
            'YIL': f_tarih.year, 'AY': f_tarih.month,
            'STHAR_SIPNUM': sip['FISNO'], 'STRA_SIPKONT': sip['SIRA'],
            'SIP_INC': sip['INCKEYNO'],
            'AY_BASLANGICI': dt.date(f_tarih.year, f_tarih.month, 1),
            'SIPARIS_TEMSILCISI': musteri['_temsilci'],
            'TEMSILCI_GRUP': musteri['_temsilci_grup'],
        })

    # -------------------------------------------------------- satın alma
    def satinalma_uret(self):
        rnd = self.rnd
        self.satinalma_siparis = []
        self.satin_alma = []
        inckey = 700000
        fis = 0
        alinabilir = self.hammadde + self.diger
        gun = self.veri_basi
        while gun <= self.bugun:
            if not is_gunu_mu(gun):
                gun += dt.timedelta(days=1)
                continue
            adet = max(0, int(rnd.gauss(3.4 * self.olcek, 1.3)))
            for _ in range(adet):
                ted = agirlikli_sec(rnd, [(c, c['_buyukluk']) for c in self.tedarikciler])
                fis += 1
                fisno = f'SAS{gun.year % 100:02d}{fis:06d}'
                kur_g = kur(gun)
                htur = 'İTHAL' if ted['ULKE_KODU'] != 'TR' else 'YERLİ'
                for sira in range(1, rnd.choice([1, 1, 2, 2, 3]) + 1):
                    mal = rnd.choice(alinabilir)
                    miktar = float(rnd.choice([500, 1000, 2000, 5000, 10000, 250, 120]))
                    fiyat = round(mal['_taban_fiyat'] * kur_g / 30 *
                                  rnd.uniform(0.9, 1.15), 4)
                    termin = gun + dt.timedelta(days=rnd.choice([10, 15, 21, 30, 45, 60, 90]))
                    gecen = (self.bugun - gun).days
                    if termin < self.bugun and rnd.random() < 0.9:
                        alinan = miktar
                    elif gecen > 20:
                        alinan = round(miktar * rnd.choice([0.0, 0.5, 1.0]), 2)
                    else:
                        alinan = 0.0
                    kalan = round(miktar - alinan, 2)
                    inckey += 1
                    tutar_usd = round(miktar * fiyat / kur_g, 4)
                    self.satinalma_siparis.append({
                        'INCKEYNO': inckey, 'STHAR_TARIH': gun, 'FISNO': fisno, 'SIRA': sira,
                        'STOK_KODU': mal['STOK_KODU'], 'STHAR_CARIKOD': ted['CARI_KOD'],
                        'STHAR_GCMIK': miktar, 'STHAR_NF': fiyat, 'ALINAN': alinan,
                        'STHAR_HTUR': htur, 'TERMIN': termin,
                        'SIPARIS_TARIHINDEN_GECEN_GUN': (self.bugun - gun).days,
                        'TERMINE_KALAN_GUN': (termin - self.bugun).days if kalan > 0 else None,
                        'KALAN': kalan, 'STHAR_GCKOD': '2', 'DOLAR_KURU': kur_g,
                        'STHAR_KOD1': mal['GRUP_KODU'], 'STHAR_KOD2': mal['KOD_2'],
                        'TUTAR_USD': tutar_usd,
                        'DURUM': 'ACIK' if kalan > 0.5 else 'KAPALI',
                        'YIL': gun.year, 'AY': gun.month, 'HAFTA': hafta_no(gun),
                    })
                    if alinan > 0:
                        kabul = min(termin + dt.timedelta(days=rnd.randint(-3, 12)), self.bugun)
                        kk = kur(kabul)
                        self.satin_alma.append({
                            'STOK_KODU': mal['STOK_KODU'], 'CARI_KOD': ted['CARI_KOD'],
                            'FISNO': f'IRS{kabul.year % 100:02d}{inckey % 1000000:06d}',
                            'TARIH': kabul, 'MIKTAR1': alinan,
                            'MIKTAR2': round(alinan / (mal['BIRIM2_CARPAN'] or 1), 3),
                            'NET_FIYAT': fiyat, 'STHAR_GCKOD': '1', 'STHAR_HTUR': htur,
                            'DOLAR_KURU': kk,
                            'STHAR_ACIKLAMA': rnd.choice(
                                ['Mal kabul', 'Kısmi teslim', 'Sevk irsaliyesi',
                                 'İthalat dosyası', 'Numune kabul']),
                            'EKALAN': rnd.choice(['E', 'H']),
                            'EKALAN1': rnd.choice(['', 'Kalite onaylı', 'Şartlı kabul']),
                            'TUTAR_USD': round(alinan * fiyat / kk, 4),
                            'ODE_GUN': rnd.choice([0, 30, 45, 60, 90]),
                            'YIL': kabul.year, 'AY': kabul.month, 'HAFTA': hafta_no(kabul),
                        })
            gun += dt.timedelta(days=1)
        print(f'   satın alma: {len(self.satinalma_siparis)} sipariş satırı, '
              f'{len(self.satin_alma)} mal kabul satırı')

    # ---------------------------------------------------------- cari bakiye
    def bakiye_uret(self):
        rnd = self.rnd
        # Bakiyelerin azınlığı ters tarafta durur: fazla tahsilat ya da alınan
        # avans yüzünden müşteri borçlu, peşin ödenen avans ya da iade dekontu
        # yüzünden tedarikçi alacaklı görünür. Aksi hâlde "Müşteri Borçları" ve
        # "Tedarikçi Alacakları" görselleri tanım gereği hep boş kalır.
        # Ayrı ve sabit tohumlu üreteç: ana rnd akışı kaymasın, dolayısıyla
        # diğer tabloların çıktısı bu değişiklikten etkilenmesin.
        ters = random.Random(RASTGELE_TOHUM + 977)
        self.alacak_borc = []
        son_kur = kur(self.bugun)
        # müşteri bazlı açık fatura tutarından kaba bakiye
        musteri_ciro = defaultdict(float)
        for c in self.ciro:
            if (self.bugun - c['STHAR_TARIH']).days < 150:
                musteri_ciro[c['STHAR_CARIKOD']] += c['TUTAR_USD'] * c['DOLAR_KURU']
        ted_alim = defaultdict(float)
        for s in self.satin_alma:
            if (self.bugun - s['TARIH']).days < 150:
                ted_alim[s['CARI_KOD']] += s['TUTAR_USD'] * s['DOLAR_KURU']

        for c in self.cari:
            if c['CARI_TIPI'] == 'MUSTERI':
                taban = musteri_ciro.get(c['CARI_KOD'], 0.0)
                alacak = round(taban * rnd.uniform(0.15, 0.55), 2)
                borc = round(taban * rnd.uniform(0.0, 0.08), 2)
                if ters.random() < TERS_BAKIYE_ORANI:
                    borc = round(taban * ters.uniform(0.06, 0.30), 2)
                    alacak = round(taban * ters.uniform(0.0, 0.04), 2)
            else:
                taban = ted_alim.get(c['CARI_KOD'], 0.0)
                borc = round(taban * rnd.uniform(0.2, 0.6), 2)
                alacak = round(taban * rnd.uniform(0.0, 0.1), 2)
                if ters.random() < TERS_BAKIYE_ORANI:
                    alacak = round(taban * ters.uniform(0.08, 0.35), 2)
                    borc = round(taban * ters.uniform(0.0, 0.05), 2)
            bakiye = round(alacak - borc, 2)
            if abs(bakiye) < 1:
                continue
            son_tarih = self.bugun - dt.timedelta(days=rnd.randint(0, 240))
            self.alacak_borc.append({
                'CARI_KOD': c['CARI_KOD'], 'SON_TARIH': son_tarih,
                'ALACAK_TL': alacak, 'BORC_TL': borc, 'BAKIYE_TL': bakiye,
                'KUR': kur(son_tarih), 'SONGUNKU_KUR': son_kur,
                'DURUM': 'ALACAK' if bakiye >= 0 else 'BORC',
                'BAKIYE_USD': round(bakiye / son_kur, 2),
                'MUTLAK_USD': round(abs(bakiye) / son_kur, 2),
            })
        print(f'   cari bakiye: {len(self.alacak_borc)} satır')

    # ------------------------------------------------------------- üretim
    def uretim_uret(self):
        """İş emirleri, makine kayıtları, duruş/arıza ve anlık OEE durumu."""
        rnd = self.rnd
        self.isemri = []
        self.uretim2 = []
        self.uak = []
        self.arizalar = []
        self.puantaj = []
        self.puantaj_gunluk = []
        self.oee = []
        self.calisan_sayisi = []

        makine_ist = {m[0]: (m[2], m[3]) for m in MAKINELER}
        takip = 900000
        uak_inc = 3000000
        ariza_inc = 4000000
        # sevk edilmiş/açık siparişlerden iş emri türet
        havuz = [s for s in self.siparis
                 if s['STHAR_TARIH'] >= self.uretim_basi - dt.timedelta(days=60)]
        rnd.shuffle(havuz)
        hedef = max(200, int(2400 * self.olcek))
        havuz = havuz[:hedef]

        for sip in havuz:
            urun = sip['_urun']
            musteri = sip['_musteri']
            # iş emri: kesim -> baskı -> pres -> montaj zincirinden bir operasyon
            zincir = rnd.choice([
                ['KSM', 'MTB', 'PRS', 'MNT'], ['KSM', 'PRS', 'MNT'],
                ['KSM', 'MTB', 'MNT'], ['KSM', 'DJT', 'PRS', 'MNT'],
            ])
            bas = sip['STHAR_TARIH'] + dt.timedelta(days=rnd.randint(2, 40))
            if bas < self.uretim_basi:
                bas = self.uretim_basi + dt.timedelta(days=rnd.randint(0, 30))
            bas_dt = dt.datetime.combine(bas, dt.time(0, 0))
            for op_sira, ist in enumerate(zincir, start=1):
                mk = rnd.choice([m for m in MAKINELER if m[2] == ist])
                takip += 1
                op_bas = bas_dt + dt.timedelta(days=op_sira - 1,
                                               hours=rnd.randint(6, 20),
                                               minutes=rnd.choice([0, 15, 30, 45]))
                if op_bas.date() > self.bugun:
                    continue
                miktar = sip['STHAR_GCMIK'] * rnd.uniform(1.0, 1.06)
                std_sure = max(0.4, 60000.0 / max(400, miktar) * rnd.uniform(0.8, 1.3))
                hazirlik = round(rnd.uniform(18, 145), 1)
                islem = round(miktar / rnd.uniform(55, 320), 1)
                ariza_sure = round(max(0, rnd.gauss(24, 34)), 1)
                hatbos = round(max(0, rnd.gauss(9, 14)), 1)
                fire_oran = abs(rnd.gauss(0.019, 0.014))
                uretilen = round(miktar * (1 - fire_oran), 0)
                fire = round(miktar - uretilen, 0)
                bitis = op_bas + dt.timedelta(minutes=hazirlik + islem + ariza_sure + hatbos)
                bitti = bitis.date() <= self.bugun - dt.timedelta(days=1)
                kapatildi = 'E' if bitti and rnd.random() < 0.86 else rnd.choice(['O', 'H'])
                durum_kod, durum_ad = (DURUM_KODLARI[2] if bitti else DURUM_KODLARI[1])
                isemrino = f'IE{op_bas.year % 100:02d}{takip % 1000000:06d}'
                verimtakip = 'E' if ist in ('PRS', 'MNT') else 'H'

                self.isemri.append({
                    'TAKIPNO': takip, 'ISEMRINO': isemrino,
                    'KALIPADI': urun['KOD_3'] or 'STD',
                    'STOK_KODU': urun['STOK_KODU'], 'STOK_ADI': urun['STOK_ADI'],
                    'CARI_KOD': musteri['CARI_KOD'], 'CARI_ISIM': musteri['CARI_AD'],
                    'SIPARIS_NO': sip['FISNO'], 'REFISEMRINO': f'RF{takip % 1000000:06d}',
                    'SIPARIS_KONT': sip['SIRA'], 'OPKODU': f'OP{op_sira:02d}',
                    'MAKINA_NO': MAKINELER.index(mk) + 1, 'MAKINE_ADI': mk[1],
                    'ISTKODU': mk[2], 'ISTISIM': mk[3], 'MIKTAR': round(miktar, 0),
                    'DURUM_KOD': durum_kod, 'DURUM_ADI': durum_ad,
                    'ACIKLAMA': rnd.choice(['', '', 'Numune onayı bekleniyor',
                                            'Müşteri baskı revizyonu', 'Acil iş']),
                    'TESLIM_TARIHI': bas + dt.timedelta(days=rnd.randint(5, 40)),
                    'TRA_ACIKLAMA': rnd.choice(['', 'Kısmi üretim', 'Fazla üretim']),
                    'STOK_GRUPKODU': urun['GRUP_KODU'], 'STOK_GRUPADI': urun['GRUP_ADI'],
                    'STOK_KOD1': urun['KOD_1'], 'STOK_AD1': urun['AD1'],
                    'STOK_KOD2': urun['KOD_2'], 'STOK_AD2': urun['AD2'],
                    'STOK_KOD3': urun['KOD_3'], 'STOK_AD3': urun['AD3'],
                    'STOK_KOD4': urun['KOD_4'], 'STOK_AD4': urun['AD4'],
                })

                self.uretim2.append({
                    'TAKIPNO': takip, 'ISEMRINO': isemrino,
                    'STOK_KODU': urun['STOK_KODU'], 'SIPARIS_NO': sip['FISNO'],
                    'SIPKONT': sip['SIRA'], 'REFISEMRINO': f'RF{takip % 1000000:06d}',
                    'TESLIM_TARIHI': bas + dt.timedelta(days=rnd.randint(5, 40)),
                    'KAPATILDI': kapatildi, 'OPKODU': f'OP{op_sira:02d}',
                    'MAKINE_ID': MAKINELER.index(mk) + 1, 'MAKINE_KODU': mk[0],
                    'VERIMLILIK': round(rnd.uniform(0.55, 1.12), 4),
                    'VERIMTAKIP': verimtakip, 'ISTKODU': mk[2], 'ISTISIM': mk[3],
                    'STHAR_CARIKOD': musteri['CARI_KOD'], 'MAMUL': urun['STOK_ADI'],
                    'STOK_ADI': urun['STOK_ADI'], 'KOD_1': urun['KOD_1'],
                    'KOD_4': urun['KOD_4'], 'PARCA': urun['AD5'],
                    'KALIP': urun['KOD_3'] or 'STD',
                    'YIL': op_bas.year, 'HAFTA': hafta_no(op_bas.date()),
                    'URETIM': uretilen, 'FIRE': fire,
                    'GERC_ARIZA': ariza_sure, 'GERC_HATBOS': hatbos,
                    'GERC_ISLEM': islem, 'GERC_HAZIRLIK': hazirlik,
                    'TEO_ISLEM': round(islem * rnd.uniform(0.75, 1.05), 1),
                    'TEO_HAZIRLIK_TAKIPSIZ': round(hazirlik * 0.8, 1),
                    'TEO_HAZIRLIK_TAKIPLI': round(hazirlik * 0.95, 1),
                    'DURUM_ADI': durum_ad,
                    'FIREORANI_MINFIRE': round(fire_oran * rnd.uniform(0.6, 1.0), 5),
                    'FIREORANI_URETIM': round(fire_oran, 5),
                })

                self.puantaj.append({
                    'ID': takip, 'YIL': op_bas.year, 'HAFTA': hafta_no(op_bas.date()),
                    'GRUP': mk[3], 'TOPLAM': round(rnd.uniform(120, 640), 1),
                })

                # günlük üretim/aktivite kayıtları
                for akt_kod, akt_ad in AKTIVITELER:
                    if akt_ad == 'DURMA' and ariza_sure < 5:
                        continue
                    uak_inc += 1
                    if akt_ad == 'HAZIRLIK':
                        sure, ur, fr = hazirlik, 0.0, 0.0
                    elif akt_ad == 'ISLEM':
                        sure, ur, fr = islem, uretilen, fire
                    else:
                        sure, ur, fr = ariza_sure, 0.0, 0.0
                    a_bas = op_bas if akt_ad == 'HAZIRLIK' else op_bas + dt.timedelta(
                        minutes=hazirlik if akt_ad == 'ISLEM' else hazirlik + islem)
                    a_bit = a_bas + dt.timedelta(minutes=sure)
                    ariza_kod, ariza_ad = (None, None)
                    if akt_ad == 'DURMA':
                        ariza_kod, ariza_ad = agirlikli_sec(
                            rnd, [((k, a), w) for k, a, w in ARIZA_TIPLERI])
                    mola = round(min(30.0, sure * 0.06), 1)
                    self.uak.append({
                        'INCKEYNO': uak_inc, 'TAKIP_ID': takip, 'ISEMRINO': isemrino,
                        'TARIH': a_bas.date(), 'YIL': a_bas.year,
                        'HAFTA': hafta_no(a_bas.date()),
                        'BASLANGICTARIH': a_bas,
                        'BITISTARIHSAAT': a_bit if a_bit.date() <= self.bugun else None,
                        'DEVAM_EDIYOR': 0 if a_bit.date() <= self.bugun else 1,
                        'URETILENMIKTAR': ur, 'FIREMIKTAR': fr,
                        'ACIKLAMA': ariza_ad or '',
                        'BRUT_SURE': round(sure + mola, 1), 'MOLA': mola,
                        'NET_SURE': round(sure, 1),
                        'AKTIVITEKODU': akt_kod, 'AKTIVITE_ADI': akt_ad,
                        'ARIZAKODU': ariza_kod, 'ARIZA_ADI': ariza_ad,
                        'SURE_DAHIL': 'E' if akt_ad != 'DURMA' else 'H',
                        'HAZIRLIK': hazirlik if akt_ad == 'HAZIRLIK' else 0.0,
                        'ISLEM': islem if akt_ad == 'ISLEM' else 0.0,
                        'ARIZA': ariza_sure if akt_ad == 'DURMA' else 0.0,
                        'HATBOS': hatbos if akt_ad == 'ISLEM' else 0.0,
                        'STDSURE_ISLEM': round(islem * rnd.uniform(0.8, 1.1), 1),
                        'KONFIGURASYON_ID': 1000 + (takip % 40),
                        'STANDARTHAZIRLIK': round(hazirlik * 0.9, 1),
                        'STANDARTMIKTAR': 1000.0, 'STANDARTSURE': round(std_sure, 3),
                        'ADDK': round(rnd.uniform(40, 340), 1),
                    })

                if ariza_sure >= 5:
                    ariza_inc += 1
                    k, a = agirlikli_sec(rnd, [((k, a), w) for k, a, w in ARIZA_TIPLERI])
                    a_bas = op_bas + dt.timedelta(minutes=hazirlik + islem * rnd.uniform(0.1, 0.9))
                    devam = 1 if (a_bas + dt.timedelta(minutes=ariza_sure)).date() > self.bugun else 0
                    self.arizalar.append({
                        'INCKEYNO': ariza_inc, 'TAKIP_ID': takip, 'ISEMRINO': isemrino,
                        'STOK_KODU': urun['STOK_KODU'], 'STOK_ADI': urun['STOK_ADI'],
                        'BASLANGICTARIH': a_bas,
                        'BITISTARIHSAAT': None if devam else a_bas + dt.timedelta(minutes=ariza_sure),
                        'SURE': ariza_sure,
                        'ACIKLAMA': rnd.choice(['', 'Bakım çağrıldı', 'Operatör müdahalesi',
                                                'Yedek parça bekleniyor', 'Kalıp söküldü']),
                        'ARIZA_ADI': a, 'DEVAM_EDIYOR': devam,
                    })
        print(f'   iş emri: {len(self.isemri)}, üretim kaydı: {len(self.uretim2)}, '
              f'aktivite: {len(self.uak)}, arıza: {len(self.arizalar)}')

    def oee_uret(self):
        """Makinelerin ANLIK durumu — SCADA ekranının kalbi.

        Kaynak görünüm, son bir ayda hareket görmüş ya da hâlâ açık olan iş
        emirlerini makine bazında tekilleştirir: her makine için tek satır.
        Rapordaki LED renkleri `VALUES(ISLEM_DURUMU)` üzerinden çalıştığı için
        bu tekillik önemli — makine başına tek satır, tek renk.
        """
        rnd = self.rnd
        simdi = dt.datetime.combine(self.bugun, dt.time(14, 22, 0))
        isemri_map = {i['TAKIPNO']: i for i in self.isemri}
        # makine -> o makinedeki en güncel üretim kaydı
        makine_isleri = defaultdict(list)
        for u in self.uretim2:
            makine_isleri[u['MAKINE_KODU']].append(u)
        konfigler = [(1, 'TEK VARDİYA'), (2, 'ÇİFT VARDİYA'), (3, 'SÜREKLİ')]

        for kod, ad, istk, ists in MAKINELER:
            isler = makine_isleri.get(kod) or []
            if not isler:
                continue
            u = max(isler, key=lambda x: (x['YIL'], x['HAFTA']))
            ie = isemri_map.get(u['TAKIPNO'])
            if not ie:
                continue
            durum = agirlikli_sec(rnd, [('ISLEM', 46), ('HAZIRLIK', 12),
                                        ('ARIZA/DURUŞ', 10), ('PASIF', 17),
                                        ('TAMAMLANDI', 10), ('KAPATILDI', 5)])
            if durum in ('ISLEM', 'HAZIRLIK', 'ARIZA/DURUŞ'):
                bas = simdi - dt.timedelta(minutes=rnd.randint(25, 460))
                bit = None
                oran = rnd.uniform(0.05, 0.88)
            elif durum == 'PASIF':
                bas = simdi + dt.timedelta(hours=rnd.randint(1, 30))
                bit = None
                oran = 0.0
            else:
                bas = simdi - dt.timedelta(hours=rnd.uniform(10, 90))
                bit = bas + dt.timedelta(hours=rnd.uniform(1.5, 9))
                oran = rnd.uniform(0.95, 1.0)
            ie_miktar = u['URETIM'] + u['FIRE']
            kf = rnd.choice(konfigler)
            satir = {
                'TAKIP_ID': u['TAKIPNO'], 'BAS_TAR': bas, 'BIT_TAR': bit,
                'ISEMRINO': u['ISEMRINO'], 'REFISEMRINO': u['REFISEMRINO'],
                'SIPARIS_NO': u['SIPARIS_NO'], 'STOKKODU': u['STOK_KODU'],
                'STOK_ADI': u['STOK_ADI'], 'ISTISIM': u['ISTISIM'],
                'MRPMAKINENO': u['MAKINE_ID'], 'DEMIR_KODU': kod, 'DEMIR_ISMI': ad,
                'ISEMRI_MIKTARI': round(ie_miktar, 0),
                'URETILENMIKTAR': round(ie_miktar * oran, 0),
                'FIREMIKTAR': round(ie_miktar * oran * abs(rnd.gauss(0.018, 0.012)), 0),
                'G_HAZIRLIK': u['GERC_HAZIRLIK'], 'G_ISLEM': u['GERC_ISLEM'],
                'DURUSSURE': u['GERC_ARIZA'], 'ISLEM_DURUMU': durum,
                'OPKODU': u['OPKODU'], 'CARI_KODU': ie['CARI_KOD'],
                'CARI_ISIM': ie['CARI_ISIM'], 'KONFIG_ID': kf[0], 'KONFIG_ADI': kf[1],
                'STD_SURE': round(rnd.uniform(0.35, 3.6), 3),
                '_durum': durum,
            }
            dagilim = self._isci_dagilimi(u['ISTISIM'])
            satir.update(dagilim)
            self.oee.append(satir)
            for gkod, gad in GOREVLER:
                if dagilim.get(gkod):
                    self.calisan_sayisi.append({
                        'TAKIPID': u['TAKIPNO'], 'GOREV_ADI': gad,
                        'ISCI_SAYISI': float(dagilim[gkod]),
                    })
        durumlar = defaultdict(int)
        for o in self.oee:
            durumlar[o['ISLEM_DURUMU']] += 1
        print(f'   OEE (anlık, makine başına tek satır): {len(self.oee)} satır '
              f'{dict(durumlar)}, çalışan dağılımı: {len(self.calisan_sayisi)} satır')

    def _isci_dagilimi(self, istisim):
        rnd = self.rnd
        d = {k: 0.0 for k, _ in GOREVLER}
        if istisim == 'PRES':
            d['PRES_OPR'] = float(rnd.randint(1, 2))
            d['PRES_ISTIFLEYICI'] = float(rnd.randint(1, 3))
            d['KALITECI'] = float(rnd.choice([0, 1]))
        elif istisim == 'KESIM':
            d['MAKAS_OPR'] = float(rnd.randint(1, 2))
            d['PRES_ISTIFLEYICI'] = float(rnd.choice([0, 1, 2]))
        elif istisim in ('MATBAA', 'DIJITAL'):
            d['BASKI_OPR'] = float(rnd.randint(1, 2))
            d['KALITECI'] = float(rnd.choice([0, 1]))
            d['PAKETLEMECI'] = float(rnd.choice([0, 1]))
        else:  # MONTAJ
            d['BANT_LIDERI'] = 1.0
            d['SEKILLENDIRME'] = float(rnd.randint(2, 6))
            d['PAKETLEMECI'] = float(rnd.randint(1, 4))
            d['KALITECI'] = float(rnd.choice([1, 1, 2]))
        return d

    def puantaj_gunluk_uret(self):
        rnd = self.rnd
        pid = 0
        gun = self.bugun - dt.timedelta(days=45)
        while gun <= self.bugun:
            if is_gunu_mu(gun):
                for grup in CALISMA_GRUPLARI:
                    pid += 1
                    taban = {'PRES': 26, 'KESİM': 11, 'MATBAA': 9, 'DİJİTAL': 4,
                             'MONTAJ': 48, 'MONTAJ_USTA': 6, 'MONTAJ_MEYDAN': 9}[grup]
                    self.puantaj_gunluk.append({
                        'ID': pid, 'BUGUNMU': gun == self.bugun, 'TARIH': gun,
                        'CALISMA_GRUP': grup,
                        'KisiSayisi': float(max(1, int(rnd.gauss(taban, taban * 0.12)))),
                    })
            gun += dt.timedelta(days=1)
        print(f'   günlük puantaj: {len(self.puantaj_gunluk)} satır')


# --------------------------------------------------------------------------
# CSV çıkışları
# --------------------------------------------------------------------------

KOLONLAR = {
    'STOK': ['STOK_KODU', 'STOK_ADI', 'GRUP_KODU', 'GRUP_ADI', 'KOD_1', 'AD1', 'KOD_2',
             'AD2', 'KOD_3', 'AD3', 'KOD_4', 'AD4', 'KOD_5', 'AD5', 'INGISIM',
             'KT_YUKSEKLIK', 'OLCU_BR1', 'OLCU_BR2', 'OLCU_BR3', 'BIRIM2_CARPAN',
             'BIRIM3_CARPAN', 'BIRIM_MALIYET'],
    'CARI': ['CARI_KOD', 'CARI_AD', 'ULKE_KODU', 'ULKEADI', 'GRUP_KODU', 'SEKTOR',
             'RAPOR_KODU1', 'BOLGE', 'RAPOR_KODU2', 'SEKTOR2', 'RAPOR_KODU3',
             'CARI_TEMSILCI', 'DEPARTMAN', 'CARI_TIPI', 'MUSTERI_YERI'],
    'CARI_ALACAKBORC': ['CARI_KOD', 'SON_TARIH', 'ALACAK_TL', 'BORC_TL', 'BAKIYE_TL',
                        'KUR', 'SONGUNKU_KUR', 'DURUM', 'BAKIYE_USD', 'MUTLAK_USD'],
    'CIRO': ['STOK_KODU', 'STHAR_CARIKOD', 'FISNO', 'STHAR_TARIH', 'STHAR_GCMIK',
             'STHAR_GCMIK2', 'STHAR_NF', 'STHAR_GCKOD', 'DOLAR_KURU', 'TUTAR_USD',
             'YIL', 'AY', 'STHAR_SIPNUM', 'STRA_SIPKONT', 'SIP_INC', 'AY_BASLANGICI',
             'SIPARIS_TEMSILCISI', 'TEMSILCI_GRUP'],
    'SIPARIS_KISA': ['INCKEYNO', 'STHAR_TARIH', 'FISNO', 'SIRA', 'STOK_KODU',
                     'STHAR_CARIKOD', 'STHAR_GCMIK', 'STHAR_NF', 'GONDERILEN', 'KALAN',
                     'SIPARIS_TEMSILCI', 'DEPARTMAN', 'STHAR_GCKOD', 'DOLAR_KURU',
                     'STHAR_KOD1', 'STHAR_KOD2', 'TUTAR_USD', 'DURUM', 'YIL', 'AY',
                     'HAFTA', 'ODEKOD', 'ODEME_ACIKLAMA', 'PESINAT_ORANI', 'VADE_GUNU',
                     'PESIN_TUTAR', 'VADELI_TUTAR', 'RPT', 'KACINCI_SIPARIS'],
    'SIPARIS_ODEME_KISA': ['INCKEYNO', 'FISNO', 'SIRA', 'STHAR_TARIH', 'ODEKOD', 'OFSET',
                           'ORAN', 'ODEME_TARIHI', 'ODEME_TUTARI_TL', 'ODEME_TUTAR_USD'],
    'SIPARIS_ODEME_UZUN': ['INCKEYNO', 'FISNO', 'SIRA', 'STHAR_TARIH', 'ODEKOD', 'OFSET',
                           'ORAN', 'ODEME_TARIHI', 'KDV_ORANI', 'ODEME_TUTARI_KDVLI_TL',
                           'ODEME_TUTARI_KDVLI_USD', 'BIRIM_FIYAT_TL', 'BIRIM_FIYAT_USD',
                           'ODEME_TUTARI_NET_TL', 'ODEME_TUTARI_NET_USD'],
    'SATIN_ALMA': ['STOK_KODU', 'CARI_KOD', 'FISNO', 'TARIH', 'MIKTAR1', 'MIKTAR2',
                   'NET_FIYAT', 'STHAR_GCKOD', 'STHAR_HTUR', 'DOLAR_KURU',
                   'STHAR_ACIKLAMA', 'EKALAN', 'EKALAN1', 'TUTAR_USD', 'ODE_GUN',
                   'YIL', 'AY', 'HAFTA'],
    'SATINALMA_SIPARIS': ['INCKEYNO', 'STHAR_TARIH', 'FISNO', 'SIRA', 'STOK_KODU',
                          'STHAR_CARIKOD', 'STHAR_GCMIK', 'STHAR_NF', 'ALINAN',
                          'STHAR_HTUR', 'TERMIN', 'SIPARIS_TARIHINDEN_GECEN_GUN',
                          'TERMINE_KALAN_GUN', 'KALAN', 'STHAR_GCKOD', 'DOLAR_KURU',
                          'STHAR_KOD1', 'STHAR_KOD2', 'TUTAR_USD', 'DURUM', 'YIL',
                          'AY', 'HAFTA'],
}
KOLONLAR['SIPARIS_UZUN'] = KOLONLAR['SIPARIS_KISA'] + [
    'MUSTERI_SIP_NO', 'TESLIM_YERI', 'EK_ACIKLAMA_1', 'EK_ACIKLAMA_2',
    'EK_ACIKLAMA_3_MALZEME', 'EK_ACIKLAMA_4', 'EK_ACIKLAMA_5']

SCADA_KOLONLAR = {
    'TBLMRPMAKINE': ['DEMIR_KODU', 'INCKEYNO', 'DEMIR_ISMI', 'ISTKODU'],
    'CALISAN_SAYISI': ['TAKIPID', 'GOREV_ADI', 'ISCI_SAYISI'],
    'VW_STOK': ['STOK_KODU', 'STOK_ADI', 'GRUP_KODU', 'GRUP_ADI', 'KOD_1',
                          'AD1', 'KOD_2', 'AD2', 'KOD_3', 'AD3', 'KOD_4', 'AD4',
                          'KOD_5', 'AD5'],
    'VW_ISEMRI': ['TAKIPNO', 'ISEMRINO', 'KALIPADI', 'STOK_KODU', 'STOK_ADI',
                             'CARI_KOD', 'CARI_ISIM', 'SIPARIS_NO', 'REFISEMRINO',
                             'SIPARIS_KONT', 'OPKODU', 'MAKINA_NO', 'MAKINE_ADI',
                             'ISTKODU', 'ISTISIM', 'MIKTAR', 'DURUM_KOD', 'DURUM_ADI',
                             'ACIKLAMA', 'TESLIM_TARIHI', 'TRA_ACIKLAMA',
                             'STOK_GRUPKODU', 'STOK_GRUPADI', 'STOK_KOD1', 'STOK_AD1',
                             'STOK_KOD2', 'STOK_AD2', 'STOK_KOD3', 'STOK_AD3',
                             'STOK_KOD4', 'STOK_AD4'],
    'VW_URETIM_HAFTALIK': ['TAKIPNO', 'ISEMRINO', 'STOK_KODU', 'SIPARIS_NO', 'SIPKONT',
                        'REFISEMRINO', 'TESLIM_TARIHI', 'KAPATILDI', 'OPKODU',
                        'MAKINE_ID', 'MAKINE_KODU', 'VERIMLILIK', 'VERIMTAKIP',
                        'ISTKODU', 'ISTISIM', 'STHAR_CARIKOD', 'MAMUL', 'STOK_ADI',
                        'KOD_1', 'KOD_4', 'PARCA', 'KALIP', 'YIL', 'HAFTA', 'URETIM',
                        'FIRE', 'GERC_ARIZA', 'GERC_HATBOS', 'GERC_ISLEM',
                        'GERC_HAZIRLIK', 'TEO_ISLEM', 'TEO_HAZIRLIK_TAKIPSIZ',
                        'TEO_HAZIRLIK_TAKIPLI', 'DURUM_ADI', 'FIREORANI_MINFIRE',
                        'FIREORANI_URETIM'],
    'VW_AKTIVITE': ['INCKEYNO', 'TAKIP_ID', 'ISEMRINO', 'TARIH', 'YIL', 'HAFTA',
                           'BASLANGICTARIH', 'BITISTARIHSAAT', 'DEVAM_EDIYOR',
                           'URETILENMIKTAR', 'FIREMIKTAR', 'ACIKLAMA', 'BRUT_SURE',
                           'MOLA', 'NET_SURE', 'AKTIVITEKODU', 'AKTIVITE_ADI',
                           'ARIZAKODU', 'ARIZA_ADI', 'SURE_DAHIL', 'HAZIRLIK', 'ISLEM',
                           'ARIZA', 'HATBOS', 'STDSURE_ISLEM', 'KONFIGURASYON_ID',
                           'STANDARTHAZIRLIK', 'STANDARTMIKTAR', 'STANDARTSURE', 'ADDK'],
    'VW_ARIZA': ['INCKEYNO', 'TAKIP_ID', 'ISEMRINO', 'STOK_KODU', 'STOK_ADI',
                         'BASLANGICTARIH', 'BITISTARIHSAAT', 'SURE', 'ACIKLAMA',
                         'ARIZA_ADI', 'DEVAM_EDIYOR'],
    'VW_PUANTAJ_HAFTALIK': ['ID', 'YIL', 'HAFTA', 'GRUP', 'TOPLAM'],
    'VW_PUANTAJ_GUNLUK': ['ID', 'BUGUNMU', 'TARIH', 'CALISMA_GRUP', 'KisiSayisi'],
    'URETIM_VERI_OEE': ['TAKIP_ID', 'BAS_TAR', 'BIT_TAR', 'ISEMRINO', 'REFISEMRINO',
                        'SIPARIS_NO', 'STOKKODU', 'STOK_ADI', 'ISTISIM', 'MRPMAKINENO',
                        'DEMIR_KODU', 'DEMIR_ISMI', 'ISEMRI_MIKTARI', 'URETILENMIKTAR',
                        'FIREMIKTAR', 'G_HAZIRLIK', 'G_ISLEM', 'DURUSSURE',
                        'ISLEM_DURUMU', 'OPKODU', 'CARI_KODU', 'CARI_ISIM', 'KONFIG_ID',
                        'KONFIG_ADI', 'STD_SURE', 'BANT_LIDERI', 'SEKILLENDIRME',
                        'KALITECI', 'PAKETLEMECI', 'PRES_OPR', 'PRES_ISTIFLEYICI',
                        'MAKAS_OPR', 'BASKI_OPR'],
}
# VW_DEVAM_EDEN_ISLER kolonları (anlık devam eden işler görünümü)
SCADA_KOLONLAR['VW_DEVAM_EDEN_ISLER'] = [
    'TAKIP_ID', 'ISEMRINO', 'AKTIVITEKODU', 'AKTIVITE_ADI', 'BASLANGICTARIH',
    'DEVAM_EDENSURE', 'MIKTAR', 'DEMIR_KODU', 'ISTISIM', 'KAPATILDI', 'OPKODU',
    'STOK_ADI', 'STOK_KODU', 'CARI_ISIM', 'SIPARIS_NO', 'REFISEMRINO', 'URETIM',
    'FIRE', 'HAZIRLIK', 'ISLEM', 'ARIZA', 'STDSURE_V', 'TAMAMLANMA',
    'INSANSAAT_HAZIRLIK', 'INSANSAAT_ISLEM', 'ORTALAMA_CALISAN_SAYISI',
    'VERIM_TAKIPET', 'KT_VERIMTAKIP']


def devam_eden_isler(u: Uretec):
    """SCADA 'Üretim' sayfasındaki anlık devam eden işler tablosu.

    Hâlâ açık olan iş emri hareketleri: çalışan makineler + tezgâhta bekleyen
    işler. STDSURE_V, ISLEM ile aynı birimdedir (dakika) — verim ölçüsü
    STDSURE_V / ISLEM olarak hesaplandığı için oran 0-1 aralığında kalır.
    """
    rnd = u.rnd
    simdi = dt.datetime.combine(u.bugun, dt.time(14, 22, 0))
    isemri_map = {i['TAKIPNO']: i for i in u.isemri}
    oee_map = {o['TAKIP_ID']: o for o in u.oee}
    uretim_map = {x['TAKIPNO']: x for x in u.uretim2}

    kaynaklar = []
    for o in u.oee:
        if o['ISLEM_DURUMU'] in ('ISLEM', 'HAZIRLIK', 'ARIZA/DURUŞ'):
            kaynaklar.append((o['TAKIP_ID'], o['ISLEM_DURUMU']))
    # tezgâhta bekleyen (henüz kapanmamış) birkaç iş daha
    bekleyen = [x for x in u.uretim2 if x['KAPATILDI'] in ('O', 'H')]
    rnd.shuffle(bekleyen)
    for x in bekleyen[:22]:
        if x['TAKIPNO'] not in oee_map:
            kaynaklar.append((x['TAKIPNO'], rnd.choice(['ISLEM', 'ISLEM', 'HAZIRLIK'])))

    satirlar = []
    for takip, durum in kaynaklar:
        ie = isemri_map.get(takip)
        pr = uretim_map.get(takip)
        if not ie or not pr:
            continue
        o = oee_map.get(takip)
        akt = {'ISLEM': ('A02', 'ISLEM'), 'HAZIRLIK': ('A01', 'HAZIRLIK'),
               'ARIZA/DURUŞ': ('A03', 'DURMA')}[durum]
        bas = o['BAS_TAR'] if o else simdi - dt.timedelta(minutes=rnd.randint(30, 600))
        gecen = max(1, int((simdi - bas).total_seconds() // 60))
        calisan = round(rnd.uniform(1.0, 6.0), 2)
        islem = max(1.0, pr['GERC_ISLEM'])
        miktar = pr['URETIM'] + pr['FIRE']
        uretilen = o['URETILENMIKTAR'] if o else round(miktar * rnd.uniform(0.05, 0.8))
        satirlar.append({
            'TAKIP_ID': takip, 'ISEMRINO': pr['ISEMRINO'],
            'AKTIVITEKODU': akt[0], 'AKTIVITE_ADI': akt[1],
            'BASLANGICTARIH': bas, 'DEVAM_EDENSURE': gecen,
            'MIKTAR': round(miktar, 0), 'DEMIR_KODU': pr['MAKINE_KODU'],
            'ISTISIM': pr['ISTISIM'], 'KAPATILDI': 'O', 'OPKODU': pr['OPKODU'],
            'STOK_ADI': pr['STOK_ADI'], 'STOK_KODU': pr['STOK_KODU'],
            'CARI_ISIM': ie['CARI_ISIM'], 'SIPARIS_NO': pr['SIPARIS_NO'],
            'REFISEMRINO': pr['REFISEMRINO'],
            'URETIM': uretilen, 'FIRE': pr['FIRE'],
            'HAZIRLIK': pr['GERC_HAZIRLIK'], 'ISLEM': islem, 'ARIZA': pr['GERC_ARIZA'],
            'STDSURE_V': round(islem * rnd.uniform(0.55, 0.98), 2),
            'TAMAMLANMA': round(uretilen / max(1.0, miktar), 4),
            'INSANSAAT_HAZIRLIK': round(pr['GERC_HAZIRLIK'] * calisan / 60, 3),
            'INSANSAAT_ISLEM': round(islem * calisan / 60, 3),
            'ORTALAMA_CALISAN_SAYISI': calisan,
            'VERIM_TAKIPET': 'E', 'KT_VERIMTAKIP': 'E' if rnd.random() < 0.78 else 'H',
        })
    return satirlar


def stok_bilgi(u: Uretec):
    """SCADA tarafındaki stok görünümü (ölçü/maliyet kolonları olmadan)."""
    return [{k: s.get(k) for k in SCADA_KOLONLAR['VW_STOK']} for s in u.stok]


def yaz(u: Uretec):
    def yol(anahtar, dosya):
        return os.path.join(KOK, RAPOR_KLASORLERI[anahtar], 'data', dosya)

    print('\n-- 01 SCADA --')
    makine_satir = [{'DEMIR_KODU': k, 'INCKEYNO': i + 1, 'DEMIR_ISMI': ad, 'ISTKODU': ik}
                    for i, (k, ad, ik, _) in enumerate(MAKINELER)]
    csv_yaz(yol('scada', 'TBLMRPMAKINE.csv'), SCADA_KOLONLAR['TBLMRPMAKINE'], makine_satir)
    csv_yaz(yol('scada', 'VW_STOK.csv'),
            SCADA_KOLONLAR['VW_STOK'], stok_bilgi(u))
    csv_yaz(yol('scada', 'VW_ISEMRI.csv'),
            SCADA_KOLONLAR['VW_ISEMRI'], u.isemri)
    csv_yaz(yol('scada', 'VW_URETIM_HAFTALIK.csv'),
            SCADA_KOLONLAR['VW_URETIM_HAFTALIK'], u.uretim2)
    csv_yaz(yol('scada', 'VW_AKTIVITE.csv'),
            SCADA_KOLONLAR['VW_AKTIVITE'], u.uak)
    csv_yaz(yol('scada', 'VW_ARIZA.csv'),
            SCADA_KOLONLAR['VW_ARIZA'], u.arizalar)
    csv_yaz(yol('scada', 'VW_PUANTAJ_HAFTALIK.csv'),
            SCADA_KOLONLAR['VW_PUANTAJ_HAFTALIK'], u.puantaj)
    csv_yaz(yol('scada', 'VW_PUANTAJ_GUNLUK.csv'),
            SCADA_KOLONLAR['VW_PUANTAJ_GUNLUK'], u.puantaj_gunluk)
    csv_yaz(yol('scada', 'URETIM_VERI_OEE.csv'),
            SCADA_KOLONLAR['URETIM_VERI_OEE'], u.oee)
    csv_yaz(yol('scada', 'CALISAN_SAYISI.csv'),
            SCADA_KOLONLAR['CALISAN_SAYISI'], u.calisan_sayisi)
    csv_yaz(yol('scada', 'VW_DEVAM_EDEN_ISLER.csv'),
            SCADA_KOLONLAR['VW_DEVAM_EDEN_ISLER'], devam_eden_isler(u))

    print('\n-- 02 Departman Ticaret --')
    csv_yaz(yol('yurtici', 'STOK.csv'), KOLONLAR['STOK'], u.stok)
    csv_yaz(yol('yurtici', 'CARI.csv'), KOLONLAR['CARI'], u.cari)
    csv_yaz(yol('yurtici', 'CARI_ALACAKBORC.csv'),
            KOLONLAR['CARI_ALACAKBORC'], u.alacak_borc)
    csv_yaz(yol('yurtici', 'CIRO.csv'), KOLONLAR['CIRO'], u.ciro)
    csv_yaz(yol('yurtici', 'SIPARIS.csv'), KOLONLAR['SIPARIS_UZUN'], u.siparis)
    csv_yaz(yol('yurtici', 'SIPARIS_ODEME.csv'),
            KOLONLAR['SIPARIS_ODEME_UZUN'], u.siparis_odeme)
    csv_yaz(yol('yurtici', 'SATIN_ALMA.csv'), KOLONLAR['SATIN_ALMA'], u.satin_alma)
    csv_yaz(yol('yurtici', 'SATINALMA_SIPARIS.csv'),
            KOLONLAR['SATINALMA_SIPARIS'], u.satinalma_siparis)

    print('\n-- 03 Satın Alma --')
    csv_yaz(yol('satinalma', 'STOK.csv'), KOLONLAR['STOK'], u.stok)
    csv_yaz(yol('satinalma', 'CARI.csv'), KOLONLAR['CARI'], u.cari)
    csv_yaz(yol('satinalma', 'CARI_ALACAKBORC.csv'),
            KOLONLAR['CARI_ALACAKBORC'], u.alacak_borc)
    csv_yaz(yol('satinalma', 'CIRO.csv'), KOLONLAR['CIRO'], u.ciro)
    csv_yaz(yol('satinalma', 'SIPARIS.csv'), KOLONLAR['SIPARIS_KISA'], u.siparis)
    csv_yaz(yol('satinalma', 'SIPARIS_ODEME.csv'),
            KOLONLAR['SIPARIS_ODEME_KISA'], u.siparis_odeme)
    csv_yaz(yol('satinalma', 'SATIN_ALMA.csv'), KOLONLAR['SATIN_ALMA'], u.satin_alma)
    csv_yaz(yol('satinalma', 'SATINALMA_SIPARIS.csv'),
            KOLONLAR['SATINALMA_SIPARIS'], u.satinalma_siparis)

    print('\n-- 04 Ürün / Kalıp --')
    csv_yaz(yol('urun', 'STOK.csv'), KOLONLAR['STOK'], u.stok)
    csv_yaz(yol('urun', 'SIPARIS.csv'), KOLONLAR['SIPARIS_KISA'], u.siparis)
    csv_yaz(yol('urun', 'CIRO.csv'), KOLONLAR['CIRO'], u.ciro)


def main():
    ap = argparse.ArgumentParser(description='Test Firma A.Ş. sentetik veri üreteci')
    ap.add_argument('--bugun', default=None, help='YYYY-MM-DD (varsayılan: bugün)')
    ap.add_argument('--olcek', type=float, default=1.0, help='veri hacmi çarpanı')
    a = ap.parse_args()
    bugun = (dt.date.fromisoformat(a.bugun) if a.bugun else dt.date.today())

    print(f'Test Firma A.Ş. sentetik veri üreteci · bugün={bugun} · ölçek={a.olcek} '
          f'· tohum={RASTGELE_TOHUM}\n')
    u = Uretec(bugun, a.olcek)
    u.stok_uret()
    u.cari_uret()
    u.siparis_uret()
    u.satinalma_uret()
    u.bakiye_uret()
    u.uretim_uret()
    u.oee_uret()
    u.puantaj_gunluk_uret()
    yaz(u)
    print('\nBitti.')


if __name__ == '__main__':
    main()
