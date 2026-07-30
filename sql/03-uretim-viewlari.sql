/* =====================================================================
   Test Firma A.Ş. · Üretim (SCADA) view'ları
   ---------------------------------------------------------------------
   Ekranın tamamı bu view'lardan beslenir. En kritik olan URETIM_VERI_OEE:
   makine başına TEK satır döndürür, çünkü rapordaki LED renkleri
   VALUES(ISLEM_DURUMU) üzerinden çalışır — makine başına birden fazla
   satır olsaydı bir makine hem yeşil hem kırmızı olurdu.
   ===================================================================== */

/* --------------------------------------------------------- boyut view'ları */
CREATE OR ALTER VIEW dbo.TBLMRPMAKINE_V AS
SELECT DEMIR_KODU, INCKEYNO, DEMIR_ISMI, ISTKODU FROM erp.TBLMRPMAKINE;
GO

CREATE OR ALTER VIEW dbo.VW_STOK AS
SELECT STOK_KODU, STOK_ADI, GRUP_KODU, GRUP_ADI,
       KOD_1, AD1, KOD_2, AD2, KOD_3, AD3, KOD_4, AD4, KOD_5, AD5
FROM dbo.STOK;   -- ticaret tarafındaki STOK view'ının alt kümesi
GO

/* ------------------------------------------------- VW_ISEMRI
   İş emri başlığı: ürün, müşteri, sipariş, makine ve durum tek satırda.  */
CREATE OR ALTER VIEW dbo.VW_ISEMRI AS
SELECT
    i.TAKIPNO,
    i.ISEMRINO,
    KALIPADI = ISNULL(NULLIF(s.KOD_3, ''), 'STD'),
    i.STOK_KODU,
    s.STOK_ADI,
    CARI_KOD  = m.CARI_KOD,
    CARI_ISIM = c.CARI_ISIM,
    SIPARIS_NO = i.SIPARIS_NO,
    i.REFISEMRINO,
    i.SIPARIS_KONT,
    i.OPKODU,
    MAKINA_NO  = mk.INCKEYNO,
    MAKINE_ADI = mk.DEMIR_ISMI,
    ISTKODU    = mk.ISTKODU,
    ist.ISTISIM,
    i.MIKTAR,
    DURUM_KOD = CASE i.KAPATILDI WHEN 'E' THEN '30' WHEN 'T' THEN '40' ELSE '20' END,
    DURUM_ADI = CASE i.KAPATILDI WHEN 'E' THEN N'TAMAMLANDI'
                                 WHEN 'T' THEN N'KAPATILDI'
                                 ELSE N'ÜRETİMDE' END,
    i.ACIKLAMA,
    i.TESLIM_TARIHI,
    TRA_ACIKLAMA = N'',
    STOK_GRUPKODU = s.GRUP_KODU,
    STOK_GRUPADI  = sv.GRUP_ADI,
    STOK_KOD1 = s.KOD_1, STOK_AD1 = sv.AD1,
    STOK_KOD2 = s.KOD_2, STOK_AD2 = sv.AD2,
    STOK_KOD3 = s.KOD_3, STOK_AD3 = sv.AD3,
    STOK_KOD4 = s.KOD_4, STOK_AD4 = sv.AD4
FROM erp.TBLISEMRI i
JOIN erp.TBLSTSABIT   s   ON s.STOK_KODU  = i.STOK_KODU
JOIN dbo.STOK         sv  ON sv.STOK_KODU = i.STOK_KODU
JOIN erp.TBLMRPMAKINE mk  ON mk.INCKEYNO  = i.MRPMAKINENO
JOIN erp.TBLISTASYON  ist ON ist.ISTKODU  = mk.ISTKODU
LEFT JOIN erp.TBLSIPAMAS m ON m.FISNO     = i.SIPARIS_NO
LEFT JOIN erp.TBLCASABIT c ON c.CARI_KOD  = m.CARI_KOD;
GO

/* --------------------------------------------------- VW_AKTIVITE
   Aktivite kayıtları. Süreler aktivite tipine göre ayrı kolonlara dağılır;
   böylece rapor tarafında SUM(HAZIRLIK) / SUM(ISLEM) / SUM(ARIZA) yeterli.
   Duruşun verim hesabına dahil olup olmadığı arıza sabitinden gelir.      */
CREATE OR ALTER VIEW dbo.VW_AKTIVITE AS
SELECT
    u.INCKEYNO,
    u.TAKIP_ID,
    u.ISEMRINO,
    TARIH = CAST(u.BASLANGICTARIH AS date),
    YIL   = YEAR(u.BASLANGICTARIH),
    HAFTA = DATEPART(ISO_WEEK, u.BASLANGICTARIH),
    u.BASLANGICTARIH,
    u.BITISTARIHSAAT,
    DEVAM_EDIYOR = CASE WHEN u.BITISTARIHSAAT IS NULL THEN 1 ELSE 0 END,
    u.URETILENMIKTAR,
    u.FIREMIKTAR,
    ACIKLAMA = ISNULL(ar.ACIKLAMA, ISNULL(u.ACIKLAMA, N'')),
    BRUT_SURE = u.SURE + ISNULL(u.MOLA, 0),
    MOLA      = ISNULL(u.MOLA, 0),
    NET_SURE  = u.SURE,
    u.AKTIVITEKODU,
    AKTIVITE_ADI = ak.ACIKLAMA,
    u.ARIZAKODU,
    ARIZA_ADI = ar.ACIKLAMA,
    SURE_DAHIL = ISNULL(ar.SUREDAHIL, 'E'),
    HAZIRLIK = CASE WHEN ak.AKTIVITETIPI = 0 THEN u.SURE ELSE 0 END,
    ISLEM    = CASE WHEN ak.AKTIVITETIPI = 1 THEN u.SURE ELSE 0 END,
    ARIZA    = CASE WHEN ak.AKTIVITETIPI = 2 AND ISNULL(ar.SUREDAHIL, 'E') = 'E'
                    THEN u.SURE ELSE 0 END,
    HATBOS   = CASE WHEN ak.AKTIVITETIPI = 2 AND ISNULL(ar.SUREDAHIL, 'E') = 'H'
                    THEN u.SURE ELSE 0 END,
    -- üretilen miktarın standart karşılığı: verim ölçüsünün payı
    STDSURE_ISLEM = CASE WHEN u.URETILENMIKTAR > 0 AND ISNULL(u.STANDARTMIKTAR, 0) > 0
                         THEN u.STANDARTSURE * u.URETILENMIKTAR / u.STANDARTMIKTAR
                         ELSE 0 END,
    KONFIGURASYON_ID = k.KONFIGID,
    u.STANDARTHAZIRLIK,
    u.STANDARTMIKTAR,
    u.STANDARTSURE,
    ADDK = CASE WHEN u.SURE > 0 THEN u.URETILENMIKTAR / u.SURE ELSE 0 END
FROM erp.TBLUAKMAS u
JOIN erp.TBLUAKAKTIVITESABIT ak ON ak.AKTIVITEKODU = u.AKTIVITEKODU
LEFT JOIN erp.TBLUAKARIZASABIT ar ON ar.ARIZAKODU = u.ARIZAKODU
LEFT JOIN (SELECT DISTINCT TAKIPID, KONFIGID FROM erp.TBLISEMRI_KAYNAK) k
       ON k.TAKIPID = u.TAKIP_ID;
GO

/* ---------------------------------------------------- VW_ARIZA */
CREATE OR ALTER VIEW dbo.VW_ARIZA AS
SELECT
    u.INCKEYNO,
    u.TAKIP_ID,
    u.ISEMRINO,
    u.STOKKODU AS STOK_KODU,
    s.STOK_ADI,
    u.BASLANGICTARIH,
    u.BITISTARIHSAAT,
    SURE = u.SURE,
    ACIKLAMA = ISNULL(u.ACIKLAMA, N''),
    ARIZA_ADI = ar.ACIKLAMA,
    DEVAM_EDIYOR = CASE WHEN u.BITISTARIHSAAT IS NULL THEN 1 ELSE 0 END
FROM erp.TBLUAKMAS u
JOIN erp.TBLUAKAKTIVITESABIT ak ON ak.AKTIVITEKODU = u.AKTIVITEKODU AND ak.AKTIVITETIPI = 2
JOIN erp.TBLUAKARIZASABIT   ar ON ar.ARIZAKODU     = u.ARIZAKODU
JOIN erp.TBLSTSABIT          s ON s.STOK_KODU      = u.STOKKODU;
GO

/* ----------------------------------------------------- VW_URETIM_HAFTALIK
   İş emri operasyonu bazında haftalık toplamlar: gerçekleşen ve teorik
   süreler yan yana. Verim takibi olmayan istasyonlarda (VERIMTAKIP='H')
   teorik süre yerine gerçekleşen süre kullanılır.                        */
CREATE OR ALTER VIEW dbo.VW_URETIM_HAFTALIK AS
SELECT
    i.TAKIPNO,
    i.ISEMRINO,
    i.STOK_KODU,
    i.SIPARIS_NO,
    SIPKONT = i.SIPARIS_KONT,
    i.REFISEMRINO,
    i.TESLIM_TARIHI,
    i.KAPATILDI,
    i.OPKODU,
    MAKINE_ID   = mk.INCKEYNO,
    MAKINE_KODU = mk.DEMIR_KODU,
    VERIMLILIK  = CASE WHEN SUM(a.ISLEM) > 0
                       THEN SUM(a.STDSURE_ISLEM) / SUM(a.ISLEM) END,
    VERIMTAKIP  = CASE WHEN ist.ISTISIM IN (N'PRES', N'MONTAJ') THEN 'E' ELSE 'H' END,
    ISTKODU = mk.ISTKODU,
    ist.ISTISIM,
    STHAR_CARIKOD = m.CARI_KOD,
    MAMUL     = s.STOK_ADI,
    s.STOK_ADI,
    KOD_1 = s.KOD_1,
    KOD_4 = s.KOD_4,
    PARCA = sv.AD5,
    KALIP = ISNULL(NULLIF(s.KOD_3, ''), 'STD'),
    YIL   = MIN(YEAR(a.BASLANGICTARIH)),
    HAFTA = MIN(DATEPART(ISO_WEEK, a.BASLANGICTARIH)),
    URETIM = SUM(a.URETILENMIKTAR),
    FIRE   = SUM(a.FIREMIKTAR),
    GERC_ARIZA    = SUM(a.ARIZA),
    GERC_HATBOS   = SUM(a.HATBOS),
    GERC_ISLEM    = SUM(a.ISLEM),
    GERC_HAZIRLIK = SUM(a.HAZIRLIK),
    TEO_ISLEM     = SUM(a.STDSURE_ISLEM),
    TEO_HAZIRLIK_TAKIPSIZ = SUM(a.STANDARTHAZIRLIK) * 0.8,
    TEO_HAZIRLIK_TAKIPLI  = SUM(a.STANDARTHAZIRLIK) * 0.95,
    DURUM_ADI = CASE i.KAPATILDI WHEN 'E' THEN N'TAMAMLANDI'
                                 WHEN 'T' THEN N'KAPATILDI'
                                 ELSE N'ÜRETİMDE' END,
    FIREORANI_URETIM   = CASE WHEN SUM(a.URETILENMIKTAR) + SUM(a.FIREMIKTAR) > 0
                              THEN SUM(a.FIREMIKTAR)
                                   / (SUM(a.URETILENMIKTAR) + SUM(a.FIREMIKTAR)) END,
    FIREORANI_MINFIRE  = CASE WHEN SUM(a.URETILENMIKTAR) > 0
                              THEN SUM(a.FIREMIKTAR) / SUM(a.URETILENMIKTAR) * 0.8 END
FROM erp.TBLISEMRI i
JOIN dbo.VW_AKTIVITE a ON a.TAKIP_ID = i.TAKIPNO
JOIN erp.TBLMRPMAKINE mk  ON mk.INCKEYNO = i.MRPMAKINENO
JOIN erp.TBLISTASYON  ist ON ist.ISTKODU = mk.ISTKODU
JOIN erp.TBLSTSABIT   s   ON s.STOK_KODU = i.STOK_KODU
JOIN dbo.STOK         sv  ON sv.STOK_KODU = i.STOK_KODU
LEFT JOIN erp.TBLSIPAMAS m ON m.FISNO = i.SIPARIS_NO
GROUP BY i.TAKIPNO, i.ISEMRINO, i.STOK_KODU, i.SIPARIS_NO, i.SIPARIS_KONT,
         i.REFISEMRINO, i.TESLIM_TARIHI, i.KAPATILDI, i.OPKODU,
         mk.INCKEYNO, mk.DEMIR_KODU, mk.ISTKODU, ist.ISTISIM,
         m.CARI_KOD, s.STOK_ADI, s.KOD_1, s.KOD_3, s.KOD_4, sv.AD5;
GO

/* --------------------------------------------- VW_DEVAM_EDEN_ISLER
   Tezgâhtaki işler: kapanmamış iş emirleri. İnsan-saat, iş emrinin görev
   bazlı işçi yükünden hesaplanır; ORT_CALISAN ölçüsü bunu geri çevirir.  */
CREATE OR ALTER VIEW dbo.VW_DEVAM_EDEN_ISLER AS
SELECT
    i.TAKIPNO AS TAKIP_ID,
    i.ISEMRINO,
    AKTIVITEKODU = MAX(a.AKTIVITEKODU),
    AKTIVITE_ADI = MAX(a.AKTIVITE_ADI),
    BASLANGICTARIH = MIN(a.BASLANGICTARIH),
    DEVAM_EDENSURE = DATEDIFF(MINUTE, MIN(a.BASLANGICTARIH), GETDATE()),
    MIKTAR = MAX(i.MIKTAR),
    DEMIR_KODU = MAX(mk.DEMIR_KODU),
    ISTISIM = MAX(ist.ISTISIM),
    KAPATILDI = MAX(i.KAPATILDI),
    OPKODU = MAX(i.OPKODU),
    STOK_ADI = MAX(s.STOK_ADI),
    STOK_KODU = MAX(i.STOK_KODU),
    CARI_ISIM = MAX(c.CARI_ISIM),
    SIPARIS_NO = MAX(i.SIPARIS_NO),
    REFISEMRINO = MAX(i.REFISEMRINO),
    URETIM = SUM(a.URETILENMIKTAR),
    FIRE   = SUM(a.FIREMIKTAR),
    HAZIRLIK = SUM(a.HAZIRLIK),
    ISLEM    = SUM(a.ISLEM),
    ARIZA    = SUM(a.ARIZA),
    STDSURE_V = SUM(a.STDSURE_ISLEM),
    TAMAMLANMA = CASE WHEN MAX(i.MIKTAR) > 0
                      THEN SUM(a.URETILENMIKTAR) / MAX(i.MIKTAR) END,
    INSANSAAT_HAZIRLIK = SUM(a.HAZIRLIK) * MAX(isc.CALISAN) / 60,
    INSANSAAT_ISLEM    = SUM(a.ISLEM)    * MAX(isc.CALISAN) / 60,
    ORTALAMA_CALISAN_SAYISI = MAX(isc.CALISAN),
    VERIM_TAKIPET = 'E',
    KT_VERIMTAKIP = CASE WHEN MAX(ist.ISTISIM) IN (N'PRES', N'MONTAJ') THEN 'E' ELSE 'H' END
FROM erp.TBLISEMRI i
JOIN dbo.VW_AKTIVITE a ON a.TAKIP_ID = i.TAKIPNO
JOIN erp.TBLMRPMAKINE mk  ON mk.INCKEYNO = i.MRPMAKINENO
JOIN erp.TBLISTASYON  ist ON ist.ISTKODU = mk.ISTKODU
JOIN erp.TBLSTSABIT   s   ON s.STOK_KODU = i.STOK_KODU
LEFT JOIN erp.TBLSIPAMAS m ON m.FISNO    = i.SIPARIS_NO
LEFT JOIN erp.TBLCASABIT c ON c.CARI_KOD = m.CARI_KOD
LEFT JOIN (SELECT TAKIPID, CALISAN = SUM(MIKTAR / NULLIF(BAZMIKTAR, 0))
           FROM erp.TBLISEMRI_KAYNAK GROUP BY TAKIPID) isc ON isc.TAKIPID = i.TAKIPNO
WHERE i.KAPATILDI IN ('O', 'H')
GROUP BY i.TAKIPNO, i.ISEMRINO;
GO

/* ------------------------------------------------------- URETIM_VERI_OEE
   Makine başına TEK satır. Durum şu sırayla belirlenir:
     1) makinede kapanmamış bir aktivite varsa -> onun tipi
        (0 HAZIRLIK, 1 ISLEM, 2 ARIZA/DURUŞ)
     2) yoksa iş emrinin kapatılma durumu (E TAMAMLANDI / T KAPATILDI / diğer PASIF)
   İşçi dağılımı görev kodlarına göre pivotlanır — SVG şeridinin sekiz kolonu.  */
CREATE OR ALTER VIEW dbo.URETIM_VERI_OEE AS
WITH son_is AS (   -- makine başına en güncel iş emri
    SELECT MRPMAKINENO, TAKIP_ID, ISEMRINO,
           BAS_TAR = MIN(BASLANGICTARIH),
           BIT_TAR = MAX(BITISTARIHSAAT),
           ACIK_SAYI = SUM(CASE WHEN BITISTARIHSAAT IS NULL THEN 1 ELSE 0 END),
           SIRA = ROW_NUMBER() OVER (PARTITION BY MRPMAKINENO
                   ORDER BY MAX(CASE WHEN BITISTARIHSAAT IS NULL THEN 1 ELSE 0 END) DESC,
                            MIN(BASLANGICTARIH) DESC)
    FROM erp.TBLUAKMAS
    WHERE BITISTARIHSAAT > DATEADD(MONTH, -1, GETDATE()) OR BITISTARIHSAAT IS NULL
    GROUP BY MRPMAKINENO, TAKIP_ID, ISEMRINO
),
acik_aktivite AS (  -- devam eden aktivitenin tipi
    SELECT u.TAKIP_ID, u.MRPMAKINENO,
           ISLEM_ADI = MAX(CASE ak.AKTIVITETIPI WHEN 0 THEN N'HAZIRLIK'
                                                WHEN 1 THEN N'ISLEM'
                                                WHEN 2 THEN N'ARIZA/DURUŞ' END)
    FROM erp.TBLUAKMAS u
    JOIN erp.TBLUAKAKTIVITESABIT ak ON ak.AKTIVITEKODU = u.AKTIVITEKODU
    WHERE u.BITISTARIHSAAT IS NULL
    GROUP BY u.TAKIP_ID, u.MRPMAKINENO
),
iscilik AS (        -- görev kodlarını kolonlara pivotla
    SELECT k.TAKIPID, k.KONFIGID,
        BANT_LIDERI      = SUM(CASE k.KAYNAK_KODU WHEN 'K001' THEN k.MIKTAR/NULLIF(k.BAZMIKTAR,0) ELSE 0 END),
        SEKILLENDIRME    = SUM(CASE k.KAYNAK_KODU WHEN 'K002' THEN k.MIKTAR/NULLIF(k.BAZMIKTAR,0) ELSE 0 END),
        KALITECI         = SUM(CASE k.KAYNAK_KODU WHEN 'K005' THEN k.MIKTAR/NULLIF(k.BAZMIKTAR,0) ELSE 0 END),
        PAKETLEMECI      = SUM(CASE k.KAYNAK_KODU WHEN 'K004' THEN k.MIKTAR/NULLIF(k.BAZMIKTAR,0) ELSE 0 END),
        PRES_OPR         = SUM(CASE k.KAYNAK_KODU WHEN 'K024' THEN k.MIKTAR/NULLIF(k.BAZMIKTAR,0) ELSE 0 END),
        PRES_ISTIFLEYICI = SUM(CASE k.KAYNAK_KODU WHEN 'K025' THEN k.MIKTAR/NULLIF(k.BAZMIKTAR,0) ELSE 0 END),
        MAKAS_OPR        = SUM(CASE k.KAYNAK_KODU WHEN 'K026' THEN k.MIKTAR/NULLIF(k.BAZMIKTAR,0) ELSE 0 END),
        BASKI_OPR        = SUM(CASE k.KAYNAK_KODU WHEN 'K027' THEN k.MIKTAR/NULLIF(k.BAZMIKTAR,0) ELSE 0 END)
    FROM erp.TBLISEMRI_KAYNAK k
    GROUP BY k.TAKIPID, k.KONFIGID
)
SELECT
    si.TAKIP_ID,
    si.BAS_TAR,
    si.BIT_TAR,
    si.ISEMRINO,
    i.REFISEMRINO,
    i.SIPARIS_NO,
    STOKKODU = i.STOK_KODU,
    s.STOK_ADI,
    ist.ISTISIM,
    MRPMAKINENO = mk.INCKEYNO,
    mk.DEMIR_KODU,
    mk.DEMIR_ISMI,
    ISEMRI_MIKTARI = i.MIKTAR,
    URETILENMIKTAR = ISNULL(t.URETILEN, 0),
    FIREMIKTAR     = ISNULL(t.FIRE, 0),
    G_HAZIRLIK     = ISNULL(t.HAZIRLIK, 0),
    G_ISLEM        = ISNULL(t.ISLEM, 0),
    DURUSSURE      = ISNULL(t.ARIZA, 0),
    ISLEM_DURUMU   = COALESCE(aa.ISLEM_ADI,
                              CASE i.KAPATILDI WHEN 'E' THEN N'TAMAMLANDI'
                                               WHEN 'T' THEN N'KAPATILDI'
                                               ELSE N'PASIF' END),
    i.OPKODU,
    CARI_KODU = m.CARI_KOD,
    CARI_ISIM = c.CARI_ISIM,
    KONFIG_ID = ic.KONFIGID,
    KONFIG_ADI = cfg.ACIKLAMA,
    STD_SURE = CASE WHEN ISNULL(sz.URETIM_SURESI, 0) = 0 THEN NULL
                    ELSE sz.MIKTAR / sz.URETIM_SURESI END,
    ic.BANT_LIDERI, ic.SEKILLENDIRME, ic.KALITECI, ic.PAKETLEMECI,
    ic.PRES_OPR, ic.PRES_ISTIFLEYICI, ic.MAKAS_OPR, ic.BASKI_OPR
FROM son_is si
JOIN erp.TBLISEMRI    i   ON i.TAKIPNO   = si.TAKIP_ID
JOIN erp.TBLMRPMAKINE mk  ON mk.INCKEYNO = si.MRPMAKINENO
JOIN erp.TBLISTASYON  ist ON ist.ISTKODU = mk.ISTKODU
JOIN erp.TBLSTSABIT   s   ON s.STOK_KODU = i.STOK_KODU
LEFT JOIN acik_aktivite aa ON aa.TAKIP_ID = si.TAKIP_ID
                          AND aa.MRPMAKINENO = si.MRPMAKINENO
LEFT JOIN (SELECT TAKIP_ID,
                  URETILEN = SUM(URETILENMIKTAR), FIRE = SUM(FIREMIKTAR),
                  HAZIRLIK = SUM(HAZIRLIK), ISLEM = SUM(ISLEM), ARIZA = SUM(ARIZA)
           FROM dbo.VW_AKTIVITE GROUP BY TAKIP_ID) t ON t.TAKIP_ID = si.TAKIP_ID
LEFT JOIN iscilik ic ON ic.TAKIPID = si.TAKIP_ID
LEFT JOIN erp.TBLMAKINE_CONFIG cfg ON cfg.KONFIGID = ic.KONFIGID
LEFT JOIN erp.TBLURETIM_STANDART_ZAMANLAR sz
       ON sz.OPKODU = i.OPKODU AND sz.KONFIGID = ic.KONFIGID
      AND sz.GRUP_KODU = ISNULL(s.KOD_4, '00')
LEFT JOIN erp.TBLSIPAMAS m ON m.FISNO    = i.SIPARIS_NO
LEFT JOIN erp.TBLCASABIT c ON c.CARI_KOD = m.CARI_KOD
WHERE si.SIRA = 1;   -- makine başına tek satır
GO

/* -------------------------------------------------------- CALISAN_SAYISI
   İş emrinin görev bazlı işçi sayısı — SVG şeridinin uzun (unpivot) hâli. */
CREATE OR ALTER VIEW dbo.CALISAN_SAYISI AS
SELECT
    TAKIPID = k.TAKIPID,
    GOREV_ADI = ks.GOREV_ADI,
    ISCI_SAYISI = SUM(k.MIKTAR / NULLIF(k.BAZMIKTAR, 0))
FROM erp.TBLISEMRI_KAYNAK k
JOIN erp.TBLKAYNAKSABIT ks ON ks.KAYNAK_KODU = k.KAYNAK_KODU
GROUP BY k.TAKIPID, ks.GOREV_ADI
HAVING SUM(k.MIKTAR / NULLIF(k.BAZMIKTAR, 0)) > 0;
GO

/* -------------------------------------------------------------- puantaj */
CREATE OR ALTER VIEW dbo.VW_PUANTAJ_GUNLUK AS
SELECT
    ID = ROW_NUMBER() OVER (ORDER BY TARIH, CALISMA_GRUP),
    BUGUNMU = CASE WHEN TARIH = CAST(GETDATE() AS date) THEN CAST(1 AS bit)
                   ELSE CAST(0 AS bit) END,
    TARIH,
    CALISMA_GRUP,
    KisiSayisi = KISI_SAYISI
FROM erp.TBLPUANTAJ;
GO

-- Haftalık puantaj, iş emri anahtarıyla eşleşecek şekilde
CREATE OR ALTER VIEW dbo.VW_PUANTAJ_HAFTALIK AS
SELECT
    ID    = i.TAKIPNO,
    YIL   = YEAR(x.BAS),
    HAFTA = DATEPART(ISO_WEEK, x.BAS),
    GRUP  = ist.ISTISIM,
    TOPLAM = ISNULL(p.TOPLAM, 0)
FROM erp.TBLISEMRI i
JOIN erp.TBLMRPMAKINE mk  ON mk.INCKEYNO = i.MRPMAKINENO
JOIN erp.TBLISTASYON  ist ON ist.ISTKODU = mk.ISTKODU
CROSS APPLY (SELECT BAS = MIN(BASLANGICTARIH) FROM erp.TBLUAKMAS u
             WHERE u.TAKIP_ID = i.TAKIPNO) x
OUTER APPLY (SELECT TOPLAM = SUM(KISI_SAYISI) FROM erp.TBLPUANTAJ p2
             WHERE p2.CALISMA_GRUP = ist.ISTISIM
               AND DATEPART(ISO_WEEK, p2.TARIH) = DATEPART(ISO_WEEK, x.BAS)
               AND YEAR(p2.TARIH) = YEAR(x.BAS)) p;
GO
