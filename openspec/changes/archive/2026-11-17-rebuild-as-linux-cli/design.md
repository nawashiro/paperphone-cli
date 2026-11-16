# Design

## Context

現行リポジトリは Android アプリ（Kotlin、`app/`、Gradle 5.4.1、Google API キー必須）で、仕様も Android の画面遷移を前提にしている。CLI 版は GNOME デスクトップ上で cron / systemd タイマーから無人実行される。この開発機には GNOME も EDS も無いため、EDS との統合は実機で検証する必要がある。

制約:

- 配布は GitHub と tangled.org のみ。Flathub と AUR は使わない。
- 認証情報は設定ファイルに置かない。朝の無人実行で問い合わせを出さない。
- 出力は PDF のみ。印刷は `lp` に任せる。
- Google Maps は使わない。CoMaps は取り込まない。
- Python 3.12+ と GNOME の共有ライブラリ（PyGObject、EDS、Pango）を前提にする。

## Goals / Non-Goals

**Goals:**

- 1コマンドで、指定タイムゾーンの「今日」の冊子 PDF を再現性高く作る。
- GNOME Online Accounts と独自 CalDAV / CardDAV を、同じ読み取り経路で扱う。
- ネットワークや source の一部が失敗しても、冊子は必ず1つ書き出す。
- 冊子の見た目と紙アプリの品質を Android 版から維持する。
- インストールと診断を1つのスクリプトと `doctor` に閉じ込める。

**Non-Goals:**

- 印刷、GUI、TUI、対話的なダッシュボード。
- Google Tasks、Google カレンダー / 連絡先の直接 API 利用。
- オフライン地図、自前の経路エンジン、地図タイルのキャッシュ。
- Flathub / AUR / Snap 向けのパッケージング。
- Android 版とのデータ移行（設定は新規に書く）。

## Decisions

### 1. Python + PyGObject + EDS を採用する

カレンダーと連絡先の読み取りに EDS を使うため、PyGObject が最も直接的である。繰り返し予定の展開、タイムゾーン、認証、オフラインキャッシュを EDS に任せられる。Rust + zbus で EDS の D-Bus プロトコルを再実装する案と、Rust から C API を FFI で叩く案を検討したが、どちらも週単位の追加作業に対して得るものが少ない。単一バイナリにはならないが、配布はソースと `install.sh` で足りる。

### 2. 描画は WeasyPrint の HTML/CSS、地図ページの回転は PDF 側で行う

冊子は mm 指定の絶対配置なので、HTML/CSS の `@page` と mm 単位で十分に表現できる。WeasyPrint は Pango 経由でフォントを埋め込み、ベクタ PDF を出す。Typst は高速だが、データ層を Rust に寄せる必要があり、ヘッドレス Chromium は配布が重い。

2ページ目の180度回転は CSS の `transform` に頼らず、WeasyPrint が出した PDF の2ページ目を pypdf で回転する。ページ全体を回すだけなので、`transform` の実装差やクリッピングの影響を受けない。

### 3. EDS を唯一の集約点にし、GOA は読み取り専用にする

GNOME Online Accounts は認証情報とアカウントの台帳で、カレンダー / 連絡先の実体は EDS の source にある。paperphone は GOA を直接変更せず、`ESourceRegistry` から source を列挙し、`ECal` / `EBook` で読む。独自 DAV も EDS の source として登録するので、読み取りコードは1本で済む。

### 4. 独自 DAV は `dav add` で EDS source とキーリングを作る

`dav add` の流れ:

1. URL（コレクション URL）と種類、ユーザーを受け取る。
2. 既存の管理 source と URL・種類・ユーザーが重複しないか確認する。
3. パスワードを `getpass` で一度だけ尋ねる。
4. `paperphone-<uuid4>` の UID で `ESource` を作り、`Calendar` 拡張の backend を `caldav`、認証拡張に host / user を設定する。`--kind tasks` では `contains` を `VTODO`、`caldav` では `VEVENT`、`carddav` ではアドレス帳にする。
5. EDS が期待する libsecret のスキーマと属性でパスワードを保存する。
6. source を commit し、`ECal` / `EBook` で一覧取得を試す。
7. 失敗したら source とキーリング項目を削除して終了コード1。
8. 成功したら `dav.toml` に管理レコードを書き、`caldav` / `tasks` は既定で `[sources]` にも追加する（`--no-select` で追加しない）。

**正確な source プロパティとキーリング属性は推測しない。** GNOME の Evolution で同じサーバーを一度手動登録し、`~/.config/evolution/sources/*.source` と `secret-tool search` の結果を観察して、その形を再現する。このスパイクを実装の最初に置く。

### 5. 設定は TOML、`dav` の管理情報は別ファイル

利用者が手で編集する `config.toml` と、`dav add|remove` が書き換える `dav.toml` を分ける。`config.toml` の編集は `tomlkit` でコメントを保ちながら行い、`dav.toml` は paperphone が全体を所有する。これにより、`dav remove` が利用者の書いた設定を壊さずに参照だけを消せる。

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
calendars = ["..."]
contacts = ["..."]
tasks = ["..."]

[weather]
latitude = 35.6812
longitude = 139.7671
label = "Tokyo"

[maps]
tile_url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
router_url = "https://example.invalid/route"
from = { latitude = 35.68, longitude = 139.76, label = "Home", address = ["1-1 Chiyoda", "Tokyo"] }
to = { latitude = 35.69, longitude = 139.70, label = "Station", address = ["2-2 Chuo", "Tokyo"] }

[photo]
path = "/home/aki/photo.jpg"

[paper_app]
name = "sudoku"
```

優先順位は `--tz` > `[booklet].timezone` > システム、`--date` > `--tz` の今日、`--out` > カレントの `paperphone-YYYY-MM-DD.pdf`。`[panels]` の未知のキー、未知の紙アプリ名、範囲外の緯度経度、天気や地図を有効にしたのに必須値が無い場合は、描画前に終了コード2で止める。

### 6. タイムゾーンは zoneinfo で一貫させる

日付境界、予定の表示、タスクの期限、天気の9/12/18時、表紙とファイル名の日付を、すべて同じ `ZoneInfo` で解決する。予定の展開は `ECal` に範囲（そのゾーンの 00:00 から翌 00:00）を渡し、返ってきたインスタンスの時刻をそのゾーンで表示する。天気は Open-Meteo の `timezone` パラメータに同じゾーンを渡す。夏時間の曖昧な時刻は EDS と zoneinfo の解決に従う。

### 7. データ取得は並列、失敗は部分結果で吸収する

天気、タイル、経路は `ThreadPoolExecutor` で並列に取り、全体に短いタイムアウトを設ける。各 source の読み取りは個別に try し、失敗したら警告を貯めて次へ進む。描画は取得結果が揃ってから1回だけ行う。ネットワークが無い朝でも、予定・連絡先・タスクだけで PDF が出る。

### 8. 地図は OSM ラスタタイル + Valhalla 形式の経路

タイルは設定された URL テンプレートから取得し、既定は `tile.openstreetmap.org`。`User-Agent: paperphone/<version> (+リポジトリURL)` を送り、先読みもディスクキャッシュもしない。帰属は PDF に印刷する。

経路は Valhalla の `/route` JSON を第一実装とし、徒歩プロファイルで1本だけ取る。返る polyline6 をデコードし、Pillow で黒線を描く。経路サービスが未設定なら地図と A/B だけを描く。タイルが取れなければ地図画像を省き、見出し・住所・点の領域だけを残す。

地図のズームは2地点（経路があれば経路全体）の bbox が地図領域に収まるように計算し、12〜17にクランプする。300dpi を前提に 3×3〜5×5 タイルを結合し、地図領域でクロップする。白黒化は Pillow の `convert("L")`。

### 9. 天気は Open-Meteo、キャッシュは地点単位

`https://api.open-meteo.com/v1/forecast` の hourly から、指定ゾーンの9時・12時・18時に最も近い値を取る。WMO コードは英語の短い天気名に変換し、同梱のモノクロアイコンを選ぶ。枠の隅に Open-Meteo の帰属を小さく入れる。取得に失敗したら `~/.cache/paperphone/weather.json` の同じ地点（緯度経度を小数3桁で丸めたキー）の前回値を使う。地点が変わったら前回値は使わない。

### 10. 冊子は HTML/CSS で組み、PDF は原子的に書く

1ページ目は `@page { size: A4 landscape; margin: 0 }` の絶対配置。8枠は 54mm×85mm、外周 10mm、固定順。連絡先と予定の枠は `transform: rotate(180deg)` で内容だけを回す。空き枠は同梱の SVG ドットパターン。1ページ目には折り位置の黒い四角を2つ、2ページ目には折り畳み用の円を2つ描く。表紙は Varela、本文は Work Sans、和文は Noto Sans CJK JP にフォールバックする。フォントは Latin 2書体を同梱し、CJK はシステムのものを使う（`doctor` で確認）。

写真は Pillow で白黒化し、横長なら90度回し、枠幅に合わせて 300dpi 相当にリサイズする。紙アプリの PNG は縦横比を無視して枠いっぱいに引き伸ばす。

PDF は一時ファイルに書き、`os.replace` で出力先へ移す。2ページ目は pypdf で180度回転してから結合する。失敗時は一時ファイルを消し、既存の出力先を変更しない。

### 11. 設定と source の解決、終了コード

`cli.py` は argparse で引数を解析し、`config.py` が TOML を dataclass に変換して検証する。`sources.py` が EDS の source を列挙し、選択された UID を解決する。解決できなかった UID は警告にして飛ばす。終了コードは 0（PDF 成功）、1（実行時エラー）、2（引数・設定エラー）。`--verbose` は source ごとの結果を標準エラーに出す。

`doctor` は Python、`gi`、`ECal` / `EBook` / `EDataServer` / `ICalGLib`、D-Bus セッション、キーリング、Pango、フォント、zoneinfo、設定、出力先を検査する。EDS と設定は必須、キーリングは管理 source がある場合のみ必須、ネットワークは警告扱い。

### 12. 配布は venv + `install.sh`、テストはフィクスチャ中心

PyGObject はシステムの Python に紐づくため、`python3 -m venv --system-site-packages` で venv を作り、その中に WeasyPrint / Pillow / httpx / tomlkit / pypdf を入れる。`install.sh` は `~/.local/share/paperphone/venv` を作り、`~/.local/bin/paperphone` を張る。システム依存は apt / dnf / pacman の例を表示し、`sudo` は実行しない。

GitHub Releases にはソースの tarball と `install.sh` を置く。CI は Android ビルドを捨て、pytest と `python -m build` に置き換える。EDS の統合テストは D-Bus と実アカウントが要るので、CI ではフィクスチャとモックに限定し、実機検証を README の手順に残す。

## Risks / Trade-offs

- **EDS の source 形式とキーリング属性がバージョンで揺れる** → 実装前に Evolution の実物を観察するスパイクを置き、`doctor` で検出する。source の生成に失敗したら、既存の Evolution 設定を壊さずに終了する。
- **キーリングがロックされていると無人実行で source が読めない** → 警告で飛ばし、PDF は残りで出す。systemd の user timer をログイン後に走らせる。`doctor` で警告する。
- **WeasyPrint の `transform` やフォント埋め込みに差がある** → 2ページ目は pypdf で回転する。1ページ目の逆向き枠はスパイクで確認し、駄目なら枠内容を SVG / 画像で回す。
- **OSM タイルの利用方針に反する** → 1日数枚、先読みなし、キャッシュなし、識別可能な UA、帰属表示。将来増えるならタイル URL を差し替える。
- **公開経路サービスが落ちる / 規約が変わる** → 既定では未設定。設定した場合も失敗時は地図のみに縮退する。自前 Valhalla / OSRM を差せる。
- **PyGObject が venv から見えない** → `--system-site-packages` を必須にし、`doctor` で検出する。pip で PyGObject を入れない。
- **和文名が Varela / Work Sans に無い** → Noto Sans CJK JP などへのフォールバックを指定し、`doctor` で CJK フォントを確認する。
- **カレンダーの終日予定や繰り返しの解釈** → EDS の展開結果を使い、終日は時刻なしで描く。
- **PDF が大きくなる** → タイルと写真を 300dpi 相当に落とし、JPEG / PNG を選ぶ。紙アプリは元 PNG の解像度を保つ。

## Migration Plan

1. 新しい Python パッケージ、`pyproject.toml`、`install.sh`、`assets/` を追加する。
2. `app/`、Gradle、`keys.properties`、Android 前提のリソースを削除する。紙アプリの PNG とフォントは `assets/` に移す。
3. README を CLI の使い方、依存、systemd の例、折り方に書き換える。
4. `openspec/specs/` の Android 仕様は、この変更の delta で廃止・置換する。
5. `openspec/config.yaml` の context を CLI の構成に更新する（実装後）。
6. 実機の GNOME で `doctor`、`sources`、`dav add`、朝の無人実行を順に確認する。

ロールバックは git の履歴で Android 版に戻せる。設定とキーリングは paperphone 管理の source だけを消せばよく、GNOME のアカウントには触れない。

## Open Questions

- なし。実装前に確定が必要な EDS の source プロパティとキーリング属性は、スパイクの結果で design を更新する。
