# Spec Delta

## Purpose

朝の一度の実行で冊子 PDF を作るための、引数・設定・タイムゾーン・終了コード・診断コマンドの契約。

## ADDED Requirements

### Requirement: 生成コマンド

`paperphone` はサブコマンドなしで設定を読み、冊子 PDF を1つ生成しなければならない (SHALL)。`--date`、`--tz`、`--out`、`--config`、`--no-map`、`--verbose` を受け付け、成功したら書き出した PDF の絶対パスを標準出力に1行で出さなければならない (SHALL)。

#### Scenario: 引数なしで実行する

- **WHEN** 設定ファイルがある状態で `paperphone` を実行する
- **THEN** 今日の日付の冊子 PDF がカレントディレクトリの `paperphone-YYYY-MM-DD.pdf` に書き出され、その絶対パスが標準出力に出る

#### Scenario: 出力先を指定する

- **WHEN** `paperphone --out /tmp/today.pdf` を実行する
- **THEN** `/tmp/today.pdf` に冊子が書き出される

#### Scenario: 地図を外す

- **WHEN** 設定で地図が有効な状態で `paperphone --no-map` を実行する
- **THEN** 1ページだけの冊子が書き出される

### Requirement: タイムゾーンの解決

`--tz` は IANA のタイムゾーン名を受け付け、冊子の日付境界、予定とタスクの期限の表示、天気の9時・12時・18時、ファイル名の日付をこのゾーンで解決しなければならない (SHALL)。未指定なら設定の `timezone`、それも無ければシステムのゾーンを使う。無効な名前は終了コード2で拒否する。

#### Scenario: 日付境界が変わる

- **WHEN** UTC で 2026-11-16 15:30 のとき `--tz Asia/Tokyo --date` を省略して実行する
- **THEN** 冊子の日付は 2026-11-17 になり、ファイル名も 2026-11-17 になる

#### Scenario: 無効なタイムゾーン

- **WHEN** `--tz Mars/Olympus` を実行する
- **THEN** 終了コード2で終わり、PDF は書き出されない

#### Scenario: 夏時間の切り替え日

- **WHEN** `--tz America/New_York` で夏時間の切り替え日を指定する
- **THEN** 予定と天気の時刻はその日の実際のオフセットで解決される

### Requirement: 設定ファイル

設定は TOML とし、既定は `$XDG_CONFIG_HOME/paperphone/config.toml`、`XDG_CONFIG_HOME` が無ければ `~/.config/paperphone/config.toml` でなければならない (SHALL)。`--config` で差し替えられる。ファイルが無い、読めない、TOML として不正、または `[booklet].name` が無い場合は、PDF を書かずに終了コード2で理由を標準エラーに出す。

#### Scenario: 既定の設定を読む

- **WHEN** `~/.config/paperphone/config.toml` に有効な設定を置いて実行する
- **THEN** その設定の名前と項目で冊子が作られる

#### Scenario: 設定が無い

- **WHEN** 設定ファイルが存在しない状態で実行する
- **THEN** 終了コード2で終わり、標準エラーに設定ファイルのパスと雛形の作り方が出る

#### Scenario: 設定が壊れている

- **WHEN** TOML として不正な設定ファイルを `--config` で指定する
- **THEN** 終了コード2で終わり、PDF は書き出されない

#### Scenario: タイムゾーンの優先順位

- **WHEN** 設定の `timezone` が `Asia/Tokyo` のとき `--tz Europe/London` を指定する
- **THEN** 欧州ロンドンの日付と時刻で冊子が作られる

### Requirement: 診断コマンド

`paperphone doctor` は、EDS の typelib と D-Bus、ログインキーリング（paperphone 管理の DAV がある場合のみ必須）、フォント、タイムゾーンデータ、設定、出力先の書き込み可否を検査し、各項目の成否を出力しなければならない (SHALL)。必須項目が1つでも失敗したら終了コード1、すべて成功したら0で終わらせる。

#### Scenario: すべて揃っている

- **WHEN** GNOME デスクトップで依存が揃った状態で `paperphone doctor` を実行する
- **THEN** 各項目が成功と表示され、終了コード0で終わる

#### Scenario: EDS が無い

- **WHEN** EDS の typelib が無い環境で `paperphone doctor` を実行する
- **THEN** 該当項目が失敗と表示され、必要なパッケージ名の案内が出て、終了コード1で終わる

### Requirement: 終了コードと部分失敗

終了コードは、PDF を書き出したら0、実行時エラーで PDF を書けなかったら1、引数か設定の誤りなら2としなければならない (SHALL)。個々の source、天気、地図、経路の取得失敗は警告として標準エラーに出し、残りの内容で PDF を書き出して0で終わらせる。

#### Scenario: 通信できなくても冊子は出る

- **WHEN** ネットワークが無い状態で実行する
- **THEN** 予定・連絡先・タスクだけで冊子が書き出され、天気と地図の警告が出て、終了コード0で終わる

#### Scenario: 引数が不正

- **WHEN** 存在しない `--date 2026-02-30` を指定する
- **THEN** 終了コード2で終わり、PDF は書き出されない

#### Scenario: 出力先に書けない

- **WHEN** 書き込み権限の無いディレクトリを `--out` に指定する
- **THEN** 終了コード1で終わり、PDF は書き出されない
