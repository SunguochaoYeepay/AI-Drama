---
name: generate-ai-drama-video
description: Turn an accepted Chinese drama story and audio track in this repository into a visual character bible, Qwen Image keyframes, and short MiniMax H3 video shots through ComfyUI. Use when an agent needs to design stable recurring characters, write keyframe or storyboard prompts, run the official Qwen Image Lightning 4-step workflow, write H3 I2VA/FL2VA prompts in the official format, run a fast H3 4-step test, inspect generated media, or prepare shots for later audio alignment and lip sync.
---

# Generate AI Drama Video

Create repeatable keyframes and short H3 shots without changing the accepted dialogue mix. Work from the repository root containing `ai_drama/`, `examples/`, `workflows/`, and `outputs/`.

Read [official-workflows.md](references/official-workflows.md) before changing a workflow or H3 prompt. Read [visual-quality.md](references/visual-quality.md) before writing character or scene prompts.
For the reusable realism and continuity prompt process, also read [../generate-ai-drama-visuals/SKILL.md](../generate-ai-drama-visuals/SKILL.md) and its references.

## Workflow

1. Inspect the current branch, working tree, story JSON, final audio, SRT, and existing video plan. Never expose `.env` values or commit generated media.
2. Confirm the raw ComfyUI API endpoint. A frontend such as DramaClaw may use port `8080` while ComfyUI itself uses port `8188`; query `/system_stats` and `/object_info` before submitting work.
3. Build one video plan under `examples/`. Define stable ages, faces, hair, clothing, location, and props once, then repeat those anchors verbatim in every keyframe prompt.
4. Split the accepted audio into shots using the SRT timing. Keep each H3 shot between 4 and 15 seconds and use 24 fps. Do not force a whole multi-minute drama into one generation.
5. Generate a neutral character lineup first, then generate the opening and conflict keyframes. Use Qwen Image Edit with accepted references for full production when identity drift matters; a direct text-to-image frame is sufficient only for an initial pipeline test.
6. Run a Qwen keyframe from the repository root:

   ```bash
   python3 -m ai_drama video-keyframe examples/<story>_video.json <keyframe_id> \
     --comfyui-url http://<host>:8188
   ```

7. Inspect faces, hands, ages, clothing, composition, and continuity. Obtain user approval for the character lineup and representative keyframes before generating all shots.
8. Write every H3 prompt with the exact official section names and order. For I2VA, anchor `<Picture 1>` at `0.00` seconds. Keep spoken dialogue out of a motion-only test when an accepted MiniMax Speech track will be synchronized later.
9. Run the first 5-second H3 test with the official 4-step 768p Turbo settings:

   ```bash
   python3 -m ai_drama video-h3 examples/<story>_video.json <shot_id> \
     --image outputs/<story>_video/video/keyframes/<keyframe_id>.png \
     --comfyui-url http://<host>:8188
   ```

10. Verify the MP4 with `ffprobe`, inspect representative frames, and listen for unwanted generated speech or music. Keep only useful local renders under ignored `outputs/`.
11. After keyframe approval, generate the remaining shots, align them to the accepted SRT/audio, and perform lip sync as a separate controlled stage. Do not replace the accepted MiniMax Speech 2.8 dialogue with H3-generated speech unless the user requests a comparison.
12. Publish the accepted artifacts to DramaClaw when a Freezone canvas is available:

    ```bash
    python3 -m ai_drama publish-canvas examples/<story>.json examples/<story>_video.json \
      --project <project-name-or-id> --canvas ai_drama_assets \
      --dramaclaws-url http://<host>:8080
    ```

    This creates deterministic nodes for the project note, script, final audio, available keyframes, H3 test shot, and video plan. It uploads only local outputs and writes the canvas through the official `/freezone/upload` and `/freezone/canvases/{canvas_id}` APIs.
13. Run `python3 -m unittest discover -v`, the Skill validator, and `git diff --check` before publishing source changes.

## Guardrails

- Base workflows on official JSON and the live `/object_info`; do not invent node names or ports.
- Preserve the 4-step H3 values: 1344x768, 124 frames, video shift 6, audio shift 3, Euler, simple scheduler, and the 4-step 768p LoRA.
- Use a fixed seed during review. Change it intentionally and record the accepted result.
- Generate one test shot before a full batch. Stop and inspect any model-load, validation, black-frame, identity-drift, or malformed-hand failure.
- Treat online-hotspot stories as potentially copyrighted, private, or defamatory. Require fact checking and meaningful adaptation before monetized publication.
