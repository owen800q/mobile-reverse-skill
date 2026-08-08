#!/usr/bin/env bash
#
# Update the 看雪 Android digest archive and publish it to the reverse-skill KB.
#
#   ./update.sh              # rescan -> fetch -> 点赞-unlock -> copy to KB -> commit+push
#   ./update.sh --dry-run    # do the crawl, but only REPORT what would be copied/pushed
#   ./update.sh --no-push    # copy and commit locally, leave the push to you
#   ./update.sh --no-copy    # crawl only, do not touch the KB repo at all
#   ./update.sh --sync-only  # skip the crawl, just copy the existing archive + push
#   ./update.sh --no-unlock  # skip the 点赞 pass, leave gated threads in locked.json
#   ./update.sh --headless   # no browser window (cannot clear a 安全验证 captcha)
#
# Any other flag is forwarded to crawl.py (e.g. --no-replies, --max-reply-pages 3).
#
# Safe to run any time: every stage is keyed on tid, so already-archived threads are
# skipped and already-liked threads are never liked again.  Ctrl-C is safe - state is
# written after each thread, so a rerun resumes where it stopped.
#
# Only kb/articles/** is committed.  INDEX.md and kb/index/embeddings.npy are rebuilt
# and committed by the repo's own kb-index.yml GitHub Action once this pushes, so this
# script deliberately does not touch them.
#
# .github/workflows/kb-crawl.yml runs this daily with --headless --no-push and handles
# the push + index rebuild itself.  A 安全验证 captcha cannot be cleared headless, so a
# CI run that hits one records the thread in failed.json and stops; rerun locally
# without --headless to clear it.
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
PY="${PYTHON:-python3}"
DONE=output/done.json
LOCKED=output/locked.json
SRC_ARTICLES="$PWD/output/articles"

# This script lives inside the KB repo (tools/kanxue-crawler/), so the repo root is
# whatever git says it is from here - true on a laptop and on a CI runner alike.
KB_REPO="${KB_REPO:-$(git rev-parse --show-toplevel)}"
KB_ARTICLES="${KB_ARTICLES:-$KB_REPO/skills/reverse-skill/kb/articles}"

DO_UNLOCK=1
DO_CRAWL=1
DO_COPY=1
DO_PUSH=1
DRY_RUN=0
ARGS=()
for a in "$@"; do
    case "$a" in
        --no-unlock) DO_UNLOCK=0 ;;
        --no-copy)   DO_COPY=0 ;;
        --sync-only) DO_CRAWL=0 ;;
        --no-push)   DO_PUSH=0 ;;
        --dry-run)   DRY_RUN=1; DO_PUSH=0 ;;
        *) ARGS+=("$a") ;;
    esac
done

count() {  # count() <json-file> -> number of keys, 0 if absent
    "$PY" -c "import json,os,sys;p=sys.argv[1];print(len(json.load(open(p))) if os.path.exists(p) else 0)" "$1"
}

tids() {   # tids() <json-file> -> one key per line
    "$PY" -c "import json,os,sys;p=sys.argv[1];print('\n'.join(json.load(open(p)))) if os.path.exists(p) else None" "$1"
}

explain_failure() {  # explain_failure() <stage> <exit-code>
    case "$2" in
        2) echo "" >&2
           echo "robots.txt now disallows the board or thread paths - stopping." >&2 ;;
        *) echo "" >&2
           echo "'$1' failed (exit $2).  The usual cause is an expired session." >&2
           echo "Fix it with:  $PY crawl.py login" >&2
           echo "then rerun this script - nothing already archived is lost." >&2 ;;
    esac
}

trap 'echo ""; echo "interrupted - progress is saved, rerun ./update.sh to resume."; exit 130' INT

BEFORE_DONE=$(count "$DONE")
BEFORE_TIDS=$(mktemp); tids "$DONE" | sort > "$BEFORE_TIDS"
SYNCED_LIST=$(mktemp)
trap 'rm -f "$BEFORE_TIDS" "$SYNCED_LIST"' EXIT

echo "==> archive currently holds $BEFORE_DONE threads"
[[ "$DRY_RUN" -eq 1 ]] && echo "==> DRY RUN: the KB will not be modified"

# ------------------------------------------------------------- stages 1-3: crawling
if [[ "$DO_CRAWL" -eq 0 ]]; then
    echo ""
    echo "==> [1-3/5] skipping the crawl (--sync-only)"
else

# ---------------------------------------------------------------- stage 1: board scan
echo ""
echo "==> [1/5] rescanning the board for new threads"
if ! "$PY" crawl.py urls "${ARGS[@]+"${ARGS[@]}"}"; then
    rc=$?; explain_failure "urls" "$rc"; exit "$rc"
fi

# ---------------------------------------------------------------- stage 2: fetch new
echo ""
echo "==> [2/5] fetching threads that are not in done.json yet"
if ! "$PY" crawl.py fetch "${ARGS[@]+"${ARGS[@]}"}"; then
    rc=$?; explain_failure "fetch" "$rc"; exit "$rc"
fi

# ---------------------------------------------------------------- stage 3: unlock
NEW_LOCKED=$(count "$LOCKED")
echo ""
if [[ "$DO_UNLOCK" -eq 0 ]]; then
    echo "==> [3/5] skipping the 点赞 pass (--no-unlock); $NEW_LOCKED thread(s) left in locked.json"
elif [[ "$NEW_LOCKED" -eq 0 ]]; then
    echo "==> [3/5] nothing gated this run - no 点赞 needed"
else
    echo "==> [3/5] unlocking $NEW_LOCKED gated thread(s) by 点赞 (0 雪币, no reply posted)"
    if ! "$PY" crawl.py unlock "${ARGS[@]+"${ARGS[@]}"}"; then
        rc=$?; explain_failure "unlock" "$rc"; exit "$rc"
    fi
fi

fi   # end DO_CRAWL

# ---------------------------------------------------------------- stage 4: copy to KB
echo ""
N_NEW=0; N_UPD=0
if [[ "$DO_COPY" -eq 0 ]]; then
    echo "==> [4/5] skipping the KB copy (--no-copy)"
elif [[ ! -d "$KB_ARTICLES" ]]; then
    echo "==> [4/5] KB articles dir not found: $KB_ARTICLES" >&2
    echo "    set KB_REPO=... or KB_ARTICLES=... and rerun." >&2
    exit 1
else
    echo "==> [4/5] syncing to $KB_ARTICLES"
    for f in "$SRC_ARTICLES"/*.md; do
        [[ -e "$f" ]] || continue
        b=$(basename "$f")
        if [[ ! -f "$KB_ARTICLES/$b" ]]; then
            [[ "$DRY_RUN" -eq 0 ]] && cp -p "$f" "$KB_ARTICLES/$b"
            echo "  new     $b" >> "$SYNCED_LIST"; N_NEW=$((N_NEW + 1))
        elif ! cmp -s "$f" "$KB_ARTICLES/$b"; then
            [[ "$DRY_RUN" -eq 0 ]] && cp -p "$f" "$KB_ARTICLES/$b"
            echo "  updated $b" >> "$SYNCED_LIST"; N_UPD=$((N_UPD + 1))
        fi
    done
    if [[ $((N_NEW + N_UPD)) -eq 0 ]]; then
        echo "    KB already matches the archive - nothing to copy"
    else
        echo "    $N_NEW new, $N_UPD updated"
        head -20 "$SYNCED_LIST"
        [[ $((N_NEW + N_UPD)) -gt 20 ]] && echo "  ... and $((N_NEW + N_UPD - 20)) more"
    fi
fi

# ---------------------------------------------------------------- stage 5: commit+push
echo ""
if [[ "$DO_COPY" -eq 0 || $((N_NEW + N_UPD)) -eq 0 ]]; then
    echo "==> [5/5] nothing to commit"
elif [[ "$DRY_RUN" -eq 1 ]]; then
    echo "==> [5/5] dry run - would commit $((N_NEW + N_UPD)) file(s) to $KB_REPO and push"
else
    echo "==> [5/5] committing to $KB_REPO"
    # Stage only the articles path, so unrelated edits in that repo are left alone.
    git -C "$KB_REPO" add -- "$KB_ARTICLES"
    if git -C "$KB_REPO" diff --cached --quiet; then
        echo "    git reports no change - nothing to commit"
    else
        MSG=$(mktemp)
        {
            if [[ "$N_UPD" -eq 0 ]]; then
                echo "kb: add $N_NEW kanxue article(s)"
            else
                echo "kb: add $N_NEW, update $N_UPD kanxue article(s)"
            fi
            echo ""
            sed 's/^  //' "$SYNCED_LIST" | head -30
            [[ $((N_NEW + N_UPD)) -gt 30 ]] && echo "... and $((N_NEW + N_UPD - 30)) more"
            echo ""
            echo "Crawled from https://bbs.kanxue.com/forum-161-1.htm?orderby=tid&digest=0"
        } > "$MSG"
        git -C "$KB_REPO" commit -q -F "$MSG"
        rm -f "$MSG"
        echo "    committed: $(git -C "$KB_REPO" log -1 --oneline)"

        if [[ "$DO_PUSH" -eq 0 ]]; then
            echo "    --no-push given; push it yourself with:  git -C $KB_REPO push"
        elif ! git -C "$KB_REPO" rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1; then
            echo "    no upstream branch configured - push manually." >&2
        else
            # kb-index.yml commits a rebuilt INDEX.md/embeddings.npy straight to main
            # after every article push, so the local branch is usually behind by one.
            echo "    rebasing onto upstream (CI commits its index rebuild to main)"
            if ! git -C "$KB_REPO" pull --rebase --quiet; then
                echo "" >&2
                echo "    rebase failed - resolve it in $KB_REPO, then: git push" >&2
                exit 1
            fi
            git -C "$KB_REPO" push --quiet
            echo "    pushed to $(git -C "$KB_REPO" rev-parse --abbrev-ref '@{upstream}')"
            echo "    kb-index.yml will rebuild INDEX.md + embeddings.npy shortly"
        fi
    fi
fi

# ---------------------------------------------------------------- summary
AFTER_DONE=$(count "$DONE")
AFTER_TIDS=$(mktemp)
tids "$DONE" | sort > "$AFTER_TIDS"

echo ""
echo "================ update summary ================"
echo "archived : $BEFORE_DONE -> $AFTER_DONE  (+$((AFTER_DONE - BEFORE_DONE)))"
echo "locked   : $(count "$LOCKED") still gated"
echo "failed   : $(count output/failed.json)"
echo "KB sync  : $N_NEW new, $N_UPD updated"

if [[ "$AFTER_DONE" -gt "$BEFORE_DONE" ]]; then
    echo ""
    echo "new articles:"
    comm -13 "$BEFORE_TIDS" "$AFTER_TIDS" | while read -r tid; do
        [[ -z "$tid" ]] && continue
        "$PY" -c "
import json,sys
v=json.load(open('$DONE'))[sys.argv[1]]
print('  %-8s %s  (%s, %d replies)'%(sys.argv[1], v['title'][:60], v.get('date') or '?', v.get('replies',0)))" "$tid"
    done
fi
rm -f "$AFTER_TIDS"

if [[ "$(count output/failed.json)" -gt 0 ]]; then
    echo ""
    echo "some threads failed - retry them with:  $PY crawl.py fetch --retry-failed"
fi
echo "================================================"
