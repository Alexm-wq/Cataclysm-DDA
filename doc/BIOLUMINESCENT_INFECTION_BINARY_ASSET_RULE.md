# Bioluminescent infection test assets — binary PNG handling rule

These test sprites are binary PNG assets. When replacing them, do **not** write base64 text through the GitHub contents/text-file path.

Required procedure:

1. Open the source PNG locally with an image decoder and verify it succeeds.
2. Build any atlas locally as an actual PNG file.
3. Re-open the finished atlas and verify the PNG again.
4. Commit the exact binary bytes using the Git blob API with `encoding: base64`.
5. Build the tree/commit from that blob SHA.
6. Fetch the committed file metadata and confirm its Git blob SHA matches the blob that was uploaded.

This exists because earlier test-sprite updates repeatedly produced SDL `Error reading the PNG file` failures when binary image data was mishandled. Future bioluminescent infection sprite replacements should follow this procedure every time.
