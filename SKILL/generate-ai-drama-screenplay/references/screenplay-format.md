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
  "shot_type": "中景",
  "camera_angle": "餐桌侧方平视",
  "lens": "50mm equivalent",
  "camera_action": "固定机位",
  "action": "One primary visible action.",
  "emotion": "Restrained and observable emotion.",
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

`visual_description` is required even when `action` is present. `audio_asset_id`, `audio_start_ms`, and `audio_end_ms` are optional and must only be used when the URL is reachable by DramaClaw.

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
