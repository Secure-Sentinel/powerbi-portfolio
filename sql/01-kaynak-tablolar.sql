/* =====================================================================
   Test Firma A.Ş. · Kaynak tablolar (sadeleştirilmiş ERP şeması)
   ---------------------------------------------------------------------
   Gerçek kurulumda bu tablolar ERP'nin kendi tabloları olur; burada
   raporların ihtiyaç duyduğu kolonlara indirgenmiş hâlleri var.
   Hedef: SQL Server 2016+
   ===================================================================== */
IF SCHEMA_ID('erp') IS NULL EXEC('CREATE SCHEMA erp');
GO

/* ----------------------------------------------------------- boyutlar */
-- Stok (ürün/malzeme) kartı. KOD_1..KOD_5 ERP'nin serbest rapor kodları:
-- bu tesiste KOD_1 = şekil, KOD_2 = kullanım alanı, KOD_3 = kalıp,
-- KOD_4 = baskı tipi, KOD_5 = parça sayısı olarak kullanılıyor.
CREATE TABLE erp.TBLSTSABIT (
    STOK_KODU       varchar(24)  NOT NULL PRIMARY KEY,
    STOK_ADI        nvarchar(80) NOT NULL,
    INGISIM         nvarchar(80) NULL,
    GRUP_KODU       varchar(8)   NULL,      -- 01 Mamul / 02 Hammadde / 03 Diğer
    KOD_1           varchar(12)  NULL,
    KOD_2           varchar(12)  NULL,
    KOD_3           varchar(12)  NULL,      -- kalıp kodu (ör. 153-118, 268-044)
    KOD_4           varchar(12)  NULL,
    KOD_5           varchar(12)  NULL,
    KT_YUKSEKLIK    decimal(9,2) NULL,      -- kutu yüksekliği (mm)
    OLCU_BR1        varchar(10)  NULL,
    OLCU_BR2        varchar(10)  NULL,
    OLCU_BR3        varchar(10)  NULL,
    BIRIM2_CARPAN   decimal(12,3) NULL,     -- 1 koli = kaç adet
    BIRIM3_CARPAN   decimal(12,3) NULL,     -- 1 palet = kaç adet
    BIRIM_MALIYET   decimal(18,4) NULL
);

-- Rapor kodu sözlüğü: kod -> ad çözümlemesi tek yerden yapılır.
CREATE TABLE erp.TBLKODSOZLUK (
    KOD_TIPI  varchar(12) NOT NULL,   -- KOD_1 / KOD_2 / ... / GRUP / SEKTOR / BOLGE
    KOD       varchar(12) NOT NULL,
    AD        nvarchar(60) NOT NULL,
    CONSTRAINT PK_TBLKODSOZLUK PRIMARY KEY (KOD_TIPI, KOD)
);

-- Cari (müşteri + tedarikçi aynı tabloda; CARI_TIPI ayırır)
CREATE TABLE erp.TBLCASABIT (
    CARI_KOD       varchar(20)  NOT NULL PRIMARY KEY,
    CARI_ISIM      nvarchar(90) NOT NULL,
    CARI_TIPI      varchar(12)  NOT NULL,   -- MUSTERI / TEDARIKCI
    DEPARTMAN      varchar(12)  NULL,       -- YURTICI / YURTDISI / BASKILI / SATINALMA
    ULKE_KODU      varchar(4)   NULL,
    GRUP_KODU      varchar(8)   NULL,
    SEKTOR_KODU    varchar(8)   NULL,
    SEKTOR2_KODU   varchar(8)   NULL,
    BOLGE_KODU     varchar(8)   NULL,
    RAPOR_KODU1    varchar(12)  NULL,
    RAPOR_KODU2    varchar(12)  NULL,
    RAPOR_KODU3    varchar(12)  NULL,
    CARI_TEMSILCI  nvarchar(40) NULL,
    MUSTERI_YERI   nvarchar(40) NULL
);

-- Günlük kur. Her hareket kendi tarihindeki kurla USD'ye çevrilir.
CREATE TABLE erp.TBLKUR (
    TARIH  date          NOT NULL PRIMARY KEY,
    USD    decimal(12,4) NOT NULL
);

/* ------------------------------------------------------ ticari hareket */
-- Sipariş başlığı (satış ve satın alma aynı yapıda; SIP_TIPI ayırır)
CREATE TABLE erp.TBLSIPAMAS (
    FISNO         varchar(20) NOT NULL PRIMARY KEY,
    SIP_TIPI      char(1)     NOT NULL,      -- S satış / A satın alma
    STHAR_TARIH   date        NOT NULL,
    CARI_KOD      varchar(20) NOT NULL,
    ODEKOD        varchar(8)  NULL,
    MUSTERI_SIPNO varchar(30) NULL,
    TESLIM_YERI   nvarchar(40) NULL
);

-- Sipariş satırı. GONDERILEN/ALINAN, stok hareketlerinden beslenen
-- kümülatif sevk/giriş miktarıdır; KALAN = miktar - gönderilen.
CREATE TABLE erp.TBLSIPATRA (
    INCKEYNO     bigint       NOT NULL PRIMARY KEY,
    FISNO        varchar(20)  NOT NULL,
    SIRA         int          NOT NULL,
    STOK_KODU    varchar(24)  NOT NULL,
    MIKTAR       decimal(18,4) NOT NULL,
    NET_FIYAT    decimal(18,4) NOT NULL,     -- TL birim fiyat
    GONDERILEN   decimal(18,4) NOT NULL DEFAULT 0,
    TERMIN       date         NULL,          -- satın almada tedarikçi termini
    HTUR         varchar(10)  NULL,          -- YERLİ / İTHAL
    ACIKLAMA1    nvarchar(60) NULL,
    ACIKLAMA2    nvarchar(60) NULL,
    ACIKLAMA3    nvarchar(60) NULL,
    ACIKLAMA4    nvarchar(60) NULL,
    ACIKLAMA5    nvarchar(60) NULL,
    CONSTRAINT UQ_TBLSIPATRA UNIQUE (FISNO, SIRA)
);

-- Stok hareketi: fatura/irsaliye satırları. GCKOD hareket türü:
-- 1 giriş (mal kabul), 4 çıkış (satış faturası)
CREATE TABLE erp.TBLSTHAR (
    INCKEYNO      bigint        NOT NULL PRIMARY KEY,
    STHAR_TARIH   date          NOT NULL,
    FISNO         varchar(20)   NOT NULL,
    STOK_KODU     varchar(24)   NOT NULL,
    CARI_KOD      varchar(20)   NOT NULL,
    GCKOD         char(1)       NOT NULL,
    MIKTAR        decimal(18,4) NOT NULL,
    NET_FIYAT     decimal(18,4) NOT NULL,
    SIP_FISNO     varchar(20)   NULL,        -- kaynak sipariş
    SIP_SIRA      int           NULL,
    ACIKLAMA      nvarchar(60)  NULL,
    ODE_GUN       int           NULL
);

-- Ödeme koşulu tanımı ve taksit ofsetleri
CREATE TABLE erp.TBLODEKOD (
    ODEKOD        varchar(8)   NOT NULL PRIMARY KEY,
    ACIKLAMA      nvarchar(40) NOT NULL,
    PESINAT_ORANI decimal(5,4) NOT NULL,
    VADE_GUNU     int          NOT NULL
);
CREATE TABLE erp.TBLODEMEPLAN (
    ODEKOD  varchar(8)   NOT NULL,
    OFSET   int          NOT NULL,           -- fatura tarihine eklenecek gün
    ORAN    decimal(5,4) NOT NULL,
    CONSTRAINT PK_TBLODEMEPLAN PRIMARY KEY (ODEKOD, OFSET)
);

-- Cari hareket (tahsilat/ödeme/fatura). Bakiye buradan toplanır.
CREATE TABLE erp.TBLCAHAR (
    INCKEYNO  bigint        NOT NULL PRIMARY KEY,
    CARI_KOD  varchar(20)   NOT NULL,
    TARIH     date          NOT NULL,
    ALACAK_TL decimal(18,2) NOT NULL DEFAULT 0,
    BORC_TL   decimal(18,2) NOT NULL DEFAULT 0
);

/* --------------------------------------------------------- üretim tarafı */
CREATE TABLE erp.TBLISTASYON (
    ISTKODU  varchar(8)   NOT NULL PRIMARY KEY,
    ISTISIM  nvarchar(30) NOT NULL           -- PRES / KESIM / MATBAA / MONTAJ / DIJITAL
);

CREATE TABLE erp.TBLMRPMAKINE (
    INCKEYNO    int          NOT NULL PRIMARY KEY,
    DEMIR_KODU  varchar(12)  NOT NULL UNIQUE,   -- PRS-01, KSM-03, MTB-02, MNT-10 ...
    DEMIR_ISMI  nvarchar(60) NOT NULL,
    ISTKODU     varchar(8)   NOT NULL
);

-- İş emri başlığı
CREATE TABLE erp.TBLISEMRI (
    TAKIPNO      bigint        NOT NULL PRIMARY KEY,
    ISEMRINO     varchar(20)   NOT NULL,
    REFISEMRINO  varchar(20)   NULL,
    STOK_KODU    varchar(24)   NOT NULL,
    SIPARIS_NO   varchar(20)   NULL,
    SIPARIS_KONT int           NULL,
    OPKODU       varchar(8)    NOT NULL,        -- operasyon sırası
    MRPMAKINENO  int           NOT NULL,
    MIKTAR       decimal(18,4) NOT NULL,
    TESLIM_TARIHI date         NULL,
    KAPATILDI    char(1)       NOT NULL,        -- E kapandı / T kapatıldı / O,H açık
    ACIKLAMA     nvarchar(60)  NULL
);

-- Aktivite sabitleri: tip 0 hazırlık, 1 işlem, 2 duruş
CREATE TABLE erp.TBLUAKAKTIVITESABIT (
    AKTIVITEKODU varchar(8)   NOT NULL PRIMARY KEY,
    ACIKLAMA     nvarchar(30) NOT NULL,
    AKTIVITETIPI tinyint      NOT NULL
);
CREATE TABLE erp.TBLUAKARIZASABIT (
    ARIZAKODU  varchar(8)   NOT NULL PRIMARY KEY,
    ACIKLAMA   nvarchar(40) NOT NULL,
    SUREDAHIL  char(1)      NOT NULL DEFAULT 'E'  -- duruş, verim hesabına dahil mi
);

-- Makine aktivite kaydı: SCADA'nın kalbi. BITISTARIHSAAT NULL ise
-- o aktivite hâlâ devam ediyor (makine o an bu durumdadır).
CREATE TABLE erp.TBLUAKMAS (
    INCKEYNO        bigint        NOT NULL PRIMARY KEY,
    TAKIP_ID        bigint        NOT NULL,
    ISEMRINO        varchar(20)   NOT NULL,
    MRPMAKINENO     int           NOT NULL,
    ISTASYONKODU    varchar(8)    NOT NULL,
    STOKKODU        varchar(24)   NOT NULL,
    AKTIVITEKODU    varchar(8)    NOT NULL,
    ARIZAKODU       varchar(8)    NULL,
    BASLANGICTARIH  datetime2(0)  NOT NULL,
    BITISTARIHSAAT  datetime2(0)  NULL,
    SURE            decimal(12,2) NULL,          -- dakika
    MOLA            decimal(12,2) NULL,
    URETILENMIKTAR  decimal(18,4) NOT NULL DEFAULT 0,
    FIREMIKTAR      decimal(18,4) NOT NULL DEFAULT 0,
    STANDARTSURE    decimal(12,4) NULL,          -- STANDARTMIKTAR adet için standart dk
    STANDARTMIKTAR  decimal(18,4) NULL,
    STANDARTHAZIRLIK decimal(12,2) NULL,
    ACIKLAMA        nvarchar(60)  NULL
);
CREATE INDEX IX_TBLUAKMAS_ACIK ON erp.TBLUAKMAS (BITISTARIHSAAT, MRPMAKINENO)
    INCLUDE (TAKIP_ID, AKTIVITEKODU);

-- İş emrinin görev bazlı işçi yükü (bir iş emrinde kaç bant lideri,
-- kaç şekillendirme operatörü çalışıyor). SVG işçi şeridi buradan gelir.
CREATE TABLE erp.TBLISEMRI_KAYNAK (
    TAKIPID      bigint        NOT NULL,
    KAYNAK_KODU  varchar(8)    NOT NULL,     -- K001 bant lideri, K002 şekillendirme ...
    KONFIGID     int           NULL,
    MIKTAR       decimal(12,4) NOT NULL,
    BAZMIKTAR    decimal(12,4) NOT NULL,
    CONSTRAINT PK_TBLISEMRI_KAYNAK PRIMARY KEY (TAKIPID, KAYNAK_KODU)
);
CREATE TABLE erp.TBLKAYNAKSABIT (
    KAYNAK_KODU varchar(8)   NOT NULL PRIMARY KEY,
    GOREV_ADI   nvarchar(30) NOT NULL
);

-- Vardiya/puantaj: çalışma grubu bazında günlük kişi sayısı
CREATE TABLE erp.TBLPUANTAJ (
    TARIH        date          NOT NULL,
    CALISMA_GRUP nvarchar(20)  NOT NULL,
    KISI_SAYISI  decimal(9,2)  NOT NULL,
    CONSTRAINT PK_TBLPUANTAJ PRIMARY KEY (TARIH, CALISMA_GRUP)
);

-- Makine konfigürasyonu ve standart zamanlar
CREATE TABLE erp.TBLMAKINE_CONFIG (
    KONFIGID int          NOT NULL PRIMARY KEY,
    ACIKLAMA nvarchar(30) NOT NULL            -- TEK VARDİYA / ÇİFT VARDİYA / SÜREKLİ
);
CREATE TABLE erp.TBLURETIM_STANDART_ZAMANLAR (
    OPKODU        varchar(8)    NOT NULL,
    KONFIGID      int           NOT NULL,
    GRUP_KODU     varchar(8)    NOT NULL,
    MIKTAR        decimal(18,4) NOT NULL,
    URETIM_SURESI decimal(12,4) NOT NULL,
    CONSTRAINT PK_STD_ZAMAN PRIMARY KEY (OPKODU, KONFIGID, GRUP_KODU)
);
GO
