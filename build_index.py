import os
import json
import faiss
import imagehash
import numpy as np
from PIL import Image
from sentence_transformers import SentenceTransformer

IMAGE_DIR = "images"
HASH_THRESHOLD = 5  # Hamming distance <= 5 is treated as a near-duplicate
VALID_EXTS = (".jpg", ".jpeg", ".png", ".webp")

def build_local_index():
    os.makedirs(IMAGE_DIR, exist_ok=True)
    accepted_hashes = []
    valid_paths = []
    valid_images = []

    print("Scanning folder and filtering duplicates...")
    for filename in sorted(os.listdir(IMAGE_DIR)):
        if not filename.lower().endswith(VALID_EXTS):
            continue

        filepath = os.path.join(IMAGE_DIR, filename)
        try:
            img = Image.open(filepath).convert("RGB")
        except Exception as e:
            print(f"Skipping unreadable file {filename}: {e}")
            continue

        # Compute perceptual hash and compare against accepted images
        img_hash = imagehash.phash(img)
        if any((img_hash - existing_hash) <= HASH_THRESHOLD for existing_hash in accepted_hashes):
            print(f"[Duplicate Skipped] {filename}")
            continue

        accepted_hashes.append(img_hash)
        valid_paths.append(filepath)
        valid_images.append(img)

    if not valid_images:
        print("No valid images found in the 'images/' folder.")
        return

    print(f"Kept {len(valid_images)} unique images. Generating CLIP embeddings...")
    # Downloads clip-ViT-B-32 on first run and caches it locally
    model = SentenceTransformer("clip-ViT-B-32")
    embeddings = model.encode(valid_images, batch_size=32, convert_to_numpy=True, show_progress_bar=True)
    embeddings = embeddings.astype("float32")

    # L2-normalize vectors so Inner Product equals Cosine Similarity
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    # Save index and file mapping to disk
    faiss.write_index(index, "image_index.faiss")
    with open("metadata.json", "w", encoding="utf-8") as f:
        json.dump(valid_paths, f, indent=2)

    print("Done! Saved 'image_index.faiss' and 'metadata.json'.")

if __name__ == "__main__":
    build_local_index()