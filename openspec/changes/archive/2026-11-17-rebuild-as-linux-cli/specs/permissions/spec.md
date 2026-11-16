# Spec Delta

## REMOVED Requirements

### Requirement: 機能ごとの権限要求

**Reason**: CLI には実行時権限の要求が無く、データへのアクセスは GNOME の D-Bus とキーリングが担う。

**Migration**: `paperphone doctor` で EDS・D-Bus・キーリングの状態を確認する。

### Requirement: 拒否後の理由表示

**Reason**: 権限ダイアログが無いため、拒否後の説明画面も無い。

**Migration**: 取得に失敗した source は警告として標準エラーに出る。

### Requirement: 許可後の続行

**Reason**: 権限要求そのものが無い。

**Migration**: 何もしなくてよい。source が読めればそのまま冊子に使われる。

### Requirement: 権限を必要としない項目

**Reason**: CLI ではすべての項目が同じ実行経路で扱われ、権限の有無で分ける必要が無い。

**Migration**: 不要。
