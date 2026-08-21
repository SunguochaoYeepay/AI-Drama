# Screenplay and Package Format

## Readable screenplay

Use a compact, visual format that DramaClaw can display without semantic rewriting:

```text
第 1 集

1-1 场景：客餐厅 夜 内
人物：陈浩、林悦、小宇

△陈浩站在左侧入户门，手里握着手机；林悦和小宇在中央木桌旁。
陈浩（压着怒气）：这个月家用卡里少了三千块，你转到哪儿去了？
△林悦停住动作，回头看向陈浩，小宇放下铅笔。
林悦（受伤、防备）：你一进门就查账？
```

Each `△` line describes visible action only. Do not put hidden backstory in a visual line. Keep one main action per beat and make spatial relationships explicit.

## Production package minimum

```json
{
  "schema_version": "ai-drama.production.v1",
  "source_package_id": "stable-id-v1",
  "project": {},
  "episode": {},
  "characters": [],
  "locations": [],
  "dialogues": [],
  "scenes": [],
  "assets": []
}
```

Each shot must have:

```json
{
  "id": "1-1-01",
  "visual_description": "Visible people, positions, action, location, and props in this frame.",
  "characters": ["chen_hao"],
  "reference_assets": ["chen_hao", "apartment_dining_room_night"],
  "location_reference_asset": "location_plate_apartment_dining_room_night",
  "prop_reference_assets": ["prop_household_ledger", "prop_black_phone"],
  "shot_type": "中景",
  "camera_angle": "餐桌侧方平视",
  "lens": "50mm equivalent",
  "camera_action": "固定机位",
  "action": "One primary visible action.",
  "emotion": "Restrained and observable emotion.",
  "speaking_character_ids": ["chen_hao"],
  "dialogue_lines": [{"id": "d001", "speaker_id": "chen_hao", "speaker_name": "陈浩", "text": "Exact spoken text.", "emotion": "restrained_anger"}],
  "dialogue_visual_prompt": "说话者与台词必须明确：陈浩说：‘Exact spoken text.’ 当前画面优先表现陈浩的自然说话嘴型和眼神，其余角色只做反应；最终对白以后期音轨为准。",
  "continuity_in": "State inherited from the preceding shot.",
  "continuity_out": "State the next shot must inherit.",
  "dialogue_ids": ["d001"],
  "keyframe_prompt": "...",
  "qwen_prompt": "...",
  "flux_prompt": "...",
  "negative_prompt": "...",
  "video_prompt": "...",
  "h3_prompt": "...",
  "status": "pending_review"
}
```

`visual_description` is required even when `action` is present. `dialogue_ids` alone are not enough: copy the speaker name and exact text into `dialogue_lines`, `dialogue_visual_prompt`, and the model prompts. `audio_asset_id`, `audio_start_ms`, and `audio_end_ms` are optional and must only be used when the URL is reachable by DramaClaw.

Location plates and prop references are independent assets. Generate the empty location first, then recurring objects, then characters and action frames. A shot must reference the location plate and every continuity-critical prop it shows. A missing image is `pending_generation`, never a made-up URL.

## Continuity chain

For every adjacent pair, record the handoff explicitly:

```json
{
  "from_shot": "1-1-01",
  "to_shot": "1-1-02",
  "transition": "tail_frame_reference",
  "tail_state": "Father reaches the table; phone remains beside the ledger; mother has turned toward him."
}
```

Use `tail_frame_reference` for the same visual chain. Use `hard_cut` when changing angle or composition, and describe the inherited pose/prop state so the new keyframe does not reset the action.
