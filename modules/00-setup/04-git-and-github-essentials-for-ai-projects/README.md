# 00.4 · Git and GitHub essentials for AI projects

**Module:** [00 · Setup and Python for AI work](../README.md) · **Time:** 45-60 minutes · **Model needs:** none

## What you will learn

- The everyday git loop: `init` or `clone`, `branch`, `commit`, `push`, and a pull request.
- What an AI project must keep *out* of git (`.env`, `.venv`, logs, data, model files,
  notebook checkpoints), and how `.gitignore` does it.
- Why `.gitignore` does not help with a file git already tracks.
- How secret scanners find keys, and what to do, and in which order, if you commit a key.

## The idea

Git saves snapshots of a folder, called commits. It lets several people work on separate
lines of change, called branches, and merge them later. GitHub keeps a copy of the
repository online so a team can share it. Teammates review each change as a pull request
before it reaches the main branch.

In an AI project, git itself is not the danger. The danger is what you hand it by accident.
A single `git add .` can commit your API key, gigabytes of downloaded models, or logs full
of employees' questions. Once you push it, assume someone has copied it.

> **Practise in your own repo.** The commands below are for a scratch practice repository
> you create yourself (for example `~/git-practice`). Do not run commands that change
> history, branches or remotes inside this course repo. The scripts in this lesson only
> *read* it.

### The everyday loop

```mermaid
flowchart LR
    A["git init / git clone"] --> B["git switch -c feature/x"]
    B --> C["edit files"]
    C --> D["git add + git commit"]
    D --> C
    D --> E["git push -u origin feature/x"]
    E --> F["open a pull request on GitHub"]
    F --> G["review, CI, merge into main"]
    G --> H["git switch main && git pull"]
```

Try it in your practice folder:

```
mkdir git-practice && cd git-practice
git init                                  # start a new repository here
# or, to copy an existing one:  git clone https://github.com/<you>/<repo>.git

git status                                # what changed, what is staged
git switch -c feature/greeting            # a new branch for one piece of work
echo 'print("hello")' > hello.py
git add hello.py                          # stage exactly the files you mean
git commit -m "Add greeting script"       # a snapshot with a message

git remote add origin https://github.com/<you>/git-practice.git
git push -u origin feature/greeting       # publish the branch
```

Then, on GitHub, open a pull request from `feature/greeting` into `main`. The pull request
shows the diff (what changed), lets teammates comment, and runs automatic checks (CI)
before anyone clicks merge. After merging, update your local copy with `git switch main`
and `git pull`.

Two habits prevent most accidents in AI projects. Run `git status` before every commit. And
add files by name with `git add <file>`, not `git add .`, until you trust your `.gitignore`.

### A .gitignore for AI projects

```
# secrets
.env
.env.*
!.env.example

# environments and caches
.venv/
__pycache__/
*.pyc
.pytest_cache/

# produced at run time: may contain prompts, replies and personal data
logs/
*.log

# data and models: large, often private, rebuilt or downloaded
data/raw/
*.csv
*.parquet
models/
*.gguf
*.safetensors
*.bin
*.pt

# notebooks
.ipynb_checkpoints/

# editors and OS
.DS_Store
.idea/
.vscode/
```

Adjust the data lines to fit your project. You can commit small sample data that tests
need. Never commit customer data or model weights (the large files that hold a trained
model). Large files that must be versioned belong in storage built for them (object
storage, Git LFS, a model registry), not in ordinary git.

### Ignored is not the same as untracked

`.gitignore` only stops git from *adding new* files. If `.env` was committed once, git keeps
tracking it, and every later change to it gets committed too. `git ls-files` shows what git
tracks. `git rm --cached .env` stops tracking the file but leaves your local copy alone.
Any key that was in it must still be treated as leaked.

### If a key is committed

```mermaid
flowchart TD
    L[A key is in a commit] --> R["1. Revoke it at the provider, now"]
    R --> N["2. Create a new key, put it in .env"]
    N --> F["3. Remove it from the code, commit the fix"]
    F --> H["4. Optionally clean history<br/>(git filter-repo, BFG) and force-push"]
    H --> T["5. Tell your team / security contact"]
```

The order matters. **Revoking the key is the only step that makes you safe.** Bots scan
public GitHub for new keys within minutes. Forks, clones, CI caches and the pull request
page may already hold the commit. Rewriting history afterwards keeps the key out of future
clones, but that is cleanup, not protection.

GitHub helps in two ways. Secret scanning recognises keys from many providers in public
repositories (and in private ones where it is turned on) and alerts you or the provider.
Push protection can block a push that contains a recognised key before it lands. Local
tools catch it even earlier, on your machine: pre-commit hooks such as `gitleaks` or
`detect-secrets`. All of them work the way script 2 shows, with patterns that match the
*shape* of a key.

## Scripts

Run both in order with `./run 00.4` (Windows: `run 00.4`), or one at a time. Both only
read. Neither changes anything in git.

### 1. `01_is_my_repo_safe.py`: is my repo safe to push?

```
./run 00.4/1
```

This script asks git two questions about this repo. First, is each dangerous path (`.env`,
`.venv/`, `logs/`, `.labkit/`, `__pycache__/`) ignored, and by which `.gitignore` rule?
Second, is any `.env` file already tracked? It also confirms that the files others need
(`.env.example`, `.gitignore`, `pyproject.toml`, `uv.lock`) are tracked. It makes no model
calls.

**Expected output** (your git version and branch name will differ):

```
──────────────────────────── 00.4/1  Is my repo safe to push? ───────────────────────────

Step 1: Is git here, and is this a repository? ─────────────────────────────────────────
git version 2.39.3, on branch 'main'.

Step 2: Are the dangerous paths ignored? ───────────────────────────────────────────────
`git check-ignore -v <path>` answers yes or no, and names the .gitignore rule responsible.
  ignored      .env           by .gitignore:2:.env          (holds your API key)
  ignored      .venv/         by .gitignore:7:.venv/        (installed packages: large, and rebuilt from the lockfile)
  ignored      logs/          by .gitignore:16:logs/        (run logs: may contain prompts, replies and personal data)
  ignored      .labkit/       by .gitignore:17:.labkit/     (local cache from the doctor)
  ignored      __pycache__/   by .gitignore:8:__pycache__/  (compiled Python files)

Step 3: Is anything secret already tracked? ────────────────────────────────────────────
.gitignore only stops NEW files being added. A file committed earlier stays tracked.
  No .env file is tracked.
  .env.example     tracked
  .gitignore       tracked
  pyproject.toml   tracked
  uv.lock          tracked

Step 4: Verdict ────────────────────────────────────────────────────────────────────────
Safe to push: secrets and local clutter are ignored, and the files others need are tracked.
Run this in your own projects too: copy the script and edit the two lists at the top.

Run summary: no model calls, 0.1s
Log: logs/20260101T100000Z-00.4-1.jsonl
```

If you downloaded the course as a zip instead of cloning it, Step 1 says the folder is not
a git repository and the script stops there.

### 2. `02_find_leaked_keys.py`: catching a key before it is committed

```
./run 00.4/2
```

This script writes a deliberately bad `settings.py` for the helpdesk bot to a temporary
folder. The file is full of *invented* keys. The script scans it line by line with four
regular expressions (text patterns), the way a secret scanner does, and reports every hit
with the value masked. It ends with what the scanner cannot see and the steps to take if a
key is committed. It makes no model calls.

**Expected output** (the keys are invented for this demo, so their masked forms are shown as they appear):

```
───────────────────── 00.4/2  Catching a key before it is committed ──────────────────────

Step 1: A settings file someone is about to commit ─────────────────────────────────────
Written to a temporary folder. Every key in it is invented. Values are masked below, as a scanner would.
   1 | # settings.py for the Larkspur Labs helpdesk bot (a deliberately bad example)
   2 | import os
   3 |
   4 | COMPANY = "Larkspur Labs"
   5 | MODEL = "small-model"
   6 | API_KEY = "<sk-...m9 (50 chars)>"          # pasted in "just to test"
   7 | CLOUD_ACCESS_KEY = "<AKI...KD (20 chars)>"
   8 | TICKET_SYSTEM_HEADERS = {"Authorization": "<Bea...Jl (57 chars)>"}
   9 | password = "<hun...ur (16 chars)>"
  10 | ESCALATION_EMAIL = "it-escalations@larkspur.example"
  11 | GOOD_API_KEY = os.environ["LLM_API_KEY"]   # the right way: read it from the environment

Step 2: Scan it ────────────────────────────────────────────────────────────────────────
4 patterns, each tried on every line:
  provider API key (sk-...)    \bsk-[A-Za-z0-9_-]{20,}
  cloud access key (AKIA...)   \bAKIA[0-9A-Z]{16}\b
  bearer token                 Bearer\s+[A-Za-z0-9._-]{20,}
  hard-coded password          (?i)\b(?:password|passwd|secret)\b\s*[=:]\s*["']([^"']{6,})["']
4 finding(s)
[
  {
    "line": 6,
    "looks like": "provider API key (sk-...)",
    "value": "sk-...m9 (50 chars)"
  },
  ...
  {
    "line": 9,
    "looks like": "hard-coded password",
    "value": "hun...ur (16 chars)"
  }
]

Step 3: What the scanner did not flag, and why ─────────────────────────────────────────
Line 11 reads the key from the environment: there is no secret in the file, so nothing to find.
Line 10 is an email address: sensitive perhaps, but not a credential.
A scanner only knows shapes. A key in an unusual format walks straight past it.

Step 4: If a key does get committed ────────────────────────────────────────────────────
1. Revoke the key at the provider NOW. This is the only step that makes you safe.
2. Create a new key and put it in .env (which is ignored).
3. Remove the key from the code and commit the fix.
4. Do not rely on deleting the commit: clones, forks and caches may already hold it.

Run summary: no model calls, 0.0s
Log: logs/20260101T100000Z-00.4-2.jsonl
```

## Try this

1. **Ask git yourself.** From the repo root, run the read-only commands the script uses:
   `git check-ignore -v .env`, `git check-ignore -v modules` (no output and exit code 1
   mean "not ignored") and `git ls-files | head`.
2. **Extend the checklist.** Add `("notebooks/.ipynb_checkpoints/", "Jupyter autosaves")`
   and `("models/", "downloaded model weights")` to `MUST_BE_IGNORED` in
   `01_is_my_repo_safe.py` and run it again. Which ones does this repo's `.gitignore` miss?
3. **Run it on your own project.** Copy `01_is_my_repo_safe.py` next to another project,
   replace the `labkit` imports with `print`, and point `cwd` at that project.
4. **Beat the scanner.** In `02_find_leaked_keys.py`, add a line to `SAMPLE_FILE` such as
   `TOKEN = "lark_live_9f8e7d6c5b4a39281706"`. The scanner does not flag it. Write a fifth
   pattern that catches it without also matching the email on line 10.
5. **Practise the loop** in a scratch repo (not this one): `git init`, commit a file,
   create a branch, commit again, and look at `git log --oneline --graph --all`.
6. **Practise the rescue** in that scratch repo: commit a fake `.env`, add `.env` to
   `.gitignore`, and see that `git status` still shows changes to it. Fix it with
   `git rm --cached .env` and commit.

## If it does not work

- `git is not installed`: install it from https://git-scm.com/downloads, open a new
  terminal and run the script again.
- `This folder is not a git repository`: you downloaded a zip. Script 1 needs a clone
  (`git clone <course url>`) to have something to inspect. Script 2 works either way.
- `NOT IGNORED` in your own project: add the path to `.gitignore`. If it is also `TRACKED`,
  run `git rm --cached <file>`, commit, and revoke any key the file contained.
- `git push` asks for a password and rejects it: GitHub no longer accepts account
  passwords over HTTPS. Use a personal access token, SSH keys, or the `gh auth login` CLI.
- For anything about your Python setup or settings, run `./run doctor`.

## In the running scenario

The Larkspur Labs helpdesk assistant will hold several credentials (a model key, a
ticket-system token). It will also write logs that contain employees' questions about
their accounts and laptops. So its repository starts with a `.gitignore` that excludes
`.env`, logs and data, a committed `.env.example`, and a check before each push like
script 1.

Changes arrive as pull requests with CI. A key pasted "just to test" gets caught by review
or by push protection before it reaches the main branch. If one does slip through, the
team knows the order: revoke first, clean up second.

**Next:** 00.5 · Async Python: concurrent LLM calls (planned)
