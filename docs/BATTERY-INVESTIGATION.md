# X68 pil / şarj araştırması

## Özet — 18 Ekim 2026 (son durum)

**Sorun yazılımda değil, pilde.** Klavyenin kendi ADC'si ile multimetre aynı
şeyi söylüyor: pil hattında yaklaşık **0.08 V** var.

| Kaynak | Değer |
| --- | --- |
| Sahibinin multimetresi | 0.08 V |
| 0.6.0 ADC anlık görüntüsü (USB takılı, pil bağlı) | 40–41 birim → ~0.08 V |
| Aynı görüntü, pil sökülü iken (önceki kayıt) | 12–13 birim → ~0.02 V |

Dönüşüm: firmware'in boş/dolu eşikleri 1510 / 2035 birim. Bunlar ADC pininde
milivolt ve 1:2 bölücü olarak okunursa 3.02 V / 4.07 V eder; tek hücreli Li-ion'un
standart çalışma penceresi. Multimetre ile aynı ölçeğin 0.08 V'ta örtüşmesi bu
okumayı destekliyor. Bölücü oranı şemadan değil çıkarımdan geliyor, bu yüzden
uygulama değeri "tahmin" olarak gösterir.

Sonuçlar:

1. **Ölçüm yolu çalışıyor.** ADC, bölücü ve firmware hesabı gerçek gerilimi
   izliyor. "Gösterge yanlış" hipotezi bu verilerle desteklenmiyor.
2. **Firmware şarjı kontrol etmiyor.** İncelenen tüm yollarda pil kodu yalnızca
   okuma yapıyor (ADC + PE4/PC3 girişleri). Şarjı açıp kapatan bir çıkış bulunmadı.
   Şarj, USB'den beslenen bağımsız şarj entegresi tarafından yapılıyor. Firmware'i
   sıfırdan yazmak bu tabloyu değiştirmez.
3. **Hücre kurtarılacak.** Sahibi pilin sağlam olduğunu ve yenisini bulamayacağını
   belirtti. Bu gerilimde koruma kartı (DW01 sınıfı) şarj FET'ini süremez; klavyenin
   şarj devresi hücreyi tek başına uyandıramaz. Çözüm: hücreye dışarıdan yavaş akımla
   "jump-start" yapmak (aşağıda). 3.0 V'a gelince normal şarja devredilir.
4. **Şarj entegresi de şüpheli.** Pil sökülüyken USB takılı ölçümde pil hattı
   ~0 V idi. TP4056 sınıfı bir entegre pilsizken genelde ~4.2 V gösterir. Arada
   bir anahtar olabileceği için kesin değil. Jump-start sonrası izleme bunu netleştirir.

### Jump-start

1. Paketi klavyeden çıkar.
2. Yavaş kaynak: seri iki AA pil + 10-33 Ω direnç (iki AA 3.2 V'u geçemez, aşırı
   şarj riski yok) ya da USB 5 V + 100 Ω (~50 mA). Kırmızı B+, siyah B-.
3. Pakette küçük bir koruma kartı varsa kabloların ucuna değil, kartın arkasındaki
   hücre tırnaklarına (B+/B-) bağla. Kart 0 V'ta yolu kapalı tutar.
4. 10 dakikada bir multimetreyle ölç. Isınma veya şişme olursa dur.
5. 3.0 V'a gelince paketi tak, USB'yi bağla, uygulamada Battery, ardından Start monitoring.

### Sahibinin yapacağı test

1. Jump-start sonrası pili tak, USB'yi bağla, uygulamada **Battery → Start monitoring**.
2. Birkaç dakika içinde voltaj yükseliyorsa ("Charging: voltage rising") şarj devresi
   sağlam; sorun yalnızca dibe inmiş hücreymiş.
3. Voltaj sabit kalıyorsa ("Not charging") şarj entegresine bak: pil konnektörü
   yakınındaki 5–8 bacaklı entegrenin üst yazısının fotoğrafı yeterli. VCC (USB'de
   5 V olmalı), CE/EN ve PROG pinleri ölçülerek arıza netleşir. Entegre birkaç
   dolarlık bir parçadır.

Yeni pil takmadan hızlı kontrol: pil sökülü, USB takılı iken karttaki pil
konnektörünün iki ucunu ölç. ~4.2 V (veya 3–4.2 V arası oynayan) değer → şarj
entegresi çalışıyor. ~0 V → entegre çıkış vermiyor.

---

## Ayrıntılı araştırma kaydı

## Sonuç ve açık soru

Pil raporunu gerçek cihazdan okuyabiliyoruz. Kablolu sorgular `00 01 00 00 00 00`
döndürdü. Bu, kalibre bir voltaj veya akım ölçümü değildir. Şarj sorunu henüz
giderilmedi; yazılım / donanım olasılıklarına sayısal olasılık atanmadı.

Firmware'de GPIO koşuluyla sabit 100 döndüren bir dal bulundu. Bu dal tek başına
yanlış doluluk gösterildiğini kanıtlamaz; pinlerin fiziksel anlamı doğrulanmalı.
Kullanıcının gördüğü dolu göstergesinin bu daldan geldiği yakalanmadı: sorguda durum 1 geliyor.
Gösterge hatası ile fiziksel şarj sorunu aynı şey olarak kabul edilmemeli.

## İncelenen sürüm

- Resmî liste: https://www.vgnlab.com.cn/api/drive/list
- Dosya: https://cdn.vgnclub.com/vgn/driver/X68/X68-V0113固件升级.exe
- EXE SHA256: `CDF4535A909900C7644E496D415552C6B210F0F87AFB77C80A54782E571BD771`
- Payload SHA256: `791ae619fb2d7dbe44203192bd42b07073029701ad9ad6363032176559136273`
- Payload uzunluğu: 236916 bayt; içeride saklı CRC: `14961BE6`.
- Cihazın bildirdiği CRC aynı. Bu, bağımsız tam flash doğrulaması değildir;
  fabrika firmware'inde hata olmasını da dışlamaz.
- VGN sürücüsü veya güncelleyicisi çalıştırılmadı. Kendi sınırlandırılmış OTA aracıyla
  önce orijinal V0113, sonra yalnızca varsayılan ekran varlıkları değiştirilmiş sürüm yazıldı.

## Pil yanıtını üreten kod

İncelenen payload'da komut `1A` handler'ı `0x2001BA0C` adresindedir.
Andes özel komutları standart RISC-V disassembler ile yanlış çözülebilir.
GP-relative yükleme ve bit dalları aşağıdaki birincil kaynaklarla çözüldü:

- [Andes'in binutils opcode ve immediate tanımları](https://sourceware.org/pipermail/binutils/2025-November/145934.html)
- [Renode Andes GP-relative komut uygulaması](https://github.com/renode/renode-infrastructure/blob/master/src/Emulator/Cores/RiscV/Andes_AndeStarV5Extension.cs)
- [Telink B91 GPIO register tanımları](https://github.com/telink-semi/tl_ble_sdk/blob/master/tl_ble_sdk/drivers/B91/reg_include/gpio_reg.h)

Firmware'de gözlenen mantık, sadeleştirilmiş sözde kod:

```text
0x2001BA0C: call 0x2000B0C4
0x2001BA10: level = signed_byte[gp + 0x370]
0x2001BA18: response[8] = level
0x2001BA1C: pe = byte[0x80140320]
0x2001BA20: if bit4(pe) == 0: goto 0x2001BF2C
0x2001BA28: pc = byte[0x80140310]
0x2001BA2C: if bit3(pc) == 0: goto 0x2001C118
0x2001BA34: response[9] = 1

0x2001BF2C: response[9] = 0

0x2001C118: response[8:10] = little_endian_16(0x0264)
            # seviye 100 (0x64), durum 2
```

Telink B91 tanımlarında bu adresler PE ve PC GPIO giriş register'larıyla
eşleşiyor. Bu eşleşme SoC ailesi için kanıttır; kesin kart revizyonu ve pinlerin
şemadaki USB/CHRG/STDBY işlevi kart üzerindeki bağlantıyla ayrıca doğrulanmalı.
Durum 1 dalı PE4=1 ve PC3=1 gerektirir. Durum 0 dalında PC3 bilinmez.
Bu pin değerleri tek başına amper cinsinden şarj akımı değildir.

`0x2000B0C4`, `gp+0x559` sıfırsa `gp+0x3F4` alanını sıfırlar ve donanım
sayacını `gp+0x3F8` alanına kopyalar. Dolayısıyla sorgu firmware'in kendi
zamanlama/önbellek durumuna dokunabilir. Flash veya şarj etkinleştirme yazması
bu handler'da görülmedi. Başka kod yollarında kontrol bulunması dışlanmadı.

Pil alanının yazıcısı `0x20010674` adresindedir; `0x200103E4` fonksiyonu ADC
register okumaları, kalibrasyon katsayıları, alt/üst eşikler ve 100 üzerinden
hesap içerir. Bu katsayıların bu karta uygunluğu, ADC'nin fiziksel giriş bağlantısı
ve fonksiyonun tüm çalışma koşulları henüz doğrulanmadı.
`0x2001055C` noktasında 100 yüklenir; ara aralıkta `0x200106A8` noktasında
çarpma, `0x200106AE` noktasında bölme vardır: `100 × (değer-alt)/(üst-alt)`.
`0x200107DC` alt eşik için sıfır yoludur. Bu kanıt, alanın firmware'deki 0–100
gösterge ölçeği olduğunu ortaya koyar. Uygulama bunu **klavyenin bildirdiği yüzde**
(`reported_percent`) olarak gösterir. Gerçek doluluk (`percent`) ve voltaj `null`
kalır; cihaz kalibrasyonunun doğru olduğu varsayılmaz. Tanınmayan veya sınır dışı
yanıtlar yüzdeye dönüştürülmez. Durum 2 / seviye 100 ayrıca sabit değer dalı olarak işaretlenir.

Doğrudan GP-relative yazma referanslarında iki çarpan başlangıç kodunda
atanıyor: `gp+0x530` alanına 4 (`0x20008154`, `s2` değeri
`0x200080E0` adresinde yükleniyor), `gp+0x531` alanına 1
(`0x200081B0`). Bu alanları değiştiren bir RGB/makro işlemi gösterilemedi.
Dolaylı bellek yazmaları ve diğer kalibrasyon/eşik alanlarının tüm kaynakları
henüz çözülmediğinden, ayar bozulması bütünüyle dışlanmış değildir.
Kalibrasyon katsayılarını tahminen değiştirmek bir şarj onarımı sayılmaz.

### Ölçümün çağrıldığı noktalar

Boot kopyalama kodu, payload `[0x12B0,0xA0B4)` alanını RAM
`[0x1200,0xA004)` alanına taşır. Bu yüzden bu bölgedeki çağrıları dosya
ofsetini flash adresi sanarak çözmek yanlıştır. ADC fonksiyonuna iki çağrı:

| Payload ofseti | Çalışma adresi | Hedef |
| --- | --- | --- |
| `0x82A0` | `0x81F0` | `0x200103E4` |
| `0x84F0` | `0x8440` | `0x200103E4` |

İlki başlangıç akışındadır. İkincisinden önce donanım sayacı ile `gp+0x540`
zaman damgası karşılaştırılır. Pil sorgusunun güncellediği alan `gp+0x3F8`'dir;
bu iki zaman damgası aynı alan değildir. Çalışma modu ve diğer koşullar da
çağrıyı etkiler; her sorgunun yeni ADC ölçümü yaptığını iddia etmiyoruz.

### Düşük riskli canlı deneme

RGB yük karşılaştırmasında yalnızca doğrulanmış parlaklık baytı (offset 2)
4'ten 0'a indirildi; diğer 63 parametre baytı korundu. Mod, renk ve bilinmeyen
bayraklar değiştirilmedi. Kapalı faz 11 örnek / yaklaşık 30 saniyeydi.
Öncesi ve geri yükleme sonrası dahil 17 raporun tamamı `00 01 00 00 00 00`
geldi. Sonunda parametre, tuş tablosu ve makro bankası başlangıçla eşleşti.

Ayrı bir denemede sorgular arasında 35 saniye bekletildi; bu arada başka X68 Lab
örneği çalışmıyordu. Bekleme öncesi ve sonrası aynı `00 01 00 00 00 00` yanıtı geldi.
Bu da sorgu sıklığının etkisini tek başına kesin dışlamaz; kısa bir gözlem kaydıdır.

Bu kısa deneme gerçek şarj akımını ölçmez ve pilin şarj almadığını kanıtlamaz.
Ancak bu ölçümlerde sabit 100 / durum 2 dalı aktif değildi. Dolayısıyla
“bu rapor sürekli 100 olduğu için şarj kesiliyor” iddiası bu kayıtlardan
desteklenmiyor. Ayrı bir şarj kontrol hatası henüz dışlanmadı.

İlk deneme RGB bayrağı `0xFF` olduğu için genel RGB decoder tarafından,
hiç ayar yazılmadan durduruldu. Deneme daha sonra yalnızca parlaklık baytını
değiştirecek şekilde sınırlandı. `0xFF`'nin bozulma olduğunu varsaymıyoruz.
Mevcut makro başlığının önceki kayıttan farklı olması da tek başına bozulma
kanıtı değildir; bu araştırmada üzerine yazılmadı.

Yerel kanıtlar: `reports/battery-rgb-trial.json`,
`reports/settings-before-battery-trial.json`, `reports/battery-firmware-proof.json`.
Bu dosyalar cihaz yolları / yerel kullanıcı yolları içerebilir ve `.gitignore`
kapsamındadır; GitHub'a otomatik eklenmez.

## Tekrarlanabilir dosya incelemesi

`tools/inspect_battery_firmware.py` yalnızca bilinen SHA256'ya sahip payload'u
kabul eder. Handler / GPIO dallarını, ADC çağrılarını ve sabit 100 yazmasını
ham opcode baytlarıyla denetler. Araç USB açmaz, vendor kodu çalıştırmaz,
firmware yazmaz. Firmware payload'u depoya dahil değildir.

```powershell
.\.venv\Scripts\python.exe tools\inspect_resources.py C:\path\Resources.resx --payload-output reports\private-payload.bin
.\.venv\Scripts\python.exe tools\inspect_battery_firmware.py reports\private-payload.bin --output reports\battery-firmware-proof.json
```

Payload'un son dört baytı `14961BE6` değerini taşır. Ayrıca
`zlib.crc32(payload[:-4]) XOR 0xFFFFFFFF` hesaplaması aynı sonucu verir.
Bu dosya bütünlüğü kontrolüdür; klavyenin flash'ının bağımsız yedeği değildir.

## Firmware yeniden yazma değerlendirmesi

Kullanıcı yeniden yazmaya izin verdi. Bu izin, dosyanın daha yeni olduğu veya
yeniden yazmanın bu sorunu düzelttiği şeklinde yorumlanmadı. Resmî API yeniden
kontrol edildiğinde X68 için yine V0113 bağlantısını verdi.

Orijinal uygulamanın OTA paketleme ve cevap kontrolü dosya üzerinden incelendi.
Telink B91 SDK'sı farklı flash başlangıç adresleri ve çoklu boot desteği
tanımlar. X68 handler incelemesinde son paketle ilk 16 baytın commit edilmesi,
CRC kontrolü ve önceki boot işaretinin temizlenmesi görüldü. Kesinti
sonrası kurtarma davranışı bu cihazda deneyle doğrulanmadı. Genel SDK desteğini bu kart için
doğrulanmış kurtarma garantisi saymıyoruz:

- [B91 boot tanımları](https://github.com/telink-semi/tl_ble_sdk/blob/master/tl_ble_sdk/drivers/B91/ext_driver/mcu_boot.h)
- [SDK OTA arayüzü](https://github.com/telink-semi/tl_ble_sdk/blob/master/tl_ble_sdk/stack/ble/service/ota/ota_server.h)

18 Ekim 2026: kendi CLI aracımızla orijinal V0113 yeniden yazıldı. Cihaz OTA
sonucu 0 verdi; sonrasında bildirilen CRC `14961BE6` idi. Pil yanıtı yine
`00 01 00 00 00 00` oldu; kullanıcı USB çıkarılınca BT/2.4G'de tepki olmadığını bildirdi.
Bu gözlem şarj onarımını doğrulamıyor.

Ardından yalnızca varsayılan LCD yazı/logo varlıkları değiştirilen sürüm yazıldı.
OTA sonucu 0 ve sonrasında bildirilen CRC `5E53D48B` hedefle eşleşti. Pil yanıtı
aynı kaldı. Şarj kodu değiştirilmedi. Kullanıcı fiziksel ekran görünümünde bozukluk
bildirdi; bu görünüm başarılı tasarım olarak değerlendirilmemeli ve pil araştırması
önceliklidir. İki işlemde tuş ve makro bankaları aynı kaldı; parametre bloğu tamamen
aynı değildi. Bilinmeyen alanlar tahminen geri yazılmadı.

Yerel oturumlar: `reports/firmware-sessions/20261018-030954-678332` ve
`reports/firmware-sessions/20261018-031833-214927`. Bunlar yayımlanmaz.
Araştırma henüz yayımlanabilir bir “şarj onarımı” değildir.

## Uygulanan tanı

`Pil / şarj` sekmesi ham seviye, durum baytı, son başarılı rapor zamanı, zaman
grafiği, kesinti sayısı, kullanıcı gözlemleri ve JSON kayıtları içerir.
Bağlantı kaybı, pil 0 diye yazılmaz. Uzun kesintide geçmişin kapasitesi aşılırsa
bile son gerçek ölçüm ayrıca korunur. Ölçülmeyen voltaj, akım ve pil varlığı
`null` kalır. `reported_percent` yalnızca cihazın gösterge değeridir.
Pil sorgusu ayar, reset veya firmware komutu göndermez.

## Bir sonraki karar

### Ekran / USB tutarsızlığının yazılım akışı

Kullanıcı USB bağlıyken fiziksel ekranda sürekli dolu pil simgesi, USB çıkarılıp
kablosuz seçilince kapanma bildiriyor. Son başarılı USB yanıtı yine seviye 0,
durum 1 idi. İki gösterge aynı değişkenden çizilmiyor:

- Ana döngü PE4 / PC3 girişlerini okuyup gecikmeli olarak `gp+0x501` durumunu
  oluşturuyor (payload `0x84A8`, `0x84B0`, `0x8642`, `0x864E`). Buradaki durum
  numaraları HID raporundaki durum numaralarıyla aynı değildir.
- Yerel ekran `0x2001A0FC` adresinde bu durumu okuyor. Durum 2,
  `0x2001A11C` dalıyla `0x2001A14C` çizim çağrısına gider; bu yolda
  `gp+0x370` pil seviyesi yüklemesi atlanır. Dolayısıyla USB seviyesinin 0 olması
  ile bu çizim yolunun seçilmesi birlikte mümkün. Çizimin fiziksel görünümü
  kullanıcının gözlemidir; bu kod akışı gerçek doluluğu kanıtlamaz.
- ADC sonucu `0x20010754` yoluna ulaşıp PE4 ve PC3 set ise önceki seviye
  `gp+0xD3` ile karşılaştırılır; `0x20010764..0x20010768` yeni değeri önceki
  seviyeye sınırlayabilir. Filtrenin tamamı ve kalıcılık davranışı çözülmeden
  bu yol tek başına cihazdaki 0 değerinin sebebi olarak ilan edilemez.

Bu ek kanıt `tools/inspect_battery_firmware.py` tarafından bilinen orijinal
payload üzerinde opcode kontrolüyle doğrulanır. Yerel çıktı:
`reports/battery-display-flow-proof.json`. Bu inceleme cihaz belleğine yazmaz.
Henüz bu durumdan fiziksel şarjı kapatan bir çıkışa doğrulanmış yol bulunmadı.
Gösterge filtresini değiştirmek veya dolu simgesini bastırmak bir şarj onarımı
olarak sunulmamalı.

USB takılı bırakılıp fiziksel anahtar 2.4G'ye alındı. Kullanıcı simgenin yine
sabit dolu kaldığını bildirdi. Yaklaşık 62 saniyelik kayıt iki başarılı kablolu
yanıt (seviye 0 / durum 1) ve ardından 11 arayüz bulunamadı hatası içeriyor.
Anahtar değişimi sonrasında USB ayar arayüzü kaybolduğundan, sonraki pil seviyesi
okunmuş değildir; arayüz kaybı boş pil ölçümü veya cihazın kapandığı kanıtı değildir.
Yerel kayıt: `reports/battery-usb-powered-mode-trial.json`.

`gp+0x501` durumunun doğrudan referansları ekran çizimi, ADC gösterge filtresi
ve `0x2000209C` kontrolündedir. Sonuncusu matris/çıkış kontrolüyle ortak bir
fonksiyondadır; çıkışların fiziksel bağlantısı doğrulanmadığından şarj kontrolü
olarak adlandırılamaz. Dolaylı pointer referansları ve bilinmeyen özel opcode'lar
nedeniyle bu liste tüm olası kontrol yollarını dışlayan bir ispat değildir.
Bu denemede firmware veya ayar yazılmadı; doğrulanmış bir şarj onarımı bulunmadı.

1. Şarj entegresinin kodu ile veri sayfasından EN/CE girişi var mı ve hangi
   mantıkta çalışıyor belirle. Karttaki bağlantısını doğrula. Entegrenin MCU'dan
   kontrol edilebildiği kanıtlanırsa ilgili GPIO başlangıç/uyku kodunu izle.
   Kullanıcı pil tarafını sökmek ve DC ölçüm yapmak istemiyor; bu nedenle
   fiziksel ölçüm yapıldığı varsayılmamalı ve yazılım araştırması sürdürülebilir.
2. Önceden ölçülmüş pil voltajı varsa rapora kullanıcı gözlemi olarak ekle.
   HID yanıtından ölçülmüş gibi üretme. Böylece ADC raporu ile fiziksel pil
   durumunun uyuşmazlığı ayrı incelenebilir.
3. Şarj kodunu değiştirmek için belirli hatalı kod/ayar ve kart bağlantısı gerekir.
   Orijinal V0113 yeniden yazıldı; şarj düzelmesi gözlenmedi. Güncelleyiciyi açmak otomatik OTA başlatabildiğinden
   pasif bir inceleme işlemi değildir.


## 0.6.0 ile gerçek ham ADC kaydı — 18 Ekim 2026

Deneysel salt-okuma komutu 19 hex/48 bayt yüklendi; OTA sonucu 0 ve bildirilen
CRC 127F9EB4. Uygulama yeniden açılmadı. Altı canlı kayıtta sekizer ADC örneği
0–8 aralığındaydı; örnekler değişti ve zaman damgası ilerledi. Katsayılar 4/1,
kalibrasyon 1172 ve +12, alt/üst eşik 1510/2035 idi. Aynı firmware aritmetiğiyle
filtre öncesi gösterge tüm kayıtlarda 0 çıktı (ölçeklenmiş kod değeri 12–13).
Bu, ölçülmüş pil voltajı değildir. Son yüzde filtresini suçlamak bu verilerle
desteklenmiyor. PE4=1, PC3=1, yerel durum=1, bağlantı modu=2; HID yine 0/durum1.

Orijinal başlangıç kodu analog EB register'ına AF yazar: SDK tanımına göre
PD1 pozitif giriş/GND negatif giriş. PD1 başlangıç yapılandırması vardır;
çalışma anındaki mux veya gerçek kart bağlantısı bundan kesinleşmez.
Gerçek pil hattı gerilimi bilinmeden pil/koruma/bağlantı/ADC yolu ayrılamaz.
PH1 B+/B- için USB yokken ve varken DC ölçümü istendi, henüz değer verilmedi.
Şarj onarımı yapılmadı ve bir şarj-etkinleştirme çıkışı belirlenmedi.

Ham kayıt: reports/battery-engineering-live.json (özel HID yolları içerir).
Özet: reports/battery-engineering-summary.json. Bu dosyalar yayımlanmaz.

## Connection-state correction and boot check — 2026-10-18

The owner reports that both battery connectors are currently unplugged. Their
connection state during the six earlier ADC snapshots was not confirmed. Those
snapshots must not be used to diagnose a pack, ADC or charging fault without that
context. The owner reports 0.08 V, but the measurement location remains unknown;
this is not a verified bare-cell voltage or a confirmed deeply discharged cell.

The offline stock-image checker now also verifies exact instruction bytes for
PD1 GPIO selection, output disable, output latch, ADC mux AF and thresholds
1510/2035. All checks passed against the hash-gated stock V0113 payload. These
are static boot settings, not runtime mux readback. No incorrect charge-control
setting or physical charger-enable pin has been established. No peripheral
control command or new firmware was sent during this follow-up.

PC2 output toggles were traced into calls which send two 192-byte buffers via a
shared serial-transfer routine at source listing 20013FD4. This is insufficient
to identify a charger-enable pin; its physical function remains unverified.
Do not toggle it as a charging experiment.

## Firmware pin haritası: şarjı kontrol eden çıkış var mı? (18 Ekim 2026)

Soru: firmware şarj entegresini kapalı tutuyor olabilir mi? Stok V0113, LLVM ile
RISC-V olarak açıldı ve Telink B91 GPIO register'larına (0x801403xx) yapılan
**bütün** doğrudan yazmalar çıkarıldı (`tools/map_firmware_pins.py`). Çıkış
olarak sürülen her pin bir işleve bağlandı:

| Pinler | İşlev | Kanıt |
| --- | --- | --- |
| PA0-4, PC1 | Tuş matrisi satırları (6) | Tarama döngüsü; keymap 384 B = 6×16×4 |
| PB0-7, PD2-6, PE5-7 | Tuş matrisi sütunları (16) | Aynı döngü, 16 adımlı sayaç |
| PE1 / PE2 / PE3 | LCD arka ışık / D-C / reset | D-C LOW iken komut 0x11 SLEEP OUT, 0x10 SLEEP IN; ardından PE1 LOW |
| PB5-7 | LCD seri hattı (matrisle paylaşımlı) | 192 baytlık aktarım rutininin hemen öncesi |
| PC5 / PC6 | Bit-bang I2C | Adres baytı 0xA2/0xA3: 7 bit 0x51, PCF8563/BM8563 RTC saat çipi |
| PA5 / PA6 | USB D-/D+ (çevre birimi modu) | FUNC_EN temizleniyor |
| PD1 | Pil ADC girişi | FUNC_EN temizleniyor, analog mux AF |
| PE4, PC3 | Giriş: şarj entegresi durum pinleri | Komut 1A durum baytı |

**Sonuç:** Firmware'in sürdüğü hiçbir pin şarj entegresine gitmiyor. I2C hattındaki tek
cihaz RTC; I2C ile ayarlanan bir şarj entegresi yok. Şarj entegresi tamamen bağımsız
çalışıyor, MCU yalnızca onun durumunu ve pil gerilimini okuyor. Firmware'i yeniden
yazmak şarj akımını değiştiremez; yalnızca gösterilen yüzdeyi değiştirebilir.

Aynı gün, klavye toplanmış ve USB'de uzun süre bekletilmişken pil hattı **0.026 V**
okundu (ADC ham örnekleri 0-11). Çalışan bir doğrusal şarj entegresi, pil bağlı
olsun ya da olmasın bu hatta voltaj gösterir. Hat sıfırda olduğuna göre entegre
çıkış vermiyor. Sıradaki adım donanım ölçümü: entegrenin üst yazısı, VCC (USB'de
~5 V olmalı), CE/EN, PROG ve varsa TEMP/NTC pini. TP4056 sınıfında TEMP pini pil
NTC'sine bağlıysa ve NTC kopuksa entegre şarjı tamamen askıya alır.
