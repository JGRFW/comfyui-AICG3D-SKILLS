# Ref2VA 人物场景替换模板

先判断模式，只保留本次使用的 Subject 和 Picture。方括号内容必须替换为实际信息。

除非用户提供了逐字台词，否则禁止输出 `<d>` 对白；任务说明、问题、素材用途和旁白不得写成人物台词。复用原音轨时只描述说话动作与口型同步。

## A. 单人替换

```text
subject_definitions:
<Subject 1> 是 <Picture 1> 中的[人物身份]，使用其脸型、五官、发型、服装和体型作为[指定人物]的身份参考。
<Video 1> 是待编辑的目标视频，提供完整时长、人物位置、动作节奏、口型、对白、镜头运动和原始音轨。

summary:
[video editing + audio reuse] 目标视频是 <Video 1> 的单人物替换版本。<Picture 1> 的身份转移到[指定人物]；原视频的动作、口型、镜头和音轨保持原样。

retention_analysis:
<Video 1>: fully_preserved - 视频时长、构图、人物位置、动作、口型、镜头运动和原始音轨完整保留。
<Subject 1>: attribute_transfer - <Picture 1> 的脸型、五官、发型、服装和体型转移到[指定人物]。

detailed_description:
[Shot 1] [时长]秒[镜头类型]，画面构图、机位和人物大小保持 <Video 1>。[描述人物位置、朝向、动作和背景].
[起始时间]–[结束时间]秒：描述替换后人物的说话动作、口型、表情或身体动作，并与 <Video 1> 的原始节奏同步；不写台词内容。
[最后时间]–[结束时间]秒：画面收束在 <Video 1> 对应姿态，人物位置、镜头大小和动作节奏保持连续。

overall_soundscape:
完整沿用 <Video 1> 的[环境声、脚步、衣料摩擦、碰撞和语言声]。

non_diegetic_music:
[有观众侧配乐就描述乐器和动态；没有写 N/A]
```

## B. 多人替换

```text
subject_definitions:
<Subject 1> 是 <Picture 1> 中的[人物身份]，作为[左侧/指定人物]的身份参考。
<Subject 2> 是 <Picture 2> 中的[人物身份]，作为[右侧/指定人物]的身份参考。
[按需要继续增加 Subject 3、Subject 4……]
<Video 1> 是待编辑的目标视频，提供动作、口型、镜头、构图、时长和原始音轨。

summary:
[video editing + audio reuse] 目标视频是 <Video 1> 的多人物替换版本。[逐项说明每个 Subject 替换哪个人物]；原视频动作、对白、镜头和音轨保持原样。

retention_analysis:
<Video 1>: fully_preserved - 完整保留动作、口型、镜头、时长和音轨。
<Subject 1>: attribute_transfer - <Picture 1> 的身份和外观转移到[指定人物]。
<Subject 2>: attribute_transfer - <Picture 2> 的身份和外观转移到[指定人物]。

detailed_description:
[Shot 1] [时长]秒[镜头类型]，保持 <Video 1> 的原始构图和人物位置。[明确写出每个人物在画面中的左右位置、前中后景关系和动作]。
[时间区间]：[每个人物分别发生的动作、口型、表情和位置变化]。
[最后时间]–[结束时间]秒：画面收束在 <Video 1> 对应姿态，每个人物保持正确的身份和位置。

overall_soundscape:
完整沿用 <Video 1> 的环境音、动作音和语言声。

non_diegetic_music:
[有观众侧配乐就描述；没有写 N/A]
```

## C. 人物 + 场景

在 A 或 B 的基础上增加一个独立背景 Subject，例如：

```text
<Subject 3> 是 <Picture 3> 中的目标背景环境，使用其中的建筑、地面、光线、色彩和空间结构作为背景参考。
```

并在 `summary` 中写明背景也发生替换，在 `retention_analysis` 中为该 Subject 使用 `attribute_transfer`。`<Video 1>` 仍然负责原视频的人物动作、镜头、口型和音轨。

## D. 单独场景

```text
subject_definitions:
<Subject 1> 是 <Picture 1> 中的目标背景环境，使用其中的建筑、地面、光线、色彩和空间结构作为背景参考。
<Video 1> 是待编辑的目标视频，提供完整时长、所有人物身份、位置、动作、口型、对白、镜头运动和原始音轨。

summary:
[video editing + audio reuse] 目标视频是 <Video 1> 的单独场景替换版本。背景环境转移为 <Picture 1> 的场景内容；原视频所有人物、动作、对白、镜头和音轨保持原样。

retention_analysis:
<Video 1>: fully_preserved - 人物身份、数量、位置、动作、口型、镜头、时长和对白完整保留。
<Subject 1>: attribute_transfer - <Picture 1> 的背景结构、地面、光线、色彩和空间关系转移到目标视频背景。

detailed_description:
[Shot 1] [时长]秒[镜头类型]，保持 <Video 1> 的原始构图、机位和所有人物位置。背景逐帧对齐 <Subject 1> 的场景结构与光线。
[时间区间]：[只描述原视频人物的动作、口型和说话节奏，不写台词]；[描述目标背景的空间、光线和材质变化]。
[最后时间]–[结束时间]秒：人物动作、口型和原始音轨保持在 <Video 1> 对应状态，镜头和画面节奏保持连续。

overall_soundscape:
完整沿用 <Video 1> 的环境音、动作音和语言声。

non_diegetic_music:
[有观众侧配乐就描述；没有写 N/A]
```