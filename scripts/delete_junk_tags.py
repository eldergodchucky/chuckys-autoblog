"""Delete junk tags listed in the junk-tags analysis file."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from push_pages import load_env, wp_request  # noqa: E402

JUNK_FILE = Path(r"C:\Users\ELDERCHUCKY\AppData\Local\Temp\opencode\junk_tags.json")


def main() -> int:
    load_env()
    junk = json.loads(JUNK_FILE.read_text(encoding="utf-8"))
    print(f"Deleting {len(junk)} junk tags...")

    deleted = 0
    failed: list[str] = []
    for name, _count in junk:
        try:
            found = wp_request(f"tags?search={name}&per_page=5")
            matches = [t for t in found if str(t.get("name", "")).strip().lower() == name.lower()]
            if not matches:
                print(f"  not found (already gone?): {name}")
                continue
            tag_id = matches[0]["id"]
            wp_request(f"tags/{tag_id}?force=true", method="DELETE")
            deleted += 1
            print(f"  deleted: {name} (id={tag_id})")
            time.sleep(0.4)
        except Exception as exc:
            failed.append(f"{name}: {exc}")
            print(f"  FAILED: {name} -> {exc}")

    print(f"\nDone. Deleted {deleted}; failures: {len(failed)}")
    for failure in failed:
        print(f"  FAILED {failure}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
