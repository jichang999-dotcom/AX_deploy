# claude-skills

Claude Code 스킬 배포용 플러그인 마켓플레이스.

| 플러그인 | 하는 일 |
|---|---|
| `git-save` | 지금 폴더의 바뀐 코드를 비밀값·개인정보 검사 후 git 커밋 → GitHub 비공개 저장소 push |

## 설치 (Claude Code 안에서)
```
/plugin marketplace add jichang999-dotcom/claude-skills
/plugin install git-save@claude-skills
```
설치 후 Claude Code 를 다시 켜고 `save 해줘` 또는 `/git-save:git-save` 로 부른다.

## 업데이트 · 삭제
```
/plugin marketplace update claude-skills
/plugin uninstall git-save@claude-skills
```

이슈 · PR 은 받지 않는다.
