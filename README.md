# Paper Phone

今日必要な情報だけを紙に刷り、デジタルから離れるための冊子を作る CLI です。
連絡先・予定・タスク・天気・地図・写真・メモ・紙アプリを A4 横向き 1〜2 枚の
PDF にまとめ、両面印刷して 8 枠の冊子に折ります。

画面はなく、項目の選択は `config.toml` に一度書きます。
朝の cron / systemd タイマーから無人で実行できるよう、認証は GNOME の
ログインキーリングに任せ、実行時に問い合わせを出しません。

## できること

- `paperphone` を実行すると、指定タイムゾーンの「今日」の PDF を 1 つ作る
- GNOME Online Accounts のカレンダー・連絡先と、自分で登録した CalDAV /
  CardDAV / VTODO を同じ経路で読む
- 天気は Open-Meteo、地図は OpenStreetMap のタイルと徒歩経路サービスを使う
- ネットワークや一部の source が失敗しても、残りの内容で必ず PDF を書く
- `doctor` で依存・キーリング・フォント・設定・出力先を検査する

## 必要なもの

- Python 3.12 以上
- GNOME デスクトップと Evolution Data Server（`ECal` / `EBook` /
  `EDataServer` / `ICalGLib` の typelib）
- libsecret とログインキーリング（独自 DAV を使う場合）
- Pango / fontconfig / HarfBuzz / Cairo
- 和文フォント（Noto Sans CJK JP など。同梱はしません）

Debian / Ubuntu:

```sh
sudo apt install python3-venv python3-gi gir1.2-eds-3.0 \
  libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 \
  fonts-noto-cjk gnome-keyring
```

Fedora:

```sh
sudo dnf install python3-pip python3-gobject evolution-data-server \
  pango harfbuzz fontconfig google-noto-sans-cjk-fonts gnome-keyring
```

Arch:

```sh
sudo pacman -S python python-gobject evolution-data-server \
  pango harfbuzz fontconfig noto-fonts-cjk gnome-keyring
```

## インストール

GitHub Releases の tarball を使う場合:

```sh
curl -LO https://github.com/google/paper-phone/releases/latest/download/paperphone.tar.gz
tar xzf paperphone.tar.gz
cd paperphone
./install.sh
```

リポジトリから直接:

```sh
git clone https://github.com/google/paper-phone.git
cd paper-phone
./install.sh
```

`install.sh` は `~/.local/share/paperphone/venv` を作り、`~/.local/bin/paperphone`
を張ります。`~/.local/bin` が `PATH` に入っていることを確認してください。
`PREFIX` と `PAPERPHONE_VENV` で置き場所を変えられます。システム依存の
インストールは行いません。

インストール後:

```sh
paperphone doctor
```

## 設定

既定は `$XDG_CONFIG_HOME/paperphone/config.toml`、無ければ
`~/.config/paperphone/config.toml` です。`--config PATH` で差し替えられます。

```toml
[booklet]
name = "Aki"
timezone = "Asia/Tokyo"

[panels]
contacts = true
calendar = true
tasks = true
weather = true
photo = true
notes = true
paper_app = true
map = true

[sources]
calendars = ["paperphone-...."]
contacts = ["contact-uid-1", "contact-uid-2"]
tasks = ["paperphone-...."]

[weather]
latitude = 35.6812
longitude = 139.7671
label = "Tokyo"

[maps]
tile_url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
router_url = "https://valhalla1.openstreetmap.de/route"
from = { latitude = 35.68, longitude = 139.76, label = "Home", address = ["1-1 Chiyoda", "Tokyo"] }
to = { latitude = 35.69, longitude = 139.70, label = "Station", address = ["2-2 Chuo", "Tokyo"] }

[photo]
path = "/home/aki/photo.jpg"

[paper_app]
name = "sudoku"
```

- `[panels]` に無い項目は無効です。空にすると表紙と 7 つの空き枠だけになります。
- `[sources].contacts` は最大 7 件です。連絡先の UID を書きます。
- `[sources].calendars` と `[sources].tasks` は source の UID を書きます。
- 天気・地図を有効にした場合、緯度経度（地図は `from` と `to`）が必須です。
- 紙アプリは `conversion_charts` `knots` `italian_phrasebook` `sign_language`
  `multiplication_table` `recipe` `pigeon_origami` `sudoku` `maze`
  `word_of_the_day` `anagram` `riddle` `typography` の 13 種です。既定は
  `pigeon_origami`。

## 実行

```sh
paperphone
paperphone --tz Asia/Tokyo --date 2026-11-17 --out ~/paper/today.pdf
paperphone --no-map
```

- `--tz` は IANA のタイムゾーン名。未指定なら設定、それも無ければシステム。
- `--date` は `YYYY-MM-DD`。未指定なら `--tz` の今日。
- `--out` は出力先。未指定ならカレントの `paperphone-YYYY-MM-DD.pdf`。
- `--no-map` は地図ページを作らず 1 ページにします。
- `--verbose` は source ごとの件数を標準エラーに出します。
- 成功すると書き出した PDF の絶対パスを標準出力に 1 行出します。

終了コードは 0（PDF を書いた）、1（実行時エラー）、2（引数か設定の誤り）です。
source や天気・地図の失敗は警告として標準エラーに出し、残りで PDF を書きます。

## source の用意

GNOME の「オンラインアカウント」で追加したカレンダー・連絡先は、そのまま
`paperphone sources` に GNOME 管理として現れます。paperphone はこれらを
変更・削除しません。

独自の DAV は `dav add` で登録します。パスワードは一度だけ尋ねられ、
ログインキーリングに保存されます。設定ファイルやログには出ません。

```sh
# CalDAV（予定）
paperphone dav add --kind caldav --url https://cloud.example.com/remote.php/dav/calendars/aki/personal/ --name Personal --user aki

# CardDAV（連絡先）
paperphone dav add --kind carddav --url https://cloud.example.com/remote.php/dav/addressbooks/users/aki/contacts/ --name Contacts --user aki

# CalDAV のタスク用コレクション（VTODO）
paperphone dav add --kind tasks --url https://cloud.example.com/remote.php/dav/calendars/aki/tasks/ --name Tasks --user aki
```

登録すると UID が表示されます。`caldav` と `tasks` は既定で `[sources]` の
選択に加わります。加えたくない場合は `--no-select` を付けます。`carddav` は
連絡先 UID を選ぶ必要があるため自動では加えません。

```sh
paperphone sources
paperphone contacts list
paperphone contacts list --query Aki
paperphone dav remove paperphone-....
```

同じ URL・種類・ユーザーを二重に登録すると終了コード 2 で拒否されます。
既存の source を使い回す場合は `--adopt` を付けます。`dav remove` は
paperphone が登録した source とキーリング項目だけを消し、GNOME 管理の
source は拒否します。

## 朝の無人実行

`~/.config/systemd/user/paperphone.service`:

```ini
[Unit]
Description=Paper Phone booklet

[Service]
Type=oneshot
WorkingDirectory=%h/paper
ExecStartPre=/bin/mkdir -p %h/paper
ExecStart=%h/.local/bin/paperphone
```

`~/.config/systemd/user/paperphone.timer`:

```ini
[Unit]
Description=Paper Phone every morning

[Timer]
OnCalendar=*-*-* 07:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```sh
systemctl --user daemon-reload
systemctl --user enable --now paperphone.timer
```

キーリングが解錠されているログイン後の時間に走らせてください。

## 印刷と折り方

```sh
lp -o media=A4 -o sides=two-sided-long-edge ~/paper/paperphone-2026-11-17.pdf
```

両面印刷し、地図ページを表にして半分に折ります。ページの円と四角が重なる
ように、さらに半分、もう半分と折ると 8 枠の冊子になります。連絡先と予定の
枠は逆向きに印刷されるので、折ったあとに正しい向きで読めます。

- 地図ページが無い設定では 1 ページだけ印刷します。
- 折り位置の目印（四角と円）は印刷したまま残ります。

## 帰属

- 地図タイル: © OpenStreetMap contributors（PDF に印刷されます）
- 天気: Open-Meteo（PDF に帰属を印刷します）
- フォント: Varela、Work Sans（SIL Open Font License 1.1）
- 紙アプリ: 元の Paper Phone プロジェクトの Apache-2.0 ライセンス資産

ライセンス文は `LICENSE` と `src/paperphone/assets/LICENSES/` にあります。

## 開発

PyGObject はシステムの Python に紐づくため、venv は
`--system-site-packages` で作ります。

```sh
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/ruff check src tests
.venv/bin/pytest
.venv/bin/python -m build
```

テストはフィクスチャとモック中心です。開発機に GNOME が無くても、rootless
Podman で EDS とキーリングを用意して doctor・DAV 登録・systemd user timer・
オフライン実行まで確認できます。手順は
[docs/gnome-container.md](docs/gnome-container.md) にあります。両面印刷と
折り畳みだけは実機で確認してください。

```sh
paperphone doctor
paperphone sources
paperphone dav add --kind caldav --url ... --name ... --user ...
systemctl --user start paperphone.service
```

## ライセンス

Apache License 2.0。詳細は [LICENSE](LICENSE) を参照してください。
