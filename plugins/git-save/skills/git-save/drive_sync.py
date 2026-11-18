"""git-save 드라이브 보관 — git 이 무시하는 파일(.env · 데이터)을 구글 드라이브에 같은 폴더 구조로 올린다.
증분(크기 · 수정 시각이 같으면 건너뜀) · 드라이브 파일은 지우지 않는다.
사용: python drive_sync.py <저장소 폴더> [--key GOOGLE_AUTH_DIR_PERSONAL] [--dest claude-backup] [--dry]
마지막 줄 = 결과 JSON. 인증은 구글 API 매뉴얼로 만든 .env 키의 gdrive_shared.py 를 쓴다."""
import argparse, importlib.util, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

SKIP = {"node_modules", ".venv", "venv", "__pycache__", ".git", "chrome-profile", "profile"}  # 재설치 가능 · 로그인 세션


def ignored_files(root):
    out = subprocess.run(["git", "-C", root, "ls-files", "-oi", "--exclude-standard", "-z"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    return [f for f in out.split("\0") if f and not (set(Path(f).parts[:-1]) & SKIP) and ".bak" not in Path(f).suffix]


def drive(key):
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
    d = os.environ.get(key)
    if not d or not Path(d, "gdrive_shared.py").exists():
        print(json.dumps({"error": "NO_AUTH", "key": key}, ensure_ascii=False)); sys.exit(2)
    s = importlib.util.spec_from_file_location("gdrive_shared_gitsave", Path(d, "gdrive_shared.py"))
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m.drive_service()


def main():
    a = argparse.ArgumentParser()
    a.add_argument("root"); a.add_argument("--key", default="GOOGLE_AUTH_DIR_PERSONAL")
    a.add_argument("--dest", default="claude-backup"); a.add_argument("--dry", action="store_true")
    a = a.parse_args()
    root = Path(a.root).resolve()
    files = ignored_files(str(root))
    svc = drive(a.key)
    from googleapiclient.http import MediaFileUpload

    def child(parent, name, folder=False):
        q = "name='%s' and '%s' in parents and trashed=false" % (name.replace("\\", "\\\\").replace("'", "\\'"), parent)
        if folder:
            q += " and mimeType='application/vnd.google-apps.folder'"
        r = svc.files().list(q=q, fields="files(id,size,modifiedTime)", pageSize=1).execute()["files"]
        return r[0] if r else None

    cache = {}
    def folder(parent, name):
        k = (parent, name)
        if k not in cache:
            f = child(parent, name, True) if parent else None
            if f:
                cache[k] = f["id"]
            elif a.dry or not parent:
                cache[k] = None
            else:
                cache[k] = svc.files().create(body={"name": name, "parents": [parent],
                                              "mimeType": "application/vnd.google-apps.folder"}, fields="id").execute()["id"]
        return cache[k]

    base = folder(folder("root", a.dest), root.name)
    up, same, errs = [], 0, []
    for rel in files:
        p = root / rel
        try:
            pid = base
            for d in Path(rel).parts[:-1]:
                pid = folder(pid, d)
            old = child(pid, p.name) if pid else None
            st = p.stat()
            mt = datetime.fromtimestamp(st.st_mtime, timezone.utc).replace(microsecond=0)
            if old and int(old.get("size", -1)) == st.st_size and \
                    datetime.fromisoformat(old["modifiedTime"].replace("Z", "+00:00")).replace(microsecond=0) >= mt:
                same += 1; continue
            up.append(rel)
            if a.dry:
                continue
            media = MediaFileUpload(str(p), mimetype="application/octet-stream", resumable=st.st_size > 5 * 2**20)
            body = {"modifiedTime": mt.isoformat().replace("+00:00", "Z")}
            if old:
                svc.files().update(fileId=old["id"], body=body, media_body=media).execute()
            else:
                svc.files().create(body={**body, "name": p.name, "parents": [pid]}, media_body=media).execute()
        except Exception as e:  # 한 파일 실패가 나머지를 막지 않게
            errs.append(f"{rel}: {e}")
    print(json.dumps({"dest": f"{a.dest}/{root.name}", "dry": a.dry, "upload": up, "same": same, "errors": errs},
                     ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
