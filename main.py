#!/usr/bin/env python3

import zipfile
import json
import tomllib
from pathlib import Path
from pprint import pprint
import io


# ----------------------------------------------------------
#  Mod IDs to exclude from results
# ----------------------------------------------------------

IGNORED_MODS = {
    "minecraft",
    "forge",
    "neoforge",
    "fabricloader",
    "fabric-loader",
    "fabric",
    "fabric-api",
    "fabric_api",
    "fabric-resource-loader-v0",
    "fabric-screen-api-v1",
    "fabric-networking-api-v1",
    "fabric-lifecycle-events-v1",
    "fabric-renderer-api-v1",
    "fabric-registry-sync-v0",
    "fabric-api-base",
    "fabric-events-interaction-v0",
    "fabric-permissions-api-v0",
    "fabric-command-api-v2",
    "fabric-kotlin",
    "java",
}


def should_ignore(modid: str) -> bool:
    return modid and modid.lower() in IGNORED_MODS


# ----------------------------------------------------------
#  Extract metadata from jar BYTES
#  (Used for nested jars inside META-INF/jars/, jarjar/, etc.)
# ----------------------------------------------------------

def extract_metadata_from_bytes(raw_bytes):
    try:
        jar = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except Exception:
        return None

    # ---- Fabric ----
    if "fabric.mod.json" in jar.namelist():
        try:
            with jar.open("fabric.mod.json") as f:
                data = json.load(f)

            mod_id = data.get("id")
            name = data.get("name") or mod_id
            depends = {}

            for dep in data.get("depends", {}).keys():
                depends[dep] = {"required": True}
            for dep in data.get("recommends", {}).keys():
                depends[dep] = {"required": False}
            for dep in data.get("suggests", {}).keys():
                depends[dep] = {"required": False}

            return {"id": mod_id, "name": name, "depends": depends}

        except:
            pass

    # ---- Forge modern ----
    if "META-INF/mods.toml" in jar.namelist():
        try:
            with jar.open("META-INF/mods.toml") as f:
                data = tomllib.loads(f.read().decode("utf-8"))

            mod_entry = data.get("mods", [])
            if not mod_entry:
                return None

            mod_id = mod_entry[0].get("modId")
            name = mod_entry[0].get("displayName") or mod_id
            depends = {}

            depArr = data.get("dependencies", {}).get(mod_id, [])
            for dep in depArr:
                dep_id = dep.get("modId")
                required = dep.get("mandatory", False)
                depends[dep_id] = {"required": required}

            return {"id": mod_id, "name": name, "depends": depends}
        except:
            pass

    # ---- Forge old (mcmod.info) ----
    if "mcmod.info" in jar.namelist():
        try:
            with jar.open("mcmod.info") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                entry = data[0]
                mod_id = entry.get("modid")
                name = entry.get("name") or mod_id
                depends = {}
                for dep in entry.get("dependencies", []):
                    depends[dep] = {"required": True}
                for dep in entry.get("requiredMods", []):
                    depends[dep] = {"required": True}
                return {"id": mod_id, "name": name, "depends": depends}
        except:
            pass

    return None


# ----------------------------------------------------------
#  Detect whether a dependency is embedded inside a .jar
# ----------------------------------------------------------

def is_dependency_embedded(jar_path, dep_id):
    dep = dep_id.lower()

    try:
        jar = zipfile.ZipFile(jar_path)
    except Exception:
        return False

    paths = jar.namelist()

    # --- 1. META-INF/jars/ and jarjar/ embedded jars ---
    embedded_prefixes = [
        "META-INF/jars/",
        "META-INF/jarjar/",
    ]
    for prefix in embedded_prefixes:
        for name in paths:
            if name.startswith(prefix) and name.endswith(".jar"):
                try:
                    raw = jar.read(name)
                    meta = extract_metadata_from_bytes(raw)
                    if meta and meta["id"] and meta["id"].lower() == dep:
                        return True
                except:
                    pass

    # --- 2. Namespace folders: assets/dep/, data/dep/ ---
    namespace_paths = [
        f"assets/{dep}/",
        f"data/{dep}/",
    ]
    for ns in namespace_paths:
        if any(p.startswith(ns) for p in paths):
            return True

    # --- 3. Class packages heuristic ---
    likely_prefixes = [
        f"{dep}/",
        f"com/{dep}/",
        f"net/{dep}/",
        f"io/{dep}/",
    ]
    for name in paths:
        n = name.lower()
        if any(n.startswith(pref) for pref in likely_prefixes):
            if n.endswith(".class"):
                return True

    # --- 4. Fabric embedded 'jars' list ---
    if "fabric.mod.json" in paths:
        try:
            data = json.load(jar.open("fabric.mod.json"))
            for entry in data.get("jars", []):
                if dep in entry.get("id", "").lower():
                    return True
        except:
            pass

    return False


# ----------------------------------------------------------
#  Extract metadata from a single mod .jar
# ----------------------------------------------------------

def extract_mod_metadata(jar_path):
    try:
        jar = zipfile.ZipFile(jar_path)
    except:
        return None

    # ---------- FABRIC ----------
    if "fabric.mod.json" in jar.namelist():
        try:
            with jar.open("fabric.mod.json") as f:
                data = json.load(f)

            mod_id = data.get("id")
            name = data.get("name") or mod_id

            depends = {}
            for dep in data.get("depends", {}).keys():
                depends[dep] = {"required": True}
            for dep in data.get("recommends", {}).keys():
                depends[dep] = {"required": False}
            for dep in data.get("suggests", {}).keys():
                depends[dep] = {"required": False}

            return {"id": mod_id, "name": name, "depends": depends, "_path": jar_path}

        except:
            pass

    # ---------- FORGE (modern) ----------
    if "META-INF/mods.toml" in jar.namelist():
        try:
            with jar.open("META-INF/mods.toml") as f:
                data = tomllib.loads(f.read().decode("utf-8"))

            mod_entry = data.get("mods", [])
            if not mod_entry:
                return None

            mod_id = mod_entry[0].get("modId")
            name = mod_entry[0].get("displayName") or mod_id

            depends = {}
            depArr = data.get("dependencies", {}).get(mod_id, [])
            for dep in depArr:
                dep_id = dep.get("modId")
                required = dep.get("mandatory", False)
                depends[dep_id] = {"required": required}

            return {"id": mod_id, "name": name, "depends": depends, "_path": jar_path}
        except:
            pass

    # ---------- FORGE old ----------
    if "mcmod.info" in jar.namelist():
        try:
            with jar.open("mcmod.info") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                entry = data[0]
                mod_id = entry.get("modid")
                name = entry.get("name") or mod_id
                depends = {}
                for dep in entry.get("dependencies", []):
                    depends[dep] = {"required": True}
                for dep in entry.get("requiredMods", []):
                    depends[dep] = {"required": True}
                return {"id": mod_id, "name": name, "depends": depends, "_path": jar_path}
        except:
            pass

    return None


# ----------------------------------------------------------
#  Scan folder of .jar files
# ----------------------------------------------------------

def scan_mod_folder(folder):
    folder = Path(folder)
    mods = {}

    for jar in folder.glob("*.jar"):
        info = extract_mod_metadata(jar)
        if info and info["id"] and not should_ignore(info["id"]):

            # Filter ignored dependencies
            info["depends"] = {
                d: info["depends"][d]
                for d in info["depends"].keys()
                if not should_ignore(d)
            }

            mods[info["id"]] = info

    return mods


# ----------------------------------------------------------
#  Export dependency graph to .dot
# ----------------------------------------------------------

def export_to_dot(mods, output_path):

    installed = set(mods.keys())
    missing_required = set()
    missing_optional = set()

    out = [
        "digraph mods {",
        '    rankdir="LR";',
        '    node [shape=box, style=filled, fillcolor="white"];'
    ]

    # Nodes for installed mods
    for mod_id, data in mods.items():
        label = f"{data['name']}\\n({mod_id})"
        out.append(f'    "{mod_id}" [label="{label}", fillcolor="white"];')

    # Edges
    for mod_id, data in mods.items():
        for dep, meta in data["depends"].items():
            required = meta["required"]
            dep_missing = dep not in installed

            # NEW: check if any mod bundles/includes this dependency internally
            if dep_missing:    
                print("checking if", dep, "is embedded in", mod_id)
                for embedded_mod in mods.values():
                    if is_dependency_embedded(embedded_mod["_path"], dep):
                        dep_missing = False
                        break

            # Now classify based on presence
            if not dep_missing:
                out.append(f'    "{mod_id}" -> "{dep}";')
            else:
                if required:
                    missing_required.add(dep)
                    out.append(f'    "{mod_id}" -> "{dep}" [color="red"];')
                else:
                    missing_optional.add(dep)
                    out.append(f'    "{mod_id}" -> "{dep}" [color="yellow"];')

    # Nodes for missing dependencies
    for dep in sorted(missing_required):
        out.append(
            f'    "{dep}" [label="{dep}\\n(MISSING REQUIRED)", fillcolor="red", fontcolor="white"];'
        )

    for dep in sorted(missing_optional):
        out.append(
            f'    "{dep}" [label="{dep}\\n(optional missing)", fillcolor="yellow", fontcolor="black"];'
        )

    out.append("}")
    Path(output_path).write_text("\n".join(out), encoding="utf-8")


# ----------------------------------------------------------
#  Main
# ----------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a dependency graph for Minecraft mods.")
    parser.add_argument("folder", help="Folder containing .jar mod files")
    parser.add_argument("--output", "-o", default="mods.dot", help="Output DOT file name")

    args = parser.parse_args()

    print(f"Scanning: {args.folder}")
    mods = scan_mod_folder(args.folder)

    print("\nIncluded mods:")
    for mod_id, data in mods.items():
        print(f"  {data['name']} ({mod_id})")
        for d, meta in data["depends"].items():
            print(f"      -> {d} (required={meta['required']})")

    export_to_dot(mods, args.output)
    print(f"\nDOT file written to: {args.output}")
