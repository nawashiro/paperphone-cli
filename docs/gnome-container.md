# rootless Podman で GNOME / EDS を用意して検証する

開発機に GNOME が無くても、rootless Podman の中に Evolution Data Server（EDS）、
GNOME キーリング、Pango、Noto CJK、PyGObject を入れて、`paperphone` の
統合部分を検証できます。UI は不要です。実際にこのリポジトリのタスク
1.1・1.2・11.1〜11.3・11.5 の確認に使いました。

物理的な両面印刷と折り畳み（11.4）だけはコンテナでは代替できません。
GNOME Online Accounts の OAuth（Google など）もこの手順の対象外です。
CalDAV / CardDAV / VTODO は、ローカルの Radicale を相手に検証します。

## 1. イメージ

```dockerfile
FROM docker.io/library/ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-gi python3-venv python3-pip \
    evolution-data-server evolution-data-server-common \
    gir1.2-edataserver-1.2 gir1.2-ecal-2.0 gir1.2-ebook-1.2 \
    gir1.2-ebookcontacts-1.2 gir1.2-ical-3.0 \
    gnome-keyring libsecret-tools dbus dbus-x11 libglib2.0-bin \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
    libfontconfig1 libcairo2 fonts-noto-cjk tzdata ca-certificates curl \
    procps ripgrep systemd \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m venv --system-site-packages /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
       weasyprint pillow httpx tomlkit pypdf pytest respx ruff radicale
```

```sh
podman build -t paperphone-gnome .
podman run --rm -v "$PWD:/src:Z" paperphone-gnome \
  dbus-run-session -- python3 -c 'import gi; gi.require_version("EDataServer","1.2"); print("ok")'
```

## 2. セッションバス・キーリング・Radicale

`dbus-run-session` の中で、キーリングを解錠し、Radicale を起動します。
Radicale は 1 オブジェクト 1 ファイルです。複数の VEVENT を 1 つの `.ics` に
入れると 400 になります。

```sh
export HOME=/root
export XDG_RUNTIME_DIR=/tmp/run
mkdir -p "$XDG_RUNTIME_DIR" "$HOME/.config/paperphone"
chmod 700 "$XDG_RUNTIME_DIR"
eval "$(printf %s testpass | gnome-keyring-daemon --unlock --components=secrets)"
```

Radicale のコレクションは、最初から作っておくと確実です。

```sh
BASE=/tmp/radicale/collections/collection-root/aki
mkdir -p "$BASE/cal" "$BASE/tasks" "$BASE/card"
echo '{"tag": "VCALENDAR"}'   > "$BASE/cal/.Radicale.props"
echo '{"tag": "VCALENDAR"}'   > "$BASE/tasks/.Radicale.props"
echo '{"tag": "VADDRESSBOOK"}' > "$BASE/card/.Radicale.props"
```

`[auth]` は htpasswd（plain）、`[rights]` は `owner_only`、`[storage]` は
`filesystem_folder` を上記にします。

## 3. 検証

doctor（11.1）:

```sh
cd /src
PYTHONPATH=src /opt/venv/bin/python -m paperphone doctor
# すべて ok で終了コード 0
```

source の登録・一覧・削除（11.2）:

```sh
printf 'secret\n' | PYTHONPATH=src /opt/venv/bin/python -m paperphone \
  dav add --kind caldav --url http://127.0.0.1:5232/aki/cal/ --name TestCal --user aki
PYTHONPATH=src /opt/venv/bin/python -m paperphone sources
PYTHONPATH=src /opt/venv/bin/python -m paperphone dav remove TestCal
```

このとき EDS が `~/.config/evolution/sources/<uid>.source` を書き、キーリングに
`org.gnome.Evolution.Data.Source` スキーマで保存します。実際のキーと属性は
[eds-source-notes.md](eds-source-notes.md) に記録しています。

## 4. systemd user timer（11.3・11.5）

rootless Podman で systemd を PID 1 にするには、イメージの systemd を直接
起動し、user manager に `XDG_RUNTIME_DIR` を渡します。

```sh
podman run -d --name paperphone-systemd --systemd=always \
  -v "$PWD:/src:Z" paperphone-gnome /usr/lib/systemd/systemd

podman exec paperphone-systemd sh -c '
  mkdir -p /run/user/0 /etc/systemd/system/user@0.service.d
  chmod 700 /run/user/0
  printf "[Service]\nEnvironment=XDG_RUNTIME_DIR=/run/user/0\n" \
    > /etc/systemd/system/user@0.service.d/runtime.conf
  systemctl daemon-reload
  systemctl start user@0.service
'
```

そのあと、コンテナ内でセッションバスを起動し、そのアドレスを
`systemctl --user set-environment DBUS_SESSION_BUS_ADDRESS=...` で user manager に
渡します。`paperphone.service` は oneshot、`paperphone.timer` は
`OnCalendar=*-*-* 07:00:00` と `OnActiveSec=5` にします。

```ini
[Service]
Type=oneshot
Environment=HOME=/root
Environment=XDG_RUNTIME_DIR=/run/user/0
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/dbus-...
Environment=PYTHONPATH=/src/src
WorkingDirectory=/work
ExecStart=/opt/venv/bin/python -m paperphone --date 2026-11-17 --out /work/timer.pdf
```

`systemctl --user start paperphone.timer` で 5 秒後に service が走り、PDF が
書き出されます。ジャーナルにパスワード入力待ちが出ないことを確認します。
Radicale を止めて同じ service をもう一度実行すると、EDS のキャッシュから
予定・連絡先・タスクを読んで終了コード 0 で PDF を書きます（11.5）。

## 制約

- 物理印刷と折り畳み（11.4）は検証できません。この変更では PDF の回転・
  座標・折り目までを完了条件とし、紙での最終確認は受け入れ時の確認に
  切り分けます。
- GOA の OAuth アカウントは対象外です。GNOME 管理 source の読み取り専用扱いと
  `dav remove` の拒否は、既存の `system-calendar` などの source で確認できます。
- rootless の systemd は環境依存です。`--systemd=always` と
  `/usr/lib/systemd/systemd`、`user@0.service` の drop-in が必要でした。
- テスト用のパスワード（`testpass` / `secret`）以外をコンテナに入れないでください。
