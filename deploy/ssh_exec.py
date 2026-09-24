"""Выполнить команду на удалённом сервере по SSH (пароль из env) со стримингом вывода.

Использование:
  python deploy/ssh_exec.py "команда"
  python deploy/ssh_exec.py --put localfile remotepath
  python deploy/ssh_exec.py --putdir localdir remotedir

Креды берутся из переменных окружения:
  DEPLOY_HOST, DEPLOY_PORT (по умолч. 22), DEPLOY_USER, DEPLOY_PASSWORD
"""
import os
import socket
import sys

import paramiko

# Консоль Windows (cp1251) не умеет часть символов из вывода docker/git — форсим UTF-8.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass


def _client() -> paramiko.SSHClient:
    host = os.environ["DEPLOY_HOST"]
    port = int(os.environ.get("DEPLOY_PORT", "22"))
    user = os.environ["DEPLOY_USER"]
    password = os.environ["DEPLOY_PASSWORD"]
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username=user, password=password, timeout=30, look_for_keys=False, allow_agent=False)
    return c


def _stream(chan) -> None:
    """Читать канал до EOF, а не до появления кода возврата.

    Код возврата готов раньше, чем долетает хвост вывода, поэтому выход по
    `exit_status_ready` молча терял конец (иногда весь вывод целиком).
    """
    grace = 0
    while True:
        try:
            chunk = chan.recv(4096)
        except socket.timeout:
            # Команда ещё работает и просто молчит. Но если она уже завершилась,
            # а данных нет две секунды подряд — EOF не придёт, выходим сами.
            if chan.exit_status_ready():
                grace += 1
                if grace >= 2:
                    return
            continue
        if not chunk:
            return
        grace = 0
        sys.stdout.write(chunk.decode("utf-8", "replace"))
        sys.stdout.flush()


def run(cmd: str) -> int:
    c = _client()
    try:
        transport = c.get_transport()
        chan = transport.open_session()
        # С pty stderr сливается в stdout — отдельный поток ошибок не читаем.
        chan.get_pty()
        chan.settimeout(1.0)
        chan.exec_command(cmd)
        _stream(chan)
        return chan.recv_exit_status()
    finally:
        c.close()


def put(local: str, remote: str) -> int:
    c = _client()
    try:
        sftp = c.open_sftp()
        sftp.put(local, remote)
        print(f"uploaded {local} -> {remote}")
        return 0
    finally:
        c.close()


def _mkdirs(sftp, remote_dir: str) -> None:
    parts = remote_dir.strip("/").split("/")
    path = ""
    for p in parts:
        path += "/" + p
        try:
            sftp.stat(path)
        except IOError:
            sftp.mkdir(path)


def putdir(local_dir: str, remote_dir: str) -> int:
    c = _client()
    try:
        sftp = c.open_sftp()
        _mkdirs(sftp, remote_dir)
        for root, dirs, files in os.walk(local_dir):
            rel = os.path.relpath(root, local_dir).replace("\\", "/")
            rdir = remote_dir if rel == "." else f"{remote_dir}/{rel}"
            _mkdirs(sftp, rdir)
            for f in files:
                lp = os.path.join(root, f)
                rp = f"{rdir}/{f}"
                sftp.put(lp, rp)
        print(f"uploaded dir {local_dir} -> {remote_dir}")
        return 0
    finally:
        c.close()


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: ssh_exec.py <cmd> | --put <local> <remote> | --putdir <local> <remote>", file=sys.stderr)
        return 2
    if sys.argv[1] == "--put":
        return put(sys.argv[2], sys.argv[3])
    if sys.argv[1] == "--putdir":
        return putdir(sys.argv[2], sys.argv[3])
    return run(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())
