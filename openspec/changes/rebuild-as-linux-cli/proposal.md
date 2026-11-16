# Proposal

## Why

Paper Phone の目的は「その日に必要な情報を紙へ刷り、デジタルから離れること」であって、スマートフォンアプリであることではない。毎朝同じ内容を刷るなら、項目の選択は実行時の画面ではなく設定ファイルに一度書けばよい。Android アプリを Linux の CLI に置き換えれば、スマートフォンを持たない利用者でも、GNOME デスクトップの cron や systemd タイマーから PDF を1枚出すだけで済む。Google API キー、Play Store、権限ダイアログも不要になる。

## What Changes

- **BREAKING** Android アプリ（Kotlin / Gradle / `app/`）を削除し、Python 製の CLI `paperphone` に置き換える。`keys.properties` は廃止する。
- 実行は `paperphone --tz Asia/Tokyo [--date YYYY-MM-DD] [--out PATH]`。選択内容は TOML の設定ファイルに置き、日付・タイムゾーン・出力先だけを引数で上書きする。
- カレンダー・連絡先・タスクは、GNOME Online Accounts が提供する source と、paperphone が EDS（Evolution Data Server）へ登録する独自 CalDAV / CardDAV の source をまとめて読む。認証情報は GNOME のログインキーリングに置き、無人実行時に問い合わせを出さない。
- タスクは CalDAV の VTODO のみを対象とする。Google Tasks は対象外。
- 地図は OpenStreetMap のラスタタイルと、設定可能な徒歩経路サービスで描く。Google Maps は使わず、CoMaps の取り込みも行わない。
- 天気は Open-Meteo から取得する。位置情報は使わず、設定した緯度経度と表示名を使う。
- 出力は PDF のみ。Android の印刷フレームワーク、オンボーディング、権限要求、ダッシュボード、コンタクトレスは廃止する。
- 冊子の見た目（A4 横向き、8枠、固定順、モノクロ、地図ページの180度回転、折り位置の目印）と、紙アプリ13種・写真・メモは維持する。
- `doctor`、`sources`、`dav add|list|remove`、`contacts list` を追加し、設定と認証を対話的に準備できるようにする。

## Capabilities

### New Capabilities

- `cli`: 引数、タイムゾーン、設定ファイル、終了コード、診断コマンドという、CLI の外側の契約。
- `sources`: GNOME Online Accounts と独自 CalDAV / CardDAV を EDS の source として統一し、一覧・登録・削除・認証を行う能力。
- `pdf-output`: 組み上がった冊子を A4 横向き・モノクロの PDF として安全に書き出す能力。

### Modified Capabilities

- `booklet-composition`: ダッシュボードでの選択を設定による選択に置き換え、表紙の日付を指定タイムゾーンで解決する。
- `booklet-extras`: 写真と紙アプリの選択をファイルパスと設定名に置き換える。
- `calendar`: データ源を EDS に変え、日の境界と表示時刻を指定タイムゾーンで解決する。
- `contacts`: 端末の連絡先を UI で選ぶ代わりに、設定の UID で選ぶ。
- `tasks`: Google Tasks をやめ、EDS の VTODO を読む。
- `weather`: 位置情報をやめ、設定地点の Open-Meteo 予報を使う。
- `maps`: Google Maps をやめ、OpenStreetMap タイルと設定可能な徒歩経路サービスを使う。帰属表示を追加する。
- `onboarding`: 廃止する。名前は設定ファイルに置く。
- `permissions`: 廃止する。CLI に実行時権限はない。
- `printing`: 廃止し、`pdf-output` に置き換える。

## Impact

- 削除: `app/` 以下の Kotlin とリソース、Gradle 一式、`keys.properties`、Android 前提の仕様10件。
- 追加: `src/paperphone/`（CLI、設定、EDS、天気、地図、描画、PDF）、`pyproject.toml`、`install.sh`、`assets/`（フォント、紙アプリの PNG）、テスト用フィクスチャ。
- 依存: Python 3.12+、PyGObject と EDS の typelib（`ECal`、`EBook`、`EDataServer`、`ICalGLib`）、libsecret、Pango / Cairo、WeasyPrint、Pillow、httpx。
- 配布: GitHub と tangled.org のソース、および GitHub Releases の tarball。Flathub と AUR は使わない。
- 開発環境: このリポジトリの開発機には EDS と GOA が無いため、統合の検証は GNOME デスクトップ上で行う。描画と PDF はフィクスチャで検証できる。
