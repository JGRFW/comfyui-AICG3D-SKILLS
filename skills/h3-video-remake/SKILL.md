---
name: h3-video-remake
description: 把任意参考视频复刻为 MiniMax H3 可生成的毛绒/IP角色版本，输出 Ref2VA 六段式提示词、分镜关键帧、上传顺序与音效音色设计。当用户提供原片视频 + 角色参考图（IP设定图）并要求"复刻视频""做H3提示词""视频翻拍""Ref2VA提示词""分镜+提示词"时使用；用户只给视频和角色图、文字请求为空或只说"复刻"时也自动触发。不适用于纯真人实拍复刻（无角色替换）或纯剪辑任务。
---

# H3 视频复刻工作流

把原片（真人/2D/3D 均可）用指定的 IP 毛绒角色重新演绎，产出可直接粘贴到 MiniMax H3 的 Ref2VA 提示词 + 分镜关键帧 + 上传指导。

## 触发后第一步：确认输入

必须拿到三样东西，缺了就问：

1. **原片视频**（本地路径或附件）
2. **角色参考图**（1~N 张，每张必须注明"这是谁"，如"图1=班主任"）
3. **完整台词**（强烈建议用户提供；若用户没给，逐帧 OCR 但要标注"可能有误"）

**可选第 4 样：参考音频**（1~N 段 wav/mp3）。若用户提供了音色音频，必须同时问清"每段音频对应哪个角色"（如"音频1=班主任"），并记录用户在 ComfyUI/工作流里的 `ref_audios.ref_audio_0/1/2` 接线顺序。有参考音频时，提示词里**不要**凭空描述音色（如"低沉磁性男声"），改用官方 `<Audio N>` 标签引用，详见第四步。

风格默认"如角色参考图"（3D CGI 毛绒玩具风），用户另有指定则从其。

## 工作目录

在主项目目录下新建 `h3_<简短主题>/`，内含 `frames/` 子目录。所有抽帧、关键帧、提示词文档都放这里。

## 第一步：视频分析

并行执行：

1. **元信息**：`ffprobe -v error -show_entries format=duration -show_entries stream=width,height,r_frame_rate -of default=noprint_wrappers=1 <视频>`
2. **镜头切点**：`ffmpeg -hide_banner -i <视频> -vf "select='gt(scene,0.3)',showinfo" -f null - 2>&1 | Select-String "pts_time"`，提取所有 `pts_time:X.X` 值
3. **抽帧**：按每个镜头的中点时间抽帧（`ffmpeg -ss <时间> -i <视频> -frames:v 1 <输出.jpg>`），长镜头（>3s）多抽 2~3 帧

读取所有抽帧，记录每个镜头的：构图、在场角色、动作、字幕/台词。若用户给了台词，把台词逐句对应到镜头和说话人。

## 第二步：角色与分段

### 角色映射
为每张角色图建立 `<Subject N>`，写明物种、毛色、标志性特征（天线/胡须/荷花苞/内裤帽等）。角色在原片里的对应关系由用户标注决定。

**音色映射**（仅当用户提供了参考音频）：把每段音频按工作流接线顺序编号为 `<Audio 1>`、`<Audio 2>`…，并绑定到对应角色和说话人 ID：
- `<Audio 1> is the voice-timbre reference for <Subject 1> (S1).`
- 说话人 ID `(Sx)` 按全片实际发声顺序分配，与音频编号一一对应，跨段复用同一编号。
- 没有参考音频时，才在首次发声处写自由音色描述（如 "a calm middle-aged male voice, low and weary"）。

### 分段策略
H3 单段上限 **15 秒**。
- 原片 ≤15s 且场景不换 → **单段生成**（连贯性最好）
- 原片 >15s → 按自然切点分段，每段 4~15s，段与段之间情绪/动作要能顺接
- 不要在一句台词中间切段

## 第三步：生成分镜关键帧

**必须生成**，用户说"不要出图"才跳过。

1. 用 `FileBatchUpload` 上传所有角色参考图，拿到 URL
2. 用 `image_edit`（model_version 默认 seedream_5.0_flash），`image_reference_url_list` 传全部角色图，prompt 里：
   - 明确写"Keep the exact appearance of all characters"
   - 描述场景、站位、构图、灯光
   - **必须写"Exactly N characters, each appears only once, no duplicates, no extra characters"**（防止模型多生成角色）
   - 1920×1080（16:9）
3. 每段至少生成 1 张首帧关键帧；有反转/爆点的段落额外生成 1 张结尾帧（结尾帧仅供参考，不上传）
4. 下载关键帧到工作目录

如果生成的关键帧里角色数量不对或特征丢失，重新生成（调整 prompt 强调），不要将就。

## 第四步：写 Ref2VA 提示词

**永远用 Ref2VA，不要用 I2VA**（I2VA 后半段角色会漂移）。

每段一个独立提示词，严格六段式，格式见 `references/ref2va-format.md`。核心要点：

- **subject_definitions**：每个 `<Subject N>` 对应一张角色图（`<Picture N>`），逐字描述外观；首帧关键帧标为最后一个 `<Picture N>` 并注明是 `[Shot 1] first frame`；**有参考音频时**，每个发声角色加一行 `<Audio N> is the voice-timbre reference for <Subject N> (Sx).`
- **summary**：`[reference generation + keyframe completion]` 开头，一段话讲清这段内容；**有参考音频时**追加任务类型 `+ audio reference`（即 `[reference generation + keyframe completion + audio reference]`）
- **retention_analysis**：每个角色每个出现镜头都标 `fully_preserved`，写明保留哪些特征；这是防漂移的关键；**有参考音频时**，每个 `<Audio N>` 单独一行标 `reference - its vocal timbre guides <Subject N>'s dialogue delivery without copying the original signal.`；不出现的角色/音频写 `not_applicable - does not appear in this segment.`
- **detailed_description**：开头一两句风格描述，然后 `[Shot 1]`（无时间戳）起，后续镜头 `[Shot N] At MM:SS.mmm, the camera cuts to...`；台词用 `<d>[Chinese] 原文。</d>`；说话人用稳定 `(S1)(S2)`，**有参考音频时**首次发声写 `<Subject N> (Sx) says, using the voice timbre referenced from <Audio N>: <d>...</d>`，不要再叠加自由音色词；无参考音频时才写音色描述+`(Sx)`
- **overall_soundscape**：1~4 句，环境音+动作音效，不重复台词
- **non_diegetic_music**：1~3 句，乐器/节奏/动态变化，无音乐写 `N/A`

> 关键原则：参考音频只借音色/语气/韵律，**绝不**把音频里的原台词搬进提示词；台词永远用用户给的原文。

### 上传顺序（写进交付文档）
角色设定图在前（按 Subject 编号），首帧关键帧在最后。例：
Picture 1=角色A设定图, Picture 2=角色B设定图, ..., Picture N=首帧关键帧

有参考音频时，另列一张**音频接线表**：Audio 1=工作流 ref_audio_0=哪个文件=对应哪个角色(S几)；Audio 2=ref_audio_1=…；以此类推。提示词里的 `<Audio N>` 编号必须与该表一致。

## 第五步：交付

1. 用 `present_files` 交付关键帧（每张单独介绍）
2. 写一份 `<主题>_H3复刻提示词_Ref2VA版.md`，包含：
   - 角色映射表
   - 上传顺序表（有音频时另附音频接线表：文件 → ref_audio 槽位 → `<Audio N>` → 角色/S几）
   - 音色设计（有参考音频时写"参考 `<Audio N>`，情绪/语气靠副词传达"；无参考音频时才写每个说话人 Sx 的音色描述）
   - 镜头与台词总览表
   - 每段完整 Ref2VA 提示词（代码块，可直接复制）
   - 生成建议（时长、比例、注意事项）
3. 用 `present_files` 交付 md 文档
4. 最后用 3~5 句话总结：分了几段、上传顺序、关键反转点、注意事项

## 硬约束

- 台词原文逐字保留，不改写、不翻译
- 原片的后期字幕/标题（如顶部"当你抽烟被父亲知道"）不要写进提示词，告知用户后期加
- 角色外观在所有镜头保持一致，不靠"画风转变"
- 镜头时间戳必须递增且在段时长内
- 每段时长 4~15s，比例默认 16:9
- 关键帧生成时必须防重复角色（"exactly N characters"）
- 有参考音频时：台词仍用用户原文，`<Audio N>` 只标音色参考关系，不把音频里的原台词写进 `<d>`；说话人 `(Sx)` 编号跨段稳定不变
