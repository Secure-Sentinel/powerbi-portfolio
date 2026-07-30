# Veri hattı — SQL katmanı

Raporlar gerçekte bir ERP veritabanı üzerindeki SQL view'larından beslenir. Bu klasör,
o katmanın **sadeleştirilmiş, okunabilir bir yeniden yazımıdır**: üretimdeki view mantığını
birebir vermez, veri hattının şeklini ve dönüşümlerini gösterir.

| Dosya | İçerik |
|---|---|
| [`01-kaynak-tablolar.sql`](01-kaynak-tablolar.sql) | ERP tarafındaki kaynak tabloların sadeleştirilmiş hâli (stok/cari sabit kartları, sipariş ve stok hareketleri, iş emri ve makine aktivite kayıtları, günlük kur) |
| [`02-ticaret-viewlari.sql`](02-ticaret-viewlari.sql) | Ticaret ve satın alma raporlarının okuduğu view'lar: `CARI`, `STOK`, `SIPARIS`, `CIRO`, `SIPARIS_ODEME`, `SATIN_ALMA`, `SATINALMA_SIPARIS`, `CARI_ALACAKBORC`, `SATINALMA_TARIHLER` |
| [`03-uretim-viewlari.sql`](03-uretim-viewlari.sql) | SCADA raporunun okuduğu view'lar: `VW_*` ve `URETIM_VERI_OEE` |

Raporları çalıştırmak için bu SQL'e **ihtiyaç yok** — Power BI projeleri doğrudan
`data/*.csv` dosyalarını okur. Bu klasör, "veri Power BI'a gelmeden önce nerede
şekillenmiş" sorusunun cevabıdır.

## Hattın mantığı

```
TBLSTSABIT / TBLCASABIT        →  STOK, CARI                     (boyutlar, rapor kodları çözülür)
TBLSIPAMAS + TBLSIPATRA        →  SIPARIS, SATINALMA_SIPARIS      (satır bazında gönderilen/kalan, termin)
TBLSTHAR                       →  CIRO, SATIN_ALMA                (fatura/irsaliye hareketleri, USD karşılığı)
TBLODEMEPLAN                   →  SIPARIS_ODEME                   (peşinat/vade taksitleri)
TBLCAHAR                       →  CARI_ALACAKBORC                 (gün sonu bakiye + kur)
TBLISEMRI + TBLUAKMAS          →  VW_*, URETIM_VERI_OEE           (iş emri, aktivite, duruş, anlık durum)
```

İki tasarım kararı hattın tamamına yayılıyor:

1. **Kur çevrimi satır bazında yapılır.** Her hareket, kendi tarihindeki kurla USD'ye
   çevrilir (`TUTAR_USD` kolonu). Toplamı tek kurla çevirmek, kurun oynadığı dönemlerde
   yanlış sonuç verir.
2. **Ölçüm anı veriye yazılır.** `TERMINE_KALAN_GUN`, `SIPARIS_TARIHINDEN_GECEN_GUN` gibi
   "bugüne göre" alanlar view içinde `GETDATE()` ile hesaplanır; rapor tarafında sadece
   okunur. Böylece aynı hesap birden fazla görselde tekrar yazılmaz.

## Depodaki CSV'ler bu view'ların çıktısıdır

`data/*.csv` dosyalarının kolonları ilgili view'ın kolonlarıyla birebir aynıdır — yani
raporu SQL Server'a bağlamak isterseniz Power Query'deki `Veri("X.csv")` çağrısını
`Sql.Database(sunucu, veritabani, [Query="SELECT * FROM dbo.X"])` ile değiştirmek yeterli.

Tersi de mümkün: CSV'leri SQL Server'a almak isterseniz view şeklinde bir tablo açıp
yükleyin.

```sql
CREATE TABLE rpt.SIPARIS (/* kolonlar: data/SIPARIS.csv başlık satırı */);

BULK INSERT rpt.SIPARIS
FROM 'C:\repo\02-yurtici-ticaret-analizi\data\SIPARIS.csv'
WITH (FORMAT = 'CSV', FIRSTROW = 2, CODEPAGE = '65001',
      FIELDQUOTE = '"', ROWTERMINATOR = '0x0a');
```
