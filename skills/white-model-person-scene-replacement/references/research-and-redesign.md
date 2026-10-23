# MiniMax H3 人物 / 场景替换：资料结论、实测与最终设计

更新时间：2026-10-17

## 一、结论先行

### 1. 白模不是人物替换的必要条件

白模路线的问题是：多一次 SAM3 / SAM3D Body 推理；容易多识别人物、丢人物或把颜色 ID 带入成片；白模动作已经和原片有差异；背景、人物、颜色、动作全部耦合，失败后很难定位。

因此白模只保留为动作预演或特殊辅助工具，最终替换优先直接使用原视频。

### 2. 单人替换标准路线

```text
源视频（24fps、17k+5 帧）
+ 人物参考图
+ MiniMax H3 Ref2VA
+ Turbo LoRA
+ Character Swap LoRA
→ er_sde / beta
```

实测参数：

```text
每段时长 = 3.75 秒 = 90 帧
分辨率 = 512×384 预览，640 短边正式
采样器 = er_sde
调度器 = beta
预览步数 = 8
一致性优先 = 20（不使用 Turbo）
Turbo LoRA = 1.0
Character Swap LoRA = 1.0
source_reference_scale = 1.0
face_anchor = 关闭优先；换不掉再打开
```

不要再把 `source_reference_scale` 长期设成 `0.20`。该值会让原片动作和构图约束明显变弱。身份失败时先换清晰参考、固定 seed 或重跑 seed，而不是牺牲动作约束。

### 3. 多人替换必须顺序执行

本机实测：两张人物参考、关闭 Character Swap LoRA、8 步联合采样，画面平均差异只有 `0.01781`，视觉上基本就是原片，没有完成换人。该路线淘汰。

最终多人路线：

```text
第一遍：只换右侧说话者
→ 合并第一遍成片
第二遍：拿第一遍成片作为 Video 1，只换左侧人物
→ 再次合并并恢复原音轨
```

每一遍只给 Character Swap LoRA 一张人物图，强度 1.0。两遍共用同一 seed 和参考标准，最终输出一个双人替换视频。

### 4. 背景替换分两种能力

#### A. AI 换景

使用场景图和 H3 Ref2VA。背景会重建，不保证逐像素还原；人物也可能被重新设计服装。适合风格化场景迁移、人物和背景一起重生成。

#### B. 静态换景并锁人物

最终推荐使用独立节点：

```text
SMS ③B 静态换景·人物像素锁定
```

流程：

1. 逐帧检测并分割所有人物。
2. 原人物像素、动作、口型、服装完全不重绘。
3. 人物遮罩以外的区域替换成场景图。
4. 合并时恢复原视频音轨。

优点：

- 人物和口型 100% 保留。
- 场景图确定性替换。
- 不需要 H3 模型、LoRA 或采样器。
- 3.75 秒、864×640 实测约 4 秒。

限制：

- 背景是固定场景图，移动镜头不会自动生成真实三维透视。
- 更适合固定机位、轻微运镜或主体锁定镜头。
- 需要 `models/ultralytics/segm/person_yolov8m-seg.pt`。

## 二、模型与 LoRA 推荐

本机已验证的主模型：

```text
MiniMax/minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors
```

本机另有 Ref2VA 专用模型：

```text
MiniMax/Minimax-h3_Singularity_ref2va_Pruned_v1.3_int8.safetensors
```

可作为后续对照，但当前工作流使用已实跑的 hybrid 模型。必须走 Ref2VA 条件通路，不要走 FL2VA。

单人物 LoRA：

```text
minimax/h3_character_swap_pro4500_1000.safetensors = 1.0
minimax/minimax_h3_turbo_v4_step600_ema_DasiwaREF2VAHybridV1_0_curveproj1025_compat_v001.safetensors = 1.0
```

多人顺序替换：

- 每一遍仍使用 Character Swap LoRA 1.0，但一遍只连接一张人物参考。
- 不要把两张人物参考同时塞给同一个 1.0 的 Character Swap LoRA。
- 不要在同一联合采样里关闭 Character Swap LoRA 后指望它自动换两个人。

不建议叠加写实人像、3D 转真实、战斗、运镜或速度 LoRA。它们会改变风格或运动分布，不能提高参考脸相似度，还会增加变量。

## 三、采样器与参数

| 项目 | 预览 | 正式 |
|---|---:|---:|
| 短边 | 384 | 640 |
| 步数 | 8 + Turbo | 20（关闭 Turbo）或 8 + Turbo |
| 采样器 | er_sde | er_sde |
| 调度器 | beta | beta |
| 每段 | 3.75 秒 / 90 帧 | 3.75 秒 / 90 帧 |
| 重叠 | 22 帧 | 22 帧 |
| seed | 123456 固定 | 固定后多跑 2～3 个 |
| 参考图尺寸 | 最大 2048 | 最大 2048 |
| 原片参考强度 | 1.0 | 1.0 |

公开 Character Swap 工作流还要求源视频恒定 24fps、连续镜头，约 3.75 秒短片最稳，结果受 seed 明显影响。

## 四、本机实测记录

### 单人标准路线

```text
输入：video-1791605232 (1).mp4，30fps，382 帧
处理：自动转 24fps，截取 90 帧
参数：512×384、er_sde/beta、8 步、Character Swap 1.0、Turbo 1.0、source 1.0
结果：人物替换成功，动作、口型、镜头、说话者保持一致
输出：单人替换_·_动作锁定_·_3.75秒预览_00001_.mp4
```

### 多人联合采样反例

```text
参数：864×640、8 步、两张人物图、关闭 Character Swap LoRA
画面差异：0.01781
视觉结果：原片复制，未完成换人
结论：淘汰该路线
```

### 多人顺序替换

```text
第一遍：右侧说话者替换成功，偏差 0.06789
第二遍：在第一遍成片上替换左侧人物，偏差 0.04569
视觉结果：两人均被替换，动作、口型、镜头和音轨保持
```

### 静态换景锁人物

```text
参数：864×640、90 帧
人物：自动逐帧分割并保留
背景：静态场景图替换
耗时：约 4.1 秒
视觉结果：场景完整替换，人物、服装、口型、动作未改变
```

## 五、最终工作流

```text
17. 单人替换 · 动作锁定 · 快速预览
18. 单人替换 · 一致性优先
19. 多人替换 · 顺序两遍
20. 人物 + 背景 · 两遍人物 + 静态换景
21. 仅背景替换 · 人物像素锁定
```

## 六、验收顺序

1. 先跑 3.75 秒、384 短边、8 步，判断是否换人。
2. 检查动作、口型、说话者和镜头是否跟随原片。
3. 身份失败：换参考图、固定 seed、多跑 2～3 个 seed；单人再尝试锁脸。
4. 多人失败：按人物顺序分两遍，不要继续堆 LoRA。
5. 背景失败：需要人物绝对不变时使用静态换景节点。
6. 最后再提高分辨率和步数，不在 384 预览档位验收清晰度。

## 七、外部资料

- https://github.com/TheBeast-Spec/minimax-h3-character-swap-lora-comfyui
- https://github.com/MacroSony/minimax-h3-chained-character-swap
- https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef
- https://github.com/nuvulabs/ComfyUI-MiniMaxH3-Inpaint
- https://github.com/BiggerFishy/comfyui-minimax-h3-studio

公开资料能证明工作流结构、帧率和采样路线；本机实测负责确认这台机器上的模型、LoRA、人物数量与背景模式。
