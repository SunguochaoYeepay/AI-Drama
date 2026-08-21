---
name: generate-ai-drama-visuals
description: Generate realistic, continuous character references, locations, keyframes, and shot prompts for AI short dramas using Qwen Image, Flux, or compatible ComfyUI workflows. Use when a confirmed screenplay must become production-ready image prompts, when generated people look synthetic, when character identity or wardrobe drifts between shots, or when keyframes must be prepared for later H3 video generation.
---

# Generate AI Drama Visuals

Turn an accepted screenplay and character bible into controlled visual assets. Treat this skill as a prompt compiler and quality-control workflow, not as a second story writer. Preserve story facts, then add concrete photographic direction only where the screenplay leaves visual choices open.

Read [realism.md](references/realism.md) before writing prompts. Read [model-profiles.md](references/model-profiles.md) when choosing Qwen, Flux, or a ComfyUI workflow.

## Non-Negotiable Rules

- Never rewrite the plot, relationships, period, setting, or character identity.
- Lock each recurring character's face anchors, age, hair, wardrobe, body type, and signature props. Repeat the same anchors in every shot.
- Use `婆婆` for the husband's mother in the family-money story. Do not replace it with `岳母`.
- Keep one main visible action per frame. Do not turn a shot into a paragraph of invisible backstory.
- Write prompts as connected, concrete sentences. State where each character starts, what single action occurs, and where the body/props end; this gives single-image-to-video a usable handoff instead of leaving the model to infer blocking from keywords.
- If a shot has dialogue, name the speaker and include the exact spoken text in the visual/video prompt. State the speaking order when there are multiple lines, then describe non-speaking characters as listeners or reactors. Do not assume a `dialogue_ids` array will be read by an image/video model.
- Use concrete camera and lighting language instead of abstract praise such as “最好看” or “高级感”.
- Keep creative freedom in incidental background details, natural lighting variation, and small gestures, not in identity, clothing, geography, or story facts.
- Do not blindly copy Stable Diffusion weighting syntax such as `(term:1.6)`. Qwen and Flux workflows may treat it as literal text or ignore it.
- Do not use “随机动作、随机角度、随机妆容” for a continuity-critical drama shot. Randomness is acceptable only when generating an unapproved exploratory portrait.
- Do not use celebrity, influencer, perfect-body, porcelain-skin, or excessive beauty language unless the story explicitly requires it. These terms often create plastic faces and fashion-editorial lighting.

## Workflow

### 1. Lock facts before prompting

Extract a fact sheet from the accepted screenplay:

- `source_package_id`, episode, scene, shot, and dialogue IDs;
- period, country, location, time of day, interior/exterior;
- visible characters and their relationships;
- action, emotional beat, props, and continuity notes;
- audio segment and target duration when available.

If a fact is missing, mark it `待确认` or choose a conservative everyday interpretation. Never silently invent a new relationship or visual genre.

### 2. Build character references first

Create one reference prompt per visual character before scene prompts. Use a neutral studio background, front view plus three-quarter view, natural expression, ordinary proportions, and the locked wardrobe. Generate multiple candidates, approve one, and keep its asset ID in every later shot.

For a narrator or voice-only role, set `visual: false`; do not create a meaningless portrait.

### 3. Build the location plate

Create a clean location reference without characters. Specify spatial anchors that a camera can preserve: door position, table position, windows, dominant light source, and fixed props. Reuse the same location asset for all shots in that scene.

Create separate multi-view reference sheets for recurring props that affect continuity: furniture, phones, ledgers, school materials, dishes, tools, or any object touched by a character. Each prop sheet should show the same object in at least six consistent views (front, three-quarter left, three-quarter right, side views, top, and a relevant detail) on a neutral seamless background with uniform studio lighting. Do not place the prop in the story room, on a table, or in a lifestyle scene; the isolated sheet is the identity reference, while the location plate controls the environment. Give each asset a stable ID and attach the location and prop asset IDs to every dependent shot. Do not invent an asset URL; mark an ungenerated reference `pending_generation`.

### 4. Compile each shot prompt

Write prompts in this order:

1. medium and photographic intent;
2. aspect ratio, composition, camera position, and lens feeling;
3. location and lighting;
4. character identity and wardrobe anchors;
5. blocking and one main action;
6. expression and restrained emotion;
7. props and spatial continuity;
8. realism constraints and exclusions.

Add a dialogue block after the action block: `说话者与台词必须明确：林悦说：“……”；陈浩说：“……”；当前画面优先表现说话者的自然嘴型和眼神，其余角色只做反应；最终对白以后期音轨为准。` For a silent shot, explicitly say that there is no dialogue and all characters keep their mouths naturally closed.

Write a required `visual_description` that states what is visibly in the frame. `action` is supplementary and never replaces `visual_description`.

Generate separate `qwen_prompt` and `flux_prompt` fields when both engines may be used. Qwen prompts can remain structured Chinese. Flux prompts should use concrete English photography language and avoid keyword piles.

For adjacent shots, add `continuity_in` and `continuity_out` when the package supports them. `continuity_out` must be copied into the next shot's `continuity_in`. If the next shot uses a new angle, label the transition as a hard cut and preserve the action state; if it continues the same action, use the previous clip's tail frame as the next image input.

### 5. Add anti-synthetic constraints

Use a small number of positive realism cues: ordinary asymmetry, natural skin texture, subtle pores, fine facial hair where appropriate, flyaway hair, slight clothing wrinkles, imperfect but believable posture, practical home lighting, candid eye lines, and restrained expressions.

Use negative constraints only for likely failure modes: extra people, duplicate limbs, deformed hands, unreadable text, costume drift, age drift, changed hair, plastic skin, over-smoothed face, beauty-editorial lighting, and unwanted period elements. See [realism.md](references/realism.md).

### 6. Generate in approval gates

Use this order:

1. character reference candidates;
2. approved character lineup;
3. location plate;
4. one opening keyframe;
5. one continuity keyframe;
6. only then batch the remaining shots.

Hold video generation until the keyframe is approved. Keep a fixed seed during comparison and record the accepted seed, workflow, resolution, and reference asset IDs.

## Production Package Contract

For DramaClaw import, every package should include:

- top-level `schema_version: "ai-drama.production.v1"`;
- top-level `source_package_id` for idempotent re-import;
- `characters`, `locations`, `scenes`, `dialogues`, and `assets`;
- every shot: `id`, `visual_description`, `characters`, `reference_assets`, `location_reference_asset`, `prop_reference_assets`, `speaking_character_ids`, `dialogue_lines`, `dialogue_visual_prompt`, `shot_type`, `action`, `emotion`, `keyframe_prompt`, `negative_prompt`, `video_prompt`, and `status`;
- optional `qwen_prompt`, `flux_prompt`, `h3_prompt`, `audio_asset_id`, `audio_start_ms`, and `audio_end_ms`.

If an audio asset is not reachable by DramaClaw, omit its `audio_asset_id` rather than inventing a URL. The visual package must still be valid.

## Quality Gate

Before delivery, check:

- Does the image look like a real person rather than a beauty ad?
- Can the viewer identify age, role, emotion, and action without explanation?
- Are hands, eyes, teeth, hair edges, clothing seams, and body proportions plausible?
- Are the same face, hair, wardrobe, table, room, and props preserved across adjacent shots?
- Is the camera framing intentional rather than randomly pretty?
- Does the prompt forbid text, subtitles, logos, watermarks, and accidental extra characters?
- Does the result still match the accepted screenplay and audio timing?

Reject and revise the prompt when a model changes identity, adds a new relationship, turns an everyday room into a luxury set, or produces polished influencer skin that contradicts the story.
