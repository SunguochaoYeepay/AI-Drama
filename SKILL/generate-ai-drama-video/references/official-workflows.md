# Official Workflow Sources

Use the following sources as the authority before changing model wiring or prompt structure:

- Qwen Image ComfyUI guide: <https://docs.comfy.org/tutorials/image/qwen/qwen-image>
- Qwen Image Lightning official repository: <https://github.com/ModelTC/Qwen-Image-Lightning>
- Qwen 4-step editor workflow: <https://github.com/ModelTC/Qwen-Image-Lightning/blob/main/workflows/qwen-image-4steps.json>
- MiniMax H3 official repository: <https://github.com/MiniMax-AI/MiniMax-H3>
- MiniMax H3 prompt Skill: <https://github.com/MiniMax-AI/MiniMax-H3/tree/main/skills/h3-prompt-writing>
- ComfyUI H3 I2V template: <https://github.com/Comfy-Org/workflow_templates/blob/main/templates/video_minimax_h3_i2v.json>
- MiniMax H3 Turbo official repository: <https://github.com/ModelTC/Minimax-H3-Turbo>

## Qwen Image 4-Step Settings

- Diffusion model: `qwen_image_fp8_e4m3fn.safetensors`
- Text encoder: `qwen_2.5_vl_7b_fp8_scaled.safetensors`, type `qwen_image`
- VAE: `qwen_image_vae.safetensors`
- LoRA: `Qwen-Image-Lightning-4steps-V1.0.safetensors`, strength `1`
- AuraFlow shift: `3`
- Sampler: Euler, simple scheduler, 4 steps, CFG `1`, denoise `1`

## H3 4-Step I2VA Settings

- Diffusion model: `minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- Text encoder: `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`, type `minimax`
- Video VAE: `minimax_h3_video_vae_fp16.safetensors`
- Audio VAE: `minimax_h3_audio_vae_fp32.safetensors`
- LoRA: `minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors`, strength `1`
- Canvas: `1344x768`; video shift `6`; audio shift `3`
- Sampler: Euler, simple scheduler, exactly 4 steps
- Duration: 24 fps and a valid `17k+5` frame count; use `124` frames for about 5.17 seconds

## H3 I2VA Prompt Form

Write the body in English. Preserve any required Chinese dialogue only inside `<d>[Chinese] ...</d>`. For a motion-only test, include no dialogue.

```text
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: N/A
```

Keep `[Shot 1]` untimestamped. Start later shots with `[Shot N] At MM:SS.mmm`. Describe camera motion using type, amplitude, and speed. Put ambient and physical sounds in `overall_soundscape`; do not repeat dialogue there.
