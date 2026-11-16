# EDS・WeasyPrint・地図のスパイク記録

## 検証スコープ

この変更では、1.1 は Evolution GUI での手動登録の代わりに EDS API で作成した
source の実物を観察することで完了とし、1.2 は systemd user oneshot での読み取りを
もって完了とします。11.4 は PDF の回転・座標・折り目までを検証範囲とし、紙での
最終確認は受け入れ時の確認に切り分けます。

この変更（`rebuild-as-linux-cli`）のタスク 1.1〜1.4 の記録です。開発機には
GNOME も EDS も無いため、EDS の実機スパイク（1.1、1.2）は rootless Podman の
GNOME/EDS コンテナで実施しました。描画と地図（1.3、1.4）は開発機で実施しています。

日付: 2026-11-17
環境: Ubuntu / Python 3.14.4 / WeasyPrint 70.0 / libpango 1.50 系 /
fontconfig / Noto Sans JP をユーザーフォントとして追加

## 1.1 EDS の source 形式とキーリング属性（コンテナで確認済み）

この開発機には GNOME が無いため、Ubuntu 24.04 の rootless Podman コンテナに
EDS 3.52.3、PyGObject、gnome-keyring、Radicale を入れ、`dbus-run-session` 上で
実際の EDS を動かして確認しました。Evolution の GUI からの手動登録ではなく、
`paperphone dav add` が GI 経由で作った source を EDS 自身に書かせています。
手順と再現方法は [gnome-container.md](gnome-container.md) にあります。

EDS が書いた `.source` の実例（CalDAV）:

```ini
[Data Source]
DisplayName=TimerCal
Enabled=true
Parent=

[Authentication]
Host=127.0.0.1
Method=plain/password
Port=5232
ProxyUid=system-proxy
RememberPassword=true
User=aki
CredentialName=
IsExternal=false

[Security]
Method=none

[WebDAV Backend]
AvoidIfmatch=false
CalendarAutoSchedule=false
Color=
DisplayName=
EmailAddress=
ResourcePath=/aki/cal
ResourceQuery=
SslTrust=
Order=4294967295

[Calendar]
BackendName=caldav
Color=#62a0ea
Selected=true
Order=0
```

CardDAV とタスクの違い:

- CardDAV: `[Address Book]` 拡張に `BackendName=carddav`。`Selected` は無い。
- タスク: `[Task List]` 拡張に `BackendName=caldav`、`Selected=true`。
- URL は `[WebDAV Backend] ResourcePath` にパスだけが入り、ホストとポートは
  `[Authentication] Host` / `Port` に入る。
- `[Security] Method=none` は http のとき。https では値が変わる可能性がある。
- `ProxyUid=system-proxy` は EDS が自動で埋める。

キーリング（`secret-tool search --all xdg:schema org.gnome.Evolution.Data.Source`）:

```text
label = Evolution Data Source "TimerCal" (Calendar - caldav)
secret = ...
schema = org.gnome.Evolution.Data.Source
attribute.e-source-uid = paperphone-...
attribute.eds-origin = evolution-data-server
```

スキーマ名や属性を自分で組み立てず、`SourceCredentialsProvider` の
`store_sync` / `lookup_sync` / `delete_sync` に任せる実装で一致しました。
`secret-tool search source-uid ...` ではヒットせず、属性名は `e-source-uid` です。

この形式で GI から source を作成し、`ECal` / `EBook` で読めること、`dav remove`
で source とキーリング項目が消えることを確認しました。

## 1.2 systemd --user の oneshot（コンテナで確認済み）

コンテナ内で systemd 259 を PID 1 として起動し、`user@0.service` の
ユーザーマネージャを動かして確認しました。`paperphone.service` は oneshot で、
`OnCalendar=*-*-* 07:00:00` と `OnActiveSec=5` の user timer から起動しました。

- 予定・連絡先・タスク・メモを含む PDF が書き出された。
- ジャーナルにパスワード入力待ちは出ていない。
- Radicale を止めた状態（実質オフライン）でも、EDS のキャッシュから
  予定・連絡先・タスクを読んで終了コード 0 で PDF を書いた。
- 通信できない source のタイムアウトで 1 回の実行に約 2 分かかった。
  朝の timer では許容できるが、`[maps]` / 天気のタイムアウトも含めた
  全体の上限は今後調整の余地がある。

制約: これは GNOME の物理セッションではなく、rootless コンテナ内の
systemd user manager です。`user@0.service` には
`XDG_RUNTIME_DIR=/run/user/0` の drop-in が必要でした。

## 1.1・1.2 で見つかった実装の差異

モックテストでは見えず、実 EDS で判明した点:

- `ECal.ClientSourceType` の値は `EVENTS`（`EVENT` ではない）。
- `get_object_list_as_comps_sync` / `get_contacts_sync` は
  `(True, out_...)` のタプルを返す。
- `generate_instances_sync` のコールバックは 5 引数で、継続には `True` を返す。
  返さないと最初の 1 件で止まる。
- `ECal.ComponentText` / `ECal.ComponentDateTime` は `.value` ではなく
  `get_value()`。
- `dav add --kind carddav` は EDS の拡張では `contacts` に対応する。
- `EBookContacts.Contact.get_const()` は GI ではポインタが int で返る。
  vCard 3.0 の文字列（`to_string(1)`）を解析する方が確実。

## 1.3 WeasyPrint の描画（実施済み）

確認したこと:

- `@page { size: 297mm 210mm; margin: 0 }` で A4 横向き（842×595pt）になる。
- mm / pt の絶対配置で 4 列 2 段の枠を置ける。枠は 154×242pt
  （約 54.3×85.4mm）、外周 28pt（約 9.9mm）。
- 連絡先と予定の枠に `transform: rotate(180deg)` を掛けると、内容だけが
  正しく逆向きになる。PDF を画像化して目視確認した。
- 2 ページ目の地図ページは、WeasyPrint では通常の向きで描き、pypdf の
  `PageObject.rotate(180)` でページ全体を回す。PDF の `/Rotate` は 180 になる。
- `@font-face` で Varela（OTF）と Work Sans（TTF）を埋め込める。
- 和文はフォントのフォールバックで出る。この開発機には CJK フォントが
  無かったため Noto Sans JP をユーザーフォントとして追加し、名前「あき」が
  豆腐にならず PDF からテキスト抽出できることを確認した。
- 空き枠の点は 17pt 間隔の SVG を `background-size: 17pt 17pt` で繰り返す。

再現コマンド:

```sh
PYTHONPATH=src .venv/bin/pytest tests/test_booklet.py
```

## 1.4 OSM タイル・Valhalla・白黒化（実施済み）

タイル取得:

```sh
curl -A "paperphone/0.1.0 (+https://github.com/google/paper-phone)" \
  -o /tmp/tile.png https://tile.openstreetmap.org/15/29096/12878.png
# HTTP 200, 28,137 bytes, PNG 256x256
```

徒歩経路:

```sh
curl -X POST -H 'Content-Type: application/json' \
  -A "paperphone/0.1.0 (+https://github.com/google/paper-phone)" \
  -d '{"locations":[{"lat":35.6812,"lon":139.7671},{"lat":35.69,"lon":139.7}],"costing":"pedestrian","units":"kilometers"}' \
  https://valhalla1.openstreetmap.de/route
# HTTP 200, 41,443 bytes
```

分かったこと:

- Valhalla の応答は `trips` ではなく `trip`（単数）を返す実装がある。
  `fetch_route` は両方を受け付けるようにした。
- `legs[].shape` は polyline6。東京駅→茅場町の経路は 420 点にデコードできた。
- タイルは 1 冊子あたり最大 25 枚（5×5）、経路 1 回、天気 1 回で、1 日 1 回の
  実行なら 27 リクエスト程度。先読みもディスクキャッシュもしない。
- `User-Agent: paperphone/<version> (+リポジトリURL)` を送る。
- 白黒化は Pillow の `convert("L")` で行い、経路は黒線を描く。
- 経路サービスは既定で未設定。設定した場合も失敗時は地図だけに縮退する。

タイル利用方針: 1 日数枚、先読みなし、キャッシュなし、識別可能な UA、
PDF に「© OpenStreetMap contributors」を印刷する。将来アクセスが増えるなら
`[maps].tile_url` を自前タイルに差し替える。
