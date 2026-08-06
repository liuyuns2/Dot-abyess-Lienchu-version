import argparse
import json
from pathlib import Path

from DotAbyss import AbyssDownloader
from UnityCatalogReader import UnityCatalogReader


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch latest DotAbyss master data and catalog without downloading every asset.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    downloader = AbyssDownloader()
    info = downloader.get_version_info()
    if not info:
        raise SystemExit("Failed to fetch version info.")

    versions = info.get("versions", {})
    asset_ver = downloader._pick_version(versions, "AssetVersionWebDmmR18", default=None)
    master_ver = downloader._pick_version(versions, "resource", default="4")
    client_ver = downloader._pick_version(versions, "ClientVersionWebDmmR18", default="1.0.0") or "1.0.0"
    client_prefix = str(client_ver).split(".")[0] if client_ver else "1"

    if not asset_ver:
        raise SystemExit("Missing AssetVersionWebDmmR18 in version response.")

    downloader.asset_ver = asset_ver
    downloader.master_ver = master_ver
    downloader.client_ver_prefix = client_prefix

    previous_cwd = Path.cwd()
    try:
        import os

        os.chdir(output)
        if not downloader.handle_master_data():
            print("Warning: MasterData download failed; continuing catalog fetch.")

        base_url = f"https://api.abyss-prod-r18.dotabyss.dmmgames.com/resources/webgl/r18/aas/{asset_ver}/aa"
        hash_url = f"{base_url}/catalog_{client_prefix}.hash"
        bin_url = f"{base_url}/catalog_{client_prefix}.bin"
        hash_path = output / f"catalog_{client_prefix}.hash"
        bin_path = output / f"catalog_{client_prefix}.bin"

        print(f"Asset version: {asset_ver}")
        print(f"Master data version: {master_ver}")
        print(f"Client prefix: {client_prefix}")
        print(f"Base URL: {base_url}")

        response = downloader.session.get(hash_url, timeout=30)
        response.raise_for_status()
        hash_path.write_text(response.text.strip(), encoding="utf-8")

        if not downloader.download_file(bin_url, str(bin_path)):
            raise SystemExit(f"Failed to download catalog: {bin_url}")

        assets_path = output / "assets.json"
        UnityCatalogReader(str(bin_path)).export_to_json(str(assets_path))

        write_json(
            output / "latest_catalog_info.json",
            {
                "asset_version": asset_ver,
                "master_data_version": master_ver,
                "client_version": client_ver,
                "client_prefix": client_prefix,
                "base_url": base_url,
                "catalog_hash_url": hash_url,
                "catalog_bin_url": bin_url,
                "catalog_hash": response.text.strip(),
                "catalog_bin": str(bin_path),
                "assets_json": str(assets_path),
            },
        )
        (output / "base_url.txt").write_text(base_url + "\n", encoding="utf-8")
        print(f"Output: {output}")
    finally:
        import os

        os.chdir(previous_cwd)


if __name__ == "__main__":
    main()
