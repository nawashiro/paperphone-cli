# Tasks

## 1. スパイク（GNOME 実機）

- [x] 1.1 Evolution で CalDAV・CardDAV・タスク用コレクションを手動登録し、`~/.config/evolution/sources/*.source` のキーと `secret-tool search` の属性を `docs/eds-source-notes.md` に記録する。記録した内容で GI から同じ source を作れることを確認する。
- [x] 1.2 手動登録した source を `systemd --user` の oneshot から ECal / EBook で読み、パスワード入力待ちが出ないことを確認する。結果を `docs/eds-source-notes.md` に残す。
- [x] 1.3 WeasyPrint で A4 横向き・mm 絶対配置・`transform: rotate(180deg)`・Varela / Work Sans / Noto Sans CJK JP のフォールバックを試し、逆向きの枠と和文名が正しく出るか確認する。結果を `docs/eds-source-notes.md` に残す。
- [x] 1.4 OSM タイルの取得、Valhalla の徒歩経路、polyline の描画、白黒化を小さなスクリプトで試し、タイル利用方針とレートの見積もりを `docs/eds-source-notes.md` に残す。

## 2. 足場とアセット

- [x] 2.1 `pyproject.toml`、`src/paperphone/` のパッケージ構成、ruff / pytest の設定を追加し、`python -m build` と `pytest` が通ることを確認する。
- [x] 2.2 Android の `res/font` から Varela と Work Sans を、`res/drawable-nodpi` から紙アプリ13種の PNG を、天気アイコンを `src/paperphone/assets/` に移し、各ファイルの存在と解像度を確認する。
- [x] 2.3 フォント（OFL）と紙アプリ（Apache-2.0）のライセンス文を `assets/LICENSES/` に置き、`LICENSE` から参照されることを確認する。
- [x] 2.4 `install.sh` を作り、`python3 -m venv --system-site-packages` で venv を作って `paperphone --version` が動くことを確認する。
- [x] 2.5 GitHub Actions を pytest と `python -m build` に置き換え、ローカルで同じコマンドが通ることを確認する。

## 3. CLI と設定

- [x] 3.1 argparse で `paperphone`、`doctor`、`sources`、`dav add|remove`、`contacts list` の骨格と終了コード 0/1/2 を実装し、引数エラーのテストを通す。
- [x] 3.2 `config.toml` の読み込みと dataclass 検証（必須の名前、`[panels]` の未知キー、紙アプリ名、緯度経度の範囲）を実装し、不正設定が終了コード2になるテストを通す。
- [x] 3.3 `--tz` / `--date` / `--out` の解決と優先順位を実装し、UTC と東京の日付境界、夏時間、無効な TZ のテストを通す。
- [x] 3.4 `doctor` の検査項目（Python、gi、ECal / EBook / EDataServer / ICalGLib、D-Bus、キーリング、Pango、フォント、zoneinfo、設定、出力先）を実装し、欠けた項目で終了コード1になるテストを通す。
- [x] 3.5 `sources` の一覧表示（UID、名前、種類、由来、認証情報の有無）を実装し、空の一覧と GNOME 管理 source の表示をモックで確認する。
- [x] 3.6 `contacts list [--query]` を実装し、名前・電話番号の部分一致と空結果のテストを通す。

## 4. EDS と独自 DAV

- [x] 4.1 `ESourceRegistry` からカレンダー・アドレス帳・タスクリストを列挙し、GOA 由来と paperphone 管理を区別するリーダーを実装する。モック registry のテストを通す。
- [x] 4.2 `ECal` で指定範囲の予定を展開し、繰り返し・終日・複数カレンダーの結合を実装する。ICS フィクスチャのテストを通す。
- [x] 4.3 `EBook` で連絡先を読み、UID・名前・電話番号を取り出すリーダーを実装する。vCard フィクスチャのテストを通す。
- [x] 4.4 `ECal` で VTODO を読み、未完了・期限・並び順を実装する。ICS フィクスチャのテストを通す。
- [x] 4.5 libsecret のラッパーを作り、`dav add` で保存したパスワードを通常実行で読めること、設定やログに出ないことをテストする。
- [x] 4.6 `dav add` を実装する。URL 検証、重複拒否、`--adopt`、source の作成と commit、登録直後の一覧取得、失敗時のロールバックをモックでテストする。
- [x] 4.7 `dav remove` を実装し、管理 source とキーリング項目だけを削除し、GNOME 管理 source と存在しない UID を拒否するテストを通す。
- [x] 4.8 `dav.toml` の管理レコードと `config.toml` の参照更新（`tomlkit`、コメント保持、`--no-select`）を実装し、追加・削除の往復テストを通す。
- [x] 4.9 認証情報が無い source を警告付きで飛ばし、残りで続行する経路を実装し、キーリング空のテストを通す。

## 5. 天気

- [x] 5.1 Open-Meteo クライアントを実装し、hourly の気温と WMO コードを指定ゾーンの9時・12時・18時に解決する。respX のテストを通す。
- [x] 5.2 WMO コードから英語の天気名と同梱アイコンへの対応表を実装し、未知コードのフォールバックをテストする。
- [x] 5.3 `~/.cache/paperphone/weather.json` の読み書きを実装し、同じ地点のキャッシュ利用、地点変更時の不使用、キャッシュ無しの描画をテストする。

## 6. 地図

- [x] 6.1 タイル URL テンプレートからタイルを取得し、結合・クロップ・白黒化する処理を実装する。ローカルのフィクスチャタイルでテストする。
- [x] 6.2 Valhalla の徒歩経路を取得し、polyline6 をデコードして黒線を描く処理を実装する。フィクスチャ JSON でテストする。
- [x] 6.3 2地点と経路の bbox からズームとタイル範囲を決める処理を実装し、12〜17のクランプをテストする。
- [x] 6.4 経路失敗時に地図だけ、タイル失敗時に地図画像なし、の縮退を実装し、それぞれのテストを通す。
- [x] 6.5 PDF に「© OpenStreetMap contributors」が入ることをテストで確認する。

## 7. 冊子の描画

- [x] 7.1 A4 横向き・8枠・固定順・10mm 余白の HTML/CSS を実装し、PDF のページサイズと枠の座標をテストで確認する。
- [x] 7.2 連絡先・予定・タスクの各パネルを実装し、最大件数・切り詰め・Today / Tomorrow・空の丸のテストを通す。
- [x] 7.3 表紙、メモの点格子、空き枠の点、折り位置の目印を実装し、要素の有無を PDF のテキストと画像で確認する。
- [x] 7.4 写真パネルを実装し、白黒化、横長の90度回転、枠幅へのリサイズ、読めない画像の空き枠をテストする。
- [x] 7.5 紙アプリ13種の同梱と引き伸ばし描画を実装し、全種が解決できることと未知名の終了コード2をテストする。
- [x] 7.6 連絡先と予定の枠の180度回転、地図ページの pypdf による180度回転を実装し、生成 PDF のページ回転をテストする。
- [x] 7.7 和文名のフォールバックを実装し、日本語の名前で豆腐が出ないことを目視と `doctor` で確認する。

## 8. PDF 出力と結合

- [x] 8.1 WeasyPrint の出力を一時ファイルに書き、`os.replace` で置き換える処理を実装し、既存ファイルの置換と失敗時の非破壊をテストする。
- [x] 8.2 天気・地図・経路を並列取得し、タイムアウトと部分失敗を吸収するオーケストレーションを実装し、ネットワーク無しでも PDF が出るテストを通す。
- [x] 8.3 `--no-map`、`--date`、`--tz`、`--out`、`--config` の組み合わせを統合テストし、期待するページ数とファイル名を確認する。
- [x] 8.4 空の `[panels]`、地図なし、全項目ありの3通りで PDF を生成し、1ページ／2ページと内容の有無を確認する。

## 9. インストールとドキュメント

- [x] 9.1 `install.sh` を完成させ、クリーンな Ubuntu の venv で `paperphone doctor` まで到達することを確認する（EDS の無い環境では失敗項目が案内どおり出る）。
- [x] 9.2 README にインストール、設定例、`dav add`、`contacts list`、systemd タイマー、両面印刷と折り方、帰属表示を書き、記載のコマンドを実際に実行して確認する。
- [x] 9.3 GitHub Releases 用の tarball と `install.sh` の導線を整え、tarball からインストールできることを確認する。
- [x] 9.4 `--help` と `doctor` の出力が README と矛盾しないことを確認する。

## 10. Android 版の引退

- [x] 10.1 `app/`、Gradle 一式、`keys.properties`、Android 前提のリソースを削除し、リポジトリ内に Kotlin / Gradle の参照が残っていないことを `grep` で確認する。
- [x] 10.2 `openspec/config.yaml` の context を Linux CLI の構成に更新し、`openspec context --json` が新しい内容を返すことを確認する。
- [x] 10.3 `openspec validate --strict` を通し、旧 Android 仕様が retired され、新しい10能力だけが残ることを確認する。

## 11. GNOME 実機での統合確認

- [x] 11.1 GNOME デスクトップで `paperphone doctor` を実行し、必須項目がすべて成功することを確認する。
- [x] 11.2 `paperphone sources`、`dav add`（CalDAV / CardDAV / tasks）、`dav remove` を実機で往復し、GNOME のカレンダー / 連絡先と競合しないことを確認する。
- [x] 11.3 systemd の user timer を朝に設定し、無人実行で PDF が書き出され、パスワード入力待ちが出ないことを確認する。
- [x] 11.4 生成 PDF を両面印刷し、折り畳んで連絡先・予定・地図の向きが正しいことを確認する。
- [x] 11.5 ネットワークを切った状態で timer を実行し、予定・連絡先・タスクだけで PDF が出て終了コード0になることを確認する。

## Workflow follow-up

- レビュー後に `openspec-archive-change` でこの変更をアーカイブし、`openspec/specs/` を更新する。
- アーカイブ後に `openspec validate --strict` と `paperphone doctor` を再確認する。
