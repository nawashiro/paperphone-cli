# contacts Specification

## Purpose

設定ファイルの `[sources].contacts` に並べた相手を、名前と電話番号を添えて冊子の連絡先枠に印刷する能力。選んだ相手は設定に残り、次の冊子でもそのまま使える。

## Requirements

### Requirement: 連絡先の選択

設定の `[sources].contacts` に列挙した連絡先 UID を冊子に載せなければならない (SHALL)。最大7件とし、8件以上が書かれている場合は設定エラーとして終了コード2で拒否する。UID が見つからない連絡先は警告を出して飛ばす。

#### Scenario: 3人を選ぶ

- **WHEN** `[sources].contacts` に3つの UID を書いて生成する
- **THEN** 3人が連絡先の枠に含まれる

#### Scenario: 7人を超える

- **WHEN** `[sources].contacts` に8つの UID を書いて実行する
- **THEN** 終了コード2で終わり、PDF は書き出されない

#### Scenario: 見つからない UID

- **WHEN** 削除済みの連絡先の UID を書いて生成する
- **THEN** 警告が出てその相手は飛ばされ、残りの相手で PDF が書き出される

### Requirement: 連絡先の一覧

`paperphone contacts list [--query TEXT]` は、EDS のアドレス帳から連絡先の UID、名前、電話番号を一覧しなければならない (SHALL)。`--query` は名前と電話番号の部分一致で絞り込む。一覧の取得だけを行い、連絡先を変更してはならない (MUST NOT)。

#### Scenario: 連絡先を一覧する

- **WHEN** アドレス帳に連絡先がある状態で `paperphone contacts list` を実行する
- **THEN** 各連絡先の UID、名前、電話番号が表示される

#### Scenario: 名前で絞り込む

- **WHEN** `paperphone contacts list --query Aki` を実行する
- **THEN** 名前に Aki を含む連絡先だけが表示される

#### Scenario: 一致しない

- **WHEN** どの連絡先にも一致しない `--query` を指定する
- **THEN** 空の一覧が表示され、終了コード0で終わる

### Requirement: 選んだ連絡先の保存

選んだ連絡先は設定ファイルに残り、次回の実行でも同じ相手が使われ、名前の昇順で並ばなければならない (SHALL)。

#### Scenario: アプリを開き直す

- **WHEN** 連絡先を3人選んだ設定で冊子を生成し、翌日もう一度実行する
- **THEN** 同じ3人が名前順で連絡先の枠に印刷される

### Requirement: 連絡先の印刷内容

連絡先の枠には「CONTACTS」の見出しに続けて、相手ごとに大文字の名前と電話番号を印刷しなければならない (SHALL)。電話番号が無い相手は名前だけを印刷する。相手が1人も選ばれていない場合は見出しだけを印刷する。

#### Scenario: 連絡先を印刷する

- **WHEN** 「Aki Tanaka」と番号を選んで生成する
- **THEN** 連絡先の枠に「AKI TANAKA」と電話番号が並んで印刷される

#### Scenario: 電話番号が無い

- **WHEN** 電話番号を持たない連絡先を選んで生成する
- **THEN** その相手は名前だけが印刷され、冊子は完成する

#### Scenario: 連絡先を選ばずに項目だけ選ぶ

- **WHEN** 連絡先の項目だけを有効にし、相手を1人も選んでいない
- **THEN** 連絡先の枠には「CONTACTS」の見出しだけが印刷される
