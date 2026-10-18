# X68 protokol notları

Bu belge yerel statik analiz ve 17–18 Ekim 2026 tarihlerindeki cihaz denemesine dayanır.
Firmware içeriği ve orijinal uygulama bu projeye dahil edilmemiştir.

## Kaynaklar

- Resmî liste: https://www.vgnlab.com.cn/api/drive/list
- Firmware aracı: https://cdn.vgnclub.com/vgn/driver/X68/X68-V0113固件升级.exe
- İncelenen dosyanın SHA-256 değeri: `CDF4535A909900C7644E496D415552C6B210F0F87AFB77C80A54782E571BD771`
- İnceleme aracı: ILSpy CLI 11.1.0.9782. Dosya çalıştırılmadan C# decompile ve resource export yapıldı.
- REA (https://github.com/morluto/rea) incelendi; bu sürüm için kurulmadı. Mevcut .NET analizi ILSpy ile yeterliydi.

## Kimlik ve arayüz seçimi

VID `320F`, PID `5055`; manufacturer `Telink`, product `SUBOR X68`.
VID/PID başka klavyelerde de kullanılır, tek başına yeterli değildir.
Yönetim arayüzü MI_02, UsagePage `FFEF`, Usage `0`.
Report ID `05`; input/output/feature raporları 64 bayt (ID dahil).
Her bağlantıda tam HID report descriptor karşılaştırılır. Eşleşmezse yazma yapılmaz.
Birden fazla aday varsa seçim yapılmaz.

## Sürüm ve CRC sorgusu

Orijinal C# aracındaki `getFwVersionToolStripMenuItem_Click` ve
`user_sendDataToDevice` birlikte incelendi. WRITE yöntemi şu 64 baytı gönderir:

```
05 01 00 00 [FF × 29] [00 × 31]
```

Yanıtın ilk 12 baytı:

```
05 01 08 00 VV VV VV VV CC CC CC CC
```

İki 32 bit alan little-endian okunur. Orijinal araç bunları Version ve CRC diye gösterir.
Deneme cihazı version alanını `00000000`, CRC alanını `14961BE6` döndürdü.
Version alanının anlamı henüz doğrulanmadı; USB release `0113` ile karıştırılmamalıdır.

Resmî resource `param_128K` içinde VID, PID, report ID, display version ve usage page vardır.
`code_2M` içinde big-endian payload boyutu offset 48'de, payload başlangıcı offset 256'dadır.
Payload boyutu 236916 bayt; son dört bayttaki CRC little-endian `14961BE6`.
Bu karşılaştırma bir tam bellek okuması veya bağımsız bütünlük denetimi değildir.
Cihazın CRC'yi anlık hesaplayıp hesaplamadığı doğrulanmadı.

## Ayar protokolü (0.2.0)

18 Ekim'de X68'in kendi resmî firmware payload'u Capstone ile statik incelendi.
RISC-V / Andes uzantılı kodda ayar dispatcher'ı `0x2001B784`, jump table
`0x2001E72C` adresinde. Komut 5/6, 8/9 ve 20/21 okuma/yazma yolları incelendi.
Bu analiz sırasında firmware belleğe yazılmadı.

İkinci kaynak: `https://wobwxe.com` sitesinin public istemci JavaScript'i.
`app~918758ea.7850b4b2.js` içindeki Evision Protocol C ve
`app~5c551db8.a4721159.js` içindeki type-0 makro codec'i statik incelendi.
Kodları projeye kopyalanmadı; paket biçimleri bağımsız yeniden uygulandı.
OpenRGB EVision kaynakları da karşılaştırıldı. VID/PID benzerliği tek başına kanıt sayılmadı;
X68 firmware dispatch tablosu, descriptor ve gerçek cihaz okumaları birlikte kullanıldı.

- Arayüz: MI_01, UsagePage FF1C, Usage 0092, report ID 04.
- Paket: `[04, checksumLE16, command, length, offsetLE24, payload (56 bayta kadar)]`.
- Checksum: raporun 3–63 baytlarının unsigned toplamı.
- ACK / okuma: cihaz ilk 8 baytı geri döndürür, veri offset 8'de bulunur.
- 01 / 02: ayar işlemi başlat / bitir.
- 05 / 06: 64 baytlık parametre kaydı oku / yaz.
- 08 / 09: 384 baytlık aktif tuş eşleme tablosu oku / yaz.
- 14 / 15 hex (20 / 21 decimal): 0xA0000 adresindeki makro ayar bankası oku / yaz.
  Uygulama yalnızca ilk 4096 bayta izin verir; ilk yazma bankanın sektörünü siler.

Parametre offset 0 korunur; RGB modu 1, parlaklık 2 (0–4), hız 3 (4= yavaş),
renk türü 5, RGB 6–8. Bilinmeyen alanlar değiştirilmez.
Tuş hücresi üç bayt: `[flags, code_hi, code_lo]`; normal tuş flag 20 hex,
modifier yüksek baytta bitmask. Fn flag A0 ve kod 0100; korunur.
Tek oynatmalı makro ataması `[71 hex, macro_index, 01]`.

Makro bankası: AA55, toplam boyut LE16, yuva sayısı LE16, 10 bayt korunan metadata,
yuva başına LE16 ofsetler, ardından makro blokları. Bir blokta olay sayısı LE16,
2 bayt metadata, olaylar `[delayLE16, action, key]`. Yeni blok metadata'sı 35 00 hex.
Klavye olayları: 8A/0A bas/bırak, modifier 89/09, fare düğmesi 81/01.
Bozuk veya tanınmayan banka üzerine yazılmaz; başka yuvalar bayt olarak korunur.

### Canlı doğrulama

- RGB parlaklık 4 → 3 yazıldı, geri okundu, sonra orijinal 4'e döndürüldü.
- Kullanılmayan ikinci makro yuvasına test makrosu yazıldı ve geri okundu;
  hiçbir fiziksel tuşa bağlanmadan orijinal 4096 baytlık banka geri yüklendi.
- Aynı tuş tablosu tekrar yazılıp geri okundu; tüm tuş atamaları korundu.
- Test sonunda parametre, tuş tablosu ve makro bankası başlangıçla bayt bayt eşleşti.
- Fiziksel tuşa basarak makro oynatma henüz kullanıcıyla doğrulanmadı.
- Ayrıntılar `reports/rgb-live-test.json` ve `reports/settings-live-test.json` dosyalarında.

## Pil sorgusu (0.3.0 / 0.3.1)

X68 firmware dispatch tablosunda komut 1A hex, `0x2001BA0C` dalına gider.
`0x2000B0C4` yardımcı fonksiyonu önbellek/zaman damgası yolunu günceller;
ilk yanıt baytı global bir seviye alanından, ikinci bayt GPIO okumalarından gelir.
Dalın bazı yollarında ikinci bayt 0 veya 1 yapılır. Başka bir dal ilk baytı
sabit 100, ikinci baytı 2 yapar (`0x2001C118`). Bunun fiziksel kartta
USB algısı mı, şarj algısı mı olduğu doğrulanmadı.

İstek, WOB Protocol C'deki `GetBatteryInformationCom` ile de eşleşir:

```
04 20 00 1A 06 00 00 00 [00 × 56]
```

İlk gerçek X68 yanıtı: aynı 8 bayt başlık + `00 01 00 00 00 00`.
Seviye alanı 0, durum 1. Sonraki kod incelemesi, seviye hesabının 100 üzerinden
oranla yapıldığını doğruladı (`0x2001055C`, `0x200106A8`, `0x200106AE`).
Bu nedenle `reported_percent=0`, klavyenin bildirdiği yüzde olarak gösterilir.
Kalibre gerçek doluluk (`percent`), şarj akımı ve voltaj bilinmediği için `null` kalır.
Kablolu modda ADC'nin güncelliği ve kart kalibrasyonu henüz doğrulanmadı.
Bu paket pilin fiziksel varlığını da doğrulamaz. 100 üzeri veya tanınmayan durumdaki
değerler yüzde diye sınırlandırılmaz; ham olarak korunur, `reported_percent=null` olur.

`x68/battery.py` raporları yorum sınırlarıyla saklar. `26` isteği için yalnızca
offset 0 ve uzunluk 6 kabul edilir; parametre taraması yapılmaz. Begin/end,
ayar veya firmware yazma işlemi pil sorgusunun parçası değildir.
Kopma ve zaman aşımı ayrı olaydır; pil alanına yapay 0 yazılmaz. Grafik kopma
üzerinden çizgi çekmez. Son başarılı rapor zamanı korunur, eski veri yeni gibi gösterilmez.

## İşlem sınırları

- GUI ve pil sorguları OTA başlatmaz. Ayrı `tools/reflash_v0113.py` aracı,
  açık `--write-firmware` seçeneğiyle doğrulanmış V0113 OTA aktarımı yapar.
  Sonuç kodu ve cihazın yeniden bildirdiği CRC kontrol edilir. Kesinti kurtarması garanti edilmez.
- Keyfî output/feature raporları, komut tarama veya fuzzing.
- Fabrika sıfırlama ve şarjı zorla açma/kapatma uygulanmadı.

Orijinal güncelleyicide cihaz bağlandıktan sonra çalışabilen `timer2_Tick` OTA yolu bulunur.
Bu nedenle programın sadece açılmasını pasif tanı olarak değerlendirmiyoruz.
Orijinal sürücü yükleyicisi Defender tarafından Vigorf.A olarak engellendi; bu projenin parçası değildir.

## Tuş gözlemi

Windows Raw Input kullanılır. Yalnızca uygulama ön plandayken, kullanıcı testi
başlatmışken ve cihaz yolu envanterdeki X68 arayüzleriyle eşleşirken olay işlenir.
Sistem çapında klavye hook'u kurulmaz. Test 60 saniyede durur. Sayaçlar tuş sırası
ve yazılan metin içermez. Fn firmware içinde işlendiğinden bağımsız olay göndermeyebilir.

## Sıradaki araştırma

Pil göstergesinin kalibrasyonu, GPIO bitlerinin karttaki anlamı ve diğer profiller için
yeni, modele özgü statik kanıt gerekir. [Pil araştırmasının bulguları](BATTERY-INVESTIGATION.md)
handler adreslerini, GPIO dallarını ve gerçekleştirilen firmware yazma sonuçlarını içerir.
Başka `320F:5055` cihazlara ait komutlar doğrudan denenmemeli.
Varsayımsal komutları göndermek yerine önce davranış ve paket biçimi kaynak kodu,
resmî doküman veya güvenilir bir USB kaydıyla eşleştirilmeli.
