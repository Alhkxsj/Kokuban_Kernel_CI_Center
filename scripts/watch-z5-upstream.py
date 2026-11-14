#!/usr/bin/env python3
import json
import subprocess
import sys

MARKER = "<!-- z5-upstream-watch -->"
WATCH_REPO = "Alhkxsj/Kokuban_Kernel_CI_Center"
WATCHES = [
    {
        "key": "source-main",
        "label": "Z5 main / LKM",
        "fork_repo": "Alhkxsj/android_kernel_samsung_sm8550_Z5",
        "upstream_repo": "YuzakiKokuban/android_kernel_samsung_sm8550_Z5",
        "branch": "main",
        "commits": "https://github.com/YuzakiKokuban/android_kernel_samsung_sm8550_Z5/commits/main",
    },
    {
        "key": "source-bakasu",
        "label": "Z5 bakasu / BakaSU",
        "fork_repo": "Alhkxsj/android_kernel_samsung_sm8550_Z5",
        "upstream_repo": "YuzakiKokuban/android_kernel_samsung_sm8550_Z5",
        "branch": "bakasu",
        "commits": "https://github.com/YuzakiKokuban/android_kernel_samsung_sm8550_Z5/commits/bakasu",
    },
    {
        "key": "ci-main",
        "label": "CI Center main",
        "fork_repo": "Alhkxsj/Kokuban_Kernel_CI_Center",
        "upstream_repo": "YuzakiKokuban/Kokuban_Kernel_CI_Center",
        "branch": "main",
        "commits": "https://github.com/YuzakiKokuban/Kokuban_Kernel_CI_Center/commits/main",
    },
]


def run(args, capture=True):
    result = subprocess.run(args, text=True, capture_output=capture, check=True)
    return result.stdout.strip() if capture else ""


def history(repo, branch):
    commits = []
    for page in range(1, 11):
        batch = json.loads(run([
            "gh", "api", f"repos/{repo}/commits?sha={branch}&per_page=100&page={page}"
        ]))
        commits.extend(batch)
        if len(batch) < 100:
            break
    return commits


def collect():
    data = []
    for watch in WATCHES:
        item = dict(watch)
        fork_history = history(item["fork_repo"], item["branch"])
        upstream_history = history(item["upstream_repo"], item["branch"])
        upstream_shas = {commit["sha"] for commit in upstream_history}
        common = next(
            (commit["sha"] for commit in fork_history if commit["sha"] in upstream_shas),
            None,
        )
        if common is None:
            raise RuntimeError(f'No common ancestor found for {item["label"]}')

        pending = []
        for commit in upstream_history:
            if commit["sha"] == common:
                break
            pending.append(commit)

        item["sha"] = upstream_history[0]["sha"]
        item["count"] = len(pending)
        item["compare"] = (
            f'https://github.com/{item["upstream_repo"]}/compare/{common}...{item["branch"]}'
        )
        item["log"] = "\n".join(
            f'{commit["sha"][:12]} {commit["commit"]["message"].splitlines()[0]}'
            for commit in pending[:15]
        )
        data.append(item)
    return data


def issue_state(body):
    state = {}
    for line in body.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in {"source-main", "source-bakasu", "ci-main", "pending"}:
            state[key] = value.strip()
    return state


def find_issue():
    output = run([
        "gh", "issue", "list", "--repo", WATCH_REPO, "--state", "all", "--limit", "100", "--json",
        "number,state,title,body,url,updatedAt",
    ])
    candidates = [issue for issue in json.loads(output) if MARKER in issue["body"]]
    if not candidates:
        return None
    open_issues = [issue for issue in candidates if issue["state"] == "OPEN"]
    return open_issues[0] if open_issues else candidates[0]


def dashboard(data):
    lines = [
        MARKER,
        "此 Issue 由 `Watch Z5 Upstream` 自动维护，用于显示上游是否有新提交。",
        "",
        f'pending={1 if any(item["count"] > 0 for item in data) else 0}',
    ]
    for item in data:
        lines.append(f'{item["key"]}={item["sha"]}')
    lines.extend([
        "",
        "## 当前状态",
        "",
        "| 分支 | 待同步提交 | 上游最新提交 | 比较链接 |",
        "| --- | ---: | --- | --- |",
    ])
    for item in data:
        lines.append(
            f'| {item["label"]} | {item["count"]} | `{item["sha"][:12]}` | [查看差异]({item["compare"]}) |'
        )
    lines.extend([
        "",
        "只有检测到新的上游 SHA 时才会在此 Issue 下新增评论，不会按周期重复提醒。",
        "同步前请检查冲突、DroidSpaces 配置和 kABI 基线，不建议直接强制合并。",
        "",
        "[手动检查上游](https://github.com/Alhkxsj/Kokuban_Kernel_CI_Center/actions/workflows/watch-z5-upstream.yml)",
    ])
    for item in data:
        if item["log"]:
            lines.extend([
                "",
                f'<details><summary>{item["label"]} 待同步提交</summary>',
                "",
                "```text",
                item["log"],
                "```",
                "</details>",
            ])
    return "\n".join(lines)


def changes(data):
    lines = ["## 检测到上游新提交", ""]
    for item in data:
        lines.extend([
            f'### {item["label"]}',
            "",
            f'- 待同步：**{item["count"]} 个提交**',
            f'- 最新：`{item["sha"][:12]}`',
            f'- [比较差异]({item["compare"]})',
            f'- [上游提交列表]({item["commits"]})',
            "",
        ])
        if item["log"]:
            lines.extend(["```text", item["log"], "```", ""])
    lines.extend([
        "同步后请重新运行构建，确认最终配置以及 kABI 的 **0 CRC mismatch、0 missing**。",
    ])
    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv
    data = collect()
    issue = find_issue()
    previous = issue_state(issue["body"]) if issue else {}
    changed = [
        item for item in data
        if item["count"] > 0 and previous.get(item["key"]) != item["sha"]
    ]
    pending = any(item["count"] > 0 for item in data)
    issue_open = bool(issue and issue["state"] == "OPEN")

    if dry_run:
        print(json.dumps({
            "current": [{
                "branch": item["label"],
                "pending": item["count"],
                "sha": item["sha"],
            } for item in data],
            "issue": None if not issue else {"number": issue["number"], "state": issue["state"]},
            "changed": [item["key"] for item in changed],
            "action": (
                "create_dashboard" if not issue_open and (not issue or changed)
                else "comment_and_update" if issue_open and changed
                else "mark_synced" if issue_open and not pending and previous.get("pending") == "1"
                else "none"
            ),
        }, ensure_ascii=False, indent=2))
        return

    if not issue_open:
        if not issue or changed:
            url = run([
                "gh", "issue", "create", "--repo", WATCH_REPO,
                "--title", "[Upstream] Z5 上游更新监视",
                "--body", dashboard(data),
            ])
            print(url)
        return

    number = str(issue["number"])
    if changed:
        run(["gh", "issue", "comment", number, "--repo", WATCH_REPO, "--body", changes(changed)])
        run(["gh", "issue", "edit", number, "--repo", WATCH_REPO, "--body", dashboard(data)])
        print(f'Updated issue #{number}: {len(changed)} branch(es) changed')
        return

    if not pending and previous.get("pending") == "1":
        run([
            "gh", "issue", "comment", number, "--repo", WATCH_REPO,
            "--body", "当前监视的上游分支均已同步，没有待同步提交。",
        ])
        run(["gh", "issue", "edit", number, "--repo", WATCH_REPO, "--body", dashboard(data)])
        print(f'Marked issue #{number} as synchronized')
        return

    print(f'No upstream changes detected (issue #{number})')


if __name__ == "__main__":
    main()
