# BDM UYAP GİRİŞ

Windows bilgisayarınızda takılı olan **akıllı kart (e-imza)** ile UYAP portalına
**otomatik giriş** yapan masaüstü programı. İsteğe bağlı olarak giriş sonrası
belirli işlemleri (dosya sorgulama, sayfaya gitme vb.) de otomatikleştirebilir.

**Öne çıkan özellikler:**
- E-imza (akıllı kart) veya mobil imza ile otomatik giriş.
- **Akıllı fallback**: takılı kart bulunamazsa ya da e-imza ile 3 deneme başarısız
  olursa otomatik olarak **mobil imza** ile giriş denenir.
- **UYAP izleme (auto-watch)**: UYAP düşerse bekler, geri gelince; oturum kapanırsa
  yeniden otomatik giriş yapar.
- **Masaüstü bildirimleri**: giriş yapıldığında / UYAP düştüğünde uyarı.
- **Canlı renkli durum göstergesi**: AYAKTA / DÜŞÜK / GİRİŞ YAPILDI / MESAİ DIŞI.
- **Mesai zamanlaması**: yalnızca belirlenen saat aralığında izleme.

> ⚠️ **Önemli (Haziran 2026):** 1 Haziran 2026 itibarıyla UYAP'ta eski **ArkSigner**
> kaldırıldı. E-imza ile giriş ve belge imzalama için artık Adalet Bakanlığı'nın
> **Adalet E-İmza Uygulaması** zorunludur. Bu program da o uygulamanın arka planda
> çalışıyor olmasını varsayar (tarayıcı ile kart arasındaki köprüyü o kurar).

---

## 1. Bu program ne yapar, ne yapmaz?

**Yapar:**
- Tarayıcıyı otomatik açar, UYAP portalına gider.
- "E-İmza ile Giriş" seçeneğine otomatik tıklar (veya mobil imza akışını başlatır).
- Açılan **PIN penceresine** PIN'inizi otomatik yazıp onaylar (izin verirseniz).
- Giriş tamamlanınca `config.json` içinde tanımladığınız işlemleri sırayla yapar.

**Yapmaz / yapamaz:**
- Kartın yerine imza atmaz; imzalamayı **Adalet E-İmza uygulaması + kartınız** yapar.
- Donanımsal (secure PIN pad'li) okuyucularda PIN'i otomatik yazamaz → PIN'i cihazdan
  elle girersiniz. Programın geri kalanı yine otomatik ilerler.

---

## 2. Ön gereksinimler (Windows)

1. **Akıllı kart okuyucu sürücüsü** ve **kart sürücüsü** (ör. AKİS) kurulu olmalı,
   kart takılı olmalı.
2. **Adalet E-İmza Uygulaması** kurulu ve **sistem tepsisinde çalışır** durumda olmalı:
   https://bedesten.adalet.gov.tr/imza/
3. (Belge imzalayacaksanız) Güncel **UYAP Doküman Editörü**:
   https://www.uyap.gov.tr/Uyap-Editor
4. **Google Chrome** veya **Microsoft Edge** kurulu olmalı.
5. **Python 3.10+**: https://www.python.org/downloads/ (kurulumda "Add to PATH" işaretleyin).

---

## 3. Kurulum

Komut istemini (CMD) proje klasöründe açın:

```bat
cd uyap-auto-login
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 4. Çalıştırma

**Arayüz (önerilen):**
```bat
python main.py
```

**Terminalden:**
```bat
python main.py --cli
```

İlk çalıştırmada `config.example.json` içeriğinden otomatik olarak `config.json`
oluşturulur. Ayarları arayüzden ya da doğrudan `config.json` dosyasından
değiştirebilirsiniz.

---

## 5. Ayarlar (config.json)

| Anahtar | Açıklama |
|---|---|
| `portal_url` | Giriş yapılacak UYAP adresi (varsayılan: **Avukat Portalı** `https://avukat.uyap.gov.tr/giris`). |
| `login_method` | `eimza` veya `mobil`. |
| `browser` | `chrome` veya `edge`. |
| `use_existing_profile` | `true` ise mevcut Chrome profilinizle açılır (oturumlar korunur). |
| `chrome_profile_dir` | Örn. `C:\Users\ADINIZ\AppData\Local\Google\Chrome\User Data`. |
| `eimza_button_selectors` | "E-İmza ile Giriş" butonu için denenecek CSS/XPath listesi. |
| `auto_type_pin` | PIN'i otomatik yaz (`true`) ya da elle gir (`false`). |
| `pin_window_titles` | PIN penceresinin başlığında aranacak kelimeler. |
| `success_url_contains` / `success_element_selector` | Giriş başarısını doğrulama ölçütü. |
| `post_login_tasks` | Giriş sonrası otomatik görevler (aşağıya bakın). |

### Avukat Portalı için hazır seçiciler
Avukat Portalı (React + DevExtreme SPA) incelendi; e-imza butonunun sabit `id`'si
yoktur, bu yüzden **metin tabanlı** seçici kullanılır. `config.example.json` içinde
bunlar hazır gelir:
- E-İmza butonu metni: **"Adalet E-imza İle Giriş"** (sağ üst menü).
- M-imza: sağ üstteki **"E-Devlet İle Giriş"** açılır menüsü altında.

### Başka bir portala geçerseniz selector güncelleme
UYAP arayüzü zamanla değişebilir veya farklı portal (Vatandaş/Kurum) kullanabilirsiniz.
Buton bulunamazsa:
1. Tarayıcıda giriş sayfasını açın, e-imza butonuna sağ tık → **İncele (Inspect)**.
2. Butonun metnini/`class` bilgisini alıp `eimza_button_selectors` listesine ekleyin
   (metinle eşleşme için XPath `//div[contains(@class,'dx-button-content') and contains(.,'E-imza')]`).

### Giriş sonrası otomatik görev örneği
```json
"post_login_tasks": [
  { "action": "goto",  "url": "https://vatandas.uyap.gov.tr/main/vatandas/dosyaSorgu.jsp" },
  { "action": "type",  "selector": "input#dosyaNo", "text": "2025/123" },
  { "action": "click", "selector": "button#sorgula" },
  { "action": "wait",  "seconds": 2 }
]
```
Desteklenen `action` değerleri: `goto`, `click`, `type`, `wait`.

---

## 6. UYAP'ı izle ve otomatik giriş yap (auto-watch)

Arayüzdeki **"UYAP'ı izle ve düşük/oturum kapandığında otomatik giriş yap"**
kutusunu işaretleyip **Giriş Yap**'a basarsanız program tek seferlik giriş yerine
**sürekli izleme** moduna geçer:

- UYAP **düşükse/erişilemiyorsa**: bekler, belirli aralıklarla tekrar dener; site
  **geri gelince kendiliğinden giriş yapar**.
- Oturumunuz **zaman aşımına uğrar / kapanırsa** (sayfa `/giris`'e dönerse):
  otomatik olarak **yeniden giriş** yapar.
- Tarayıcı kapanırsa yeniden başlatıp giriş yapar.
- **Durdur** butonuyla izleme döngüsü sonlandırılır (tarayıcı açık kalır).

İlgili `config.json` ayarları:

| Anahtar | Açıklama |
|---|---|
| `auto_watch` | İzleme modunu varsayılan açık başlatır. |
| `watch_interval_seconds` | Oturum/erişim kontrol aralığı (sn, varsayılan 30). |
| `site_down_retry_seconds` | UYAP düşükken bekleme süresi (sn, varsayılan 60). |
| `max_login_retries` | Arka arkaya giriş deneme sınırı (`0` = sınırsız). |
| `notifications` | Masaüstü bildirimleri (giriş yapıldı / UYAP düştü). |
| `fallback_to_mobil` | E-imza olmazsa mobil imzaya geç (`true`/`false`). |
| `eimza_max_attempts` | Mobil imzaya geçmeden önceki e-imza deneme sayısı (varsayılan 3). |
| `card_detection` | Takılı kartı PKCS#11 ile tespit et; yoksa mobil imzaya geç. |
| `pkcs11_lib` | (Opsiyonel) `akisp11.dll` tam yolu. Boşsa yaygın yollar denenir. |
| `schedule.enabled` | Mesai saati zamanlamasını aç/kapat. |
| `schedule.start` / `schedule.end` | İzleme saat aralığı (ör. `09:00` – `18:00`). |
| `schedule.days` | Günler (1=Pzt … 7=Paz). Örn. hafta içi `[1,2,3,4,5]`. |

### Otomatik fallback (kart yoksa / e-imza başarısızsa mobil imza)
`login_method: "eimza"` iken:
1. Program önce **takılı e-imza kartını** kontrol eder (`card_detection`).
   - Kart yoksa ve `fallback_to_mobil: true` ise doğrudan **mobil imza** denenir.
2. Kart varsa e-imza ile giriş denenir. **`eimza_max_attempts` (3) kez** başarısız
   olursa otomatik olarak **mobil imza** ile giriş denenir.

> Kart tespiti için `PyKCS11` kurulu ve `akisp11.dll` erişilebilir olmalıdır. Değilse
> tespit "bilinmiyor" sayılır ve doğrudan e-imza denenir (3 denemeden sonra yine mobile
> geçilir).

### Mobil imza bilgileri (e-Devlet)
Mobil imza seçilince (veya fallback olunca) program **E-Devlet İle Giriş → Mobil İmza
İle Giriş** yolunu izleyip **e-Devlet Kapısı** formunu otomatik doldurur. Bunun için
`config.json > mobil_imza` altını doldurun:

| Alan | Açıklama |
|---|---|
| `tc_kimlik` | T.C. Kimlik No. |
| `phone` | 10 haneli GSM (ör. `5XXXXXXXXX`). |
| `operator` | `turkcell`, `turktelekom` veya `vodafone`. |

Bilgileri girdikten sonra program **Devam Et**'e basar; ardından **telefonunuza gelen
mobil imza onayını** vermeniz gerekir (bu adım cihazınızdan manueldir). Alanları boş
bırakırsanız e-Devlet ekranı açılır ve bilgileri elle girersiniz.

### Giriş sonrası görev şablonları
`task_examples.json` içinde hazır örnekler var (dosya sorgu, iş listesi, gelen evrak,
derdest dosyalar, arama, **evrak gönder + imzala**). İstediğiniz bloğu kopyalayıp
`config.json > post_login_tasks` dizisine yapıştırın.

Desteklenen `action` türleri:
| action | Alanlar | Açıklama |
|---|---|---|
| `goto` | `url` | Adrese git. |
| `click` | `selector` | Öğeye tıkla. |
| `type` | `selector`, `text` | Alana yaz. |
| `select` | `selector`, `text` | Açılır listeden metne göre seç. |
| `upload` | `selector`, `path` | Dosya yükle (`input[type=file]`). |
| `sign` | `selector`, `wait_after` | İmzala butonuna tıkla; Adalet E-İmza PIN penceresi açılınca PIN otomatik girilir. |
| `screenshot` | `path` | Ekran görüntüsü kaydet. |
| `wait` | `seconds` | Bekle. |

> **Otomatik imzalama** için `sign` aksiyonu kullanılır. İmzalama sırasında açılan
> Adalet E-İmza PIN penceresini, PIN'i "otomatik gir" seçiliyse program doldurur;
> secure PIN pad'li okuyucularda PIN'i cihazdan elle girmeniz gerekir.

### İzleme raporunu dışa aktarma
Arayüzdeki **Rapor** butonuyla o ana kadarki tüm durum olaylarını (zaman, durum,
mesaj) **CSV veya TXT** olarak kaydedebilirsiniz. Ayrıca tüm loglar `uyap_login.log`
dosyasına da yazılır.

### Zamanlı görevler (belirli saatte otomatik dosya sorgu/rapor)

**Kolay yol:** Ana penceredeki **"Görevler"** butonuna tıklayın. Açılan pencerede
görev ekleyip silebilir; ad, saat, günler, rapor üretimi ve adımları (goto / wait /
click / type / screenshot) formdan düzenleyebilirsiniz. "Kaydet ve Kapat" ile
`config.json`'a otomatik yazılır — dosyayı elle düzenlemeye gerek yoktur.

**Manuel yol:** İzleme modu (auto-watch) açıkken, `config.json > scheduled_tasks` içinde tanımladığınız
görevler **belirtilen gün ve saatte otomatik** çalışır. Her görev:

| Alan | Açıklama |
|---|---|
| `name` | Görev adı (rapor/loglarda görünür). |
| `time` | Çalışma saati `HH:MM` (ör. `09:00`). |
| `days` | Günler (1=Pzt … 7=Paz). |
| `tasks` | Çalıştırılacak aksiyonlar (goto/click/type/select/upload/sign/screenshot/wait). |
| `export_report` | `true` ise o ana kadarki izleme olaylarından rapor üretir. |
| `report_path` | Rapor dosyası (`.csv`/`.txt`) veya klasör (dosya adı otomatik). |

Her görev **günde bir kez** çalışır (saat geçtiğinde ve o gün henüz çalışmadıysa).
Hazır örnekler için `task_examples.json > ornek_7_zamanli_gorevler`.

> Not: Zamanlı görevler yalnızca **izleme modu** çalışırken tetiklenir. Bilgisayar
> açılışında otomatik başlaması için bkz. Bölüm 9 (Windows başlangıcında çalıştırma).




> Not: Otomatik yeniden giriş için PIN gerekir. İzleme modunda kesintisiz çalışması
> için PIN'i "otomatik gir" + "güvenli sakla" ile kaydetmeniz gerekir; aksi halde her
> yeniden girişte PIN'i elle girmeniz istenir.

---

## 7. Çoklu hesap (profiller) ve sistem tepsisi

### Çoklu hesap / profil
Birden fazla e-imza veya kullanıcı için ayrı **profiller** tutabilirsiniz. Her profil
kendi portal adresini, giriş yöntemini, tarayıcısını, mobil imza bilgilerini ve
(güvenli sakladıysanız) kendi PIN'ini saklar.

- Arayüzün üstündeki **Profil** açılır listesinden hesap seçin.
- **Yeni** ile mevcut ayarları kopyalayarak yeni profil oluşturun.
- **Sil** ile profili (ve o profile ait kayıtlı PIN'i) kaldırın.
- **Kaydet** aktif profili ve genel ayarları `config.json`'a yazar.

`config.json` yapısı: `profiles` (isim → ayarlar) ve `active_profile`. Genel ayarlar
(izleme, bildirim, mesai, kart tespiti, timeouts) tüm profiller için ortaktır.

### Sistem tepsisi (tray)
Program `pystray` ile **sistem tepsisinde** çalışır:
- Pencereyi kapatınca (X) uygulama kapanmaz, **tepside çalışmaya devam eder**
  (`minimize_to_tray: true`).
- Tepsi simgesine sağ tık: **Göster / İzlemeyi Başlat / Durdur / Çıkış**.
- Simge rengi anlık durumu yansıtır (yeşil=giriş yapıldı, kırmızı=düşük, turuncu=giriş
  yapılıyor, gri=mesai dışı).

> `pystray`/`Pillow` kurulu değilse tepsi devre dışı kalır ve pencere kapatınca program
> normal şekilde kapanır.

---

## 8. PIN güvenliği

- PIN'i "güvenli sakla" seçeneğiyle işaretlerseniz, PIN düz metin olarak **dosyaya
  yazılmaz**; Windows Kimlik Bilgileri Kasası (Credential Manager) üzerinden `keyring`
  ile **profil bazında** saklanır.
- İşaretlemezseniz PIN yalnızca o oturum için bellekte tutulur.
- En güvenli yöntem: `auto_type_pin: false` bırakıp PIN'i her seferinde elle girmek.

---

## 9. Windows başlangıcında otomatik çalıştırma (izleme modu)

Bilgisayar her açıldığında programın **gizli (penceresiz)** olarak izleme modunda
başlamasını isterseniz:

1. Önce arayüzde PIN'i **"otomatik gir" + "güvenli sakla"** ile bir kez kaydedin
   (izleme modu PIN'i Windows Kimlik Kasası'ndan okur).
2. Proje klasöründeki **`install_startup.bat`** dosyasına çift tıklayın
   (gerekirse "Yönetici olarak çalıştır").
3. Artık her oturum açılışında `run_watch.bat` → `python main.py --watch` gizli çalışır.

Kaldırmak için **`uninstall_startup.bat`**'ı çalıştırın.

Manuel arayüzsüz çalıştırma: `python main.py --watch`

---

## 10. Tek tıkla .exe oluşturma (opsiyonel)

### Yöntem A — Tam otomatik (önerilen, hiçbir kurulum gerekmez)

`make_exe_oneclick.bat` dosyasına **çift tıklayın**. Script:
1. Python kurulu değilse otomatik indirip sessizce kurar
2. Tüm paketleri yükler
3. `dist\BDM-UYAP-GIRIS.exe` dosyasını oluşturur ve klasörü açar

Oluşan exe'yi `config.json` ile birlikte istediğiniz bilgisayara kopyalayabilirsiniz —
o bilgisayarda Python gerekmez.

Masaüstü kısayolu otomatik oluşturulur; sonradan tekrar oluşturmak isterseniz
`create_shortcut.bat` dosyasına çift tıklayın.

> **Not:** Windows Defender/SmartScreen yeni oluşturulan exe'ler için uyarı verebilir.
> "Ek bilgi → Yine de çalıştır" diyerek geçebilirsiniz; dosya sizin bilgisayarınızda
> derlendiği için güvenlidir.

### Yöntem B — Python zaten kuruluysa

```bat
pip install pyinstaller
build_exe.bat
```
Oluşan `dist\BDM-UYAP-GIRIS.exe` dosyasını çalıştırabilirsiniz. `config.json`'ı exe ile
aynı klasöre koyun.

---

## 11. Sık karşılaşılan sorunlar

| Sorun | Çözüm |
|---|---|
| E-imza ekranı gelmiyor | Adalet E-İmza tepsi uygulaması çalışıyor mu? Tarayıcı önbelleğini temizleyin (Ctrl+Shift+Delete), `localhost` erişimine izin verin. |
| "Buton bulunamadı" | `eimza_button_selectors` değerini bölüm 5'teki gibi güncelleyin. |
| PIN otomatik girilmiyor | Okuyucunuz secure PIN pad olabilir; PIN'i cihazdan elle girin. |
| Chrome sürüm hatası | Selenium 4.20+ sürücüyü otomatik indirir; Chrome'u güncelleyin. |
| Kart okunmuyor | Kart sürücüsü (AKİS) ve okuyucu sürücüsü kurulu mu, kart takılı mı? |

---

## 12. Yasal / etik not

Bu araç **yalnızca kendi e-imzanızla, kendi UYAP erişiminiz için** tasarlanmıştır.
E-imza kişiye özeldir ve hukuki bağlayıcılığı vardır; PIN'inizi ve kartınızı
başkalarıyla paylaşmayın. Programı yalnızca yetkili olduğunuz hesap ve işlemler
için kullanın.
