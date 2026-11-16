import os
import shutil
import hashlib
import datetime
import zipfile
import io
import imagehash
import streamlit as st
from PIL import Image
from collections import defaultdict

st.set_page_config(page_title="Local Exact Image Matcher", layout="wide")
st.title("Local Offline Exact & Duplicate Image Finder")
st.caption("100% Local • Zero Internet • Byte-level SHA-256 + Perceptual Hash Matching • Safe Deletion")

VALID_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def get_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def get_sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

def get_image_details(filepath):
    try:
        size = os.path.getsize(filepath)
        mtime = os.path.getmtime(filepath)
        dt_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        with Image.open(filepath) as img:
            dims = f"{img.width}x{img.height}"
        return {"size": size, "dims": dims, "mtime_str": dt_str, "mtime": mtime}
    except Exception:
        return {
            "size": os.path.getsize(filepath) if os.path.exists(filepath) else 0,
            "dims": "N/A",
            "mtime_str": "N/A",
            "mtime": 0
        }

def auto_select_original(paths):
    """
    Intelligently suggest the best file to keep as original:
    1. Prefer files without 'copy', '(1)', etc. in the filename
    2. Prefer higher resolution
    3. Prefer oldest creation/modification time
    4. Prefer shorter filename
    """
    def score(path):
        name = os.path.basename(path).lower()
        has_copy = 1 if any(tag in name for tag in ("copy", "(1)", "(2)", "(3)", "(4)")) else 0
        mtime = os.path.getmtime(path) if os.path.exists(path) else float("inf")
        try:
            with Image.open(path) as img:
                res = img.width * img.height
        except Exception:
            res = 0
        return (has_copy, -res, mtime, len(name))

    return min(paths, key=score)

def delete_file(filepath, delete_method="backup", backup_dir=None):
    """
    Deletes or moves a single file.
    Returns (success, size_freed).
    """
    if not os.path.exists(filepath):
        return True, 0
    size = os.path.getsize(filepath)
    try:
        if delete_method == "backup" and backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            dest_filename = os.path.basename(filepath)
            dest_path = os.path.join(backup_dir, dest_filename)
            counter = 1
            base, ext = os.path.splitext(dest_filename)
            while os.path.exists(dest_path):
                dest_path = os.path.join(backup_dir, f"{base}_{counter}{ext}")
                counter += 1
            shutil.move(filepath, dest_path)
        else:
            os.remove(filepath)
        return True, size
    except Exception as e:
        st.error(f"Failed to delete {filepath}: {e}")
        return False, 0

# Initialize Session State
if "duplicate_groups" not in st.session_state:
    st.session_state["duplicate_groups"] = []
if "scanned_folder" not in st.session_state:
    st.session_state["scanned_folder"] = ""
if "scan_performed" not in st.session_state:
    st.session_state["scan_performed"] = False
if "status_alert" not in st.session_state:
    st.session_state["status_alert"] = None

mode = st.radio(
    "Choose input method:",
    ["Scan a Local Folder Path (Recommended)", "Upload Multiple Images / Drag Folder"],
    horizontal=True
)

match_strictness = st.slider(
    "Match Strictness (0 = Exact Match Only, 1–5 = Catch Resized/Compressed Copies)",
    min_value=0, max_value=8, value=0
)

if mode == "Scan a Local Folder Path (Recommended)":
    if st.session_state.get("scanned_folder"):
        default_dir = st.session_state["scanned_folder"]
    elif os.path.isdir("images"):
        default_dir = os.path.abspath("images")
    else:
        default_dir = os.getcwd()

    folder_path = st.text_input("Enter full folder path:", value=default_dir)
    include_subfolders = st.checkbox("Include subfolders", value=True)

    col_scan, col_clear = st.columns([2, 8])
    with col_scan:
        scan_clicked = st.button("🔍 Find Exact Matches", type="primary")
    with col_clear:
        if st.session_state["scan_performed"]:
            if st.button("Clear Results"):
                st.session_state["duplicate_groups"] = []
                st.session_state["scan_performed"] = False
                st.session_state["status_alert"] = None
                st.rerun()

    if scan_clicked:
        if not os.path.isdir(folder_path):
            st.error("Folder path not found. Please check the path and try again.")
            st.stop()

        image_files = []
        if include_subfolders:
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if f.lower().endswith(VALID_EXTS):
                        image_files.append(os.path.join(root, f))
        else:
            image_files = [
                os.path.join(folder_path, f)
                for f in os.listdir(folder_path)
                if f.lower().endswith(VALID_EXTS)
            ]

        if not image_files:
            st.warning("No images found in that folder.")
            st.session_state["duplicate_groups"] = []
            st.session_state["scan_performed"] = True
            st.session_state["status_alert"] = None
        else:
            st.info(f"Scanning {len(image_files)} images...")
            if match_strictness == 0:
                groups = defaultdict(list)
                for path in sorted(image_files):
                    try:
                        file_hash = get_sha256(path)
                        groups[file_hash].append(path)
                    except Exception:
                        continue
                found_groups = [paths for paths in groups.values() if len(paths) > 1]
            else:
                hashes = []
                for path in sorted(image_files):
                    try:
                        with Image.open(path) as img:
                            ph = imagehash.phash(img.convert("RGB"))
                        hashes.append((path, ph))
                    except Exception:
                        continue

                visited = set()
                found_groups = []
                for i, (path_i, hash_i) in enumerate(hashes):
                    if i in visited:
                        continue
                    current_group = [path_i]
                    visited.add(i)
                    for j in range(i + 1, len(hashes)):
                        if j not in visited and (hash_i - hashes[j][1]) <= match_strictness:
                            current_group.append(hashes[j][0])
                            visited.add(j)
                    if len(current_group) > 1:
                        found_groups.append(current_group)

            st.session_state["duplicate_groups"] = found_groups
            st.session_state["scanned_folder"] = folder_path
            st.session_state["scan_performed"] = True
            st.session_state["status_alert"] = None
            st.rerun()

    # Display Alerts if any
    if st.session_state["status_alert"]:
        alert_type, alert_text = st.session_state["status_alert"]
        if alert_type == "success":
            st.success(alert_text)
        elif alert_type == "warning":
            st.warning(alert_text)
        elif alert_type == "error":
            st.error(alert_text)

    # Display Duplicate Groups and Deletion Options
    if st.session_state["scan_performed"]:
        st.divider()
        duplicate_groups = st.session_state["duplicate_groups"]

        if not duplicate_groups:
            st.success("🎉 No duplicate images found in this folder (or all duplicates have been cleaned up)!")
        else:
            total_groups = len(duplicate_groups)
            total_dupes = sum(len(g) - 1 for g in duplicate_groups)

            # Calculate total reclaimable space assuming 1 file kept per group
            total_reclaimable_bytes = 0
            for group in duplicate_groups:
                orig_candidate = auto_select_original(group)
                for p in group:
                    if p != orig_candidate and os.path.exists(p):
                        total_reclaimable_bytes += os.path.getsize(p)

            # Metric Banner
            mcol1, mcol2, mcol3 = st.columns(3)
            with mcol1:
                st.metric("Duplicate Groups", total_groups)
            with mcol2:
                st.metric("Duplicate Files Found", total_dupes)
            with mcol3:
                st.metric("Reclaimable Disk Space", format_size(total_reclaimable_bytes))

            st.write("---")
            st.subheader("⚙️ Deletion Settings & Batch Cleanup")

            c_del1, c_del2 = st.columns([1, 1])
            with c_del1:
                del_method = st.radio(
                    "Select Deletion Mode:",
                    [
                        "Move to '_duplicates_backup/' folder (Safe & Reversible)",
                        "Permanently Delete from Disk"
                    ],
                    help="Safe mode moves duplicate files to a backup subfolder so you can restore them if needed."
                )
                is_backup = "Safe & Reversible" in del_method
                backup_folder = os.path.join(st.session_state["scanned_folder"], "_duplicates_backup") if is_backup else None
                if is_backup:
                    st.caption(f"📁 Backup destination: `{backup_folder}`")

            with c_del2:
                st.write("**Batch Action (Clean All Duplicates)**")
                confirm_bulk = st.checkbox(
                    f"I confirm I want to remove all {total_dupes} duplicate files (keeping 1 original per group)",
                    key="confirm_bulk_del"
                )
                bulk_delete_clicked = st.button(
                    f"🗑️ Delete All {total_dupes} Duplicates Across All Groups",
                    type="primary",
                    disabled=not confirm_bulk
                )

            # Execute Bulk Delete if triggered
            if bulk_delete_clicked:
                deleted_count = 0
                freed_bytes = 0
                remaining_groups = []

                for g_idx, group in enumerate(duplicate_groups, start=1):
                    # Check which original the user picked in session state or default
                    orig_key = f"orig_choice_{g_idx}"
                    orig_file = st.session_state.get(orig_key, auto_select_original(group))

                    kept_files = [orig_file]
                    for p in group:
                        if p != orig_file:
                            # Check if explicitly uncheck
                            chk_key = f"mark_del_{g_idx}_{p}"
                            should_delete = st.session_state.get(chk_key, True)
                            if should_delete:
                                ok, size = delete_file(
                                    p,
                                    delete_method="backup" if is_backup else "permanent",
                                    backup_dir=backup_folder
                                )
                                if ok:
                                    deleted_count += 1
                                    freed_bytes += size
                            else:
                                kept_files.append(p)
                    if len(kept_files) > 1:
                        remaining_groups.append(kept_files)

                st.session_state["duplicate_groups"] = remaining_groups
                action_word = "moved to backup" if is_backup else "permanently deleted"
                st.session_state["status_alert"] = (
                    "success",
                    f"✅ Successfully {action_word} {deleted_count} duplicate file(s)! Freed {format_size(freed_bytes)}."
                )
                st.rerun()

            st.write("---")
            st.subheader("📋 Review Groups & Select Originals")
            st.caption("Each group contains identical/matching images. Choose which file to **KEEP (Original)**. Duplicates are marked for deletion.")

            # Per-Group Display and Individual Action
            for idx, group in enumerate(duplicate_groups, start=1):
                # Filter out any non-existent files
                existing_group = [p for p in group if os.path.exists(p)]
                if len(existing_group) <= 1:
                    continue

                best_original = auto_select_original(existing_group)
                orig_key = f"orig_choice_{idx}"
                if orig_key not in st.session_state:
                    st.session_state[orig_key] = best_original
                elif st.session_state[orig_key] not in existing_group:
                    st.session_state[orig_key] = best_original

                with st.expander(f"📁 Group #{idx}: {len(existing_group)} Identical Files", expanded=True):
                    # Radio button to pick original
                    chosen_orig = st.radio(
                        "Keep as Original:",
                        options=existing_group,
                        index=existing_group.index(st.session_state[orig_key]),
                        format_func=lambda p: f"{'⭐ (Suggested Original) ' if p == best_original else ''}{os.path.basename(p)} ({format_size(os.path.getsize(p))})",
                        key=orig_key,
                        horizontal=False
                    )

                    # Show thumbnails and file details in columns
                    cols = st.columns(min(len(existing_group), 4))
                    for c_i, p in enumerate(existing_group):
                        col = cols[c_i % len(cols)]
                        is_original = (p == chosen_orig)
                        details = get_image_details(p)

                        with col:
                            try:
                                with Image.open(p) as img_preview:
                                    st.image(img_preview, use_container_width=True)
                            except Exception:
                                st.write("*(Cannot preview image)*")

                            if is_original:
                                st.success("✅ **KEEP (Original)**")
                                st.caption(
                                    f"**File:** `{os.path.basename(p)}`\n\n"
                                    f"**Dimensions:** {details['dims']}\n\n"
                                    f"**Size:** {format_size(details['size'])}\n\n"
                                    f"**Modified:** {details['mtime_str']}"
                                )
                            else:
                                st.warning("🗑️ **DUPLICATE**")
                                del_chk_key = f"mark_del_{idx}_{p}"
                                st.checkbox(
                                    "Mark to delete",
                                    value=True,
                                    key=del_chk_key
                                )
                                st.caption(
                                    f"**File:** `{os.path.basename(p)}`\n\n"
                                    f"**Dimensions:** {details['dims']}\n\n"
                                    f"**Size:** {format_size(details['size'])}\n\n"
                                    f"**Modified:** {details['mtime_str']}"
                                )

                    # Group Deletion Button
                    st.write("")
                    col_del_btn, _ = st.columns([2, 5])
                    with col_del_btn:
                        group_del_clicked = st.button(
                            f"🗑️ Delete Duplicates in Group #{idx}",
                            key=f"btn_del_group_{idx}"
                        )

                    if group_del_clicked:
                        g_deleted = 0
                        g_freed = 0
                        remaining_in_group = [chosen_orig]

                        for p in existing_group:
                            if p != chosen_orig:
                                chk_key = f"mark_del_{idx}_{p}"
                                if st.session_state.get(chk_key, True):
                                    ok, size = delete_file(
                                        p,
                                        delete_method="backup" if is_backup else "permanent",
                                        backup_dir=backup_folder
                                    )
                                    if ok:
                                        g_deleted += 1
                                        g_freed += size
                                else:
                                    remaining_in_group.append(p)

                        # Update groups
                        new_groups = []
                        for g in duplicate_groups:
                            if g == group:
                                if len(remaining_in_group) > 1:
                                    new_groups.append(remaining_in_group)
                            else:
                                new_groups.append(g)

                        st.session_state["duplicate_groups"] = new_groups
                        action_word = "moved to backup" if is_backup else "permanently deleted"
                        st.session_state["status_alert"] = (
                            "success",
                            f"✅ Group #{idx}: Successfully {action_word} {g_deleted} duplicate file(s) ({format_size(g_freed)} freed)!"
                        )
                        st.rerun()

else:
    # Upload Mode
    st.info("💡 **Tip**: Web browsers do not allow web pages to delete files directly from your computer disk. To delete files automatically from disk, use **'Scan a Local Folder Path'** above.")

    uploaded_files = st.file_uploader(
        "Select multiple images from a folder",
        type=["jpg", "jpeg", "png", "webp", "bmp"],
        accept_multiple_files=True
    )

    if uploaded_files:
        if match_strictness == 0:
            groups = defaultdict(list)
            for uf in uploaded_files:
                file_hash = get_sha256_bytes(uf.getvalue())
                groups[file_hash].append(uf)
            duplicate_groups = [items for items in groups.values() if len(items) > 1]
        else:
            hashes = []
            for uf in uploaded_files:
                img = Image.open(uf).convert("RGB")
                hashes.append((uf, imagehash.phash(img)))
            visited = set()
            duplicate_groups = []
            for i, (uf_i, hash_i) in enumerate(hashes):
                if i in visited:
                    continue
                current_group = [uf_i]
                visited.add(i)
                for j in range(i + 1, len(hashes)):
                    if j not in visited and (hash_i - hashes[j][1]) <= match_strictness:
                        current_group.append(hashes[j][0])
                        visited.add(j)
                if len(current_group) > 1:
                    duplicate_groups.append(current_group)

        st.divider()
        if not duplicate_groups:
            st.success("No exact duplicate images found in your selection!")
        else:
            total_uploaded_dupes = sum(len(g) - 1 for g in duplicate_groups)
            st.warning(f"Found {len(duplicate_groups)} duplicate group(s) ({total_uploaded_dupes} duplicates).")

            # Allow user to download a clean ZIP with only 1 original file per duplicate group
            all_dupes_to_skip = set()
            for group in duplicate_groups:
                # Keep the first, skip the rest
                for duplicate in group[1:]:
                    all_dupes_to_skip.add(duplicate.name)

            unique_files = [uf for uf in uploaded_files if uf.name not in all_dupes_to_skip]

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for uf in unique_files:
                    zip_file.writestr(uf.name, uf.getvalue())
            zip_buffer.seek(0)

            st.download_button(
                label=f"📥 Download Deduplicated Images as ZIP ({len(unique_files)} Unique Files)",
                data=zip_buffer,
                file_name="deduplicated_images.zip",
                mime="application/zip",
                type="primary"
            )

            for idx, group in enumerate(duplicate_groups, start=1):
                st.subheader(f"Match Group #{idx} ({len(group)} files)")
                cols = st.columns(min(len(group), 4))
                for c_i, uf in enumerate(group):
                    col = cols[c_i % len(cols)]
                    with col:
                        st.image(Image.open(uf), use_container_width=True)
                        if c_i == 0:
                            st.success("✅ Original (Kept in ZIP)")
                        else:
                            st.warning("🗑️ Duplicate (Excluded)")
                        st.caption(f"**{uf.name}** ({format_size(uf.size)})")
