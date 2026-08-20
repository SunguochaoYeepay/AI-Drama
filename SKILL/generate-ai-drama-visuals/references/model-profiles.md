# Qwen and Flux Profiles

## Qwen Image

Use Qwen when Chinese structured descriptions, image editing, and reference-driven identity preservation are the priority. Put the shot facts first, then identity anchors, then camera and lighting. Use the approved character and location images as references whenever continuity matters.

Prefer a direct, readable prompt over a keyword cloud. Keep the negative prompt focused on actual failure modes. Use the repository's official ComfyUI workflow and its supported resolution, sampler, steps, and reference inputs; do not invent node names or assume that a different Qwen checkpoint accepts the same parameters.

## Flux

Use Flux when natural photographic texture, lighting, and lens language are the priority. Write an English sentence-like prompt with concrete subjects and blocking. Keep the identity anchors near the beginning and explicitly state what must remain unchanged from the reference images.

Do not assume that Stable Diffusion-style `(term:weight)` syntax works. Use reference images, prompt order, fixed seeds, and candidate review instead.

## Shared continuity protocol

For either model:

1. Generate and approve a character reference.
2. Generate and approve a location plate.
3. Pass both references into the shot workflow.
4. Keep the same seed during prompt comparisons.
5. Change one variable at a time: framing, action, lighting, or expression.
6. Save the accepted workflow, seed, prompt, and reference asset IDs in the production package.

The model profile changes wording and workflow parameters; it must never change the screenplay facts or character identity contract.
