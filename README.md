<p align="center">
  <img src="brand/firma-logo.png" alt="Test Firma A.Ş." width="360">
</p>

<h1 align="center">Power BI Portföyü — Üretim & Ticaret Raporları</h1>

<p align="center">
  <a href="README.en.md">🇬🇧 English</a> ·
  <b>🇹🇷 Türkçe</b>
</p>

Kurgusal bir üretim işletmesinin **üretim izleme**, **ticaret**, **satın alma**
ve **ürün portföyü** raporlarından oluşan dört Power BI projesi. Hepsi ERP verisiyle çalışan
gerçek raporların yapısıdır; bu depoda **tamamen sentetik veriyle** yayınlanmıştır.

> **Test Firma A.Ş.** kurgusal bir firmadır. Bu depodaki müşteri, tedarikçi,
> sipariş, fiyat ve üretim kayıtlarının tamamı `tools/veri_uret.py` tarafından üretilmiştir;
> hiçbir gerçek firmaya ait veri içermez. Fabrika yerleşim çizimleri de kurgudur.

---

## Dört rapor

| | Proje | Ne yapıyor | Sayfa · Görsel · Ölçü |
|---|---|---|---|
| 🏭 | **[SCADA Üretim İzleme](01-scada-uretim-izleme/)** | Fabrika yerleşim planı üzerinde 48 makinenin anlık durumu: ne üretiyor, kaç kişiyle, hangi arızada | 6 · 175 · 16 |
| 📈 | **[Departman Bazlı Ticaret Analizi](02-departman-ticaret-analizi/)** | Sipariş–ciro–cari üçlüsünün departman şablonu: müşteri, kalıp, çeyrek ve tahsilat kırılımları | 8 · 109 · 84 |
| 🛒 | **[Satın Alma Analizi](03-satin-alma-analizi/)** | Açık satın alma siparişleri, termin gecikmeleri ve tedarikçi bakiyeleri | 5 · 51 · 16 |
| 📦 | **[Ürün & Kalıp Analizi](04-urun-kalip-analizi/)** | Ürün kataloğunu kümülatif ciro payına göre sınıflandırıp robot yatırımına aday kalıpları çıkarır | 4 · 23 · 14 |

Her projenin kendi README'si var (TR + EN): ekran görüntüleri, veri modeli, öne çıkan DAX
ve nasıl açılacağı orada.

---

## Nasıl açılır

Raporlar **Power BI Project (`.pbip`)** formatındadır: model `model.bim` (TMSL), rapor
`report.json` olarak metin dosyasıdır — yani sürüm kontrolünde okunabilir ve diff'lenebilir.

```bash
git clone https://github.com/Secure-Sentinel/powerbi-portfolio.git
```

1. Power BI Desktop'ta ilgili klasördeki `.pbip` dosyasını açın
   (Power BI Desktop 2.130+ · gerekirse *Dosya → Seçenekler → Önizleme özellikleri →
   Power BI Project (.pbip) kaydetme* seçeneğini işaretleyin).
2. **Yenile**'ye basın. Veri, `VeriKaynagi` parametresindeki adresten okunur; varsayılan
   değer bu deponun `data/` klasörünün GitHub raw adresidir.
3. Çevrimdışı çalışmak isterseniz `VeriKaynagi` parametresini klonladığınız klasördeki
   `data` yoluna çevirin, örn. `C:\repo\01-scada-uretim-izleme\data`.

Veriyi kendiniz üretmek isterseniz:

```bash
python tools/veri_uret.py --bugun 2026-07-30
```

Aynı `--bugun` ve `--olcek` ile çıktı birebir aynıdır (sabit tohum). Tarih parametresi
önemli: raporlarda `TODAY()` tabanlı ölçüler var, veri "bugün"ün etrafına konumlanır.

`.pbip` dosyalarını açmadan önce deponun kendi içinde tutarlı olduğunu kontrol edebilirsiniz
— CSV başlıkları ile modelin kolonları, ilişki/sıralama referansları, DAX içindeki tablo
adları ve rapordaki her alan referansı denetlenir:

```bash
python tools/dogrula.py
```

---

## Depo yapısı

```
powerbi-portfolio/
├── 01-scada-uretim-izleme/
│   ├── SCADA Uretim Izleme.pbip              ← Power BI Desktop bunu açar
│   ├── SCADA Uretim Izleme.Report/           ← report.json + görseller (logo, plan)
│   ├── SCADA Uretim Izleme.SemanticModel/    ← model.bim (tablolar, DAX, ilişkiler)
│   ├── data/                                 ← sentetik CSV'ler
│   ├── docs/                                 ← ekran görüntüleri
│   ├── README.md · README.en.md
├── 02-departman-ticaret-analizi/ (aynı düzen)
├── 03-satin-alma-analizi/        (aynı düzen)
├── 04-urun-kalip-analizi/        (aynı düzen)
├── sql/                          ← veri hattının sadeleştirilmiş SQL karşılığı
├── brand/                        ← kurgusal marka varlıkları
└── tools/
    ├── veri_uret.py              ← sentetik veri üreteci
    └── dogrula.py                ← depo tutarlılık denetimi
```

---

## Gerçek hayatta veri nereden geliyor

Orijinal raporlar ERP veritabanı üzerinde kurulu SQL view'larından beslenir:
sipariş/fatura hareketleri, cari bakiye, iş emri takibi ve makine aktivite kayıtları.
Power BI tarafı **import** modda çalışır, günde birkaç kez yenilenir; SCADA raporu
üretim sahasındaki ekranlarda otomatik yenilemeyle döner.

Bu depoda o katman iki parçaya ayrıldı:

- **[`sql/`](sql/)** — her raporun beslendiği tabloların sadeleştirilmiş, okunabilir SQL
  karşılığı. Üretimdeki view mantığını birebir vermez; şekli ve joinleri gösterir.
- **`data/` + `tools/veri_uret.py`** — aynı şemayı dolduran sentetik veri.

Model tarafındaki her şey (tablo/kolon adları, DAX ölçüleri, hesaplanmış kolonlar,
ilişkiler, biçim dizeleri, otomatik tarih hiyerarşileri) orijinalinden birebir taşındı.

---

## Teknik notlar

- **Model dili `tr-TR`.** Bazı DAX ifadeleri Türkçe kültüre bağlı isim çözümlemesine
  dayanıyor (ör. `[Yıl]` ile `[YIL]` eşleşmesi), bu yüzden kültür değiştirilmemelidir.
- **Otomatik tarih/saat açık.** Raporda birkaç görsel otomatik tarih hiyerarşisini
  kullanıyor; ilgili `LocalDateTable_*` tabloları modelde açıkça tanımlıdır.
- **Yalnızca yerleşik görseller** kullanıldı — hiçbir özel (custom) görsel yok, dolayısıyla
  dosyalar herhangi bir Power BI Desktop kurulumunda açılır.
- CSV'ler UTF-8, virgül ayraçlı, ondalık ayırıcı `.`; M tarafında `"en-US"` kültürüyle
  tiplenir.

## Lisans

[MIT](LICENSE). Sentetik veri ve kurgusal marka varlıkları da aynı lisansa tabidir.
