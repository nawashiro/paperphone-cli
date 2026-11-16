#!/bin/sh
set -eu

PREFIX="${PREFIX:-$HOME/.local}"
VENV="${PAPERPHONE_VENV:-$PREFIX/share/paperphone/venv}"
BIN="$PREFIX/bin"
SRC=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON="${PYTHON:-python3}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "python3 が見つかりません。Python 3.12 以上を入れてください。" >&2
    exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "Python 3.12 以上が必要です: $("$PYTHON" --version 2>&1)" >&2
    exit 1
fi

mkdir -p "$PREFIX/share/paperphone" "$BIN"

if [ ! -x "$VENV/bin/python" ]; then
    "$PYTHON" -m venv --system-site-packages "$VENV"
fi

if ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
    if ! "$VENV/bin/python" -m ensurepip --upgrade >/dev/null 2>&1; then
        echo "venv に pip がありません。python3-venv を入れてから再実行してください。" >&2
        echo "  Debian/Ubuntu: sudo apt install python3-venv python3-pip" >&2
        echo "  Fedora:        sudo dnf install python3-pip" >&2
        exit 1
    fi
fi

PIP_DISABLE_PIP_VERSION_CHECK=1 "$VENV/bin/python" -m pip install --upgrade "$SRC"

cat > "$BIN/paperphone" <<SHIM
#!/bin/sh
exec "$VENV/bin/python" -m paperphone "\$@"
SHIM
chmod +x "$BIN/paperphone"

"$BIN/paperphone" --version

echo
echo "次に依存関係と設定を確認してください:"
echo "  $BIN/paperphone doctor"
echo
echo "GNOME の GNOME ソフトウェア / Evolution でカレンダーと連絡先を用意し、"
echo "~/.config/paperphone/config.toml を書いてから paperphone を実行します。"
