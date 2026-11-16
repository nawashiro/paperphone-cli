# Spec Delta

## REMOVED Requirements

### Requirement: 出力方法の選択

**Reason**: CLI は PDF を書き出すだけであり、印刷・保存・折り方の選択画面を持たない。

**Migration**: `paperphone` を実行し、必要なら `lp` で印刷する。

### Requirement: 印刷

**Reason**: 印刷は OS の印刷コマンドに任せ、paperphone は関与しない。

**Migration**: 生成した PDF を `lp` などの印刷コマンドに渡す。

### Requirement: PDF の保存

**Reason**: PDF の書き出しは `pdf-output` が担う。

**Migration**: `--out` で出力先を指定する。未指定ならカレントディレクトリに `paperphone-YYYY-MM-DD.pdf` が作られる。

### Requirement: 出力前のデータ取得

**Reason**: データ取得は生成処理の一部として常に行われ、画面の読み込み表示も無い。

**Migration**: 不要。取得に失敗した source は警告付きで飛ばされる。

### Requirement: 折り方の説明

**Reason**: CLI には説明画面が無い。

**Migration**: 折り方は README に書き、冊子の折り位置の目印を使う。
