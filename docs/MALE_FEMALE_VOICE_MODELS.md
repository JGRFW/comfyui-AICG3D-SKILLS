# 男女声识别方案选型

本插件不再只依靠音高猜测男女声。数字人歌词反推会优先加载本地 wav2vec2 男女声分类模型，并与音色聚类交叉确认。

## 当前采用

### `7wolf/wav2vec2-base-gender-classification`

- 任务：二分类语音性别识别。
- 架构：`Wav2Vec2ForSequenceClassification`。
- 参数量：约 9460 万。
- 许可证：Apache-2.0。
- 模型卡标注：验证集准确率 98.92%。
- 来源：https://huggingface.co/7wolf/wav2vec2-base-gender-classification
- 本地目录：`ComfyUI/models/audio_classifiers/gender_wav2vec2_7wolf`
- 本插件实测：当前测试歌曲第一句判为男声 `0.8535`，第二句判为女声 `0.9876`，与人工听感一致。

模型输出仍会与 MFCC 音色聚类交叉确认，避免单句分类抖动。只有模型和聚类无法形成可靠男女声分组时，才回退到音高算法。

## 调研过的其他方案

### `JaesungHuh/voice-gender-classifier`

- MIT。
- ECAPA-TDNN，约 1550 万参数。
- 基于 VoxCeleb2 微调，模型卡标注 98.7% 准确率。
- 需要使用作者自定义的 ECAPA 推理代码，不是标准 Transformers 分类器，暂不作为默认。
- 来源：https://github.com/JaesungHuh/voice-gender-classifier

### `prithivMLmods/Common-Voice-Gender-Detection`

- Apache-2.0。
- Wav2Vec2 二分类，模型卡标注 98.46% 准确率。
- 在本次歌曲测试中第二句高置信度判成男声，识别结果不如当前模型稳定，因此未采用。

### `alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech`

- Apache-2.0。
- XLS-R 3 亿参数，LibriSpeech 测试 F1 0.9993。
- 权重较大，对中文演唱的泛化没有本地实测优势，暂不作为默认。

### `ComfyUI-SpeakerSplit`

- MIT。
- 使用 VAD、SpeechBrain ECAPA 音色嵌入和层次聚类完成说话人分离。
- 适合从多说话人音频中拆出不同声纹，但它输出的是“说话人 1/2”，本身不判断男女。
- 来源：https://github.com/Gothdir/ComfyUI-SpeakerSplit

### Pyannote 说话人分离节点

- 可做高质量说话人 diarization。
- 通常需要额外安装 pyannote 并接受 Hugging Face 模型条款，部分模型需要 Token。
- 适合后续升级为独立声纹轨道，不作为当前零配置方案的默认依赖。

## 已知限制

- 训练集可能存在语言、性别表达、音域和录音条件偏差。
- 假声、童声、合唱、强混响、重电音和男女重叠演唱可能降低置信度。
- 性别识别不能替代按时间码分轨渲染。它只能帮助生成正确的 S1/S2 图片映射。
- 如状态提示置信度低，仍应在“台词时间线”中手动校正 S1/S2。
