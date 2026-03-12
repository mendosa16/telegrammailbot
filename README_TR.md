# Telegram kişisel stok botu

Bu proje, sadece senin kullanacağın basit bir Telegram stok botudur.

Komut mantığı:
- `/stok` → kalan kayıt sayısını gösterir
- `/liste` → ilk 20 kaydı gösterir
- `/ekle kayit_123` → stoğa yeni kayıt ekler
- `/ver 10` → stoktan 10 kayıt verir ve stoktan düşer

## 1) Gerekli şeyler

- Telegram hesabı
- BotFather üzerinden alınmış bot token
- Railway hesabı
- GitHub hesabı
- Bilgisayarında Python kurulu olması şart değil, çünkü Railway çalıştıracak

## 2) Dosya yapısı

- `bot.py` → ana bot kodu
- `requirements.txt` → Python paketleri
- `Procfile` → Railway başlatma komutu
- `.env.ornek` → ortam değişkeni örneği
- `data/stok.json` → stok kayıtları
- `data/islem_loglari.json` → işlem logları

## 3) Telegram bot oluşturma

1. Telegram'da `@BotFather` aç.
2. `/newbot` yaz.
3. Bot adı ver.
4. Bot kullanıcı adı ver. Sonu `bot` ile bitmeli.
5. Sana bir `BOT_TOKEN` verecek. Bunu kaydet.

Telegram botu BotFather üzerinden oluşturulur ve bot, backend sunucuna bağlanarak çalışır. Telegram'ın Bot API'si HTTP tabanlıdır. citeturn268029search2turn268029search5

## 4) Kendi chat id'ni öğrenme

En kolay yol:
1. Botunu başlat.
2. Telegram'da `userinfobot` benzeri bir kimlik botuna girip chat id öğren.
3. Ya da daha sonra kod içine geçici bir komut eklenebilir.

## 5) Railway'e yükleme

Railway, GitHub repo üzerinden Python servislerini deploy etmeyi destekler. Start command yapılandırması da Railway'de tanımlanabilir. citeturn268029search1turn268029search4

Adımlar:
1. Bu klasörü GitHub'a yükle.
2. Railway'de yeni proje oluştur.
3. `Deploy from GitHub Repo` seç.
4. Repo'nu seç.
5. Variables kısmına şunları gir:
   - `BOT_TOKEN`
   - `ADMIN_CHAT_ID`
6. Deploy et.

## 6) Railway değişkenleri

Örnek:

```env
BOT_TOKEN=123456:ABC-DEF
ADMIN_CHAT_ID=123456789
```

## 7) Stok ekleme

`data/stok.json` dosyasına kayıtları şu şekilde yaz:

```json
{
  "stok": [
    "kayit_001",
    "kayit_002",
    "kayit_003"
  ]
}
```

## 8) Bot komutları

- `/start`
- `/help`
- `/stok`
- `/liste`
- `/ekle kayit_123`
- `/ver 10`

## 9) Teknik not

Bu proje `python-telegram-bot` kütüphanesinin güncel 22.x serisine uygun `ApplicationBuilder` yapısını kullanır. Bu yapı, resmi dokümantasyonda anlatılan uygulama kurulum desenidir. citeturn268029search6turn268029search0turn268029search16

## 10) Önemli uyarı

Bu örnek proje nötr bir stok/kayıt botu mantığı içindir. İçeriği kullanırken ilgili platformların kurallarına ve yürürlükteki mevzuata uygun hareket etmelisin.
