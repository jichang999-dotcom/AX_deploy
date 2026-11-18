"""git-save 드라이브 보관 — GitHub 에 없는 파일(.env · 데이터 · 커밋에서 뺀 파일)을 구글 드라이브에 같은 폴더 구조로 둔다.
목적: 다른 PC 에서 git clone + --restore 로 그대로 세팅.
백업: python drive_sync.py <저장소 폴더> [--dry]          (증분 · 크기·수정시각 같으면 건너뜀 · 드라이브 파일은 지우지 않음)
복원: python drive_sync.py <저장소 폴더> --restore [--dry] (없는 파일만 받음 · 이미 있고 다르면 덮지 않고 conflict 로 보고)
공통: [--key GOOGLE_AUTH_DIR_PERSONAL] [--dest claude-backup] [--name <드라이브 폴더명, 기본 = 저장소 폴더명>]
마지막 줄 = 결과 JSON. 인증은 구글 API 매뉴얼로 만든 .env 키의 gdrive_shared.py 를 쓴다."""
import argparse, importlib.util, io, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

SKIP = {"node_modules", ".venv", "venv", "__pycache__", ".git", "chrome-profile", "profile"}  # 재설치 가능 · 로그인 세션
FOLDER = "application/vnd.google-apps.folder"


def untracked_files(root):
    """git 에 없는 파일 전부(무시된 것 + 커밋에서 뺀 것)."""
    out = subprocess.run(["git", "-C", root, "ls-files", "-o", "-z"], capture_output=True, check=True).stdout.decode("utf-8")
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


def ts(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(microsecond=0)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("root"); a.add_argument("--key", default="GOOGLE_AUTH_DIR_PERSONAL")
    a.add_argument("--dest", default="claude-backup"); a.add_argument("--name")
    a.add_argument("--restore", action="store_true"); a.add_argument("--dry", action="store_true")
    a = a.parse_args()
    root = Path(a.root).resolve()
    name = a.name or root.name
    svc = drive(a.key)
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

    def children(parent, nm=None, folder=False):
        q = "'%s' in parents and trashed=false" % parent
        if nm:
            q += " and name='%s'" % nm.replace("\\", "\\\\").replace("'", "\\'")
        if folder:
            q += " and mimeType='%s'" % FOLDER
        res, tok = [], None
        while True:
            r = svc.files().list(q=q, fields="nextPageToken,files(id,name,mimeType,size,modifiedTime)",
                                 pageSize=1000, pageToken=tok).execute()
            res += r["files"]; tok = r.get("nextPageToken")
            if not tok:
                return res

    cache = {}
    def folder(parent, nm, create):
        k = (parent, nm)
        if k not in cache:
            f = children(parent, nm, True) if parent else []
            if f:
                cache[k] = f[0]["id"]
            elif not create or a.dry or not parent:
                cache[k] = None
            else:
                cache[k] = svc.files().create(body={"name": nm, "parents": [parent], "mimeType": FOLDER},
                                              fields="id").execute()["id"]
        return cache[k]

    base = folder(folder("root", a.dest, not a.restore), name, not a.restore)
    done, same, conflict, errs = [], 0, [], []

    if a.restore:
        if not base:
            print(json.dumps({"error": "NO_BACKUP", "dest": f"{a.dest}/{name}"}, ensure_ascii=False)); sys.exit(3)
        stack = [(base, Path())]
        while stack:
            fid, rel = stack.pop()
            for f in children(fid):
                r = rel / f["name"]
                if f["mimeType"] == FOLDER:
                    stack.append((f["id"], r)); continue
                if f["mimeType"].startswith("application/vnd.google-apps"):
                    continue  # 구글 문서 · 시트는 파일이 아니라 받지 않음
                p = root / r
                try:
                    if p.exists():
                        if p.stat().st_size == int(f.get("size", -1)):
                            same += 1
                        else:
                            conflict.append(r.as_posix())
                        continue
                    done.append(r.as_posix())
                    if a.dry:
                        continue
                    p.parent.mkdir(parents=True, exist_ok=True)
                    with io.FileIO(p, "wb") as fh:
                        dl = MediaIoBaseDownload(fh, svc.files().get_media(fileId=f["id"]))
                        while not dl.next_chunk()[1]:
                            pass
                    t = ts(f["modifiedTime"]).timestamp(); os.utime(p, (t, t))  # 다음 백업 때 「같음」으로 보이게
                except Exception as e:
                    errs.append(f"{r.as_posix()}: {e}")
    else:
        for rel in untracked_files(str(root)):
            p = root / rel
            try:
                pid = base
                for d in Path(rel).parts[:-1]:
                    pid = folder(pid, d, True) if pid else None
                old = (children(pid, p.name) or [None])[0] if pid else None
                st = p.stat()
                mt = datetime.fromtimestamp(st.st_mtime, timezone.utc).replace(microsecond=0)
                if old and int(old.get("size", -1)) == st.st_size and ts(old["modifiedTime"]) >= mt:
                    same += 1; continue
                done.append(rel)
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

    print(json.dumps({"mode": "restore" if a.restore else "backup", "dest": f"{a.dest}/{name}", "dry": a.dry,
                      "files": done, "same": same, "conflict": conflict, "errors": errs}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
