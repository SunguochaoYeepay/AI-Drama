# Realistic People Reference

## Useful realism cues

Use a small number of concrete cues that describe observable evidence:

- ordinary, believable facial asymmetry;
- natural skin texture and subtle pores;
- slight under-eye variation appropriate to age;
- individual flyaway hairs and believable hair clumps;
- small clothing wrinkles and practical fabric tension;
- imperfect but natural posture;
- candid eye lines and restrained facial movement;
- practical room lighting with a clear source;
- modest lived-in props and non-showroom interiors;
- documentary or candid photography feeling when the shot allows it.

Do not stack every cue into every prompt. Pick the cues that solve the current failure.

## Anti-fake vocabulary

When a face is plastic, replace beauty language with: `ordinary face`, `natural asymmetry`, `unretouched skin`, `subtle pores`, `non-editorial lighting`, `believable age`, and `restrained expression`.

When a scene is too staged, add: `candid blocking`, `practical household layout`, `slightly imperfect posture`, `unposed moment`, and a specific camera position.

When a scene is too cinematic, reduce: `epic`, `masterpiece`, `perfect composition`, `luxury`, `glamour`, and heavy backlight. Keep one clear light source and a normal lens feeling.

## Cues to avoid by default

Avoid `网红脸`, `完美身材`, `最佳骨相`, `陶瓷肌`, `冷白皮`, `INS风`, `偶像气质`, `随机妆容`, and repeated quality superlatives. They bias the model toward generic influencer portraits and destroy age, occupation, and continuity.

## Prompt weighting

Parenthetical weights are not portable across engines. Treat them as workflow-specific syntax only when the ComfyUI node documentation confirms support. For Qwen and Flux, express priority through ordering, repetition of identity anchors, reference images, and explicit exclusions.

## Candidate review

Generate four candidates for a new character or location. Reject any candidate with:

- changed age, hair, or wardrobe;
- smooth mannequin skin or symmetrical “AI face”;
- missing or extra fingers;
- unreadable but prominent pseudo-text;
- a background that contradicts the location plate;
- a pose that cannot be reproduced in the next shot.

Keep the accepted asset ID and seed. Do not silently replace it during later shot generation.
