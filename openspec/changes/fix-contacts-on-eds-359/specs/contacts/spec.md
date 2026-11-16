# Spec Delta

## MODIFIED Requirements

### Requirement: 連絡先の一覧

`paperphone contacts list [--query TEXT]` は、EDS のアドレス帳から連絡先の UID、名前、電話番号を一覧しなければならない (SHALL)。`--query` は名前と電話番号の部分一致で絞り込む。読み出せなかった連絡先は標準エラーに警告を出して飛ばし、UID・名前・電話番号がすべて空の行を出力してはならない (MUST NOT)。一覧の取得だけを行い、連絡先を変更してはならない (MUST NOT)。

#### Scenario: 連絡先を一覧する

- **WHEN** アドレス帳に連絡先がある状態で `paperphone contacts list` を実行する
- **THEN** 各連絡先の UID、名前、電話番号が表示される

#### Scenario: 名前で絞り込む

- **WHEN** `paperphone contacts list --query Aki` を実行する
- **THEN** 名前に Aki を含む連絡先だけが表示される

#### Scenario: 一致しない

- **WHEN** どの連絡先にも一致しない `--query` を指定する
- **THEN** 空の一覧が表示され、終了コード0で終わる

#### Scenario: 読めない連絡先

- **WHEN** アドレス帳に vCard として読み出せない連絡先が1件ある状態で `paperphone contacts list` を実行する
- **THEN** その連絡先について標準エラーに警告が出て一覧から飛ばされ、空白だけの行は表示されず、残りの連絡先は表示される
