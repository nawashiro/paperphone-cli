# Design

## Context

連絡先の読み出しは `eds.read_contacts()` が `EBookContacts.Contact` を vCard 文字列に変換し、`UID` / `FN` / `TEL` の行を自前で解析している。`docs/eds-source-notes.md` の実機スパイクで、`Contact.get_const()` は GI ではポインタが int で返るため使えず、vCard 文字列の解析が確実と判断した経緯がある。

問題は文字列化の API が EDS 3.59.1 で変わったことにある（経緯は proposal.md を参照）。旧 API は `to_string(format)`、新 API は引数なしの `to_string()` で、形式変換は `convert_to_string(version)` に分かれた。現行コードは旧 API しか呼ばないため、新しい EDS では変換が毎回例外になり、空の連絡先として扱われる。

テストは `tests/conftest.py` のフェイクで EDS を差し替えており、開発機に EDS は無い。フェイクの `FakeContact.to_string()` は引数に既定値を持つため、旧 API と新 API のどちらも呼べてしまい、この破綻を検出できなかった。

## Goals / Non-Goals

**Goals:**

- EDS 3.58 以前と 3.59 以降の両方で、同じ連絡先を同じ UID・名前・電話番号として読める
- 読み出せない連絡先が、一覧でも冊子でも空白の行として現れない
- 新しい EDS の実機が無くても、フェイクで新旧両方の API 形状を再現して回帰テストできる

**Non-Goals:**

- vCard 4.0 固有の値の正規化（`TEL;VALUE=uri:tel:...` の `tel:` 除去、エスケープ解除）
- `contacts list` の表示形式（末尾タブ、`--verbose` の扱い）
- EDS のバージョンを実行時に判定する仕組み

## Decisions

### 1. 変換 API は「呼んでみる」順で解決する

`to_string()` → `to_string(1)` → `to_string(0)` の順に試し、最初に成功した文字列を使う。例外は握り潰さず次の候補へ進み、全滅したら未変換として扱う。

- 代替案: `Contact.to_string.__doc__` や `inspect.signature` で引数の有無を判定する。GI のメソッドはバインディングの実装依存で、`__doc__` の形式はバージョンで変わる。壊れやすいので採らない。
- 代替案: EDS のバージョンを `gi` から取得して分岐する。typelib にバージョン番号を返す公開 API が無く、採れない。
- 旧 API の引数は int の `1`（3.0）と `0`（2.1）のままにする。`EBookContacts.VCardFormat` のメンバー名は 3.52 の `30` と将来の `VCARD_30` で異なり、名前で参照するとバージョン差で壊れる。有効な列挙値に対応する int は PyGObject が受理することを 3.52.3 と 3.56.2 で確認済み。

### 2. 変換結果の解析と、変換の実行を分ける

`_vcard_text(contact)` が文字列化だけを担い、`_vcard_fields(text)` が解析を担う。現行の `_vcard_fields(contact)` は両方を兼ねているため、フェイクで片方ずつ試せない。分けたうえで、`read_contacts` は「3つのフィールドがすべて空」の連絡先を飛ばす。変換に失敗した場合も、変換は成功したが該当行が無い場合も、同じ扱いにそろう。

### 3. 警告は呼び出し側に委ねる

`read_contacts` に省略可能な `warn` コールバックを足し、飛ばした件数を1回だけ通知する（例: `3 件の連絡先を読み出せませんでした`）。既定は `None` で、ライブラリ単体では標準出力・標準エラーに書かない。

- `generate._selected_contacts` は既存の `WarningCollector` を渡し、source 名を前置する
- `cli._contacts_list` は source 名を前置して標準エラーに出す
- 件数をまとめるのは、1件ごとに同じ警告を並べても利用者の役に立たないため

代替案として `read_contacts` が `(contacts, skipped)` を返す案は、2つの呼び出し元とテストの戻り値契約を変えるので採らない。

### 4. フェイクで新旧の API 形状を作り分ける

`tests/conftest.py` に、引数必須の `to_string(self, version)` を持つ旧 API 用フェイクと、引数なしの `to_string(self)` を持つ新 API 用フェイクを用意する。既存の `FakeContact` は引数に既定値があるため、新 API 経路しか通らない。旧 API の経路は引数必須のフェイクでしか再現できない。

## Risks / Trade-offs

- **将来 EDS が `to_string` を再び変える** → 呼び出しを3通り試す構造なので、引数なし・引数ありのどちらでも追随できる。全滅した場合は警告が出るため、無言で空にはならない
- **全滅時の警告が原因を特定しにくい** → まず source 名を前置し、必要なら `verbose` で詳細を出す余地を残す（今回は件数のみ）
- **`to_string()` が vCard 4.0 を返す環境で電話番号に `tel:` が付く** → 既知の範囲外。表示の正規化は別の変更で行う
- **変換に失敗した連絡先が冊子から消える** → `[sources].contacts` に UID が書かれていれば、既存の「連絡先が見つかりません」警告で利用者に伝わる
