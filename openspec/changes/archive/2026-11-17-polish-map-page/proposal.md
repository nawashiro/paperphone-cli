# Proposal

## Why

地図ページは冊子の主役だが、現状は OSM ラスタを白黒化して黒い線を引いただけで、線の向きが分からず、細かい背景に経路が埋もれる。MapLibre 級のベクター化は Node とネイティブレンダラ、鍵なしでも SLA のないタイル配信に依存し、単一 venv・鍵なし・無人 cron という現在の運用を壊す。ラスタ＋Pillow の構成を維持したまま、印刷向けの cartography で経路と A/B を主役にする。

## What Changes

- 地図画像を白方向に8%薄め、背景のコントラストを下げる（L モードのまま）。
- 徒歩経路を白い縁取り（14px）＋黒い芯（6px）で描き、背景から浮かせる。
- 出発地と目的地を地図上に A/B の丸で示す。経路が取れない場合も地点だけで示す。
- 地図タイルが取れない場合は従来通り画像を省く（A/B は住所欄のみ）。
- 依存、設定キー、外部サービス、帰属表示は増やさない。
- **非目標**: MapLibre / ベクタータイル、300dpi 化、鍵付きラスタの README 案内、タイルキャッシュ（別 change）。

## Capabilities

### New Capabilities

なし。

### Modified Capabilities

- `maps`: 地図ページの内容と経路の描画。地図上 A/B、経路の白い縁取り、背景の抑制を要求に加える。

## Impact

- `src/paperphone/maps.py`: 背景処理、経路描画、A/B 描画。
- `tests/test_maps.py`: 画素ベースのテスト。
- `openspec/specs/maps/spec.md`: アーカイブ時に delta を反映。
- 設定・依存・PDF のページ構成は変わらない。
