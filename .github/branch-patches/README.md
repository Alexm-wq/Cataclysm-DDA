# Branch patch runner

This directory is used by `.github/workflows/apply-branch-patch.yml` for temporary, guarded source migrations that are awkward to express through the GitHub contents API.

## Usage

1. Add `.github/branch-patches/active.py` on the branch that should be patched.
2. The workflow compiles and runs that script on the same branch.
3. The script edits source files in-place and should fail if its expected source patterns do not match exactly.
4. The workflow runs `git diff --check`, rejects changes to `.github/workflows` and `.github/branch-patches`, commits the resulting source diff, and pushes it back to the same branch.
5. Delete `active.py` after the patch commit lands. The deletion triggers the workflow once more, but it exits without doing anything.

A patch script may optionally write a one-line commit message to `/tmp/branch_patch_commit_message`. Otherwise the workflow uses `Apply branch patch`.

Keep patch scripts narrowly scoped and guarded with exact occurrence counts so a stale script cannot silently patch the wrong code.
