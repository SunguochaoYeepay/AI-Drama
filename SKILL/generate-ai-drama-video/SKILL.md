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
3. Build one video plan under `examples/`. Define stable ages, faces, hair, clothing, location, and props once. For each keyframe, connect the location plate first and the visible character references after it; leave prop references unconnected until a specific object shot is approved. Put the matching `@图片N=角色/场景` map in the still-image prompt, keep the complete continuity inventory in the package and canvas, and send no more than five image references to a Qwen generation request. Generate and approve the location plate and recurring prop reference images before generating dependent character/action frames.
4. Split the accepted audio into shots using the SRT timing. Keep each H3 shot between 4 and 15 seconds and use 24 fps. Do not force a whole multi-minute drama into one generation.
5. Generate a neutral character lineup first, then generate the opening and conflict keyframes. Use Qwen Image Edit with accepted references for full production when identity drift matters; a direct text-to-image frame is sufficient only for an initial pipeline test.
6. Before batching keyframes, make a continuity table for adjacent shots. Record `continuity_in`, `continuity_out`, fixed character positions, facing direction, hand/prop state, door state, lighting, and the intended transition (`tail_frame_reference` or `hard_cut`). A prompt must describe the inherited state in ordinary connected sentences; do not rely on isolated keyword lists.
7. For same-angle or same-action clips, generate the next clip from the previous clip's final frame. Inspect and save the final frame, then use it as the next shot's start image while retaining the approved character and location references. This is the default single-image-to-video chain.
8. For a deliberate angle or composition change, do not morph between unrelated keyframes. Cut at an action or dialogue pause, generate the new keyframe from the previous tail-state description, and keep the next clip's first pose consistent with that state.
9. Run a Qwen keyframe from the repository root:

   ```bash
   python3 -m ai_drama video-keyframe examples/<story>_video.json <keyframe_id> \
     --comfyui-url http://<host>:8188
   ```

10. Inspect faces, hands, ages, clothing, composition, and continuity. Obtain user approval for the character lineup and representative keyframes before generating all shots.
11. Write every H3 prompt with the exact official section names and order. For I2VA, anchor `<Picture 1>` at `0.00` seconds. Include the exact speaker name and spoken line in the H3/video prompt, plus the speaking order for multiple lines. Describe the other characters as listeners/reactors. Keep this dialogue block out of the Qwen/Flux still-image prompt; the H3 audio can be muted or replaced later, but its visual prompt must still direct who is speaking and what is being said.
12. Run the first 5-second H3 test with the official 4-step 768p Turbo settings:

   ```bash
   python3 -m ai_drama video-h3 examples/<story>_video.json <shot_id> \
     --image outputs/<story>_video/video/keyframes/<keyframe_id>.png \
     --comfyui-url http://<host>:8188
   ```

13. Verify the MP4 with `ffprobe`, inspect the first and last frame, and listen for unwanted generated speech or music. Keep only useful local renders under ignored `outputs/`. A clip is not approved until its tail frame matches the next shot's expected input state.
14. After keyframe approval, generate the remaining shots, align them to the accepted SRT/audio, and perform lip sync as a separate controlled stage. Do not replace the accepted MiniMax Speech 2.8 dialogue with H3-generated speech unless the user requests a comparison.
15. Publish the accepted artifacts to DramaClaw when a Freezone canvas is available:

    ```bash
    python3 -m ai_drama publish-canvas examples/<story>.json examples/<story>_video.json \
      --project <project-name-or-id> --canvas ai_drama_assets \
      --dramaclaws-url http://<host>:8080
    ```

    This creates deterministic nodes for the project note, script, final audio, available keyframes, H3 test shot, and video plan. It uploads only local outputs and writes the canvas through the official `/freezone/upload` and `/freezone/canvases/{canvas_id}` APIs.
16. Run `python3 -m unittest discover -v`, the Skill validator, and `git diff --check` before publishing source changes.

## Guardrails

- Base workflows on official JSON and the live `/object_info`; do not invent node names or ports.
- Preserve the 4-step H3 values: 1344x768, 124 frames, video shift 6, audio shift 3, Euler, simple scheduler, and the 4-step 768p LoRA.
- Use a fixed seed during review. Change it intentionally and record the accepted result.
- Generate one test shot before a full batch. Stop and inspect any model-load, validation, black-frame, identity-drift, or malformed-hand failure.
- Treat online-hotspot stories as potentially copyrighted, private, or defamatory. Require fact checking and meaningful adaptation before monetized publication.
