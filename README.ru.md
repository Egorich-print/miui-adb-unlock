# miui-adb-unlock

**Включение тех настроек MIUI для разработчиков, которые стоковая MIUI 12 режет для adb — без аккаунта Xiaomi.**

[English](README.md) · [Русский](README.ru.md)

MIUI 12 убирает у adb-сессии целый набор возможностей: нельзя инжектить события
ввода, выдавать runtime-разрешения, писать в `Settings.Secure`, ставить системные
свойства, становиться device owner. Те две настройки, которые это вернули бы, —
*«Отладка по USB (Настройки безопасности)»* и *«Установка через USB»* — сами
закрыты проверкой вендора: нужна подписанная учётная запись Xiaomi и доступная
сеть.

Этот инструмент включает их на устройстве, которым вы владеете, через тот
единственный канал, который MIUI не закрывает: **accessibility-действия**. Он
управляет штатным harness'ом `uiautomator` на телефоне и нажимает нужные
переключатели за вас — без root и без модификации системы.

Замерено на Redmi Note 5 / MIUI 12: клик доходит до собственной верификации MIUI,
и вендор отвечает **«Sign in with your Mi Account»** — на этой сборке *обе* опции
требуют входа в аккаунт Xiaomi. С залогиненным аккаунтом инструмент проходит весь
сценарий без участия человека: обе настройки включаются, а заблокированные
возможности adb (`pm grant`, `input tap`, `settings put secure`) возвращаются.

```
$ miui-adb-unlock doctor
[     ok] device — Redmi Note 5 (whyred) · Android 9 · MIUI V12 V12.0.2.0.PEIMIXM
[blocked] settings put secure/global — MIUI блокирует WRITE_SECURE_SETTINGS для uid 2000 …
[blocked] pm grant — MIUI блокирует GRANT_RUNTIME_PERMISSIONS для uid 2000
[blocked] input tap — сервер событие принимает, но MIUI его теряет
[blocked] dpm set-device-owner — MANAGE_DEVICE_ADMINS закрыт для uid 2000
[blocked] setprop persist.* — SELinux запрещает запись свойств из shell-домена
[    off] security-debugging option — persist.security.adbinput=<unset>
[    off] install-over-usb option — persist.security.adbinstall=<unset>
[     no] device internet — MIUI проверяет устройство через srv.sec.miui.com …
[     ok] accessibility channel — uiautomator harness: dump
```

---

## Почему очевидные способы не работают

MIUI 12 правит проверки в `system_server`, поэтому shell-идентичность теряет
возможности, которые пакет shell по-прежнему *объявляет*:

| Операция | Результат на MIUI 12 |
|---|---|
| `settings put secure/global …` | `SecurityException: … WRITE_SECURE_SETTINGS` |
| `pm grant`, `adb install -g` | `SecurityException` (`GRANT_RUNTIME_PERMISSIONS`) |
| `dpm set-device-owner` | `SecurityException` (`MANAGE_DEVICE_ADMINS`) |
| `input tap`, `input keyevent` | сервер принимает, дальше событие теряется фильтром MIUI |
| `setprop persist.*` | запрещено SELinux (даже `persist.sys.*`) |
| `/dev/input/event*` | `Permission denied` (группа `input`) |
| `/dev/uhid` | в ядре нет HID-драйвера |
| instrumentation с `targetPackage="android"` | отбрасывается PMS (цель должна быть подписана тем же ключом) |
| подпись платформенным ключом | собственный ключ Xiaomi (`release-keys`, `CN=MIUI`), а не публичный AOSP test-key |
| `adb root`, `su` | отказ (production build) |

Подробности с точными путями в коде MIUI — в
[`docs/research/miui-security-gates.md`](docs/research/miui-security-gates.md).

## Что это за настройки

| Настройка в UI | Где лежит состояние | Кто может записать |
|---|---|---|
| Отладка по USB (Настройки безопасности) | системное свойство `persist.security.adbinput` | только uid 1000 (`android.uid.system`) |
| Установка через USB | преференция MIUI `security_adb_install_enable` + зеркало `persist.security.adbinstall` | uid 1000, через provider с `signature\|privileged` |

Штатный путь MIUI: `com.android.settings.development.c` → `AdbInputApplyActivity`
→ `AdbInstallVerifyActivity` → HTTPS-запрос к `srv.sec.miui.com/data/adb`.

Два гейта замерены на устройстве:

* **без сети** — запрос не уходит, MIUI показывает тост
  «Подключитесь к сети и повторите попытку»;
* **с сетью** — запрос уходит, и сервер отклоняет его ответом
  «Sign in with your Mi Account»: в payload пустой `xiaomi_id` (аккаунт не задан).

Если аккаунт Xiaomi залогинен, `AdbInputApplyActivity` уходит по другой ветке и
показывает локальный диалог, который ставит свойство без обращения к серверу — именно
этим путём и идёт инструмент. Диалог многошаговый, его положительная кнопка —
`com.miui.securitycenter:id/accept`, и до срабатывания у неё идёт обратный отсчёт,
поэтому сценарий кликает её, пока настройка действительно не включится.

## Как работает инструмент

MIUI блокирует `InputManager.injectInputEvent()` для shell, но **не** блокирует
accessibility-действия. Штатный harness `uiautomator` на устройстве работает,
поэтому инструмент:

1. заливает небольшой Java-драйвер в `/data/local/tmp`;
2. просит его найти строку нужной настройки и выполнить `performAction(ACTION_CLICK)`;
3. тем же способом подтверждает собственный диалог верификации MIUI;
4. проверяет результат (`getprop persist.security.adbinput`).

Accessibility-действия отправляет accessibility-сервис, а не конвейер ввода,
поэтому фильтр MIUI их не видит. Побочный плюс: инструмент работает и на
устройствах с битым тачскрином, где нажатия по координатам ненадёжны.

Драйвер additionally обходит две особенности MIUI:

* список Settings никогда не приходит в состояние *idle*, поэтому
  `getRootInActiveWindow()` отваливается по таймауту — драйвер перечисляет
  accessibility-окна и сокращает ожидание idle;
* зависший процесс harness держит сервис `UiAutomation` занятым, поэтому перед
  каждым запуском остатки убиваются.

## Требования

* `adb`, устройство подключено, **отладка по USB включена** (это MIUI не блокирует).
* Устройство должно достучаться до `srv.sec.miui.com` — иначе верификация MIUI не пройдёт.
* Python 3.9+ на хосте. Сторонних Python-пакетов нет.
* Драйвер поставляется собранным; для пересборки нужен Android SDK
  (см. [`scripts/build-harness.sh`](scripts/build-harness.sh)).

## Установка

```shell
git clone https://github.com/Egorich-print/miui-adb-unlock
cd miui-adb-unlock
python3 -m pip install -e .        # либо: python3 -m miui_adb_unlock
```

Без установки тоже работает:

```shell
python3 -m miui_adb_unlock doctor
```

## Использование

```shell
# 1. Что сейчас закрыто на устройстве?
miui-adb-unlock doctor

# 2. Включить «Отладка по USB (Настройки безопасности)».
#    Нужен интернет на устройстве; аккаунт Xiaomi не нужен.
miui-adb-unlock unlock security-debugging

# 3. Убедиться, что возможности adb вернулись.
miui-adb-unlock verify

# 4. «Установка через USB» — тут MIUI требует аккаунт Xiaomi.
miui-adb-unlock unlock install-over-usb

# 5. Вывести устройство в сеть (если оно ещё не онлайн).
MIUI_WIFI_PASSWORD='…' miui-adb-unlock wifi 'MyNetwork'

# 6. Посмотреть accessibility-дерево текущего экрана.
miui-adb-unlock dump
```

При нескольких подключённых устройствах — `--serial <serial>`, `-v` покажет
трассировки драйвера.

### Пароли

Пароли не сохраняются и не логируются. Команда `wifi` берёт пароль из переменной
окружения (по умолчанию `MIUI_WIFI_PASSWORD`) и передаёт его устройству одним
accessibility-действием. Держите его вне истории команд:

```shell
read -rs MIUI_WIFI_PASSWORD && export MIUI_WIFI_PASSWORD
miui-adb-unlock wifi 'Ultra_Wi-Fi_2.0'
unset MIUI_WIFI_PASSWORD
```

## Что меняется на устройстве

* запрошенная настройка (преференция MIUI и/или системное свойство);
* `/data/local/tmp/miui-a11y.jar` и `/data/local/tmp/miui_a11y_cmd.txt` (harness);
* больше ничего. Приложения не ставятся, системный раздел не трогается,
  учётные записи не создаются.

## Карта документации

| Нужно | Файл |
|---|---|
| Текущее состояние | [STATUS.md](STATUS.md) |
| Что делать дальше | [docs/STATE.md](docs/STATE.md) |
| Архитектура | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Решения | [docs/adr/](docs/adr/) |
| Реверс гейтов MIUI | [docs/research/miui-security-gates.md](docs/research/miui-security-gates.md) |
| Правила раскладки по каталогам | [docs/REPOSITORY_GUIDE.md](docs/REPOSITORY_GUIDE.md) |
| Правила для агентов | [AGENTS.md](AGENTS.md) |
| История изменений | [CHANGELOG.md](CHANGELOG.md) |

## Правовые и safety-заметки

Применяйте только к устройствам, которыми владеете или администрируете с
разрешения. Инструмент включает опции, которые вендор намеренно ограничил;
часть из них ослабляет защиту устройства от вредоносного компьютера. Он не
обходит модель безопасности Android, не требует root и не трогает системный
раздел.

## Лицензия

MIT — см. [LICENSE](LICENSE).
