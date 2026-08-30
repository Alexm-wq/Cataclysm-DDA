import subprocess

# Re-run the exact guarded source migration staged in the parent commit.  Its
# source edits were correct; only one post-migration audit needle incorrectly
# expected a namespace-qualified function definition.
original = subprocess.run(
    ["git", "show", "HEAD^:.github/branch-patches/active.py"],
    check=True,
    capture_output=True,
    text=True,
).stdout
original = original.replace(
    '"construction_ui::resume_persistent_editor_after_activity",',
    '"void resume_persistent_editor_after_activity()",',
    1,
)
exec(compile(original, ".github/branch-patches/active.py", "exec"))
