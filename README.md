# Hosts & DNS Manager

Упрощённый аналог вкладки «редактор hosts» из проекта zapret: графическое приложение (PyQt5,
Windows), которое позволяет:

- **Сайты (hosts)** — включать/выключать сервисы (сгруппированы по категориям:
  «Напрямую из hosts», «ИИ», «Остальные», «Дополнительно») и выбирать для каждого свой
  вариант DNS. Все записи пишутся в управляемый блок файла hosts (остальной файл не трогается).
- **DNS-серверы** — применять готовые варианты DNS (Cloudflare, Google, Quad9, AdGuard, Comss и др.)
  на сетевой адаптер, сбрасывать на авто (DHCP), чистить DNS-кэш.
- **Каталог** — редактировать сервисы, домены и IP по вариантам; импортировать готовый
  каталог (одним JSON или папкой формата оригинала), или **автоматически заполнить IP
  через DoH-резолвер**.

## Готовый каталог (68 сервисов, реальные IP)

Стартовый `data/catalog.json` уже **заполнен реальными адресами**, восстановленными из
выгрузок файла hosts оригинального приложения по всем 8 вариантам DNS:

| Категория | Сервисы |
|-----------|---------|
| Напрямую из hosts (10) | Discord, YouTube, GitHub, WhatsApp, x.com/Twitter, Rutor, ntc.party, Discord-голос (Flowseal), Supercell, Instagram |
| ИИ (9) | ChatGPT & Sora, Gemini, Claude, Microsoft (Copilot/Designer/Xbox), Grok, Manus, Meta AI, Trae.ai, Windsurf |
| Остальные (48) | TikTok, Spotify, Twitch, Notion, DeepL, Canva, ElevenLabs, JetBrains, AMD, Autodesk, Badoo, Broadcom, Chess, Deezer, Dell, Dyson, Elgato, Fitbit, FMHY, Framer, Guidedhacking, Guilded, Imgur, Intel, Linear.app, Make, Naukri, Nvidia, Oracle, Patreon, Posthog, Pump.fun, Qwant, Reve, SketchUp, Strava, Tableau, Tailscale, TeamViewer, Tria.ge, Truth Social, Tuta, Weather Underground, Weather.com, Web Archive, WorkOS, Xerox, Остальное |
| Дополнительно (1) | Блокировка Adobe (домены активации → 127.0.0.1) |

**8 вариантов DNS** (профилей), между которыми можно переключаться по каждому сервису:
XBOX DNS, XBOX DNS (old), Comss DNS, Malw DNS, Malw DNS v2, play2go.cloud DNS, Zapret DNS, Fin DNS.

- В варианте **XBOX DNS** у каждого домена свой реальный IP.
- Остальные варианты — это прокси-DNS: все проксируемые домены указывают на один
  шлюзовой IP провайдера (напр. Comss → `95.182.120.241`, Malw → `185.246.223.127`,
  play2go → `144.31.14.104`, Zapret → `72.56.93.144`, Fin → `31.77.140.129`).
- Сервисы категории «Напрямую из hosts» имеют фиксированные IP (один и тот же во всех
  вариантах) и работают простым переключателем вкл/выкл.

Если какие-то адреса со временем устареют — их можно обновить вручную во вкладке «Каталог»
или дозаполнить через встроенный DoH-резолвер (см. ниже).

## Автозаполнение IP через DoH

В открытом репозитории zapret сам список IP лежит в закрытой части (папка `private_zapretgui`,
её нет в исходниках). Чтобы не зависеть от него, во вкладке «Каталог» есть встроенный
резолвер доменов через DNS-over-HTTPS (только стандартная библиотека Python):

1. Выберите **DoH-резолвер** (Cloudflare / Google / Quad9 / AdGuard).
2. Выберите **вариант** (колонку), куда записать полученные IP.
3. Нажмите «Заполнить IP: сервис» (только выделенный) или «Заполнить IP: все».
4. При желании включите **IPv6**.
5. Нажмите «Сохранить каталог», чтобы записать результат в `data/catalog.json`.

Резолвинг также доступен прямо в редакторе отдельного сервиса (кнопка «Заполнить IP через DoH»).

> Примечание: DoH возвращает обычные (не проксирующие) IP доменов. Это подходит для
> обхода DNS-блокировок (когда провайдер подменяет DNS-ответ), но не заменяет
> специальные «обходные» IP из закрытого каталога оригинала, если там используются
> нестандартные адреса.

## Запуск

```bat
python -m pip install -r requirements.txt
python main.py
```

Для записи в hosts и смены DNS нужны **права администратора**. Приложение попытается
перезапуститься с запросом UAC автоматически.

## Сборка EXE

```bat
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --onefile --uac-admin ^
  --add-data "data;data" --name HostsDnsManager main.py
```

## Структура

```
main.py                 — точка входа
app/admin.py            — проверка/запрос прав админа (UAC)
app/providers.py        — список DNS-провайдеров
app/catalog.py          — модель каталога (сервисы/домены/варианты)
app/resolver.py         — DoH-резолвер (домен → IP)
app/hosts_manager.py    — чтение/запись hosts, бэкапы, управляемый блок
app/dns_manager.py      — смена DNS на адаптерах (netsh) + flushdns
app/gui/                — графический интерфейс (вкладки)
data/catalog.json       — стартовый каталог
```
