import argparse
import json
import re
from pathlib import Path


TAG_RE = re.compile(r"<[^>]+>")
HIGH_RISK_TERMS = (
    "咱們",
    "這兒",
    "那兒",
    "哪兒",
    "啥",
    "沒法",
    "幹活",
    "手辦",
    "視頻",
    "軟件",
    "屏幕",
    "默認",
    "充值",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--novels", required=True)
    args = parser.parse_args()

    root = Path(args.novels)
    files = sorted(root.glob("*/zh_Hant.json"))
    total_entries = 0
    empty_entries = 0
    parse_errors = []
    tag_errors = []
    risky_values = []

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            parse_errors.append(f"{path}: {exc}")
            continue

        for key, value in data.items():
            total_entries += 1
            if value is None or value == "":
                empty_entries += 1
                continue
            if not isinstance(value, str):
                tag_errors.append(f"{path}: non-string value for {key!r}")
                continue
            if TAG_RE.findall(key) != TAG_RE.findall(value):
                tag_errors.append(
                    f"{path}: tags differ\n"
                    f"  source={TAG_RE.findall(key)}\n"
                    f"  value ={TAG_RE.findall(value)}\n"
                    f"  key={key}"
                )
            hits = [term for term in HIGH_RISK_TERMS if term in value]
            if hits:
                risky_values.append(f"{path}: {hits}: {value}")

    print(f"files={len(files)}")
    print(f"entries={total_entries}")
    print(f"empty={empty_entries}")
    print(f"parse_errors={len(parse_errors)}")
    print(f"tag_errors={len(tag_errors)}")
    print(f"high_risk_values={len(risky_values)}")

    for title, items in (
        ("PARSE ERRORS", parse_errors),
        ("TAG ERRORS", tag_errors),
        ("HIGH-RISK VALUES", risky_values),
    ):
        if items:
            print(f"\n{title}")
            for item in items:
                print(item)


if __name__ == "__main__":
    main()
