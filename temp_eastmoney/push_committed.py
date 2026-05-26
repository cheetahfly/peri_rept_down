"""
Push committed changes to GitHub via Git Data API (bypass GFW).
Usage: python push_committed.py [commit_sha]
  如果指定commit_sha则推送该commit，否则推送HEAD
"""
import os, json, base64, subprocess, sys, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not TOKEN:
    print("ERROR: Set GITHUB_TOKEN or GH_TOKEN environment variable")
    sys.exit(1)
OWNER = "cheetahfly"
REPO = "peri_rept_down"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "push-committed",
}


def api(method, url, data=None):
    body = json.dumps(data).encode() if data else None
    req = Request(url, data=body, method=method, headers=HEADERS)
    if body:
        req.add_header("Content-Type", "application/json")
    with urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def git_run(args):
    result = subprocess.run(["git"] + args, capture_output=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        try:
            err = result.stderr.decode("utf-8")[:200]
        except:
            err = str(result.stderr[:200])
        print(f"  git error: {err}")
        return None
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeDecodeError:
        try:
            return result.stdout.decode("gbk").strip()
        except:
            return result.stdout.decode("utf-8", errors="replace").strip()


def get_commit_files(commit_sha):
    """获取commit中新增/修改的文件列表 (不包含删除的)"""
    out = git_run(["diff-tree", "--no-commit-id", "-r", "--name-only", "-z", commit_sha])
    if not out:
        return []
    return [f for f in out.split("\0") if f]


def get_file_mode(commit_sha, filepath):
    """获取文件在commit中的mode"""
    out = git_run(["ls-tree", commit_sha, filepath])
    if out:
        parts = out.split()
        if len(parts) >= 3:
            return parts[0]  # e.g. "100644" or "100755"
    return "100644"


def create_blob(content):
    """创建blob，返回SHA"""
    if not content:
        payload = {"content": "", "encoding": "utf-8"}
    else:
        try:
            payload = {"content": content.decode("utf-8"), "encoding": "utf-8"}
        except UnicodeDecodeError:
            b64 = base64.b64encode(content).decode("ascii")
            payload = {"content": b64, "encoding": "base64"}
    data = api("POST", f"{API}/git/blobs", payload)
    return data["sha"]


def main():
    commit_sha = sys.argv[1] if len(sys.argv) > 1 else git_run(["rev-parse", "HEAD"])
    print(f"Pushing commit: {commit_sha[:12]}")

    # 1. Get commit info
    commit_data = git_run(["cat-file", "-p", commit_sha])
    lines = commit_data.split("\n")
    tree_sha = None
    parent_sha = None
    message_lines = []
    in_msg = False
    for line in lines:
        if line.startswith("tree "):
            tree_sha = line.split()[1]
        elif line.startswith("parent "):
            parent_sha = line.split()[1]
        elif not line:
            in_msg = True
        elif in_msg:
            message_lines.append(line)
    commit_msg = "\n".join(message_lines)
    print(f"  Tree: {tree_sha[:12]}, Parent: {parent_sha[:12] if parent_sha else 'none'}")

    # 2. Get all files in this commit's tree recursively
    files_out = git_run(["ls-tree", "-r", commit_sha])
    all_files = []
    for line in files_out.split("\n"):
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 4:
            mode, type_, sha = parts[0], parts[1], parts[2]
            path = " ".join(parts[3:])
            all_files.append((path, sha, mode))
    print(f"  Total files in commit: {len(all_files)}")

    # 3. Get changed files (only push what changed from parent)
    changed_files = get_commit_files(commit_sha)
    # Also include the tree entry for root
    print(f"  Changed files: {len(changed_files)}")

    # 4. Create blobs for changed files
    print(f"\nCreating blobs for {len(changed_files)} files...")
    blob_map = {}  # path -> (sha, mode)
    for idx, fpath in enumerate(changed_files, 1):
        full_path = os.path.join(REPO_ROOT, fpath)
        if not os.path.exists(full_path):
            print(f"  [{idx}/{len(changed_files)}] {fpath} -> DELETED")
            blob_map[fpath] = (None, "100644")
            continue
        with open(full_path, "rb") as f:
            content = f.read()
        sha = create_blob(content)
        mode = get_file_mode(commit_sha, fpath)
        blob_map[fpath] = (sha, mode)
        sz = len(content)
        print(f"  [{idx}/{len(changed_files)}] {fpath[:55]:55s} {sha[:8]} ({sz/1024:.0f}KB)")

    # 5. Build tree incrementally from base
    print(f"\nBuilding tree...")
    # Get remote HEAD and base tree
    try:
        remote_head = api("GET", f"{API}/git/refs/heads/main")
        remote_head_sha = remote_head["object"]["sha"]
        print(f"  Remote HEAD: {remote_head_sha[:12]}")
        remote_commit = api("GET", f"{API}/git/commits/{remote_head_sha}")
        base_tree_sha = remote_commit["tree"]["sha"]
    except:
        base_tree_sha = None
        print(f"  No remote HEAD, creating initial commit")

    # Build tree in batches
    batch_size = 50
    tree_items = []
    for path, (sha, mode) in sorted(blob_map.items()):
        if sha is None:
            tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": sha})
        else:
            tree_items.append({"path": path, "mode": mode, "type": "blob", "sha": sha})

    tree_sha_result = None
    for i in range(0, len(tree_items), batch_size):
        batch = tree_items[i:i+batch_size]
        payload = {"tree": batch}
        if tree_sha_result:
            payload["base_tree"] = tree_sha_result
        elif i == 0 and base_tree_sha:
            payload["base_tree"] = base_tree_sha
        result = api("POST", f"{API}/git/trees", payload)
        tree_sha_result = result["sha"]
        print(f"  Batch {i//batch_size+1}: tree={tree_sha_result[:12]} ({i+len(batch)}/{len(tree_items)})")
        time.sleep(0.5)

    if not tree_sha_result:
        print("  No tree created!")
        return

    # 6. Create commit
    print(f"\nCreating commit with message: {commit_msg[:60]}...")
    parents = [remote_head_sha] if base_tree_sha else []
    data = api("POST", f"{API}/git/commits", {
        "message": commit_msg,
        "tree": tree_sha_result,
        "parents": parents,
    })
    new_commit_sha = data["sha"]
    print(f"  Commit: {new_commit_sha[:12]}")

    # 7. Update ref
    print(f"\nUpdating refs/heads/main...")
    api("PATCH", f"{API}/git/refs/heads/main", {"sha": new_commit_sha, "force": False})
    print(f"  Done! Ref updated to {new_commit_sha[:12]}")
    print(f"  https://github.com/{OWNER}/{REPO}")


if __name__ == "__main__":
    main()
