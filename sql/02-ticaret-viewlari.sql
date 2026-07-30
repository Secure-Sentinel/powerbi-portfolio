/* =====================================================================
   Test Firma A.Ş. · Ticaret & satın alma view'ları
   ---------------------------------------------------------------------
   Power BI modelindeki tablolar bu view'lardan birebir okunur; view adı
   = model tablosu adı. Rapor tarafında hiçbir join yapılmaz.
   ===================================================================== */

/* --------------------------------------------------------------- STOK
   Rapor kodları (KOD_1..KOD_5) sözlükten çözülür; rapor tarafı hem kodu
   hem adı görür. AD3'ü "Kalıp <kod>" olarak üretiyoruz çünkü kalıbın
   ayrı bir sabit tablosu yok, kod zaten ölçüyü taşıyor.               */
CREATE OR ALTER VIEW dbo.STOK AS
SELECT
    s.STOK_KODU,
    s.STOK_ADI,
    s.GRUP_KODU,
    GRUP_ADI = g.AD,
    s.KOD_1, AD1 = k1.AD,
    s.KOD_2, AD2 = k2.AD,
    s.KOD_3, AD3 = CASE WHEN s.KOD_3 IS NULL OR s.KOD_3 = '' THEN ''
                        ELSE N'Kalıp ' + s.KOD_3 END,
    s.KOD_4, AD4 = k4.AD,
    s.KOD_5, AD5 = k5.AD,
    s.INGISIM,
    s.KT_YUKSEKLIK,
    s.OLCU_BR1, s.OLCU_BR2, s.OLCU_BR3,
    s.BIRIM2_CARPAN, s.BIRIM3_CARPAN,
    s.BIRIM_MALIYET
FROM erp.TBLSTSABIT s
LEFT JOIN erp.TBLKODSOZLUK g  ON g.KOD_TIPI  = 'GRUP'  AND g.KOD  = s.GRUP_KODU
LEFT JOIN erp.TBLKODSOZLUK k1 ON k1.KOD_TIPI = 'KOD_1' AND k1.KOD = s.KOD_1
LEFT JOIN erp.TBLKODSOZLUK k2 ON k2.KOD_TIPI = 'KOD_2' AND k2.KOD = s.KOD_2
LEFT JOIN erp.TBLKODSOZLUK k4 ON k4.KOD_TIPI = 'KOD_4' AND k4.KOD = s.KOD_4
LEFT JOIN erp.TBLKODSOZLUK k5 ON k5.KOD_TIPI = 'KOD_5' AND k5.KOD = s.KOD_5;
GO

/* --------------------------------------------------------------- CARI */
CREATE OR ALTER VIEW dbo.CARI AS
SELECT
    c.CARI_KOD,
    CARI_AD = c.CARI_ISIM,
    c.ULKE_KODU,
    ULKEADI = u.AD,
    c.GRUP_KODU,
    SEKTOR  = sk.AD,
    c.RAPOR_KODU1,
    BOLGE   = b.AD,
    c.RAPOR_KODU2,
    SEKTOR2 = s2.AD,
    c.RAPOR_KODU3,
    c.CARI_TEMSILCI,
    c.DEPARTMAN,
    c.CARI_TIPI,
    c.MUSTERI_YERI
FROM erp.TBLCASABIT c
LEFT JOIN erp.TBLKODSOZLUK u  ON u.KOD_TIPI  = 'ULKE'    AND u.KOD  = c.ULKE_KODU
LEFT JOIN erp.TBLKODSOZLUK sk ON sk.KOD_TIPI = 'SEKTOR'  AND sk.KOD = c.SEKTOR_KODU
LEFT JOIN erp.TBLKODSOZLUK s2 ON s2.KOD_TIPI = 'SEKTOR2' AND s2.KOD = c.SEKTOR2_KODU
LEFT JOIN erp.TBLKODSOZLUK b  ON b.KOD_TIPI  = 'BOLGE'   AND b.KOD  = c.BOLGE_KODU;
GO

/* ------------------------------------------------------------ SIPARIS
   Satış siparişi satırları. Üç şey burada hesaplanır:
     * KALAN         = miktar - gönderilen  (raporun "açık sipariş" tanımı)
     * TUTAR_USD     = satırın kendi tarihindeki kurla USD karşılığı
     * KACINCI_SIPARIS = müşterinin kaçıncı siparişi (1 ise yeni müşteri)   */
CREATE OR ALTER VIEW dbo.SIPARIS AS
WITH sip AS (
    SELECT
        t.INCKEYNO, m.STHAR_TARIH, t.FISNO, t.SIRA, t.STOK_KODU,
        STHAR_CARIKOD = m.CARI_KOD,
        STHAR_GCMIK   = t.MIKTAR,
        STHAR_NF      = t.NET_FIYAT,
        t.GONDERILEN,
        KALAN         = t.MIKTAR - t.GONDERILEN,
        SIPARIS_TEMSILCI = c.CARI_TEMSILCI,
        DEPARTMAN     = CASE c.DEPARTMAN WHEN 'YURTICI'  THEN 'YURT_ICI'
                                         WHEN 'YURTDISI' THEN 'YURT_DISI'
                                         ELSE c.DEPARTMAN END,
        STHAR_GCKOD   = '1',
        DOLAR_KURU    = kur.USD,
        STHAR_KOD1    = s.KOD_1,
        STHAR_KOD2    = s.KOD_2,
        TUTAR_USD     = ROUND(t.MIKTAR * t.NET_FIYAT / NULLIF(kur.USD, 0), 4),
        DURUM         = CASE WHEN t.MIKTAR - t.GONDERILEN > 0.5 THEN 'ACIK' ELSE 'KAPALI' END,
        YIL           = YEAR(m.STHAR_TARIH),
        AY            = MONTH(m.STHAR_TARIH),
        HAFTA         = DATEPART(ISO_WEEK, m.STHAR_TARIH),
        m.ODEKOD,
        ODEME_ACIKLAMA = o.ACIKLAMA,
        o.PESINAT_ORANI,
        o.VADE_GUNU,
        RPT           = CASE WHEN t.ACIKLAMA5 = N'Yeni ürün' THEN 0 ELSE 1 END,
        SIPARIS_SIRASI = DENSE_RANK() OVER (PARTITION BY m.CARI_KOD
                                            ORDER BY m.STHAR_TARIH, m.FISNO),
        MUSTERI_SIP_NO = m.MUSTERI_SIPNO,
        m.TESLIM_YERI,
        EK_ACIKLAMA_1  = t.ACIKLAMA1,
        EK_ACIKLAMA_2  = t.ACIKLAMA2,
        EK_ACIKLAMA_3_MALZEME = t.ACIKLAMA3,
        EK_ACIKLAMA_4  = t.ACIKLAMA4,
        EK_ACIKLAMA_5  = t.ACIKLAMA5
    FROM erp.TBLSIPATRA t
    JOIN erp.TBLSIPAMAS m ON m.FISNO = t.FISNO AND m.SIP_TIPI = 'S'
    JOIN erp.TBLCASABIT c ON c.CARI_KOD = m.CARI_KOD
    JOIN erp.TBLSTSABIT s ON s.STOK_KODU = t.STOK_KODU
    LEFT JOIN erp.TBLODEKOD o ON o.ODEKOD = m.ODEKOD
    LEFT JOIN erp.TBLKUR kur  ON kur.TARIH = m.STHAR_TARIH
)
SELECT *,
       PESIN_TUTAR   = ROUND(TUTAR_USD *      PESINAT_ORANI , 4),
       VADELI_TUTAR  = ROUND(TUTAR_USD * (1 - PESINAT_ORANI), 4),
       KACINCI_SIPARIS = SIPARIS_SIRASI
FROM sip;
GO

/* --------------------------------------------------------------- CIRO
   Satış faturası satırları (GCKOD = 4). Sipariş numarası taşındığı için
   rapor tarafında "siparişten ne kadarı faturalandı" izlenebiliyor.     */
CREATE OR ALTER VIEW dbo.CIRO AS
SELECT
    h.STOK_KODU,
    STHAR_CARIKOD = h.CARI_KOD,
    h.FISNO,
    h.STHAR_TARIH,
    STHAR_GCMIK  = h.MIKTAR,
    STHAR_GCMIK2 = ROUND(h.MIKTAR / NULLIF(s.BIRIM2_CARPAN, 0), 2),   -- koli adedi
    STHAR_NF     = h.NET_FIYAT,
    STHAR_GCKOD  = h.GCKOD,
    DOLAR_KURU   = kur.USD,
    TUTAR_USD    = ROUND(h.MIKTAR * h.NET_FIYAT / NULLIF(kur.USD, 0), 4),
    YIL          = YEAR(h.STHAR_TARIH),
    AY           = MONTH(h.STHAR_TARIH),
    STHAR_SIPNUM  = h.SIP_FISNO,
    STRA_SIPKONT  = h.SIP_SIRA,
    SIP_INC       = t.INCKEYNO,
    AY_BASLANGICI = DATEFROMPARTS(YEAR(h.STHAR_TARIH), MONTH(h.STHAR_TARIH), 1),
    SIPARIS_TEMSILCISI = c.CARI_TEMSILCI,
    TEMSILCI_GRUP = CASE c.DEPARTMAN WHEN 'YURTICI'  THEN 'YURT_ICI'
                                     WHEN 'YURTDISI' THEN 'YURT_DISI'
                                     ELSE c.DEPARTMAN END
FROM erp.TBLSTHAR h
JOIN erp.TBLSTSABIT s ON s.STOK_KODU = h.STOK_KODU
JOIN erp.TBLCASABIT c ON c.CARI_KOD  = h.CARI_KOD
LEFT JOIN erp.TBLKUR kur ON kur.TARIH = h.STHAR_TARIH
LEFT JOIN erp.TBLSIPATRA t ON t.FISNO = h.SIP_FISNO AND t.SIRA = h.SIP_SIRA
WHERE h.GCKOD = '4';
GO

/* ------------------------------------------------------- SIPARIS_ODEME
   Ödeme koşulunun taksit planı sipariş satırına açılır: her satır için
   1..n taksit, oranı ve vade tarihi. KDV %20 varsayılıyor.              */
CREATE OR ALTER VIEW dbo.SIPARIS_ODEME AS
SELECT
    t.INCKEYNO,
    t.FISNO,
    t.SIRA,
    m.STHAR_TARIH,
    p.ODEKOD,
    p.OFSET,
    p.ORAN,
    ODEME_TARIHI = DATEADD(DAY, p.OFSET, m.STHAR_TARIH),
    KDV_ORANI    = CAST(0.20 AS decimal(5,4)),
    ODEME_TUTARI_NET_TL  = ROUND(t.MIKTAR * t.NET_FIYAT * p.ORAN, 4),
    ODEME_TUTARI_NET_USD = ROUND(t.MIKTAR * t.NET_FIYAT * p.ORAN / NULLIF(kur.USD, 0), 4),
    ODEME_TUTARI_KDVLI_TL  = ROUND(t.MIKTAR * t.NET_FIYAT * p.ORAN * 1.20, 4),
    ODEME_TUTARI_KDVLI_USD = ROUND(t.MIKTAR * t.NET_FIYAT * p.ORAN * 1.20
                                   / NULLIF(kur.USD, 0), 4),
    BIRIM_FIYAT_TL  = t.NET_FIYAT,
    BIRIM_FIYAT_USD = ROUND(t.NET_FIYAT / NULLIF(kur.USD, 0), 6)
FROM erp.TBLSIPATRA t
JOIN erp.TBLSIPAMAS m   ON m.FISNO = t.FISNO AND m.SIP_TIPI = 'S'
JOIN erp.TBLODEMEPLAN p ON p.ODEKOD = m.ODEKOD
LEFT JOIN erp.TBLKUR kur ON kur.TARIH = m.STHAR_TARIH;
GO

/* --------------------------------------------------- SATINALMA_SIPARIS
   "Bugüne göre" alanlar burada hesaplanır: termine kalan gün negatifse
   sipariş gecikmiş demektir. Kalan miktar yoksa gecikme anlamsız, NULL.  */
CREATE OR ALTER VIEW dbo.SATINALMA_SIPARIS AS
SELECT
    t.INCKEYNO,
    m.STHAR_TARIH,
    t.FISNO,
    t.SIRA,
    t.STOK_KODU,
    STHAR_CARIKOD = m.CARI_KOD,
    STHAR_GCMIK   = t.MIKTAR,
    STHAR_NF      = t.NET_FIYAT,
    ALINAN        = t.GONDERILEN,
    STHAR_HTUR    = t.HTUR,
    t.TERMIN,
    SIPARIS_TARIHINDEN_GECEN_GUN = DATEDIFF(DAY, m.STHAR_TARIH, CAST(GETDATE() AS date)),
    TERMINE_KALAN_GUN = CASE WHEN t.MIKTAR - t.GONDERILEN > 0.5
                             THEN DATEDIFF(DAY, CAST(GETDATE() AS date), t.TERMIN) END,
    KALAN         = t.MIKTAR - t.GONDERILEN,
    STHAR_GCKOD   = '2',
    DOLAR_KURU    = kur.USD,
    STHAR_KOD1    = s.GRUP_KODU,
    STHAR_KOD2    = s.KOD_2,
    TUTAR_USD     = ROUND(t.MIKTAR * t.NET_FIYAT / NULLIF(kur.USD, 0), 4),
    DURUM         = CASE WHEN t.MIKTAR - t.GONDERILEN > 0.5 THEN 'ACIK' ELSE 'KAPALI' END,
    YIL           = YEAR(m.STHAR_TARIH),
    AY            = MONTH(m.STHAR_TARIH),
    HAFTA         = DATEPART(ISO_WEEK, m.STHAR_TARIH)
FROM erp.TBLSIPATRA t
JOIN erp.TBLSIPAMAS m ON m.FISNO = t.FISNO AND m.SIP_TIPI = 'A'
JOIN erp.TBLSTSABIT s ON s.STOK_KODU = t.STOK_KODU
LEFT JOIN erp.TBLKUR kur ON kur.TARIH = m.STHAR_TARIH;
GO

/* --------------------------------------------------------- SATIN_ALMA
   Gerçekleşen mal kabuller (GCKOD = 1).                                 */
CREATE OR ALTER VIEW dbo.SATIN_ALMA AS
SELECT
    h.STOK_KODU,
    CARI_KOD = h.CARI_KOD,
    h.FISNO,
    TARIH    = h.STHAR_TARIH,
    MIKTAR1  = h.MIKTAR,
    MIKTAR2  = ROUND(h.MIKTAR / NULLIF(s.BIRIM2_CARPAN, 0), 3),
    NET_FIYAT = h.NET_FIYAT,
    STHAR_GCKOD = h.GCKOD,
    STHAR_HTUR  = CASE WHEN c.ULKE_KODU = 'TR' THEN N'YERLİ' ELSE N'İTHAL' END,
    DOLAR_KURU  = kur.USD,
    STHAR_ACIKLAMA = h.ACIKLAMA,
    EKALAN  = CASE WHEN h.ODE_GUN > 0 THEN 'E' ELSE 'H' END,
    EKALAN1 = N'',
    TUTAR_USD = ROUND(h.MIKTAR * h.NET_FIYAT / NULLIF(kur.USD, 0), 4),
    h.ODE_GUN,
    YIL   = YEAR(h.STHAR_TARIH),
    AY    = MONTH(h.STHAR_TARIH),
    HAFTA = DATEPART(ISO_WEEK, h.STHAR_TARIH)
FROM erp.TBLSTHAR h
JOIN erp.TBLSTSABIT s ON s.STOK_KODU = h.STOK_KODU
JOIN erp.TBLCASABIT c ON c.CARI_KOD  = h.CARI_KOD
LEFT JOIN erp.TBLKUR kur ON kur.TARIH = h.STHAR_TARIH
WHERE h.GCKOD = '1';
GO

/* ---------------------------------------------------- CARI_ALACAKBORC
   Cari hareketlerin gün sonu toplamı + son işlem tarihindeki kur. USD
   karşılığı bugünkü kurla verilir; rapor "bugün ne kadar" sorusunu sorar. */
CREATE OR ALTER VIEW dbo.CARI_ALACAKBORC AS
WITH bakiye AS (
    SELECT
        CARI_KOD,
        SON_TARIH = MAX(TARIH),
        ALACAK_TL = SUM(ALACAK_TL),
        BORC_TL   = SUM(BORC_TL)
    FROM erp.TBLCAHAR
    GROUP BY CARI_KOD
),
songun AS (
    SELECT USD FROM erp.TBLKUR WHERE TARIH = (SELECT MAX(TARIH) FROM erp.TBLKUR)
)
SELECT
    b.CARI_KOD,
    b.SON_TARIH,
    b.ALACAK_TL,
    b.BORC_TL,
    BAKIYE_TL     = b.ALACAK_TL - b.BORC_TL,
    KUR           = k.USD,
    SONGUNKU_KUR  = sg.USD,
    DURUM         = CASE WHEN b.ALACAK_TL - b.BORC_TL >= 0 THEN 'ALACAK' ELSE 'BORC' END,
    BAKIYE_USD    = ROUND((b.ALACAK_TL - b.BORC_TL)      / NULLIF(sg.USD, 0), 2),
    MUTLAK_USD    = ROUND(ABS(b.ALACAK_TL - b.BORC_TL)   / NULLIF(sg.USD, 0), 2)
FROM bakiye b
CROSS JOIN songun sg
LEFT JOIN erp.TBLKUR k ON k.TARIH = b.SON_TARIH
WHERE ABS(b.ALACAK_TL - b.BORC_TL) >= 1;
GO

/* -------------------------------------------------- SATINALMA_TARIHLER
   Takvim. Power BI projesinde bu tablo saf M ile üretiliyor; SQL karşılığı
   burada duruyor ki hat tek yerden okunabilsin.                          */
CREATE OR ALTER VIEW dbo.SATINALMA_TARIHLER AS
WITH Tarihler AS (
    SELECT CAST('2012-01-01' AS date) AS Tarih
    UNION ALL
    SELECT DATEADD(DAY, 1, Tarih) FROM Tarihler WHERE Tarih < '2030-01-01'
)
SELECT Tarih FROM Tarihler;
GO
-- Not: özyinelemeli CTE 100 satır sınırını aşar, çağıran taraf
-- OPTION (MAXRECURSION 0) vermelidir:
--   SELECT * FROM dbo.SATINALMA_TARIHLER OPTION (MAXRECURSION 0);
