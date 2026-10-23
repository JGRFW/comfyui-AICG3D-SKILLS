# 3D白模人物场景替换模板

先根据节点设置选择模式。只输出六段正文，不要把模式标题、说明或方括号提示一起输出。

## 通用替换规则

- `<Video 1>` 只作为动作、口型、身体朝向、站位、镜头、时长和音轨母版。
- 白模表面、绿色背景、黑色背景都不能出现在最终画面中。
- 彩色白模默认：`<Picture 1>` 对应蓝色 ID / Subject 1，`<Picture 2>` 对应红色 ID / Subject 2，依次类推。人物交叉换位时仍按颜色锁身份。
- 双人物换背景时使用 `<Picture 3>`；单人换背景时使用 `<Picture 2>`；不替换背景时不要定义场景图。
- 用户明确指定的 Picture 编号优先于默认编号。
- 人物身份保持稳定，不出现换脸闪烁、五官漂移、服装串色、左右人物互换。
- 逐人彩色 ID 白模只用于锁定身份：蓝=Subject 1、红=Subject 2、绿=Subject 3、品红=Subject 4、青=Subject 5、黄=Subject 6。人物换位或交错时颜色身份不变，最终画面不得保留这些标识色。
- 原视频有真实台词时，使用真实台词时间线；没有真实台词时不要输出 `<d>` 对白。
- 没有逐人台词时间线时，不得指定某一侧全程说话。左右人物必须各自继承原位人物的说话/不说话时序、嘴部开合、停顿和倾听状态，不得把一侧的口型转移到另一侧。

## A. 绿幕白模：替换两个人物并替换背景

```text
subject_definitions:
<Picture 1> 是蓝色 ID / <Subject 1> 的唯一身份参考，严格使用其中的脸型、五官、发型、发饰、服装款式、服装颜色和体型，完整替换白模中的蓝色人物。
<Picture 2> 是红色 ID / <Subject 2> 的唯一身份参考，严格使用其中的脸型、五官、发型、服装款式、服装颜色和体型，完整替换白模中的红色人物。
<Picture 3> 是目标背景场景参考，使用其中的建筑结构、地面、树木、光线、色彩和空间关系，替换 <Video 1> 的背景环境。
<Video 1> 是绿幕背景的逐人彩色 3D 白模动作母版，只用于提供人物颜色 ID、位置、身体动作、走路、转身、头部运动、手部动作、口型节奏、镜头运动、完整时长和原始音轨。蓝红颜色、白模材质、绿色背景和三视图排版绝对不能出现在最终画面中。

summary:
[video editing + audio reuse] 目标视频是 <Video 1> 的双人物替换与场景替换版本。<Picture 1> 原样替换蓝色 ID 人物，<Picture 2> 原样替换红色 ID 人物，<Picture 3> 替换整个背景环境；原视频的动作、口型、镜头、时长和音轨保持不变。

retention_analysis:
<Video 1>: fully_preserved - 完整保留时间轴、人物位置、身体动作、手部动作、头部朝向、口型节奏、镜头运动和原始音轨。3D 白模只作为动作参考，不作为最终画面外观。
<Subject 1>: attribute_transfer - 将 <Picture 1> 的脸型、五官、发型、发饰、服装和体型转移到蓝色 ID 人物；替换后不再保留蓝色白模材质。
<Subject 2>: attribute_transfer - 将 <Picture 2> 的脸型、五官、发型、服装和体型转移到红色 ID 人物；替换后不再保留红色白模材质。
<Subject 3>: attribute_transfer - 将 <Picture 3> 的建筑、地面、树木、光线、色彩和空间结构转移到目标视频背景，并保持 <Video 1> 对应的镜头视角和透视关系。

detailed_description:
[Shot 1] 保持 <Video 1> 的原始构图、人物大小、运动轨迹、镜头运动和时间节奏。蓝色 ID 人物使用 <Subject 1> 的完整身份与外观，红色 ID 人物使用 <Subject 2> 的完整身份与外观，背景整体替换为 <Subject 3>。
0.00-4.00 秒：蓝红 ID 锁定人物身份，两个人物保持 <Video 1> 对应的站位、朝向、身体重心和视线关系。蓝色 ID 严格对应 <Picture 1>，红色 ID 严格对应 <Picture 2>。<Subject 1> 只继承蓝色 ID 的说话或不说话状态、嘴部开合、停顿和倾听状态；<Subject 2> 只继承红色 ID 的对应状态。任何一侧都不得借用另一侧的口型、身份或说话动作。
4.00-8.00 秒：即使人物穿插、遮挡、移动或左右换位，<Subject 1> 仍只跟随蓝色 ID，<Subject 2> 仍只跟随红色 ID。人物继续执行 <Video 1> 中属于各自 ID 的转头、对视、嘴部开合、眉眼神态和上半身动作，不出现脸型漂移、换脸闪烁、五官变形、服装串色、人物身份互换或口型串换。
8.00 秒至结束：镜头、人物动作和口型节奏完整跟随 <Video 1>。背景始终保持 <Picture 3> 的建筑和空间结构，透视、主光方向、地面位置与原始镜头一致；最终画面中不出现绿色背景、白模、黑底、三视图、设定板或拼接排版。
人物动作、视线、遮挡关系、身体轮廓和镜头连续性以 <Video 1> 为准。人物身份和外观以 <Picture 1>、<Picture 2> 为准。场景外观以 <Picture 3> 为准。不要添加新人物，不要改变原视频人物数量、性别、年龄、服装款式和颜色 ID 对应关系。

overall_soundscape:
完整复用 <Video 1> 的原始音轨，包括对话、语言、语速、停顿、环境声、脚步、衣料摩擦、碰撞声和其他现场声音。说话动作和口型严格与原始音轨同步，不重新生成对白。

non_diegetic_music:
保留原视频中已有的背景音乐、配乐和音乐动态；原视频没有观众侧配乐时写 N/A。
```

## B. 白模保留原场景：只替换两个人物

```text
subject_definitions:
<Picture 1> 是蓝色 ID / <Subject 1> 的唯一身份参考，严格使用其中的脸型、五官、发型、发饰、服装款式、服装颜色和体型，完整替换白模中的蓝色人物。
<Picture 2> 是红色 ID / <Subject 2> 的唯一身份参考，严格使用其中的脸型、五官、发型、服装款式、服装颜色和体型，完整替换白模中的红色人物。
<Video 1> 是保留原视频场景的逐人彩色 3D 白模动作母版，提供颜色 ID、人物位置、身体动作、头部朝向、手部动作、口型节奏、镜头运动、原始背景和原始音轨。蓝红颜色和白模材质不能出现在最终画面中，原视频场景必须保留。

summary:
[video editing + audio reuse] 目标视频是 <Video 1> 的双人物替换版本。<Picture 1> 原样替换蓝色 ID 人物，<Picture 2> 原样替换红色 ID 人物；原视频背景、动作、口型、镜头、时长和音轨保持原样。

retention_analysis:
<Video 1>: fully_preserved - 完整保留原视频背景、人物位置、动作、口型、镜头、时长和原始音轨。
<Subject 1>: attribute_transfer - 将 <Picture 1> 的脸型、五官、发型、发饰、服装和体型转移到蓝色 ID 人物。
<Subject 2>: attribute_transfer - 将 <Picture 2> 的脸型、五官、发型、服装和体型转移到红色 ID 人物。

detailed_description:
[Shot 1] 保持 <Video 1> 的原始背景、构图、人物大小、运动轨迹、镜头运动和时间节奏。蓝色 ID 人物使用 <Subject 1> 的完整身份与外观，红色 ID 人物使用 <Subject 2> 的完整身份与外观。
0.00-4.00 秒：蓝红 ID 锁定人物身份，两个人物保持 <Video 1> 对应的站位、朝向、身体重心和视线关系，原视频背景保持不变。<Subject 1> 和 <Subject 2> 分别继承同一颜色 ID 的说话或不说话状态、嘴部开合、停顿和倾听状态，不得串换。
4.00-8.00 秒：即使人物穿插、遮挡、移动或左右换位，<Subject 1> 仍只跟随蓝色 ID，<Subject 2> 仍只跟随红色 ID，不出现脸型漂移、换脸闪烁、五官变形、服装串色、人物身份互换或口型串换。
8.00 秒至结束：镜头和人物动作完整跟随 <Video 1>，原视频背景的光线、建筑、空间结构和遮挡关系保持不变。最终画面中不出现白模、黑色背景、三视图、设定板或拼接排版。

overall_soundscape:
完整复用 <Video 1> 的原始音轨，包括对话、语言、环境声、脚步、衣料摩擦和其他现场声音。说话动作和口型严格与原始音轨同步。

non_diegetic_music:
保留原视频中已有的背景音乐、配乐和音乐动态；原视频没有观众侧配乐时写 N/A。
```

## C. 单人替换并替换背景

默认编号为：`<Picture 1>` 是蓝色 ID / Subject 1，`<Picture 2>` 是目标场景。只定义这两个 Picture。

```text
subject_definitions:
<Picture 1> 是蓝色 ID / <Subject 1> 的唯一人物身份参考。
<Picture 2> 是目标背景场景参考，整体替换 <Video 1> 的背景。
<Video 1> 是绿幕彩色白模动作母版，只提供蓝色 ID 的动作、口型、镜头、时长和原音轨；蓝色、绿色和白模不能进入最终画面。

summary:
[video editing + audio reuse] <Picture 1> 替换蓝色 ID 人物，<Picture 2> 替换背景；动作、口型、镜头、时长和音轨保持 <Video 1>。

retention_analysis:
<Video 1>: fully_preserved - 保留蓝色 ID 的动作、口型、轨迹、镜头、时长和音轨。
<Subject 1>: attribute_transfer - 将 <Picture 1> 的真实身份、发型、服装和体型转移到蓝色 ID 人物。
<Subject 2>: attribute_transfer - 将 <Picture 2> 的空间、地面、建筑、光线和色彩转移为背景。

detailed_description:
[Shot 1] 蓝色 ID 人物替换为 <Subject 1>，背景整体替换为 <Subject 2>。人物身份、动作、口型和镜头逐帧跟随 <Video 1>，背景透视与主光方向匹配原镜头。最终不出现蓝色、绿色或白模。

overall_soundscape:
完整复用 <Video 1> 的原音轨。

non_diegetic_music:
按原视频保留；没有则写 N/A。
```

## D. 单人替换并保留原场景

节点使用“保留原视频场景=开，绿色背景=关”。只定义 `<Picture 1>`，不要定义场景 Picture。

```text
subject_definitions:
<Picture 1> 是蓝色 ID / <Subject 1> 的唯一人物身份参考。
<Video 1> 提供蓝色 ID 的动作、口型、镜头、原背景、时长和原音轨；白模和蓝色标识色不得进入最终画面。

summary:
[video editing + audio reuse] <Picture 1> 替换蓝色 ID 人物，原视频背景和其他人物保持不变。

retention_analysis:
<Video 1>: fully_preserved - 保留背景、动作、口型、镜头、时长和音轨。
<Subject 1>: attribute_transfer - 将 <Picture 1> 的真实身份和外观转移到蓝色 ID 人物。

detailed_description:
[Shot 1] 蓝色 ID 人物替换为 <Subject 1>，原背景、构图、动作、口型和镜头保持不变。最终不出现白模或蓝色标识色。

overall_soundscape:
完整复用 <Video 1> 的原音轨。

non_diegetic_music:
按原视频保留；没有则写 N/A。
```

## E. 只替换背景，保留所有人物

只有当所有人物的身份和服装都要保留时使用。优先把原视频作为 `<Video 1>`；如果使用白模，必须额外提供原人物的身份参考。默认 `<Picture 1>` 是场景图，未参与的人不要定义。

```text
subject_definitions:
<Picture 1> 是目标背景场景参考，整体替换 <Video 1> 的背景。
<Video 1> 提供原视频人物身份、人数、服装、动作、口型、镜头、时长和原音轨。

summary:
[video editing + background replacement] 只替换背景，所有人物、服装、动作、口型、镜头和音轨保持不变。

retention_analysis:
<Video 1>: fully_preserved - 保留人物身份、数量、服装、动作、口型、镜头、时长和音轨。
<Subject 1>: attribute_transfer - 将 <Picture 1> 的空间、地面、建筑、光线和色彩转移为背景。

detailed_description:
[Shot 1] 保持原视频所有人物和动作，只将背景整体替换为 <Subject 1>。背景透视、主光方向、地面位置和遮挡关系匹配原镜头。

overall_soundscape:
完整复用 <Video 1> 的原音轨。

non_diegetic_music:
按原视频保留；没有则写 N/A。
```
