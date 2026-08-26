#!/bin/sh
# The long-suite lock.  Rule and rationale: tests/CLAUDE.md § The long-suite lock.
#
# Rung 3 (the full / `-m slow` suite) is exclusive across the sessions sharing
# this checkout.  Two at `-n auto` put twice the workers on the same cores,
# which breaks the premise conftest.pytest_configure sets one rank down (one
# kernel thread per worker, so a budget is not a function of the worker count).
# The cost is not slowness: § Budgets in tests has load turning a real-data
# row's *answer*, and § Quoting numbers the same tree at 5:44 alone and 12:40
# beside another suite.
#
# The lock lives in the git common dir — the one path every worktree spells
# identically, and one no `reset --hard` or `clean` in any of them can reach.
#
# Liveness is the mtime, never a PID: a session is a *sequence* of processes,
# each exiting with its own command, so `refresh` beside each long command is
# what keeps a legitimately 30-minute run from reading as abandoned.  STALE_MIN
# is the only cover for a lock whose owner was killed before releasing it.
#
# Usage: suite-lock.sh claim <who> <what> | refresh | release | status
#        claim exits 3 and prints the holder when the lock is held.

set -eu

STALE_MIN=45 # past the suite's own 15-30 min range

LOCK="$(git rev-parse --path-format=absolute --git-common-dir)/rietx-suite.lock"

held() {
	[ -f "$LOCK" ] || return 1
	[ -z "$(find "$LOCK" -mmin +"$STALE_MIN" 2>/dev/null)" ]
}

case "${1:-status}" in
claim)
	if held; then
		echo "long-suite lock HELD — do not start a long run:" >&2
		sed 's/^/  /' "$LOCK" >&2
		exit 3
	fi
	printf 'who:     %s\nwhat:    %s\nstarted: %s\n' \
		"${2:?claim needs <who>}" "${3:?claim needs <what>}" \
		"$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$LOCK"
	echo "long-suite lock claimed by ${2}"
	;;
refresh)
	[ -f "$LOCK" ] || {
		echo "no lock to refresh" >&2
		exit 1
	}
	touch "$LOCK"
	;;
release)
	rm -f "$LOCK"
	echo "long-suite lock released"
	;;
status)
	if held; then
		sed 's/^/  /' "$LOCK"
	elif [ -f "$LOCK" ]; then
		echo "stale (>${STALE_MIN}m), claimable:"
		sed 's/^/  /' "$LOCK"
	else
		echo "free"
	fi
	;;
*)
	echo "usage: $0 claim <who> <what> | refresh | release | status" >&2
	exit 2
	;;
esac
