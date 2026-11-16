# Proposal

## Why

EDS 3.59.1（2026-01-02）で vCard を文字列化する API が `to_string(format)` から引数なしの `to_string()` に変わった。現行の `read_contacts` は引数付きの旧 API しか呼ばないため、新しい EDS では全連絡先が空文字列として読まれる。結果として `paperphone contacts list` は連絡先の数だけ空白行を出力し、冊子の連絡先枠も空のまま印刷される。

開発機には GNOME も EDS も無く、検証は EDS 3.52.3 のコンテナだけで行っていた。そのため新旧 API の分岐は出荷後に利用者の環境で初めて表面化した。

## What Changes

- vCard の文字列化を新旧両方の API に対応させる。引数なしの `to_string()` を先に試し、失敗したら旧 API の `to_string(1)`、続いて `to_string(0)` を試す。
- どの方法でも読めなかった連絡先は、標準エラーに警告を出して一覧と冊子から飛ばす。空の UID・名前・電話番号だけの行を出力しない。
- `contacts` 仕様の「連絡先の一覧」に、読めなかった連絡先を警告して飛ばす振る舞いを要求として加える。

今回の範囲外（別の変更で扱う）:

- `contacts list --verbose` が受け付けられるだけで何もしない件
- 電話番号が無い行に残る末尾のタブ
- vCard 4.0 の `TEL;VALUE=uri:tel:...` から `tel:` を剥がす正規化

## Capabilities

### New Capabilities

なし。

### Modified Capabilities

- `contacts`: 連絡先の一覧で、読み出せなかった連絡先を空行として出さず、警告して飛ばすことを要求に加える。

## Impact

- `src/paperphone/eds.py` の `read_contacts` と vCard 解析ヘルパー
- `tests/test_eds.py` と `tests/conftest.py` のフェイク（新旧 API の再現が必要）
- 間接的に冊子の連絡先パネル。連絡先が読めなくなると冊子も空になる
- 新しい EDS での実機確認が必要。開発機に EDS は無いため、コンテナまたは EDS 3.59 以降の環境で確かめる
