# 人物场景替换速用卡

```text
【人物场景替换｜速用卡】

一、先选模式
[ ] 单人替换
    换人 LoRA：h3_character_swap_pro4500_1000，强度 0.9-1.0
    锁脸：开
    原片参考强度：0.10-0.18

[ ] 多人替换
    换人 LoRA：关
    锁脸：关
    原片参考强度：0.10-0.15
    每个人物使用独立 Picture / Subject

[ ] 人物 + 场景
    人物：按上面“单人/多人”规则
    场景：单独一张纯背景图
    人物 LoRA 与锁脸按人数决定

[ ] 单独场景
    人物 LoRA：关
    锁脸：关
    原片参考强度：0.25-0.40
    人物身份、动作、对白、音轨全部保留

二、固定参数
主模型：minimax_h3_hybrid_fl2va_ref2va_b25-49-int8
模式：Ref2VA 全能参考
换人模式：开启
参考图尺寸：1K，细节不足用 1.5K
输出：至少 480P，优先跟随原片比例
采样器：er_sde
调度器：simple
步数：25，身份不足用 30-35
降噪：1.0

三、提示词必须是六段
subject_definitions:
summary:
retention_analysis:
detailed_description:
overall_soundscape:
non_diegetic_music:

四、四条硬检查
1. 不用的 Picture 不定义、不引用。
2. 多人替换必须关闭单人物换人 LoRA。
3. 正确运行日志必须出现：空潜变量起点、参考预编码、video/image 参考。
4. 用户没有给出确切台词时，不写 <d> 对白，不把任务说明写成人物台词。

五、台词识别接入
视频音轨 → 视频台词识别
多人映射：S1 = Picture 1 | 0.00-1.25；S2 = Picture 2 | 1.25-3.00
台词时间线 → H3 提示词推理
只逐字使用识别文本，保持原语言、原标点和原时间码。
原音轨复用：fully_copy；口型和说话节奏与 Video 1 同步。

六、不要同时叠加
换人 LoRA + 风格 LoRA + 动作 LoRA + 加速 LoRA
身份优先时，只保留真正负责身份的那一个 LoRA。
```
