---
name: git-save
description: 지금 폴더의 바뀐 코드를 비밀값·개인정보 검사 후 git 커밋하고 GitHub 비공개 저장소로 push 하고, git 에 안 넣는 .env·데이터 파일은 연결된 구글 드라이브(API 또는 MCP)에 보관한다. 사용자가 "save", "git-save", "저장해줘", "백업해줘", "커밋 푸시 해줘", "깃허브에 올려줘"를 말할 때 트리거한다. 에디터의 파일 저장·코드 안의 save() 함수 이야기에는 쓰지 않는다.
argument-hint: "[커밋 메모]"
---

# git-save — 코드는 GitHub, .env · 데이터는 구글 드라이브

지금 열린 폴더 하나를 대상으로 한다. 순서대로 하고, **멈추라는 곳에서는 사용자 답을 받은 뒤** 진행한다.

## 1. 준비 확인
- `git --version` 이 안 되면 멈추고 「Git for Windows 를 먼저 설치하세요」라고 안내한다.
- `git rev-parse --is-inside-work-tree` 가 실패하면(저장소 아님) **멈추고 묻는다**: 「이 폴더를 git 저장소로 만들까요?」 → 예면 `git init -b main`.
- `git config user.name` · `user.email` 이 비어 있으면 **묻고** 그 저장소에만(`git config` , `--global` 아님) 설정한다.

## 2. .gitignore 기본 줄
`.gitignore` 에 아래 줄이 없으면 맨 끝에 추가한다(있는 줄은 건드리지 않는다).
```
# git-save 기본
.env*
*token*.json
*credential*.json
client_secret*
*.pem
*.key
node_modules/
__pycache__/
.venv/
*.bak
# 데이터 = 드라이브로
*.csv
*.xlsx
*.xls
*.xlsm
*.hwp
*.docx
*.pptx
*.pdf
*.zip
data/
out/
output/
```
이미 커밋된 데이터 파일은 건드리지 않는다(빼려면 사용자에게 묻고 `git rm --cached`).

## 3. 검사 (커밋 전, 반드시)
`git add -A` 후 `git diff --cached --name-only` 로 올라갈 파일을 본다. 아래 중 하나라도 걸리면 **그 파일을 `git restore --staged <파일>` 로 빼고, 목록을 보여 주며 멈추고 묻는다**(.gitignore 에 넣을지 · 이번만 뺄지).

| 검사 | 기준 |
|---|---|
| 큰 파일 | 5MB 초과 |
| 이름 | `.env` · `token` · `credential` · `secret` · `cookie` · `.pem` · `.key` 가 들어간 파일(.py · .md 제외) |
| 내용 — 키·토큰 | `gh[pousr]_` · `github_pat_` · `xox[baprs]-` · `hooks.slack.com/services/` · `AIza` · `sk-` 뒤 30자 이상 · `-----BEGIN ... PRIVATE KEY-----` · `eyJ...` 세 토막(JWT) · `...apps.googleusercontent.com` |
| 내용 — 비밀번호 | `password`/`pwd` 에 따옴표 값이 박힘 · `://아이디:비번@` 꼴 DB 주소 |
| 내용 — 개인정보 | 휴대전화 `01X-XXXX-XXXX` · 주민번호 `XXXXXX-[1-4]XXXXXX` · 회원·학생 번호처럼 보이는 같은 꼴 번호가 3건 이상 |

내용 검사는 `git grep --cached -nIE "<패턴>"` 으로 한다. 걸린 줄은 값을 가리고(앞 4자만) 보여 준다.

## 4. 커밋
걸린 것이 없거나 정리된 뒤 `git commit -m "save: <YYYY-MM-DD> <인자 메모>"`. 바뀐 것이 없으면 「커밋할 변경 없음」으로 5단계(push 안 된 커밋 확인)만 한다.

## 5. push
- `git remote get-url origin` 이 없으면 **멈추고 묻는다**: 저장소 이름(영문 · 기본 = 폴더명). 공개 여부는 **비공개가 기본**이며, 공개는 사용자가 직접 말할 때만.
  - `gh auth status` 가 되면 `gh repo create <이름> --private --source . --remote origin`.
  - 아니면 「github.com/new 에서 그 이름으로 **비공개 · README 없이** 빈 저장소를 만들고 주소를 붙여 주세요」라고 안내 → 받은 주소로 `git remote add origin <주소>`.
- `git push -u origin HEAD`. 처음이면 브라우저 GitHub 로그인 창이 뜬다고 미리 알려 준다.
- 거절(rejected)되면 force 하지 말고 멈추고 보고한다.

## 6. 드라이브 보관 (.env · 데이터)
git 이 무시하는 파일(`git ls-files -oi --exclude-standard` — .env · 데이터 · 검사에서 .gitignore 로 보낸 파일)을 드라이브 `claude-backup/<폴더명>/` 에 같은 구조로 올린다. `node_modules` · `.venv` · `__pycache__` · 브라우저 로그인 프로필은 올리지 않는다. **드라이브 파일은 지우지 않는다.** 아래 순서로 **이미 연결된 것을 찾아** 쓴다. 새로 세팅하지 않는다.

1. **구글 API** — **`.env` 를 직접 열지 않는다**(키 찾기는 스크립트가 한다 · 상위 폴더 `.env` 와 환경변수까지 본다). 저장소 폴더에서 이 스킬 폴더의 `drive_sync.py` 를 먼저 `--dry` 로 돌린다:
   `python "<이 스킬 폴더>/drive_sync.py" . --dry` (기본 = 개인 `GOOGLE_AUTH_DIR_PERSONAL`) → 올릴 목록을 보여 주고 → `--dry` 빼고 실행.
   - `NO_AUTH` 면 `--key GOOGLE_AUTH_DIR --dry` 로 다시 본다. 되면 **회사 계정이라고 알리고 올릴지 묻는다.**
   - 둘 다 `NO_AUTH` 거나 `ModuleNotFoundError` 면 2번으로. `python` 이 없으면 `py -3`.
2. **MCP 구글 드라이브 커넥터** — `create_file` 이 있는 구글 드라이브 도구가 보이면 쓴다. 폴더는 `search_files` 로 찾고 없으면 폴더로 만든다. 파일은 **내용을 읽어 붙이지 말고** 파일 참조로 올린다: `base64Content` = `sha256:<sha256 소문자 64자>:<절대 경로, / 구분>` (해시는 `certutil -hashfile <파일> SHA256` 또는 `sha256sum`), `disableConversionToGoogleType: true`. 같은 이름이 이미 있으면 크기가 다를 때만 옛 파일 제목 끝에 `.old_<YYYYMMDD>` 를 붙이고(update_file) 새로 올린다. 20개가 넘으면 「API 가 빠르다」고 알리고 진행할지 묻는다. **커넥터는 계정을 고를 수 없다** — 첫 파일을 올리기 전에 폴더 검색 결과의 owner(계정)를 보여 주고 「이 계정 드라이브에 .env · 데이터를 올릴까요?」 확인받는다.
3. 둘 다 없으면 건너뛰고 「드라이브 연결 없음 — 구글 API 매뉴얼이나 claude.ai Google Drive 커넥터를 연결하면 다음부터 보관」이라고 보고한다.

.env 는 **비공개 내 드라이브에만** 둔다. 공유 링크를 만들지 않는다.

## 7. 보고
| 폴더 | 커밋 | push | 드라이브 | 비고 |
|---|---|---|---|---|

드라이브 칸 = 「API(개인) 3개 올림 · 12개 같음」 / 「MCP 2개」 / 「연결 없음」. 비고에는 검사에서 뺀 파일 · 새로 만든 저장소 주소 · 드라이브 오류를 적는다.

## 하지 말 것
- `git push --force` · `--no-verify` · 저장소 공개 전환을 묻지 않고 하기.
- `.env` · 토큰 · 키 파일을 커밋하기, 걸린 값이나 .env 내용을 화면에 출력하기.
- 드라이브 파일 삭제 · 휴지통 · 공유 설정 바꾸기, 구글 API 를 새로 세팅하기.
- `--global` git 설정 바꾸기, 이 폴더 밖 파일 건드리기.
