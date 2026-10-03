# Ideas

Features that are not in the build spec. Written down here instead of built (rule 6).

- Also pass the lower-case proxy variables (`http_proxy`, `https_proxy`, `no_proxy`) to plugins. Section 4.4 lists only the upper-case names.
- Reuse reference embeddings across runs with a cache keyed by reference hash, plugin, device,
  thread setting and versions (environment id, wrapper version). Removed from 0.1 by amendment A9
  because the content-hash-only key mixed CPU and GPU results.
- A golden file per CPU thread setting, so CPU golden tests can run on machines with other core
  counts instead of being skipped.
- A Docker `full` image with the plugin environments built in. Removed from 0.1 (amendment A16,
  Roy at GATE 3) because fadtk and kadtk write their three CLAP checkpoints (4.9 GB each tool)
  into their own package folders inside the environment the first time they run. In an image
  that is read only (Apptainer, `docker run --user`) the write fails, and otherwise the files are
  downloaded again in every new container. Weights must not be baked into an image, and nothing
  may be linked into installed packages. A future version needs a way to keep those files outside
  the environment.

