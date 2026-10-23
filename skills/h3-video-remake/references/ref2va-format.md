# Ref2VA 六段式提示词格式规范

H3 Ref2VA 模式的完整输出必须严格按以下六段顺序，字段名逐字保留。全部用英文撰写，仅台词 `<d>` 内和画面可见文字保留原文（中文）。

## 六段结构

```
subject_definitions:
<Subject 1> is ... in <Picture 1>, with ...
<Subject 2> is ... in <Picture 2>, with ...
# 有参考音频时加（可选）：
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).
<Picture N> is the first-frame keyframe for [Shot 1], showing ...

summary:
[reference generation + keyframe completion] The target video is ...
# 有参考音频时任务类型追加 + audio reference：
# [reference generation + keyframe completion + audio reference]

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 3]): fully_preserved - ...
<Subject 2> (appears in [Shot 2]): fully_preserved - ...
# 有参考音频时加：
<Audio 1>: reference - its vocal timbre guides <Subject 1>'s dialogue delivery without copying the original signal.
<Picture N> ([Shot 1] first frame): fully_preserved - ...

detailed_description:
The target video uses a 3D CGI plush-toy cinematic style with ...
[Shot 1] ...
[Shot 2] At 00:03.300, the camera cuts to ...

overall_soundscape:
...

non_diegetic_music:
...
```

## 各段写法

### 1. subject_definitions
- 每个角色一行，用 `<Subject N>`，对应 `<Picture N>`（角色设定图）
- 描述要具体到物种、毛色、标志性器官/配饰、体型
- 首帧关键帧单独一行，标为 `<Picture N>`（N 为角色图之后的下一个编号），注明 `first-frame keyframe for [Shot 1]`
- 不在本段出现的角色也要定义（后面镜头会出现），但可注明 "does not appear in this segment"

### 2. summary
- 必须以 `[reference generation + keyframe completion]` 开头（如果是纯参考生成无关键帧则用 `[reference generation]`）
- 一段话讲清：时长、风格、场景、这段发生了什么、角色关系
- 不要在这里重复台词

### 3. retention_analysis
- 每个 `<Subject N>` 一行，括号内列出出现的镜头编号
- 关系标记固定用 `fully_preserved`（角色复刻必须全保留），后接破折号说明保留了哪些具体特征
- 首帧关键帧也一行，标 `([Shot 1] first frame): fully_preserved - ...`
- 不出现的角色写 `not_applicable - does not appear in this segment`
- **这是防漂移的核心段，必须每个角色都覆盖**

### 4. detailed_description
- 开头 1~2 句风格描述（灯光、色调、景深）
- `[Shot 1]` 无时间戳，从首帧关键帧构图开始
- 后续镜头：`[Shot N] At MM:SS.mmm, the camera cuts to ...`
- 时间戳必须递增，且在段时长内
- 台词格式：`<d>[Chinese] 原文逐字，标点也保留。</d>`
- 说话人：首次出现时在角色名后写音色描述 + `(S1)`，后续直接用 `(S1)`；**有参考音频时**改为 `<Subject N> (Sx) says, using the voice timbre referenced from <Audio N>: <d>...</d>`，不要再叠加自由音色词，情绪靠副词（angrily / indignantly）传达
- 镜头运动写自然英语：`The camera pushes in with small amplitude at slow speed toward...`
- 角色首次在镜头里出现时，引用 `<Subject N>` 并描述其当前动作/表情

### 5. overall_soundscape
- 1~4 句，一段连续文字
- 覆盖：环境底噪（办公室嗡嗡声/街道声等）、动作音效（拍桌、脚步声、物品碰撞）、非语言人声（呼吸、笑声）
- **不要重复台词和唱歌**
- 完全静音写 `N/A`（极少用）

### 6. non_diegetic_music
- 1~3 句，描述角色听不到、只有观众听到的配乐
- 写具体：乐器、节奏、动态变化（渐强/骤停/收尾）
- 不要写"感人的""紧张的"这类抽象情绪词
- 无配乐写 `N/A`

## 参考音频（Audio N）写法

当用户在 ComfyUI/工作流里接了 `ref_audios` 参考音频、希望角色用指定音色说话时使用。**没有参考音频时本节整段跳过**，按上面示例自由描述音色即可。

- **编号**：按工作流接线顺序 `ref_audio_0/1/2…` → `<Audio 1>/<Audio 2>/<Audio 3>`，在交付文档里列出"文件 → 槽位 → `<Audio N>` → 角色/S几"对照表。
- **绑定**：在 `subject_definitions` 里写 `<Audio N> is the voice-timbre reference for <Subject N> (Sx).`，把音频、角色、说话人 ID 三者锁死。
- **任务类型**：`summary` 开头追加 `+ audio reference`。
- **保留关系**：`retention_analysis` 里每个音频一行，固定用 `reference`（不是 fully_copy），写明"只借音色不复制信号"；不出现的音频写 `not_applicable`。
- **台词处引用**：`<Subject N> (Sx) says, using the voice timbre referenced from <Audio N>, <情绪副词>: <d>[Chinese] 用户原文。</d>`。
- **铁律**：音频只借音色/语气/韵律，**绝不**把音频里的原台词搬进 `<d>`；台词永远用用户提供的原文。

## 完整示例（单段 14s，4 角色）

```text
subject_definitions:
<Subject 1> is the blue-and-white round plush shark in <Picture 1>, with soft fuzzy blue dorsal fur, a white belly, a pointed dorsal fin, big round eyes, and a wide mouth full of small sharp teeth.
<Subject 2> is the grey-brown spotted round plush catfish in <Picture 2>, with mottled grey-brown fur, a cream belly, two small antennae, long thin whiskers, two buck teeth, and a fish tail.
<Subject 3> is the light-green round plush dragon in <Picture 3>, with pale-green fur, a cream belly, pink lotus flower buds on its head and tail, pink blush, long eyelashes, and two small fangs.
<Subject 4> is the brown capybara plush in <Picture 4>, with warm tan-brown fur, a big round nose, two front teeth, and a white underwear with bear prints worn on its head.
<Picture 5> is the first-frame keyframe for [Shot 1], showing all four characters in a teacher's office.

summary:
[reference generation + keyframe completion] The target video is a 14-second 3D CGI plush-toy comedy skit in a school teacher's office. The teacher confronts the student about smoking, with both parents present. The student says he smokes because of stress; the father pauses and delivers a twist implying he also smokes.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 5]): fully_preserved - blue-and-white fur, dorsal fin, proportions and toothy grin retained.
<Subject 2> (appears in [Shot 1], [Shot 3], [Shot 5]): fully_preserved - grey-brown spotted fur, antennae, whiskers, buck teeth and fish tail retained; expression shifts from angry to sly.
<Subject 3> (appears in [Shot 1], [Shot 3], [Shot 5]): fully_preserved - green fur, lotus buds, blush and fangs retained.
<Subject 4> (appears in [Shot 1], [Shot 2], [Shot 4], [Shot 5]): fully_preserved - brown fur, nose, front teeth and bear-print underwear hat retained.
<Picture 5> ([Shot 1] first frame): fully_preserved - office desk composition, character placement and lighting retained.

detailed_description:
The target video uses a 3D CGI plush-toy cinematic style with warm desk-lamp glow mixed with cool fluorescent ceiling light, shallow depth of field.
[Shot 1] A medium-wide shot establishes the office matching <Picture 5>. <Subject 1> stands behind a wooden desk; <Subject 2> and <Subject 3> sit in green chairs facing it; <Subject 4> stands in the foreground with its back to camera. <Subject 1>'s calm middle-aged male voice, low and weary (S1), says: <d>[Chinese] 孩子初三就学抽烟。</d> <Subject 3>'s gentle female voice, high and worried (S3), asks: <d>[Chinese] 这能行吗？</d> <Subject 2>'s gruff raspy male voice, loud and impatient (S2), barks: <d>[Chinese] 你初三你抽啥烟啊！</d>
[Shot 2] At 00:03.300, the camera cuts to a close-up of <Subject 4>, who turns with a blank innocent expression. Its nasally teenage male voice, slow and unbothered (S4), answers: <d>[Chinese] 抽炫赫门。</d>
[Shot 3] At 00:04.800, the camera cuts to a medium shot of <Subject 2> and <Subject 3>. <Subject 3> leans forward placatingly and says quickly (S3): <d>[Chinese] 不，你爸的意思是问你为啥学抽烟。</d>
[Shot 4] At 00:07.600, the camera cuts back to a close-up of <Subject 4>, who answers with conviction (S4): <d>[Chinese] 压力大。</d>
[Shot 5] At 00:08.300, the camera cuts back to the medium-wide shot. <Subject 2>'s frown melts into a sly smirk. He leans forward and lowers his voice to a conspiratorial murmur (S2): <d>[Chinese] 你压力大。</d> He pauses, narrows his eyes, and adds with a faint chuckle: <d>[Chinese] 你……抽利群啊。</d> <Subject 1> and <Subject 3> freeze with wide shocked eyes. The camera pushes in slowly at slow speed toward <Subject 2>'s smirk.

overall_soundscape:
A low fluorescent office hum and faint air-conditioning drone run throughout, with soft squeaks of plush fabric and chairs. The father's paw slaps the chair armrest with a dull thud. Near the end, a faint metallic click of a lighter is heard, followed by a comedic bass-drum sting.

non_diegetic_music:
A light comedic piano and marimba pattern at a moderate tempo underscores the first four shots. On the father's pause, the music drops out completely; after the twist line a single comedic trombone slide and bass-drum hit land, then cut to silence.
```

## 常见错误

- ❌ 台词改写或翻译 → 必须逐字原文
- ❌ retention_analysis 漏掉某个角色 → 必须全覆盖
- ❌ 用 I2VA 格式（integrated_multimodal_description）→ Ref2VA 用 detailed_description
- ❌ 镜头时间戳递减或超出段长 → 必须递增且 ≤ 段长
- ❌ 说话人 ID 跨镜头变化 → S1 始终是同一个人
- ❌ 关键帧 prompt 没写"exactly N characters" → 会多生成角色
- ❌ 有参考音频却在台词处写自由音色（"低沉磁性男声"）或把音频里的原台词搬进 `<d>` → 音色用 `<Audio N>` 引用，台词用用户原文
