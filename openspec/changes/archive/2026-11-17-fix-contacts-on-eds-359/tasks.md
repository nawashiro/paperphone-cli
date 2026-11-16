# Tasks

## 1. vCard 変換の互換化

- [x] 1.1 `eds.py` に `_vcard_text(contact)` を追加し、`to_string()` → `to_string(1)` → `to_string(0)` の順に試して最初に成功した文字列を返す。`_vcard_fields` は文字列を受け取る形に変える。検証: `.venv/bin/pytest tests/test_eds.py` が通り、既存の UID・名前・電話番号の抽出結果が変わらない
- [x] 1.2 `read_contacts` に省略可能な `warn` コールバックを追加し、UID・名前・電話番号がすべて空になった連絡先を結果から飛ばして件数を1回通知する。既定の `warn=None` では何も出力しない。検証: 変換が失敗するフェイクで結果が空になり、`warn` が1回だけ呼ばれるテストが通る
- [x] 1.3 `docs/eds-source-notes.md` に EDS 3.59.1 の API 変更（`to_string()` が引数なしになり、形式変換は `convert_to_string(version)` に分かれた）と、新旧どちらも呼べるようにした理由を追記する。検証: 追記した記述どおりに `_vcard_text` の候補順が実装されていることを読み合わせる

## 2. 呼び出し側の警告

- [x] 2.1 `generate._selected_contacts` が `read_contacts` に `WarningCollector` を渡し、警告に source 名を前置する。検証: `tests/test_generate.py` の既存テストが通り、読み出せない連絡先がある場合に警告が標準エラーへ出る新規テストが通る
- [x] 2.2 `cli._contacts_list` が `read_contacts` に source 名付きの警告出力を渡す。検証: 読み出せない連絡先がある状態で `paperphone contacts list` が終了コード0で終わり、標準出力に空白だけの行が無く、標準エラーに警告が出ることを `capsys` で確認する
- [x] 2.3 電話番号が無い連絡先と、`--query` で一致しない連絡先の既存の振る舞いが変わっていないことを確認する。検証: `tests/test_sources_cli.py` が通る

## 3. 新旧 API のフェイクと回帰

- [x] 3.1 `tests/conftest.py` に、引数必須の `to_string(self, version)` を持つ旧 API 用フェイクと、引数なしの `to_string(self)` を持つ新 API 用フェイクを用意する。検証: どちらのフェイクでも `read_contacts` が同じ UID・名前・電話番号を返すテストが通る
- [x] 3.2 3つすべての呼び出しが失敗するフェイクで、`read_contacts` が空の一覧を返し、`warn` に件数が渡ることを確認する。検証: `tests/test_eds.py` の新規テストが通る
- [x] 3.3 `paperphone contacts list` の出力に、Uid・名前・電話番号がすべて空の行が現れないことを確認する。検証: `tests/test_sources_cli.py` の新規テストで標準出力を検査し、`"\t\t"` だけの行が無いことを確かめる

## 4. 実機と静的検査

- [x] 4.1 EDS 3.59 以降の環境（利用者の GNOME 環境、または新しい EDS を入れたコンテナ）で `paperphone contacts list` を実行し、連絡先の UID・名前・電話番号が表示され、空白行が出ないことを確認する。検証: 実行結果の目視。開発機に新しい EDS が無い場合は利用者に確認を依頼する
- [x] 4.2 EDS 3.52.3 のコンテナ（`docs/gnome-container.md`）で、従来どおり連絡先が読めることを確認する。検証: Radicale に連絡先を置いて `paperphone contacts list` の出力を確認する
- [x] 4.3 `.venv/bin/ruff check src tests` と `.venv/bin/pytest` を実行し、警告も失敗も無いことを確認する

## Workflow follow-up

- レビュー後に `openspec-archive-change` で `openspec/specs/contacts/spec.md` を更新し、変更を `openspec/changes/archive/` へ移す。
