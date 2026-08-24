---
name: generate-ai-drama-screenplay
description: Turn a Chinese story, novel excerpt, or social-media plot into a complete, faithful short-drama screenplay and a DramaClaw-compatible production package. Use when dialogue, scene actions, shot descriptions, character continuity, audio line IDs, and visual prompts must be planned before MiniMax audio or Qwen/Flux/H3 production.
---

# Generate AI Drama Screenplay

Convert an accepted story into production data without asking a second model to rewrite the plot. This skill owns story decomposition, scene blocking, dialogue IDs, and the contract consumed by the audio and visual skills. DramaClaw's native novel analyzer is not the source of truth for this workflow.

## Workflow

1. Read the complete story and extract facts before writing: setting and period, characters and relationships, conflict, escalation, turning point, resolution, props, and any facts that must not be invented. For a current or real-person story, mark claims that require verification and avoid defamatory assertions.
2. Build a character bible. Give every recurring speaker a stable ID, name, role, age range, voice direction, visual anchors, wardrobe, and relationship. Use `婆婆` for the husband's mother when that relationship is intended; never silently change it to `岳母`.
3. Divide the story into scenes. Each scene has one location/time and one dramatic purpose. Preserve chronology. A practical short-drama scene normally contains 2-6 shots, with one visible primary action per shot.
4. Write a readable screenplay in the local DramaClaw format. Every beat needs a concrete `△` visual action, and every spoken line needs a speaker, performance direction, and stable dialogue ID in the production package. Include OS narration only when it exists in the accepted story.
5. Write the production package under `examples/` with `schema_version: "ai-drama.production.v1"`, `source_package_id`, `project`, `episode`, `characters`, `locations`, `dialogues`, `scenes`, and `assets`. Do not use `package_id`; the field is `source_package_id`.
6. For every shot, include `visual_description`; `action` cannot substitute for it. Also include `characters`, `reference_assets`, `shot_type`, `camera_angle`, `lens`, `camera_action`, `emotion`, `keyframe_prompt`, `negative_prompt`, `video_prompt`, `h3_prompt`, `transition_mode`, `previous_shot_id`, `keyframe_generation`, `qwen_reference_plan`, and status. Keep Qwen prompts structured Chinese and Flux prompts sentence-like English when both engines are planned.
7. Add continuity states to the shot plan: what is true at the start (`continuity_in`) and at the end (`continuity_out`). State positions, facing direction, hand/prop state, emotional level, lighting, and any door or furniture state. A later shot must inherit the previous shot's end state. Default to `tail_frame_continue`; choose `tail_frame_reframe` only when a new narrative focus, reveal, or detail shot earns a camera change.
8. Create a continuous prompt chain. For `tail_frame_continue`, set `keyframe_generation: "skip_keyframe_use_previous_video_tail"`: the next video starts from the previous clip's tail frame. For `tail_frame_reframe`, set `keyframe_generation: "generate_new_angle_from_previous_video_tail"`, make the predecessor tail `@图片1`, and allow only two further Qwen Edit identity references. Mark this keyframe `waiting_for_previous_video_tail`; never invent a tail-frame asset URL or pre-generate it.
9. Keep visual prompts grounded. Repeat identity and wardrobe anchors, use ordinary facial asymmetry, natural skin, practical lighting, clothing wrinkles, and lived-in rooms. Do not add influencer language, random actions, random angles, or invented props. Read `../generate-ai-drama-visuals/SKILL.md` for the realism gate.
10. Validate before handing off:

   ```bash
   python3 -m json.tool examples/<package>.json >/dev/null
   python3 -m ai_drama generate examples/<audio-story>.json --dry-run
   git diff --check
   ```

   Confirm every shot has `visual_description`, every dialogue ID is unique, every referenced character and location exists, every `continuity_in` matches the preceding `continuity_out`, and no audio URL is invented.

## Handoff Order

Use this order after the package is approved:

`screenplay/package -> generate-ai-drama-audio -> approve dialogue mix -> generate-ai-drama-visuals -> approve keyframes -> generate-ai-drama-video -> H3 clips -> final edit`

The screenplay skill does not generate audio, images, or video. It prepares the stable facts and shot contract those skills must preserve.

## Import Guardrails

- Import `examples/<package>.json` through DramaClaw's structured production-package entry.
- Do not upload a storyboard-only JSON (`ai-drama.storyboard.v1`) through the production-package validator; it intentionally lacks `project`, `episode`, and `scenes`.
- Keep storyboard diagrams, continuity references, and generated media as separate canvas resources. They are review aids, not replacements for the production package.
- `assets` entries with `status: "pending_generation"` are production metadata only. They will not display as images until a real asset URL is present or the DramaClaw importer is extended to map location/prop assets to its native scene and prop records.
- Do not commit `.env`, API keys, or generated files under `outputs/`.

## References

- Read [screenplay-format.md](references/screenplay-format.md) for the local screenplay and package field contract.
- Read [../generate-ai-drama-visuals/SKILL.md](../generate-ai-drama-visuals/SKILL.md) before authoring visual prompts.
