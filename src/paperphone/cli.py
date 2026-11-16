from __future__ import annotations

import argparse
import datetime as dt
import getpass
import sys
from pathlib import Path

from . import __version__, dav, eds
from .config import Config, load_config, system_zone
from .davbackend import EdsDavBackend
from .errors import PaperphoneError, RuntimeFailure
from .generate import generate
from .paths import config_path
from .timeutil import output_path, parse_date, today

EPILOG = """\
生成した PDF は両面印刷し、地図ページを表にして半分に折り、
円と四角が重なるように折り畳んでください。天気は Open-Meteo、
地図は © OpenStreetMap contributors を使います。
"""


def _date_argument(value: str) -> dt.date:
    try:
        return parse_date(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", metavar="PATH", help="設定ファイルのパス")
    parser.add_argument("--verbose", action="store_true", help="source ごとの結果を表示する")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperphone",
        description="今日の冊子を A4 横向きの PDF に書き出す",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--date", type=_date_argument, metavar="YYYY-MM-DD", help="冊子の日付")
    parser.add_argument("--tz", metavar="ZONE", help="IANA のタイムゾーン名")
    parser.add_argument("--out", metavar="PATH", help="出力先の PDF")
    parser.add_argument("--no-map", action="store_true", help="地図ページを作らない")
    _add_common(parser)

    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="依存と設定を検査する")
    _add_common(doctor)
    doctor.add_argument("--out", metavar="PATH", help="出力先の確認に使うパス")

    subparsers.add_parser("sources", help="source を一覧する").add_argument(
        "--verbose", action="store_true"
    )

    dav_parser = subparsers.add_parser("dav", help="独自 CalDAV / CardDAV を管理する")
    dav_sub = dav_parser.add_subparsers(dest="dav_command", required=True)
    dav_add = dav_sub.add_parser("add", help="source を登録する")
    dav_add.add_argument("--kind", required=True, choices=dav.KINDS)
    dav_add.add_argument("--url", required=True)
    dav_add.add_argument("--name", required=True)
    dav_add.add_argument("--user", required=True)
    dav_add.add_argument("--adopt", action="store_true", help="登録済みの source を使う")
    dav_add.add_argument("--no-select", action="store_true", help="設定の選択に加えない")
    _add_common(dav_add)
    dav_remove = dav_sub.add_parser("remove", help="source を削除する")
    dav_remove.add_argument("target", help="UID または名前")
    _add_common(dav_remove)

    contacts = subparsers.add_parser("contacts", help="連絡先を一覧する")
    contacts_sub = contacts.add_subparsers(dest="contacts_command", required=True)
    contacts_list = contacts_sub.add_parser("list", help="連絡先を一覧する")
    contacts_list.add_argument("--query", metavar="TEXT", help="名前と電話番号の部分一致")
    _add_common(contacts_list)

    return parser


def _zone_for(args, config: Config):
    from .config import load_zone

    name = args.tz or config.timezone
    return load_zone(name) if name else system_zone()


def _generate(args) -> int:
    config = load_config(args.config, no_map=args.no_map)
    zone = _zone_for(args, config)
    date = args.date or today(zone)
    destination = output_path(args.out, date)
    path = generate(
        config,
        date=date,
        zone=zone,
        out=destination,
        no_map=args.no_map,
        verbose=args.verbose,
    )
    print(path)
    return 0


def _doctor(args) -> int:
    from .doctor import run_doctor

    out = Path(args.out).expanduser() if args.out else None
    config_file = Path(args.config).expanduser() if args.config else None
    return run_doctor(config_file=config_file, out=out)


def _sources(args) -> int:
    registry = eds.open_registry()
    credentials = eds.CredentialStore(registry)
    infos = eds.list_sources(registry, credentials)
    print("UID\t名前\t種類\t由来\t認証情報")
    for info in infos:
        origin = "GNOME" if info.origin == "gnome" else "paperphone"
        credentials = {"keyring": "keyring", "gnome": "GNOME", "none": "なし"}[
            info.credentials
        ]
        print(f"{info.uid}\t{info.name}\t{info.kind}\t{origin}\t{credentials}")
    if not infos:
        print("source がありません。GNOME の設定か `paperphone dav add` で追加してください。")
    return 0


def _contacts_list(args) -> int:
    registry = eds.open_registry()
    credentials = eds.CredentialStore(registry)
    infos = eds.list_sources(registry, credentials)
    query = (args.query or "").casefold()
    contacts = []
    for info in infos:
        if info.kind != "contacts" or not info.usable_credentials:
            continue
        source = eds.find_source(registry, info.uid)
        if source is None:
            continue
        try:
            contacts.extend(
                eds.read_contacts(
                    source,
                    warn=lambda message, name=info.name: print(
                        f"paperphone: 警告: {name}: {message}", file=sys.stderr
                    ),
                )
            )
        except Exception as exc:
            print(f"paperphone: 警告: {info.name}: {exc}", file=sys.stderr)
    if query:
        contacts = [
            contact
            for contact in contacts
            if query in contact.name.casefold() or query in contact.phone.casefold()
        ]
    contacts.sort(key=lambda contact: (contact.name.casefold(), contact.uid))
    print("UID\t名前\t電話番号")
    for contact in contacts:
        print(f"{contact.uid}\t{contact.name}\t{contact.phone}")
    return 0


def _password() -> str:
    try:
        return getpass.getpass("パスワード: ")
    except (EOFError, KeyboardInterrupt) as exc:
        raise RuntimeFailure("パスワードを取得できませんでした") from exc


def _dav_add(args) -> int:
    backend = EdsDavBackend()
    config_file = Path(args.config).expanduser() if args.config else config_path()
    uid = dav.add_source(
        backend,
        kind=args.kind,
        url=args.url,
        name=args.name,
        user=args.user,
        password_getter=_password,
        config_file=config_file,
        no_select=args.no_select,
        adopt=args.adopt,
    )
    print(uid)
    return 0


def _dav_remove(args) -> int:
    backend = EdsDavBackend()
    config_file = Path(args.config).expanduser() if args.config else config_path()
    uid = dav.remove_source(backend, args.target, config_file=config_file)
    print(uid)
    return 0


def _dispatch(args) -> int:
    if args.command == "doctor":
        return _doctor(args)
    if args.command == "sources":
        return _sources(args)
    if args.command == "contacts":
        return _contacts_list(args)
    if args.command == "dav":
        if args.dav_command == "add":
            return _dav_add(args)
        return _dav_remove(args)
    return _generate(args)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except PaperphoneError as exc:
        print(f"paperphone: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("paperphone: 中断しました", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 1
    except Exception as exc:
        print(f"paperphone: 予期しないエラー: {exc}", file=sys.stderr)
        return 1
