# 出图模型

四种，在 `config` 里选。主图（锚点）和派生图可以分开设，重出单张可以使用 `gen --model` 临时换。
适配器都在 `scripts/models.mjs`，统一接口：给 `{text, negative, ratio, refs[文件路径], seed}`，返回 PNG 字节。

尺寸三档（四个模型通用，都满足 gpt-image-2 的尺寸规则，也都落在视频模型参考图的交集里）：

| 比例 | 尺寸 | 用在 |
| --- | --- | --- |
| 2:3 | 1056×1584 | 正面全身、侧面、背面 |
| 4:5 | 1152×1440 | 大头照 |
| 1:1 | 1328×1328 | 细节 |

视频模型参考图的交集（H3 / Wan / Seedance）：单边 300–5760 像素、宽高比 0.4–2.5、单张 ≤20MB。检查门就按这个查。

## qwen —— Qwen Image 2.1（自己的 ComfyUI）

- 连接：`COMFY_URL`，有鉴权再给 `COMFY_USER` / `COMFY_PASS`（Basic）。放环境变量，或 `config --qwen-env-file <.env>`
- 工作流：`UNETLoader`（`qwen_image_2.1_int8_convrot.safetensors`）→ `ModelSamplingAuraFlow`（shift 3.1）→
  `KSampler`（euler / simple，20 步，cfg 2.5）；`CLIPLoader`（`qwen3vl_8b_int8_convrot.safetensors`，type `qwen_image`）；
  `VAELoader`（`qwen_image_2.1_vae_bf16.safetensors`）；`EmptySD3LatentImage` 给尺寸
- 锚点使用 `CLIPTextEncode` 文生图；派生图使用 `TextEncodeQwenImageEditPlus`，参考图接 `image1..3`（最多 3 张，本 skill 最多挂 2 张）
- 参考图先 `POST /upload/image`，再 `POST /prompt`，轮询 `/history/<id>`，从 `/view` 取图
- 服务器上模型文件名不一样，改 `config.local.json` 里 `models.qwen` 的 `unet` / `clip` / `vae`
- 实测：每张 25–50 秒，尺寸精确，身份一致性好；角度和取景全靠提示词第一句（见 `prompting.md`）

## codex —— codex 内置出图（GPT）

- 调本机 `codex exec`，参考图通过 `-i` 挂上，提示词从标准输入给；自动找版本最高的 codex，也可 `--codex-bin` 指定
- **不要 API key，但吃 ChatGPT 订阅额度**：Plus 约 25 张触顶（`usage_limit_reached`），几小时后恢复。一部剧角色多时不够，
  使用它出锚点或补救单张，批量派生交给 qwen / openai
- 内置工具不收尺寸参数，比例写进提示词；实测照出了严格的 2:3 和 4:5
- 每张 80–160 秒。登录失效会报 401，`codex logout && codex login`
- **出的是透明背景 PNG**（看图软件显示成白底，实际是透明的黑）。存盘前自动铺成白底，记录里留注——视频模型拿到透明图怎么处理背景说不准
- 实测：角度最准（45° 更接近 45°），细节图材质最好

## openai —— OpenAI Images API（GPT Image 2）

- key：`OPENAI_API_KEY`，放环境变量或 `config --openai-env-file <.env>`；接口地址默认 `https://api.openai.com/v1`，
  兼容 OpenAI 格式的中转使用 `--openai-base-url`（或 `.env` 里的 `OPENAI_BASE_URL`）
- 锚点走 `POST /images/generations`；派生图走 `POST /images/edits`（multipart，参考图作为 `image[]`）
- 默认 `gpt-image-2`、`quality: high`。gpt-image-2 尺寸任意（两边 16 的倍数、总像素 655,360–8,294,400），
  参考图恒为高保真，不收 `input_fidelity`；没有反向词参数，反向词拼成提示词末尾的 `Avoid: …`
- 换成 `gpt-image-1` 系列会传 `input_fidelity=high`，但它们只支持 1024×1024 / 1024×1536 / 1536×1024，
  本 skill 的尺寸会被接口拒掉——只用 gpt-image-2
- **只使用本地假服务器验过请求格式，没有使用真 key 跑过**。第一次使用先出一张锚点确认

## custom:<名字> —— 自定义命令

```bash
node scripts/character-refs.mjs config --custom 'mine=mytool --prompt-file {prompt_file} --neg-file {negative_file} --ref {refs} --size {width}x{height} --out {out}'
node scripts/character-refs.mjs config --model custom:mine
```

占位符（全部自动加引号，未知的原样保留）：

| 占位符 | 值 |
| --- | --- |
| `{prompt}` / `{negative}` | 提示词 / 反向词正文 |
| `{prompt_file}` / `{negative_file}` | 写好的文本文件路径（长提示词使用这个更稳） |
| `{refs}` | 参考图路径，空格分隔；锚点没有参考图时为空 |
| `{ref1}` `{ref2}` `{ref3}` | 单张参考图，没有就是空字符串 |
| `{out}` | 命令必须把 PNG 写到这里 |
| `{width}` `{height}` `{ratio}` | 尺寸与比例 |
| `{seed}` | 种子 |

同一条模板要能处理有参考图和没有参考图两种情况（锚点没有）。命令退出后 `{out}` 不存在就算失败，报错带上 stderr 前 300 字。

## 换模型

一致性来自同一张锚点，不来自同一个模型。实测组合（沈知微，每种 1 个种子）：

| 锚点 | 派生 | 结果 |
| --- | --- | --- |
| Qwen | GPT | 7/7 一次全对，细节图最好 |
| GPT | Qwen | 可用，Qwen 完全跟随 GPT 锚点的设计（七分袖也照着出） |
| Qwen | Qwen + GPT 混用 | 衔接得上，细节图之间有轻微亮度差 |

推荐：派生默认 qwen（快、不吃额度），出不好的单张使用 `gen <视图> --model codex` 重出。
