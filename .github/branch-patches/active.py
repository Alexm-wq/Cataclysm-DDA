import subprocess

# Re-run the guarded migration staged two commits back.  The branch-patch
# workflow checks out depth=1, so deepen once before reading the parent script.
subprocess.check_call(
    ["git", "fetch", "--deepen=2", "origin", "mouse-inventory-0-i-test"]
)
script = subprocess.check_output(
    ["git", "show", "HEAD~2:.github/branch-patches/active.py"], text=True
)
exec( compile( script, "staged_vehicle_viewport_migration.py", "exec" ) )
