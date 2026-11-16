# Spec Delta

## Purpose

GNOME のオンラインアカウントと独自の CalDAV / CardDAV を同じ source の一覧として扱い、選択・登録・認証・削除を可能にする能力。

## ADDED Requirements

### Requirement: source の一覧

`paperphone sources` は、利用可能なカレンダー・アドレス帳・タスクリストを、source UID、表示名、種類、由来（GNOME 管理または paperphone 管理）、認証情報の有無とともに一覧しなければならない (SHALL)。一覧の取得だけを行い、source を変更してはならない (MUST NOT)。

#### Scenario: GNOME と独自 DAV を並べる

- **WHEN** GNOME Online Accounts に Google アカウントがあり、paperphone が1つの CalDAV を登録している状態で `paperphone sources` を実行する
- **THEN** 両方のカレンダーが UID と由来付きで表示される

#### Scenario: source が無い

- **WHEN** 利用可能な source が1つも無い状態で `paperphone sources` を実行する
- **THEN** 空の一覧と、`dav add` または GNOME の設定で追加する旨の案内が表示され、終了コード0で終わる

### Requirement: GNOME 管理 source の尊重

paperphone は GNOME Online Accounts が作った source を読み取り専用として扱い、変更・削除してはならない (MUST NOT)。

#### Scenario: GNOME の source を削除しようとする

- **WHEN** GNOME 管理の source UID を `paperphone dav remove` に渡す
- **THEN** 削除は拒否され、GNOME の設定で削除するよう案内が出て、終了コード2で終わる

### Requirement: 独自 CalDAV / CardDAV の登録

`paperphone dav add --kind caldav|carddav|tasks --url URL --name NAME --user USER` は、指定されたコレクション URL の source を EDS に登録し、source UID を `paperphone-` で始まる値にしなければならない (SHALL)。`caldav` は予定、`carddav` は連絡先、`tasks` は VTODO のタスクリストとして登録する。登録した `caldav` と `tasks` は既定で `[sources]` の選択に加え、`--no-select` を指定した場合は加えない。登録直後に一覧の取得を試し、失敗したら登録を取り消して終了コード1で終わらせる。

#### Scenario: CalDAV を登録する

- **WHEN** Nextcloud のカレンダー URL を `--kind caldav` で指定する
- **THEN** source が登録され、`paperphone sources` に paperphone 管理のカレンダーとして現れ、設定に使う UID が表示される

#### Scenario: タスクリストを登録する

- **WHEN** CalDAV のタスク用コレクション URL を `--kind tasks` で指定する
- **THEN** VTODO を含む source として登録され、タスクの枠から読めるようになる

#### Scenario: 選択に加えない

- **WHEN** `--no-select` を付けて CalDAV を登録する
- **THEN** source は登録され UID が表示されるが、`[sources]` の選択には加わらない

#### Scenario: 同じ URL を二重に登録する

- **WHEN** 登録済みと同じ URL・種類・ユーザーで `dav add` を実行する
- **THEN** 重複として終了コード2で拒否され、既存の source UID と `--adopt` の案内が表示される

#### Scenario: 登録直後の読み取りに失敗する

- **WHEN** URL は到達できるが認証に失敗する
- **THEN** 登録は取り消され、終了コード1で理由が表示される

### Requirement: 認証情報の非対話性

独自 DAV のパスワードはログインキーリングだけに保存し、設定ファイル・標準出力・ログに出してはならない (MUST NOT)。`dav add` はパスワードを一度だけ対話的に尋ねるが、`paperphone` の通常実行と `doctor` は認証を対話的に尋ねてはならない (MUST NOT)。認証情報が無い source は警告を出して読み取りを飛ばし、残りの内容で冊子を書き出す。

#### Scenario: 無人実行

- **WHEN** cron から `paperphone` を実行する
- **THEN** パスワードの入力待ちは発生せず、登録済み source がそのまま読まれる

#### Scenario: キーリングに認証情報が無い

- **WHEN** source はあるがキーリングにパスワードが無い状態で実行する
- **THEN** その source は警告付きで飛ばされ、他の source だけで PDF が書き出される

### Requirement: 管理 source の削除

`paperphone dav remove <uid|name>` は、paperphone が登録した source とそのキーリング項目だけを削除し、設定からもその source の参照を取り除かなければならない (SHALL)。GNOME 管理の source と存在しない UID は削除できない。

#### Scenario: 登録した CalDAV を消す

- **WHEN** paperphone 管理の source UID を `dav remove` に渡す
- **THEN** source とキーリング項目が削除され、`paperphone sources` から消える

#### Scenario: 存在しない UID を消す

- **WHEN** 存在しない UID を `dav remove` に渡す
- **THEN** 何も変更せず、終了コード2で終わる
