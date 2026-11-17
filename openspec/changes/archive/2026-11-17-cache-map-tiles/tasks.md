# Tasks

## 1. キャッシュ層

- [x] 1.1 `src/paperphone/tilecache.py` を追加し、URL の SHA-256 をファイル名にしたタイルとメタデータの読み書き、原子的な replace を実装して、パスに URL や座標が現れないテストを通す
- [x] 1.2 `Cache-Control` の `max-age` と `no-store` の解釈、ヘッダが無い場合の7日フォールバック、鮮度切れの判定を実装し、それぞれの単体テストを通す
- [x] 1.3 壊れたメタデータ・読めないタイルをキャッシュミスとして扱うテストを通す

## 2. 取得への組み込み

- [x] 2.1 `fetch_mosaic` が新鮮なキャッシュをネットワークなしで使うよう変更し、2回目の呼び出しでタイルリクエストが増えないテストを通す
- [x] 2.2 期限切れ時に `If-None-Match` を送り、304 で保存済みバイト列と新しい鮮度を使い、200 でタイルと ETag を差し替えるテストを通す
- [x] 2.3 キャッシュの読み書き失敗・破損時はネットワーク取得に落ち、期限切れタイルの取得失敗時は古いタイルを使わずに画像を省くテストを通す
- [x] 2.4 画像として開けないタイルはキャッシュに保存されないテストを通す

## 3. 統合確認

- [x] 3.1 `.venv/bin/pytest` と `.venv/bin/ruff check src tests` を通す
- [x] 3.2 実データで `XDG_CACHE_HOME` を一時ディレクトリに向けて PDF を生成し、タイルとメタデータが作られ、2回目も PDF が作られることを確認する（転送の有無は 2.1 のテストで担保）
- [x] 3.3 `openspec validate cache-map-tiles` を通す

## Workflow follow-up

- レビュー後に `openspec-archive-change` でアーカイブし、`openspec/specs/maps/spec.md` に delta を反映する。
- 実機の cron 実行で、キャッシュディレクトリが `~/.cache/paperphone/tiles` に作られることを確認する。
