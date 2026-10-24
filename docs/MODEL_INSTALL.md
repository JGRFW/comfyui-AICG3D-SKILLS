# 模型下载与放置说明

本插件不会把模型权重提交到 GitHub。模型统一放在 ComfyUI 的 `models` 目录，不要放进 `custom_nodes/comfyui-AICG3D-SKILLS`。

## 一、数字人歌词识别模型

数字人提示词生成需要 Whisper 或兼容的本地 `.pt` 模型。

推荐目录：

```text
ComfyUI/
└─ models/
   └─ audio_encoders/
      ├─ large-v3-turbo.pt
      ├─ large-v3.pt
      └─ medium.pt
```

插件同时扫描：

```text
ComfyUI/models/audio_encoders/
ComfyUI/models/whisper/
```

| 模型 | 约体积 | 用途 |
|---|---:|---|
| `large-v3-turbo.pt` | 1.6 GB | 速度与准确率平衡，默认推荐 |
| `large-v3.pt` | 3 GB | 中文歌词准确率优先 |
| `medium.pt` | 1.5 GB | 显存或速度受限时使用 |

如果模型放在其他目录，可以把完整 `.pt` 路径填写到节点的“本地模型路径”。

## 二、男女声分类模型

当前默认模型：

```text
7wolf/wav2vec2-base-gender-classification
```

许可证：Apache-2.0

标准目录：

```text
ComfyUI/
└─ models/
   └─ audio_classifiers/
      └─ gender_wav2vec2_7wolf/
         ├─ config.json
         ├─ model.safetensors
         └─ preprocessor_config.json
```

其中 `model.safetensors` 约 378 MB。

### 自动下载

首次运行数字人提示词生成时，插件会自动检查上述文件。缺失时会从 Hugging Face 镜像下载：

```text
https://hf-mirror.com/7wolf/wav2vec2-base-gender-classification
```

不需要 Hugging Face Token。下载完成后模型会一直保存在：

```text
ComfyUI/models/audio_classifiers/gender_wav2vec2_7wolf
```

### 手动下载

使用 Hugging Face CLI：

```powershell
huggingface-cli download 7wolf/wav2vec2-base-gender-classification `
  --local-dir "H:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\models\audio_classifiers\gender_wav2vec2_7wolf"
```

也可以直接下载以下三个文件并放入同一目录：

```text
https://huggingface.co/7wolf/wav2vec2-base-gender-classification/resolve/main/config.json
https://huggingface.co/7wolf/wav2vec2-base-gender-classification/resolve/main/model.safetensors
https://huggingface.co/7wolf/wav2vec2-base-gender-classification/resolve/main/preprocessor_config.json
```

### 自定义模型目录

可通过环境变量指定其他目录：

```powershell
$env:AICG3D_GENDER_MODEL_DIR = "D:\AI\Models\gender_wav2vec2_7wolf"
```

目录中仍必须包含：

```text
config.json
model.safetensors
preprocessor_config.json
```

## 三、本地视觉提示词模型

本地视觉模型扫描目录：

```text
ComfyUI/
└─ models/
   └─ llm/
```

支持 Transformers 和 GGUF 视觉模型。GGUF 主模型需要匹配的 `mmproj` 文件；缺少 `llama-cpp-python` 时，模型设置面板会显示依赖状态。

## 四、如何确认男女声模型已工作

1. 添加一个 `PreviewAny` 节点。
2. 把 H3 多参考提示词推理节点的“运行状态”接到 `PreviewAny`。
3. 运行数字人提示词生成。
4. 状态中应出现：

```text
wav2vec2 男女声模型 + 音色聚类
```

同时 `H3请求JSON` 会包含：

```json
"audio_analysis": {
  "gender_model_used": true,
  "gender_model_id": "7wolf/wav2vec2-base-gender-classification"
}
```

## 五、常见问题

- “技能包”里找不到男女声模型：这是正常现象。它不是 Skill，不参与技能包下拉选择，而是数字人提示词节点的后台识别组件。
- 模型目录不存在：第一次运行数字人模式时会自动创建并下载。
- 下载失败：检查能否访问 `hf-mirror.com`，或按上面的手动下载步骤放置文件。
- 状态显示回退音高算法：说明模型未成功加载，请检查目录和三个文件是否完整。
- 音频仍出现声部错误：把 `运行状态` 里的时间线复制到“台词时间线”，逐段修正 `S1/S2` 后重新运行。
