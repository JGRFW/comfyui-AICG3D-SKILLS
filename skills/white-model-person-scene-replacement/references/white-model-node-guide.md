# 3D人物白模节点模型与参数速查

节点名称：`3D人物白模（视频→动作骨架）`  
节点类：`MiniMaxH3EasyWhiteModelRig`  
所属插件：`ComfyUI-AICG3D-Integrated`

这个节点不加载 H3 主模型和 H3 LoRA。H3 主模型、人物替换 LoRA、VAE 和文本编码器由后面的 `MiniMax H3 Aicg Loader` 负责。

## 一、模型放置目录

ComfyUI 本地模型目录：

```text
ComfyUI/models/checkpoints/
ComfyUI/models/diffusion_models/
ComfyUI/models/detection/
ComfyUI/models/geometry_estimation/
```

本机共享模型目录：

```text
H:\Comfy-Desktop\ComfyUI-Shared\models\checkpoints\
H:\Comfy-Desktop\ComfyUI-Shared\models\diffusion_models\
H:\Comfy-Desktop\ComfyUI-Shared\models\detection\
H:\Comfy-Desktop\ComfyUI-Shared\models\geometry_estimation\
```

## 二、节点模型槽位

| 节点参数 | 默认文件 | 模型目录 | 作用 |
|---|---|---|---|
| `sam3_checkpoint` | `sam3.1_multiplex_fp16.safetensors` | `models/checkpoints/` | SAM3/SAM3.1 人物分割和视频跟踪 |
| `rtdetr_model` | `rt_detr_v4-x-hgnet_fp16.safetensors` | `models/diffusion_models/` | RT-DETR 人物检测，辅助 SAM3 定位 |
| `body_model` | `sam_3d_body_dinov3_bf16.safetensors` | `models/detection/` | SAM3D Body 人体动作、姿态和表情提取 |
| `moge_model` | `geometry_estimation\moge_3_vitg_fp16.safetensors` | `models/geometry_estimation/` | 可选 MoGe 镜头几何和视场估算 |

## 三、全部参数设置

| 参数 | 默认值 | 作用 | 建议 |
|---|---:|---|---|
| `目标提示词` | `person` | 告诉 SAM3 要检测什么对象 | 人物任务保持 `person` |
| `sam3_checkpoint` | `sam3.1_multiplex_fp16.safetensors` | 选择 SAM3 分割/跟踪模型 | 保持默认 |
| `rtdetr_model` | `rt_detr_v4-x-hgnet_fp16.safetensors` | 选择人物检测模型 | 保持默认 |
| `body_model` | `sam_3d_body_dinov3_bf16.safetensors` | 选择人体动作模型 | 保持默认 |
| `moge_model` | `geometry_estimation\moge_3_vitg_fp16.safetensors` | 选择 MoGe 几何模型 | 只有开启 MoGe 时生效 |
| `启用MoGe` | `关` | 估算镜头 FOV 和几何 | 显存紧张时关闭；复杂运镜可尝试开启 |
| `MoGe分辨率等级` | `5` | MoGe 处理精度 | 默认 5；显存不足降到 3~4 |
| `MoGe细化步数` | `0` | MoGe 后处理细化 | 默认 0；需要时提高到 1~3 |
| `最大人物数` | `16` | 最多跟踪和渲染几个人 | 双人任务填 `2`，实际多少人填多少，避免路人和重复跟踪 |
| `检测阈值` | `0.50` | 人物检测置信度门槛 | 通常 `0.50~0.60`；漏人时降低，出现路人时提高 |
| `检测间隔` | `1` | 每隔几帧重新检测 | 固定保持 `1`，人物遮挡和换位更稳定 |
| `长边像素` | `736` | 白模内部工作分辨率 | 默认 736；显存和内存足够可提高 |
| `推理批大小` | `64` | SAM3D Body 每批处理帧数 | 默认 64；显存不足降到 32、16 或 8 |
| `渲染模式` | `mesh` | 白模显示方式 | 优先 `mesh` |
| `着色器` | `default` | 白模材质显示方式 | 优先 `default` |
| `人物颜色衰减` | `1.00` | 控制人物调色板向统一颜色衰减 | 逐人颜色开启时通常保持 `1.00` |
| `启用表情` | `开` | 提取眼神、嘴型和面部表情 | 保持开启 |
| `启用平滑` | `开` | 平滑人体动作抖动 | 保持开启 |
| `保留原始音频` | `开` | 把 Resource Library 音频带入白模视频 | 需要原音轨时保持开启 |
| `保留原视频场景` | `关` | 白模叠加在原视频背景上 | 只换人物并保留原场景时开启 |
| `绿色背景` | `关` | 输出绿幕白模 | 人物和背景一起替换时开启 |
| `逐人锁定颜色` | `开` | 给每个稳定人物分配固定颜色 ID | 多人替换开启；单人且不希望颜色影响成片时可关闭 |
| `人物颜色排序` | `左到右` | 颜色 ID 的分配顺序 | 常用 `左到右`；按面积时选 `面积优先` |
| `人物颜色强度` | `0.75` | 颜色 ID 的叠加强度 | 推荐 `0.45~0.55`；蓝色场景中建议 `0.25~0.35` |

## 四、推荐配置

### 多人替换并替换背景

```text
最大人物数 = 实际人数
检测阈值 = 0.55
检测间隔 = 1
长边像素 = 736
推理批大小 = 64
渲染模式 = mesh
着色器 = default
启用表情 = 开
启用平滑 = 开
保留原始音频 = 开
保留原视频场景 = 关
绿色背景 = 开
逐人锁定颜色 = 开
人物颜色排序 = 左到右
人物颜色强度 = 0.45
```

### 只替换人物并保留原场景

```text
保留原视频场景 = 开
绿色背景 = 关
逐人锁定颜色 = 开
人物颜色强度 = 0.25~0.35
```

如果原场景本身就是蓝色，人物和背景会自然带蓝光；想彻底避免蓝色，需要关闭逐人颜色或替换为其他背景场景图。

### 单人替换且不要颜色影响人物

```text
最大人物数 = 1
保留原视频场景 = 按需求
绿色背景 = 按需求
逐人锁定颜色 = 关
```

### 黑底白模

```text
保留原视频场景 = 关
绿色背景 = 关
```

## 五、颜色 ID 顺序

```text
蓝色 = Subject 1
红色 = Subject 2
绿色 = Subject 3
品红 = Subject 4
青色 = Subject 5
黄色 = Subject 6
```

颜色 ID 只用于锁定人物身份，最终成片必须恢复 Picture 参考中的真实肤色、头发和服装。
