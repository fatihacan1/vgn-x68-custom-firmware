"""Interface language: English (source) and Turkish.

English strings are the keys, so untranslated text simply falls back to English.
Only display text goes through t(); internal values, logs, backups and exported
JSON stay in English. The language is read once at start-up (see app.py) and a
change takes effect after the app restarts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LANGUAGES = {'en': 'English', 'tr': 'Türkçe'}
LANG = 'en'

# Labels drawn in the Press Start 2P pixel font (all-caps headings) use a plain I:
# that font draws İ at lowercase height, so 'PİL' would read as 'PiL'. Body text
# (DotGothic16 plus the system fallback) keeps the correct dotted İ.
TR = {
    # Navigation and page titles
    'Home': 'Ana Sayfa',
    'Lighting': 'Aydınlatma',
    'Keymap': 'Tuş Atama',
    'Macros': 'Makrolar',
    'Screen': 'Ekran',
    'Battery': 'Pil',
    'Firmware': 'FIRMWARE',  # loanword: keep the Latin I when upper-cased
    'Knowledge': 'Bilgi',
    'Advanced': 'Gelişmiş',
    'Preview an effect, then send it to the keyboard.': 'Bir efekti önizleyin, sonra klavyeye gönderin.',
    'Pick a key on the board and give it a new action.': 'Şemadan bir tuş seçin ve ona yeni bir eylem atayın.',
    'Shortcuts stored on the keyboard itself.': 'Doğrudan klavyenin içinde saklanan kısayollar.',
    'Measure the pack and watch it charge.': 'Bataryayı ölçün ve şarj oluşunu izleyin.',
    'Reviewed X68 builds, installed only when you say so.': 'İncelenmiş X68 sürümleri, yalnızca siz isterseniz yüklenir.',
    'Raw data, backups and the key tester.': 'Ham veriler, yedekler ve tuş test aracı.',
    'Send an image or GIF to the 160x96 screen.': '160x96 ekrana resim veya GIF gönderin.',
    'Verified facts and open questions, ready to copy.': 'Doğrulanmış bilgiler ve açık sorular, kopyalamaya hazır.',
    'Plug in over USB. Nothing is written until you press Send.': 'USB ile bağlayın. Gönder\'e basana kadar hiçbir şey yazılmaz.',

    # Sidebar, header and status bar
    'CUSTOM\nFIRMWARE': 'ÖZEL\nFIRMWARE',
    'COMMAND': 'MENÜ',
    'LINK': 'BAĞLANTI',
    'LANGUAGE': 'DIL',
    'BATTERY': 'PIL',
    'FIRMWARE': 'FIRMWARE',
    'Not connected': 'Bağlı değil',
    'LOOKING FOR X68': 'X68 ARANIYOR',
    'Connect the X68 over USB or its 2.4 GHz receiver.': 'X68\'i USB kablosuyla veya 2.4 GHz alıcısıyla bağlayın.',
    'Connect': 'Bağlan',
    'Connecting...': 'Bağlanıyor...',
    'Refresh': 'Yenile',
    'USB / wired mode': 'USB / kablolu mod',
    '2.4 GHz receiver (firmware and LCD media need USB)': '2.4 GHz alıcı (firmware ve LCD medyası için USB gerekir)',
    'Connected. Device protocol verified.': 'Bağlandı. Cihaz protokolü doğrulandı.',
    '[ ]  X68 NOT CONNECTED': '[ ]  X68 BAĞLI DEĞİL',
    'Choosing keys, colours or files never writes the keyboard. Each page has its own Send button.':
        'Tuş, renk veya dosya seçmek klavyeye hiçbir şey yazmaz. Her sayfanın kendi Gönder düğmesi vardır.',
    'Language': 'Dil',
    'Restart the app now to switch the language?': 'Dili değiştirmek için uygulama şimdi yeniden başlatılsın mı?',
    'Language saved. It applies the next time the app opens.': 'Dil kaydedildi. Uygulama bir sonraki açılışta bu dille başlar.',

    # Lighting
    'Wave': 'Dalga', 'Colour cloud': 'Renk bulutu', 'Vortex': 'Girdap', 'Spectrum': 'Spektrum',
    'Breathing': 'Nefes', 'Solid': 'Sabit', 'Reactive': 'Tepkili', 'Ripple': 'Halka',
    'Trail': 'İz', 'Stars': 'Yıldızlar', 'Flowers': 'Çiçekler', 'Scroll': 'Kayan',
    'Wings': 'Kanatlar', 'Build up': 'Dolma', 'Rain': 'Yağmur', 'Scan': 'Tarama',
    'Spread': 'Yayılma', 'Fast wave': 'Hızlı dalga', 'Custom table': 'Özel tablo', 'Off': 'Kapalı',
    'EFFECT': 'EFEKT',
    'LIGHT': 'IŞIK',
    'BRIGHTNESS': 'PARLAKLIK',
    'SPEED': 'HIZ',
    'COLOUR': 'RENK',
    'MODE': 'MOD',
    'PREVIEW': 'ÖNIZLEME',
    'Keep': 'Koru',
    'Single': 'Tek renk',
    'Rainbow': 'Gökkuşağı',
    'Effect': 'Efekt',
    'Key draft': 'Tuş taslağı',
    'Send to keyboard': 'Klavyeye gönder',
    'Read from keyboard': 'Klavyeden oku',
    'Export draft': 'Taslağı dışa aktar',
    'The board is a preview. In Key draft, click keys to paint them; drafts stay on this computer.':
        'Şema yalnızca önizlemedir. Tuş taslağı modunda tuşlara tıklayıp boyayın; taslaklar bu bilgisayarda kalır.',
    'Per-key draft is local only. Select Effect preview to send global lighting.':
        'Tuş taslağı yalnızca yereldir. Genel aydınlatmayı göndermek için Efekt önizlemesini seçin.',
    'Connect the keyboard and read its settings first.': 'Önce klavyeyi bağlayın ve ayarlarını okuyun.',
    '{key} colour staged locally. Per-key device upload is not verified.':
        '{key} rengi yerel taslağa eklendi. Tuş başına cihaza yükleme henüz doğrulanmadı.',

    # Keymap
    'SELECTED KEY': 'SEÇILI TUŞ',
    'Click a key on the board.': 'Şemadan bir tuşa tıklayın.',
    'ACTION TYPE': 'EYLEM TÜRÜ',
    'Keyboard': 'Klavye',
    'Media': 'Medya',
    'NEW ACTION': 'YENI EYLEM',
    'Add to draft': 'Taslağa ekle',
    'Fn and reserved firmware functions stay protected.': 'Fn ve firmware\'e ayrılmış işlevler korunur.',
    'DRAFT': 'TASLAK',
    'Empty. Picking keys never writes the keyboard.': 'Boş. Tuş seçmek klavyeye hiçbir şey yazmaz.',
    'Send draft ({count})': 'Taslağı gönder ({count})',
    'Discard': 'Vazgeç',
    'Cell': 'Hücre',
    'Matrix cell {index}': 'Matris hücresi {index}',
    '{key}\nnow sends {action}': '{key}\nşu an gönderiyor: {action}',
    'This key is reserved, unassigned or not yet mapped.': 'Bu tuş ayrılmış, atanmamış ya da henüz eşlenmemiş.',
    'Select an editable source key.': 'Düzenlenebilir bir kaynak tuş seçin.',
    'Select an editable source key first.': 'Önce düzenlenebilir bir kaynak tuş seçin.',
    'Added to draft. No command was sent.': 'Taslağa eklendi. Hiçbir komut gönderilmedi.',
    'Draft discarded. No command was sent.': 'Taslak silindi. Hiçbir komut gönderilmedi.',
    '{source}  to  {target}': '{source}  →  {target}',
    'Add a change to the draft first.': 'Önce taslağa bir değişiklik ekleyin.',
    'Keymap sent and verified.': 'Tuş ataması gönderildi ve doğrulandı.',
    'Play': 'Oynat', 'Prev': 'Önceki', 'Next': 'Sonraki', 'Vol+': 'Ses+', 'Vol−': 'Ses−', 'Mute': 'Sessiz',

    # Macros
    'SLOT': 'YUVA',
    'White: slot holds\na macro.': 'Beyaz: yuvada\nmakro var.',
    'Load slot': 'Yuvayı yükle',
    'SCRIPT': 'BETIK',
    'One shortcut or WAIT per line. Click a card above to add it.':
        'Her satıra bir kısayol veya WAIT yazın. Eklemek için yukarıdaki kartlara tıklayın.',
    'Check': 'Denetle',
    'Save to selected key': 'Seçili tuşa kaydet',
    'Pick the target key in Keymap first.': 'Önce Tuş Atama sayfasında hedef tuşu seçin.',
    'Valid macro / {count} events. Not saved yet.': 'Geçerli makro / {count} olay. Henüz kaydedilmedi.',
    'Invalid macro. Use balanced DOWN / UP events and valid WAIT values.':
        'Geçersiz makro. DOWN / UP olaylarını eşleştirin ve geçerli WAIT değerleri kullanın.',
    'This slot contains events the text editor cannot represent.': 'Bu yuva, metin düzenleyicinin gösteremediği olaylar içeriyor.',
    'Slot loaded from the keyboard.': 'Yuva klavyeden yüklendi.',
    'Empty slot. Write a new macro.': 'Boş yuva. Yeni bir makro yazın.',
    'Pick the target key in Keymap first, then come back here.': 'Önce Tuş Atama sayfasında hedef tuşu seçin, sonra buraya dönün.',

    # Battery
    'PACK VOLTAGE': 'BATARYA VOLTAJI',
    'DEVICE LEVEL': 'CIHAZ SEVIYESI',
    'FULL': 'DOLU',
    'No report yet.': 'Henüz ölçüm yok.',
    'Plug in over USB to measure.': 'USB ile bağlayıp ölçün.',
    'Monitoring stopped': 'İzleme durduruldu',
    'Monitoring / every 5 seconds': 'İzleniyor / 5 saniyede bir',
    ' / {count} readings': ' / {count} ölçüm',
    'Measure now': 'Şimdi ölç',
    'Start monitoring': 'İzlemeyi başlat',
    'Stop': 'Durdur',
    'EXPORT': 'DIŞA AKTAR',
    'Connect the keyboard over USB in wired mode.': 'Klavyeyi kablolu modda USB ile bağlayın.',
    'Voltage needs the Lavender Quest 0.6.0 build (Firmware page).': 'Voltaj ölçümü için Lavender Quest 0.6.0 sürümü gerekir (Firmware sayfası).',
    'Battery monitoring started / every 5 seconds.': 'Pil izleme başladı / 5 saniyede bir.',
    'Monitoring stopped. The last reading is retained.': 'İzleme durduruldu. Son ölçüm saklanıyor.',
    'Read at {stamp}. USB power {power}. Estimate via an inferred 1:2 divider.':
        '{stamp} saatinde okundu. USB gücü {power}. Tahmini değer (1:2 bölücü varsayımıyla).',
    'present': 'var',
    'absent': 'yok',
    'Device-reported level only.': 'Yalnızca cihazın bildirdiği seviye.',
    'Read {stamp} / raw level {level}, status {status}. Voltage is measured only by the 0.6.0 build.':
        '{stamp} okundu / ham seviye {level}, durum {status}. Voltaj yalnızca 0.6.0 sürümüyle ölçülür.',
    'Battery read complete at {stamp} / {value}.': 'Pil okuması tamamlandı: {stamp} / {value}.',
    'No voltage on the battery line.': 'Batarya hattında voltaj yok.',
    'Check that the battery connector is fully seated.': 'Batarya konnektörünün tam oturduğunu kontrol edin.',
    "If it is, the pack's protection board has cut the cell off. Jump-start it as below.":
        'Oturuyorsa bataryanın koruma kartı hücreyi devreden çıkarmıştır. Aşağıdaki gibi canlandırın.',
    'Unplug the pack. Clip a slow source to the cell tabs (B+ / B-) behind the protection board.':
        'Bataryayı çıkarın. Koruma kartının arkasındaki hücre uçlarına (B+ / B-) yavaş bir kaynak bağlayın.',
    'Back at 3.0 V, plug it in with USB and press Start monitoring here.':
        '3.0 V\'a geri geldiğinde USB ile takın ve buradan İzlemeyi başlat\'a basın.',
    'Deeply discharged. Jump-start it.': 'Tamamen boşalmış. Canlandırılması gerekiyor.',
    'Unplug the pack from the keyboard.': 'Bataryayı klavyeden çıkarın.',
    'Slow source: two AA cells in series through 10-33 ohm, or USB 5 V through 100 ohm. Red to B+, black to B-.':
        'Yavaş kaynak: 10-33 ohm üzerinden seri iki AA pil veya 100 ohm üzerinden USB 5 V. Kırmızı B+, siyah B- ucuna.',
    'If a small protection board sits on the pack, clip to the cell tabs behind it, not the wire ends.':
        'Batarya üzerinde küçük bir koruma kartı varsa kablo uçlarına değil, arkasındaki hücre uçlarına bağlayın.',
    'Measure every 10 minutes. Stop if the pack gets warm or swells.':
        '10 dakikada bir ölçün. Batarya ısınır veya şişerse hemen durun.',
    'At 3.0 V, plug it back in with USB and press Start monitoring. Rising voltage means the keyboard charges it.':
        '3.0 V\'ta USB ile tekrar takın ve İzlemeyi başlat\'a basın. Voltaj yükseliyorsa klavye şarj ediyor demektir.',
    'Low but recoverable.': 'Düşük ama kurtarılabilir.',
    'Keep USB connected and press Start monitoring.': 'USB bağlı kalsın ve İzlemeyi başlat\'a basın.',
    "Rising voltage within a few minutes means the keyboard's charger is working.":
        'Birkaç dakika içinde voltaj yükseliyorsa klavyenin şarj devresi çalışıyor demektir.',
    'Flat line: keep the slow source on until 3.0 V, then try again.':
        'Düz çizgi: yavaş kaynağı 3.0 V\'a kadar bağlı tutun, sonra tekrar deneyin.',
    'Low. Charge before wireless use.': 'Düşük. Kablosuz kullanmadan önce şarj edin.',
    'Keep USB connected. Voltage should rise steadily while charging.': 'USB bağlı kalsın. Şarj olurken voltaj düzenli yükselmeli.',
    'Battery voltage looks healthy.': 'Batarya voltajı sağlıklı görünüyor.',
    'Nothing to do. Use monitoring to watch it charge or discharge.':
        'Yapılacak bir şey yok. Şarj veya deşarjı görmek için izlemeyi kullanın.',
    'Voltage above a normal Li-ion cell.': 'Voltaj normal bir Li-ion hücrenin üzerinde.',
    'This often means no battery is attached and the charger output is being read.':
        'Bu genelde batarya takılı olmadığını ve şarj devresinin çıkışının okunduğunu gösterir.',
    'Check the connector, then read again.': 'Konnektörü kontrol edip tekrar okuyun.',
    'Collecting readings. Keep monitoring for at least 2 minutes.': 'Ölçümler toplanıyor. En az 2 dakika izlemeye devam edin.',
    'Charging: voltage rising {slope} mV/min.': 'Şarj oluyor: voltaj {slope} mV/dk artıyor.',
    'Discharging: voltage falling {slope} mV/min.': 'Boşalıyor: voltaj {slope} mV/dk düşüyor.',
    'Not charging: USB power present but voltage flat ({slope} mV/min) over the last few minutes.':
        'Şarj olmuyor: USB gücü var ama son birkaç dakikada voltaj sabit ({slope} mV/dk).',
    'Steady ({slope} mV/min).': 'Sabit ({slope} mV/dk).',

    # Firmware
    'Installed build: not checked': 'Yüklü sürüm: kontrol edilmedi',
    'Import file': 'Dosya içe aktar',
    'Check installed version': 'Yüklü sürümü kontrol et',
    'Allow my unreviewed binary (hardware recovery may be required)':
        'İncelenmemiş kendi dosyama izin ver (donanımsal kurtarma gerekebilir)',
    "Builds are made on this computer from the official V0113 firmware, downloaded once from VGN's own server. Offline? Import the official updater EXE or your own 236,916-byte .bin. Importing never uploads anything.":
        'Sürümler bu bilgisayarda, VGN\'in kendi sunucusundan bir kez indirilen resmi V0113 firmware\'inden üretilir. İnternet yok mu? Resmi güncelleyici EXE\'sini veya kendi 236.916 baytlık .bin dosyanızı içe aktarın. İçe aktarma hiçbir şey yüklemez.',
    'Install selected firmware': 'Seçili firmware\'i yükle',
    'Sync keyboard clock': 'Klavye saatini eşitle',
    'Select a build or inspect your own file, then explicitly click Install.':
        'Bir sürüm seçin veya kendi dosyanızı inceleyin, ardından açıkça Yükle\'ye tıklayın.',
    'Selected file:': 'Seçilen dosya:',
    'ORIGINAL V0113': 'ORIJINAL V0113',
    'YOUR FIRMWARE': 'SIZIN FIRMWARE',
    'X68 PIXEL DESKTOP': 'X68 PIKSEL MASAÜSTÜ',
    "VGN's factory firmware, unchanged. Use it to roll back.": 'VGN\'in değiştirilmemiş fabrika firmware\'i. Geri dönmek için kullanın.',
    'No trusted visual preview for an imported binary. Inspect its checks before installing.':
        'İçe aktarılan dosya için güvenilir önizleme yok. Yüklemeden önce kontrol sonuçlarını inceleyin.',
    'Single purple pixel scene.\nRAM clock sync and image/GIF player.': 'Tek mor piksel sahnesi.\nRAM saat eşitleme ve resim/GIF oynatıcı.',
    '\nBattery voltage readout for the Battery page.': '\nPil sayfası için batarya voltajı okuma.',
    '\nLive WIN/MAC and Windows-key lock in the header.': '\nBaşlıkta canlı WIN/MAC ve Windows tuşu kilidi.',
    '\nTheme illustration / sample time.': '\nTema çizimi / örnek saat.',
    ' FACTORY FIRMWARE \n\n VGN V0113 ': ' FABRIKA FIRMWARE \n\n VGN V0113 ',
    ' CUSTOM BINARY \n\n NO TRUSTED PREVIEW ': ' ÖZEL DOSYA \n\n GÜVENILIR ÖNIZLEME YOK ',
    'Import the official updater or a V0113 .bin': 'Resmi güncelleyiciyi veya bir V0113 .bin dosyasını içe aktarın',
    'Firmware or official updater': 'Firmware veya resmi güncelleyici',
    'Not the official updater and not a 236,916-byte V0113 .bin.': 'Bu dosya ne resmi güncelleyici ne de 236.916 baytlık bir V0113 .bin.',
    'Official V0113 recognised by SHA256 and cached. All builds can now be made offline.':
        'Resmi V0113 SHA256 ile tanındı ve önbelleğe alındı. Artık tüm sürümler çevrimdışı üretilebilir.',
    'Official firmware imported. Nothing was uploaded.': 'Resmi firmware içe aktarıldı. Hiçbir şey yüklenmedi.',
    'bytes': 'bayt',
    'Known reviewed image': 'Bilinen, incelenmiş imaj',
    'Structurally valid; code and hardware behavior are NOT reviewed': 'Yapısal olarak geçerli; kod ve donanım davranışı İNCELENMEDİ',
    'File inspected locally. Nothing was uploaded.': 'Dosya yerel olarak incelendi. Hiçbir şey yüklenmedi.',
    'Choose a valid firmware file first.': 'Önce geçerli bir firmware dosyası seçin.',
    'This binary is unreviewed. Enable the explicit unreviewed-file option before installing.':
        'Bu dosya incelenmemiş. Yüklemeden önce incelenmemiş dosya seçeneğini açıkça etkinleştirin.',
    'This is YOUR UNREVIEWED CODE. Structural checks do not establish hardware compatibility; recovery may require a programmer.':
        'Bu SİZİN İNCELENMEMİŞ KODUNUZ. Yapısal kontroller donanım uyumluluğunu kanıtlamaz; kurtarmak için programlayıcı gerekebilir.',
    'Install firmware': 'Firmware yükle',
    'Install {name}?': '{name} yüklensin mi?',
    '\n\nThe official V0113 firmware is downloaded from VGN once if it is not cached yet.\nKeep USB connected in wired mode until verification completes.\nSettings are backed up before writing.':
        '\n\nResmi V0113 firmware\'i önbellekte yoksa VGN\'den bir kez indirilir.\nDoğrulama bitene kadar USB kablolu modda bağlı kalsın.\nYazmadan önce ayarlar yedeklenir.',
    'Preparing the official V0113 base and applying the patch...': 'Resmi V0113 tabanı hazırlanıyor ve yama uygulanıyor...',
    'Installation complete. Device-reported CRC matches the selected build.':
        'Yükleme tamamlandı. Cihazın bildirdiği CRC seçilen sürümle eşleşiyor.',
    'Installed: {build}  /  CRC {crc}': 'Yüklü: {build}  /  CRC {crc}',
    'Installed build: not reported over 2.4 GHz  /  receiver CRC {crc}': 'Yüklü sürüm: 2.4 GHz üzerinden bildirilmiyor  /  alıcı CRC {crc}',
    'Unrecognized build': 'Tanınmayan sürüm',
    'Unknown build': 'Bilinmeyen sürüm',
    'Version read complete / {build} / CRC {crc}': 'Sürüm okundu / {build} / CRC {crc}',
    'Writing packet {done} / {total}. Do not unplug the keyboard.': 'Paket yazılıyor {done} / {total}. Klavyeyi çıkarmayın.',
    'Update stopped. Check Advanced logs before retrying; no automatic retry was sent.':
        'Güncelleme durdu. Tekrar denemeden önce Gelişmiş sayfasındaki kayıtlara bakın; otomatik yeniden deneme yapılmadı.',

    # Screen
    'Crop': 'Kırp', 'Fit': 'Sığdır', 'Stretch': 'Uzat',
    'Choose image / GIF': 'Resim / GIF seç',
    'Upload': 'Yükle',
    'PNG, JPG, GIF, WEBP or BMP. Long GIFs are sampled to 8 frames.': 'PNG, JPG, GIF, WEBP veya BMP. Uzun GIF\'lerden 8 kare alınır.',
    'SCENE': 'EKRAN GÖRÜNÜMÜ',
    'The keyboard screen shows either the clock scene or the image/GIF you upload. A new upload replaces the previous one. Press the button below to go back to the clock scene.':
        'Klavyenin ekranı ya saat sahnesini ya da yüklediğiniz resmi/GIF\'i gösterir. Yeni bir yükleme öncekinin yerine geçer. Saat sahnesine dönmek için aşağıdaki düğmeye basın.',
    'Lavender desktop': 'Saat sahnesine dön',
    'CLOCK': 'SAAT',
    'Sync time automatically': 'Saati otomatik eşitle',
    'Every': 'Her',
    'minutes': 'dakikada bir',
    'Time format': 'Saat biçimi',
    '24-hour': '24 saat',
    '12-hour (AM/PM)': '12 saat (ÖÖ/ÖS)',
    'Open at login on Mac': 'Mac oturumu açılınca başlat',
    'Launch when I sign in to Windows': 'Windows\'a giriş yapınca başlat',
    'Sync time now': 'Saati şimdi eşitle',
    'AM/PM needs Lavender Quest 0.8.0 or newer. On 2.4 GHz, the format is checked after syncing; use wired USB if it cannot be verified.':
        '12 saat biçimi için Lavender Quest 0.8.0 veya üstü gerekir. 2.4 GHz\'de biçim eşitlemeden sonra kontrol edilir; doğrulanamazsa kablolu USB kullanın.',
    'Time and format stay in RAM. After a full power loss, reopen the app to sync again.':
        'Saat ve biçim RAM\'de tutulur. Güç tamamen kesilirse yeniden eşitlemek için uygulamayı açın.',
    'Waiting for a verified 0.5.1+ connection.': 'Doğrulanmış bir 0.5.1+ bağlantısı bekleniyor.',
    'Choose an image or animation': 'Bir resim veya animasyon seçin',
    'Images and animations': 'Resimler ve animasyonlar',
    'All files': 'Tüm dosyalar',
    '{name}  /  {source} → {frames} frames  /  {period} ms per frame  /  {size} bytes':
        '{name}  /  {source} → {frames} kare  /  kare başına {period} ms  /  {size} bayt',
    'Preview ready. Nothing has been sent to the keyboard.': 'Önizleme hazır. Klavyeye hiçbir şey gönderilmedi.',
    'Choose an image or GIF first.': 'Önce bir resim veya GIF seçin.',
    'Install Lavender Quest 0.6.0 in Firmware first.': 'Önce Firmware sayfasından Lavender Quest 0.6.0 yükleyin.',
    'Install Lavender Quest 0.6.0 first.': 'Önce Lavender Quest 0.6.0 yükleyin.',
    'Replace custom animation': 'Özel animasyonu değiştir',
    'Upload the converted preview?\n\nThis replaces the keyboard’s entire custom image/GIF bank. The previous animation cannot be read back.\nKeep USB connected until the transfer completes.':
        'Dönüştürülen önizleme yüklensin mi?\n\nBu işlem klavyedeki tüm özel resim/GIF bankasının yerine geçer. Önceki animasyon geri okunamaz.\nAktarım bitene kadar USB bağlı kalsın.',
    'Transfer acknowledged; display settings read back. Check the physical screen. Converted data and transfer log saved in reports/media.':
        'Aktarım onaylandı; ekran ayarları geri okundu. Klavyenin ekranını kontrol edin. Dönüştürülen veri ve aktarım kaydı reports/media klasörüne kaydedildi.',
    'Custom media selected. Use Lavender desktop to return to the clock scene.':
        'Özel medya seçildi. Saat sahnesine dönmek için Lavender masaüstü\'nü kullanın.',
    'Lavender desktop selected.': 'Lavender masaüstü seçildi.',
    'Uploading {done} / {total} bytes. Keep USB connected.': '{done} / {total} bayt yükleniyor. USB bağlı kalsın.',
    'Transfer stopped. Check Advanced logs. No automatic retry was sent.':
        'Aktarım durdu. Gelişmiş sayfasındaki kayıtlara bakın. Otomatik yeniden deneme yapılmadı.',
    'Time format saved. Press Sync time now to apply to the keyboard.':
        'Saat biçimi kaydedildi. Klavyeye uygulamak için Saati şimdi eşitle\'ye basın.',
    'The app will open at your next Mac login.': 'Uygulama bir sonraki Mac oturumunda açılacak.',
    'Windows startup enabled.': 'Windows açılışında başlatma etkin.',
    'Open at login disabled.': 'Açılışta başlatma kapatıldı.',
    'Startup setting failed: ': 'Başlangıç ayarı yapılamadı: ',
    'Connect the keyboard and wait for its settings to load before syncing.':
        'Eşitlemeden önce klavyeyi bağlayın ve ayarlarının yüklenmesini bekleyin.',
    'Live sync requires Lavender Quest 0.5.1 or newer. Install it in Firmware.':
        'Canlı eşitleme için Lavender Quest 0.5.1 veya üstü gerekir. Firmware sayfasından yükleyin.',
    'Another operation is running. Try Sync time now when it finishes.':
        'Başka bir işlem sürüyor. Bitince Saati şimdi eşitle\'yi deneyin.',
    'AM/PM needs Lavender Quest 0.8.0 or newer. Check the installed build in Firmware.':
        '12 saat biçimi için Lavender Quest 0.8.0 veya üstü gerekir. Firmware sayfasında yüklü sürümü kontrol edin.',
    'Applying {format} time to the keyboard...': 'Klavyeye {format} biçiminde saat uygulanıyor...',
    'Keyboard synced: {time} / {format}': 'Klavye eşitlendi: {time} / {format}',
    'Sync failed: ': 'Eşitleme başarısız: ',

    # Knowledge
    'FACTS YOU CAN TAKE WITH YOU': 'YANINIZDA GÖTÜREBILECEĞINIZ BILGILER',
    'Copy this context into an AI chat. Verified behavior and open questions are explicitly separated. No private device paths are included.':
        'Bu içeriği bir yapay zekâ sohbetine kopyalayın. Doğrulanmış davranışlar ve açık sorular ayrı tutulur. Cihaza özel yollar dahil edilmez. (İçerik İngilizcedir.)',
    'Copy AI context': 'YZ içeriğini kopyala',
    'Export Markdown': 'Markdown olarak aktar',
    'Export JSON': 'JSON olarak aktar',
    'Knowledge file missing. Use the complete application folder.': 'Bilgi dosyası eksik. Uygulama klasörünün tamamını kullanın.',
    'AI context copied to clipboard.': 'YZ içeriği panoya kopyalandı.',
    'Knowledge exported.': 'Bilgi dışa aktarıldı.',

    # Advanced
    'Device & packets': 'Cihaz ve paketler',
    'Key tester': 'Tuş test aracı',
    'Backups & logs': 'Yedekler ve kayıtlar',
    'Focused-window Raw Input from the X68 only. Key tester requires Windows.':
        'Yalnızca bu pencere öndeyken ve yalnızca X68\'den gelen tuşlar okunur. Tuş test aracı Windows gerektirir.',
    'Start 60-second test': '60 saniyelik testi başlat',
    'Stop test': 'Testi durdur',
    'Clear results': 'Sonuçları temizle',
    'No key events recorded.': 'Henüz tuş basışı kaydedilmedi.',
    'Every settings write creates a backup and verifies readback.': 'Her ayar yazımı önce yedek alır ve sonra geri okuyarak doğrular.',
    'Restore settings backup': 'Ayar yedeğini geri yükle',
    'Export diagnostics': 'Tanılama verisini aktar',
    'Open reports folder': 'Rapor klasörünü aç',
    'Read cached ADC snapshot': 'Önbellekteki ADC verisini oku',
    'Advanced matrix-cell selection (optional):': 'Gelişmiş matris hücresi seçimi (isteğe bağlı):',
    'Connect the X68 in wired mode first.': 'Önce X68\'i kablolu modda bağlayın.',
    'Testing. Keep this window focused.': 'Test ediliyor. Bu pencere önde kalsın.',
    '{key} / {count} press events / {keys} distinct keys': '{key} / {count} basış / {keys} farklı tuş',
    'Restore X68 settings backup': 'X68 ayar yedeğini geri yükle',
    'JSON backup': 'JSON yedeği',
    'Check the installed version first.': 'Önce yüklü sürümü kontrol edin.',
    'ADC snapshot read. Raw counts and calculation are in Advanced; physical voltage/current remain unknown.':
        'ADC verisi okundu. Ham değerler ve hesap Gelişmiş sayfasında; gerçek voltaj/akım bilinmiyor.',
    'File saved.': 'Dosya kaydedildi.',
    'Interface error recorded in Advanced. Other actions remain available.':
        'Arayüz hatası Gelişmiş sayfasına kaydedildi. Diğer işlemler kullanılabilir.',
    'Wait for the device transfer to finish before closing.': 'Kapatmadan önce cihaz aktarımının bitmesini bekleyin.',

    # Safety warnings
    'Made a mistake? Every send is backed up first. Undo it in Advanced > Restore settings backup.':
        'Yanlış mı oldu? Her gönderimden önce yedek alınır. Gelişmiş > Ayar yedeğini geri yükle ile geri alabilirsiniz.',
    'SAFETY: these steps mean opening the keyboard and powering a lithium battery from outside. Lithium batteries can get hot, swell or catch fire. If you are not comfortable with electronics, take it to a repair shop instead. Never leave it unattended.':
        'GÜVENLİK: Bu adımlar klavyeyi açmayı ve lityum bataryaya dışarıdan güç vermeyi gerektirir. Lityum piller ısınabilir, şişebilir veya alev alabilir. Elektronik konusunda emin değilseniz bir teknik servise götürün. Bataryayı asla başından ayrılarak bırakmayın.',
    "CAUTION: installing firmware rewrites the keyboard's own internal software. If it is interrupted (cable unplugged, power cut, computer goes to sleep) the keyboard may stop working. Lighting, keys and macros do NOT need a firmware install.":
        'DİKKAT: Firmware yüklemek klavyenin kendi iç yazılımını değiştirir. İşlem yarıda kesilirse (kablo çıkarsa, elektrik giderse, bilgisayar uykuya geçerse) klavye çalışmayabilir. Aydınlatma, tuş atama ve makrolar için firmware yüklemeniz GEREKMEZ.',
    'Connect the X68 with a USB cable before installing firmware.': 'Firmware yüklemeden önce X68\'i USB kablosuyla bağlayın.',
    'Firmware can only be installed over a USB cable. Set the keyboard switch to wired and plug in the cable.':
        'Firmware yalnızca USB kablosuyla yüklenebilir. Klavyedeki anahtarı kablolu konuma getirin ve kabloyu takın.',
    'This computer is running on battery. Plug in the charger before you continue.':
        'Bu bilgisayar şu an pille çalışıyor. Devam etmeden önce şarj cihazını takın.',
    "Firmware is the keyboard's own internal software; installing replaces it and takes a few minutes.":
        'Firmware, klavyenin kendi iç yazılımıdır; yükleme onu değiştirir ve birkaç dakika sürer.',
    'The keyboard is connected with a USB cable and its switch is set to wired.': 'Klavye USB kablosuyla bağlı ve anahtarı kablolu konumda.',
    'The computer is plugged into power (a laptop is on its charger).': 'Bilgisayar prize takılı (dizüstüyse şarj cihazı takılı).',
    'I will not unplug the cable, close this app, or shut down or sleep the computer until it says the installation is complete.':
        'Yükleme tamamlandı yazana kadar kabloyu çıkarmayacağım, bu uygulamayı kapatmayacağım, bilgisayarı kapatmayacağım veya uyku moduna almayacağım.',
    'I understand that if the installation is interrupted, the keyboard may stop working and need special hardware to recover.':
        'Yükleme yarıda kesilirse klavyenin çalışmayabileceğini ve kurtarmak için özel donanım gerekebileceğini anlıyorum.',
    'Install': 'Yükle',
    'Cancel': 'Vazgeç',
    'Tick every box to continue:': 'Devam etmek için tüm kutuları işaretleyin:',
    "Restore this backup?\n\nThe keyboard's current lighting, keymap and macros will be replaced with the ones in the backup.":
        'Bu yedek geri yüklensin mi?\n\nKlavyedeki mevcut aydınlatma, tuş atamaları ve makrolar yedektekilerle değiştirilecek.',
    'Transfer in progress': 'Aktarım sürüyor',
    'Do not close the app or unplug the keyboard yet. Closing now could leave the keyboard unusable. Wait until it says the transfer is complete.':
        'Uygulamayı henüz kapatmayın ve klavyeyi çıkarmayın. Şimdi kapatmak klavyeyi kullanılamaz hale getirebilir. Aktarımın tamamlandığı yazana kadar bekleyin.',
    'Unreviewed firmware': 'İncelenmemiş firmware',
    'This lets you install a firmware file that nobody has checked. A wrong or broken file can make the keyboard stop working for good, and fixing it needs a hardware programmer.\n\nOnly continue if you know exactly what this file is. Turn this option on?':
        'Bu seçenek, kimsenin kontrol etmediği bir firmware dosyasını yüklemenize izin verir. Yanlış veya bozuk bir dosya klavyeyi kalıcı olarak bozabilir; düzeltmek için donanım programlayıcısı gerekir.\n\nYalnızca bu dosyanın ne olduğunu kesin olarak biliyorsanız devam edin. Bu seçenek açılsın mı?',

    'This keyboard runs firmware this app does not recognise (CRC {crc}). Installing firmware is blocked to protect it. Lighting, keys and macros still work.':
        'Bu klavyede uygulamanın tanımadığı bir firmware var (CRC {crc}). Klavyeyi korumak için firmware yükleme engellendi. Aydınlatma, tuş atama ve makrolar yine çalışır.',
    'Unrecognised firmware': 'Tanınmayan firmware',
    "Your keyboard has VGN's older factory firmware, V0112 (CRC {crc}). The builds here can only be installed on V0113, so installing is blocked to protect the keyboard. To use them: 1) on VGN's official page download.vgnlab.com.cn/firmware open VGN X68 and download the middle item, X68 键盘固件 (X68-V0113固件升级.exe, 2,580,992 bytes); 2) close this app, connect the keyboard by USB cable in wired mode with the computer on mains power, run the updater and wait for OTA Success; 3) reopen this app: it should show Original V0113 and allow the install. Lighting, keys and macros already work on V0112.":
        'Klavyenizde VGN\'in eski fabrika firmware\'i V0112 var (CRC {crc}). Buradaki sürümler yalnızca V0113 üzerine kurulabildiği için, klavyenizi korumak amacıyla yükleme engellendi. Kullanmak için: 1) VGN\'in resmi sayfası download.vgnlab.com.cn/firmware adresinde VGN X68\'i açın ve ortadaki X68 键盘固件 dosyasını indirin (X68-V0113固件升级.exe, 2.580.992 bayt); 2) bu uygulamayı kapatın, klavyeyi kablolu modda USB kablosuyla bağlayın, bilgisayar prize takılı olsun, güncelleyiciyi çalıştırıp OTA Success yazısını bekleyin; 3) bu uygulamayı yeniden açın: Original V0113 görünmeli ve yüklemeye izin verilmeli. Aydınlatma, tuş atama ve makrolar V0112\'de de çalışır.',
    "The builds here were made only for VGN's original V0113 firmware. Writing them over a different version could leave the keyboard unusable.":
        'Buradaki sürümler yalnızca VGN\'in orijinal V0113 firmware\'i için hazırlandı. Farklı bir sürümün üzerine yazmak klavyeyi kullanılamaz hale getirebilir.',

    # Lighting preview
    'Colours flow across the keyboard from left to right.': 'Renkler klavyede soldan sağa akar.',
    'Soft clouds of colour drift and blend slowly.': 'Yumuşak renk bulutları yavaşça süzülür ve birbirine karışır.',
    'Colours spin around the centre of the keyboard.': 'Renkler klavyenin ortası etrafında döner.',
    'The whole keyboard cycles through every colour together.': 'Tüm klavye aynı anda sırayla bütün renklere geçer.',
    'Keys slowly fade in and out, like breathing.': 'Tuşlar nefes alır gibi yavaşça yanıp söner.',
    'Every key stays on one steady colour.': 'Bütün tuşlar sabit tek bir renkte kalır.',
    'Only the keys you press light up, then fade away.': 'Yalnızca bastığınız tuşlar yanar, sonra yavaşça söner.',
    'Each key press sends a ring of light outwards.': 'Her tuş basışı dışa doğru yayılan bir ışık halkası oluşturur.',
    'A light runs across the keys, leaving a fading tail.': 'Bir ışık tuşların üzerinde koşar, arkasında sönen bir iz bırakır.',
    'Random keys twinkle on and off like stars.': 'Rastgele tuşlar yıldızlar gibi parıldar.',
    'Patches of colour bloom open and fade, one after another.': 'Renk lekeleri çiçek gibi açılır ve sırayla solar.',
    'Bands of colour scroll up the keyboard row by row.': 'Renk şeritleri sıra sıra yukarı doğru kayar.',
    'Colours spread outwards from the middle to both sides.': 'Renkler ortadan iki yana doğru kanat gibi açılır.',
    'Keys light up column by column until the board is full.': 'Tuşlar sütun sütun yanar, klavye dolana kadar birikir.',
    'Drops of light fall down the keyboard.': 'Işık damlaları klavyede yukarıdan aşağı düşer.',
    'A bar of light sweeps from side to side.': 'Bir ışık çubuğu bir yandan öbür yana tarar.',
    'Rings of colour keep spreading out from the centre.': 'Renk halkaları ortadan sürekli dışa yayılır.',
    'The wave effect, flowing much faster.': 'Dalga efektinin çok daha hızlı akan hâli.',
    'Plays the per-key colour table stored on the keyboard; shown here as one colour.':
        'Klavyede kayıtlı tuş başına renk tablosunu oynatır; burada tek renk olarak gösterilir.',
    'All lighting is switched off.': 'Tüm aydınlatma kapalıdır.',
    'The animation is an approximation; Send shows the real effect on the keyboard.':
        'Animasyon yaklaşıktır; gerçek efekti görmek için klavyeye gönderin.',
    'Key draft is local only and is never sent to the keyboard.': 'Tuş taslağı yalnızca bu bilgisayardadır, klavyeye asla gönderilmez.',
    'Send will write: {effect} / brightness {brightness}/4 / speed {speed}/4 / colour {colour} / mode {mode}':
        'Gönderilecek: {effect} / parlaklık {brightness}/4 / hız {speed}/4 / renk {colour} / mod {mode}',
    "The keyboard's current lighting has not been read yet.": 'Klavyedeki mevcut aydınlatma henüz okunmadı.',
    'effect': 'efekt', 'brightness': 'parlaklık', 'speed': 'hız', 'colour': 'renk', 'mode': 'mod',
    'Different from the keyboard now: {fields}.': 'Klavyedeki ayardan farklı olanlar: {fields}.',
    'Same as the keyboard now; sending changes nothing.': 'Klavyedeki ayarla aynı; göndermek bir şey değiştirmez.',

    # Macros page
    'WHAT IS A MACRO?': 'MAKRO NEDIR?',
    'A macro makes one key press several keys for you, in order. For example, one key can copy, wait a moment and paste. Macros are stored inside the keyboard, so they work even when this app is closed.':
        'Makro, tek bir tuşa bastığınızda sizin yerinize birkaç tuşa sırayla basar. Örneğin tek bir tuş kopyalayıp kısa bir an bekleyip yapıştırabilir. Makrolar klavyenin içinde saklanır; bu program kapalıyken de çalışır.',
    '1. START FROM AN EXAMPLE': '1. BIR ÖRNEKLE BAŞLAYIN',
    'Or write your own on the right.': 'Ya da sağda kendiniz yazın.',
    '2. THE STEPS': '2. ADIMLAR',
    '3. WHICH KEY RUNS IT?': '3. HANGI TUŞ ÇALIŞTIRSIN?',
    'Copy and paste': 'Kopyala ve yapıştır',
    'Select all and copy': 'Tümünü seç ve kopyala',
    'Screenshot of an area': 'Ekran alıntısı al',
    'Task Manager': 'Görev Yöneticisi',
    'Show the desktop': 'Masaüstünü göster',
    'Lock the computer': 'Bilgisayarı kilitle',
    'Close the window': 'Pencereyi kapat',
    'Undo three times': 'Üç kez geri al',
    'One step per line:\n  CTRL+C  keys pressed together, joined with +\n  ENTER  a single key by its name (A, F5, ESC, SPACE...)\n  WAIT 100  wait 100 milliseconds before the next step\n  Click a card above to add it.':
        'Her satır bir adımdır:\n  CTRL+C  birlikte basılan tuşlar, + ile birleştirilir\n  ENTER  tek bir tuş, adıyla (A, F5, ESC, SPACE...)\n  WAIT 100  sonraki adımdan önce 100 milisaniye bekle\n  Eklemek için yukarıdaki kartlara tıklayın.',
    'Connect the keyboard to choose a key.': 'Tuş seçmek için klavyeyi bağlayın.',
    'Choose a key from the list.': 'Listeden bir tuş seçin.',
    'Right now this key sends: {action}': 'Bu tuş şu an şunu gönderiyor: {action}',
    'Save macro to {key}': 'Makroyu {key} tuşuna kaydet',
    'Save macro': 'Makroyu kaydet',
    'Tip: pick a key you rarely use, such as Ins, PgUp or PgDn. That key will run the macro instead of its normal job. You can give it back its normal job on the Keymap page.':
        'İpucu: Ins, PgUp veya PgDn gibi az kullandığınız bir tuş seçin. O tuş normal işi yerine makroyu çalıştıracak. Tuş Atama sayfasından eski işini geri verebilirsiniz.',
    'Saved in slot': 'Kaydedileceği yuva',
    'The keyboard keeps up to 16 macros. White numbers are slots already in use; a free slot is picked for you. To see what a slot holds, click it and press Load slot.':
        'Klavye en fazla 16 makro saklar. Beyaz numaralar dolu yuvalardır; boş bir yuva sizin için otomatik seçilir. Bir yuvada ne olduğunu görmek için ona tıklayıp Yuvayı yükle\'ye basın.',
    'Choose the key that should run the macro, then press Save macro.': 'Makroyu çalıştıracak tuşu seçin, sonra Makroyu kaydet\'e basın.',
    'right': 'sağ', 'left': 'sol',
    'The macro is empty. Add at least one step.': 'Makro boş. En az bir adım ekleyin.',
    'This macro is valid: {count} key events. It is not saved yet.': 'Makro geçerli: {count} tuş olayı. Henüz kaydedilmedi.',
    'Line {line}: "{name}" is not a key name this keyboard knows.': '{line}. satır: "{name}" bu klavyenin tanıdığı bir tuş adı değil.',
    'Line {line}: WAIT needs a number of milliseconds, for example WAIT 100.': '{line}. satır: WAIT\'ten sonra milisaniye cinsinden bir sayı gelmeli, örneğin WAIT 100.',
    'There is a mistake in the macro. Use one step per line, keys joined with + and WAIT followed by a number.':
        'Makroda bir hata var. Her satıra bir adım yazın, tuşları + ile birleştirin, WAIT\'ten sonra bir sayı yazın.',
    'Connect the keyboard first.': 'Önce klavyeyi bağlayın.',
    'Choose the key that should run the macro first (step 3).': 'Önce makroyu çalıştıracak tuşu seçin (3. adım).',
    'Save this macro to {key}?\n\nFrom now on, pressing {key} runs the macro instead of its normal job. You can undo this on the Keymap page or in Advanced > Restore settings backup.':
        'Bu makro {key} tuşuna kaydedilsin mi?\n\nBundan sonra {key} tuşuna basınca normal işi yerine makro çalışacak. Bunu Tuş Atama sayfasından veya Gelişmiş > Ayar yedeğini geri yükle ile geri alabilirsiniz.',
    # Battery chart
    'No readings yet. Press Measure now or Start monitoring.': 'Henüz ölçüm yok. Şimdi ölç veya İzlemeyi başlat\'a basın.',
    '{count} readings': '{count} ölçüm',

    # Firmware preview and screen legend
    'Newest, recommended. Windows logo (four colours) or Apple logo, a WIN/MAC chip and a padlock that shows the Windows-key lock. Includes everything from the older builds.':
        'En yeni sürüm, önerilen. Dört renkli Windows logosu veya Apple logosu, WIN/MAC rozeti ve Windows tuşu kilidini gösteren asma kilit. Eski sürümlerdeki her şey dahil.',
    'Windows/Apple logo and padlock badges (cyan Windows logo with a coloured rail). Includes everything from the older builds.':
        'Windows/Apple logosu ve asma kilit rozeti (mavi Windows logosu ve renkli bir çizgi). Eski sürümlerdeki her şey dahil.',
    'Header shows WIN/MAC and L:ON/L:OFF as text. Includes everything from the older builds.':
        'Üst şeritte WIN/MAC ve L:ON/L:OFF yazı olarak görünür. Eski sürümlerdeki her şey dahil.',
    'Adds the 12-hour AM/PM clock. Includes everything from the older builds.': '12 saatlik (AM/PM) saat seçeneğini ekler. Eski sürümlerdeki her şey dahil.',
    'Adds the real battery voltage on the Battery page. The screen looks the same as 0.5.1.': 'Pil sayfasına gerçek batarya voltajını ekler. Ekran 0.5.1 ile aynı görünür.',
    'First stable build: purple pixel scene, clock set from the computer, image/GIF player and a battery badge on the screen.':
        'İlk kararlı sürüm: mor piksel sahne, bilgisayardan ayarlanan saat, resim/GIF oynatıcı ve ekranda pil rozeti.',
    'This build is installed on your keyboard now.': 'Bu sürüm şu an klavyenizde yüklü.',
    'Live preview of this build: the clock runs, and the Windows/Mac and lock badges change every few seconds to show what they look like.':
        'Bu sürümün canlı önizlemesi: saat işler; Windows/Mac ve kilit rozetleri nasıl göründüklerini göstermek için birkaç saniyede bir değişir.',
    'ON THE SCREEN': 'EKRANDA NE VAR?',
    "Top-left logo and WIN/MAC: the keyboard's Windows or Mac mode. Fn + A switches to Windows, Fn + S to Mac (0.9.0 and newer).":
        'Sol üstteki logo ve WIN/MAC: klavyenin Windows ya da Mac modu. Fn + A Windows\'a, Fn + S Mac\'e geçirir (0.9.0 ve üstü).',
    'Padlock at the top right: the Windows-key lock, so the Windows key cannot interrupt a game. Fn + Windows key turns it on or off. Gold and closed = locked, green and open = unlocked.':
        'Sağ üstteki asma kilit: Windows tuşu kilidi; oyun oynarken Windows tuşuna yanlışlıkla basınca masaüstüne atılmazsınız. Fn + Windows tuşu ile açılıp kapanır. Altın ve kapalı = kilitli, yeşil ve açık = kilitsiz.',
    'Big clock and DD/MM date: set from this computer (Screen page > Clock). They keep running when the app is closed, until the keyboard loses power.':
        'Büyük saat ve GÜN/AY tarihi: bu bilgisayardan ayarlanır (Ekran sayfası > Saat). Uygulama kapalıyken de işlemeye devam eder; klavyenin gücü tamamen kesilene kadar.',
    'Battery at the bottom: the battery level the keyboard reports.': 'Alttaki pil: klavyenin bildirdiği pil seviyesi.',
    'X68.EXE, CLOCK, DAY-MO, START and READY: decorative pixel-game text. They have no function.':
        'X68.EXE, CLOCK, DAY-MO, START ve READY: piksel oyun havası veren süs yazıları. Bir işlevleri yok.',
    'The bunny blinks and the coin spins: animation only.': 'Tavşanın göz kırpması ve dönen altın para: yalnızca animasyon.',
    'Fn + PgUp steps through the screen modes 0-4. On 0.10.0 screen 0 is the clock and screens 1-4 each show their own image (an empty one shows the clock). On older builds modes 0-3 all show the clock and mode 4 shows your image. The Screen page buttons switch directly.':
        "Fn + PgUp 0-4 arası ekran modlarında sırayla gezer. 0.10.0'da 0. ekran saattir, 1-4. ekranların her biri kendi resmini gösterir (boş olan saati gösterir). Eski sürümlerde 0-3 arası modların hepsi saati, 4. mod resminizi gösterir. Ekran sayfasındaki düğmeler doğrudan geçiş yapar.",

    # Screen picker
    'Show my image/GIF': 'Resmimi göster',
    'Connect the keyboard to see which screen is showing.': 'Hangi ekranın açık olduğunu görmek için klavyeyi bağlayın.',
    'The keyboard has 5 screen modes (0-4); Fn + PgUp / PgDn steps through them. On Lavender, modes 0-3 all show the clock scene and mode 4 shows your uploaded image/GIF.':
        'Klavyede 5 ekran modu var (0-4); Fn + PgUp / PgDn bunlar arasında sırayla gezer. Lavender\'da 0-3 arası modların hepsi saat sahnesini, 4. mod ise yüklediğiniz resmi/GIF\'i gösterir.',
    'Upload an image or GIF first; there is nothing to show yet.': 'Önce bir resim veya GIF yükleyin; henüz gösterilecek bir şey yok.',
    'Your image/GIF is now on the keyboard screen.': 'Resminiz/GIF\'iniz şu an klavye ekranında.',
    'Showing now: screen {mode} - {what}': 'Şu an açık: {mode}. ekran - {what}',
    'your image/GIF': 'sizin resminiz/GIF\'iniz',
    'clock scene': 'saat sahnesi',

    # Separate screens (0.10.0)
    'SEPARATE SCREENS': 'AYRI EKRANLAR',
    'With Lavender Quest 0.10.0, screens 1-4 each show their own image or GIF and Fn + PgUp steps through them. Screen 0 is always the clock. All screens share 8 frames.':
        'Lavender Quest 0.10.0 ile 1-4. ekranların her biri kendi resmini veya GIF\'ini gösterir; Fn + PgUp aralarında gezer. 0. ekran her zaman saattir. Tüm ekranlar toplam 8 kareyi paylaşır.',
    'Screen {n}': 'Ekran {n}',
    'empty': 'boş',
    '{count} frames': '{count} kare',
    'Choose': 'Seç',
    'Clear': 'Temizle',
    'Show': 'Göster',
    'Frames used: {used} / {total}': 'Kullanılan kare: {used} / {total}',
    'Upload all screens': 'Tüm ekranları yükle',
    'Needs Lavender Quest 0.10.0 (experimental) from the Firmware page. On other builds screens 1-3 show the clock.':
        'Firmware sayfasından Lavender Quest 0.10.0 (deneysel) gerekir. Diğer sürümlerde 1-3. ekranlar saati gösterir.',
    'No frames left. Clear another screen first.': 'Boş kare kalmadı. Önce başka bir ekranı temizleyin.',
    'Screen {n} ready: {count} frames. Nothing has been sent yet.': '{n}. ekran hazır: {count} kare. Henüz hiçbir şey gönderilmedi.',
    'Choose an image for at least one screen.': 'En az bir ekran için resim seçin.',
    'Upload all four screens now?\n\nThis replaces every image on the keyboard, including a single image uploaded earlier. Keep USB connected until it finishes.':
        'Dört ekran şimdi yüklensin mi?\n\nBu, klavyedeki tüm resimlerin yerine geçer; daha önce tek başına yüklenen resim de dahil. Bitene kadar USB bağlı kalsın.',
    'All screens uploaded. Screen {n} is showing; use the Show buttons or Fn + PgUp to switch.':
        'Tüm ekranlar yüklendi. Şu an {n}. ekran açık; geçmek için Göster düğmelerini veya Fn + PgUp\'ı kullanın.',
    'screen {n} image/GIF': '{n}. ekranın resmi/GIF\'i',
    'Screen {n} is empty on the keyboard; it shows the clock. Upload screens first.': '{n}. ekran klavyede boş, saati gösteriyor. Önce ekranları yükleyin.',
    'Uploading screens': 'Ekranlar yükleniyor',
    'Experimental. The same screen as 0.9.2, plus screens 1-4 can each show their own image or GIF (Screen page). Built and emulator-tested in this fork; not yet reviewed by the original author.':
        'Deneysel. 0.9.2 ile aynı ekran; ek olarak 1-4. ekranların her biri kendi resmini veya GIF\'ini gösterebilir (Ekran sayfası). Bu fork\'ta derlendi ve emülatörde test edildi; orijinal geliştirici henüz incelemedi.',

    # Screen page on 0.10.0
    'No frames left': 'Boş kare kalmadı',
    'All 8 frames are in use. Share them out evenly between the screens so this one fits too? GIFs keep their timing but use fewer frames. Nothing is sent until you press Upload all screens.':
        '8 karenin hepsi kullanılıyor. Bu ekran da sığsın diye kareler ekranlara eşit paylaştırılsın mı? GIF\'ler zamanlamasını korur ama daha az kare kullanır. Tüm ekranları yükle\'ye basana kadar hiçbir şey gönderilmez.',
    'Frames shared out between the screens. Nothing has been sent yet; press Upload all screens.':
        'Kareler ekranlara paylaştırıldı. Henüz hiçbir şey gönderilmedi; Tüm ekranları yükle\'ye basın.',
    'The keyboard has 5 screens: 0 is the clock and 1-4 are your screens below. Fn + PgUp / PgDn steps through them; an empty screen shows the clock.':
        'Klavyede 5 ekran var: 0 saat, 1-4 aşağıdaki sizin ekranlarınız. Fn + PgUp / PgDn aralarında sırayla gezer; boş ekran saati gösterir.',
    'Choose a picture for each screen below, then press Upload all screens. The preview shows the screen that is on the keyboard now.':
        'Aşağıda her ekran için bir resim seçin, sonra Tüm ekranları yükle\'ye basın. Önizleme klavyede şu an açık olan ekranı gösterir.',

    # Background operations (shown as "<name>..." and "<name> complete.")
    '{operation} complete.': '{operation} tamamlandı.',
    '{operation} is still running. Please wait.': '{operation} hâlâ sürüyor. Lütfen bekleyin.',
    'Operation failed. Check the connection; details are in Advanced.': 'İşlem başarısız. Bağlantıyı kontrol edin; ayrıntılar Gelişmiş sayfasında.',
    'Finding X68': 'X68 aranıyor',
    'Reading keyboard settings': 'Klavye ayarları okunuyor',
    'Checking installed build': 'Yüklü sürüm kontrol ediliyor',
    'Saving lighting': 'Aydınlatma kaydediliyor',
    'Sending keymap draft': 'Tuş ataması taslağı gönderiliyor',
    'Saving macro': 'Makro kaydediliyor',
    'Reading battery': 'Pil okunuyor',
    'Installing firmware': 'Firmware yükleniyor',
    'Inspecting firmware file': 'Firmware dosyası inceleniyor',
    'Converting image': 'Resim dönüştürülüyor',
    'Uploading screen media': 'Ekran medyası yükleniyor',
    'Selecting screen': 'Ekran seçiliyor',
    'Syncing keyboard clock': 'Klavye saati eşitleniyor',
    'Restoring settings backup': 'Ayar yedeği geri yükleniyor',
    'Reading cached ADC snapshot': 'Önbellekteki ADC verisi okunuyor',
    'Settings loaded. Nothing is written until you press Send.': 'Ayarlar yüklendi. Gönder\'e basana kadar hiçbir şey yazılmaz.',
}

CATALOGS = {'tr': TR}


def t(text: str, lang: str | None = None) -> str:
    """Translate an English interface string; unknown text is returned unchanged."""
    return CATALOGS.get(lang or LANG, {}).get(text, text)


def upper(text: str, lang: str | None = None) -> str:
    """Upper-case with Turkish dotted/dotless i rules when Turkish is active."""
    if (lang or LANG) == 'tr':
        text = text.replace('i', 'İ').replace('ı', 'I')
    return text.upper()


def pixel_caps(text: str) -> str:
    """For the Press Start 2P headings: replace İ, which that font draws at lowercase height."""
    return text.replace('İ', 'I')


def system_language() -> str:
    """'tr' when the Windows display language (or the locale elsewhere) is Turkish."""
    try:
        if sys.platform == 'win32':
            import ctypes
            return 'tr' if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x1F else 'en'
        import locale
        return 'tr' if (locale.getlocale()[0] or '').lower().startswith('tr') else 'en'
    except Exception:
        return 'en'


def load(preferences: Path) -> str:
    """Pick the language from preferences.json, falling back to the system language."""
    global LANG
    try:
        chosen = json.loads(Path(preferences).read_text(encoding='utf-8')).get('language')
    except (OSError, ValueError, AttributeError):
        chosen = None
    LANG = chosen if chosen in LANGUAGES else system_language()
    return LANG
