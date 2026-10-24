# 数字人演唱提示词模板

```text
subject_definitions:
<Subject 1> 是 <Picture 1> 中的人物，保持脸型、五官、发型、服装、配饰、体型、背景和空间关系稳定。人物是目标视频中的歌手（S1）。

summary:
[reference generation + digital human audio reuse] 人物保持 <Picture 1> 中的身份与外观，按照锁定歌曲音轨完成逐字演唱和口型同步。

retention_analysis:
<Picture 1>: fully_preserved - 人物身份、外观、服装和场景关系保持稳定。
锁定歌曲音轨: fully_copy - 原歌曲、人声、伴奏、节奏和时长完整复用。

detailed_description:
[Shot 1] 开场。低机位三分之二广角横移，借现场前景视差从环境揭示歌手；首句起唱时落到完整面部。<Subject 1>（S1）是当前唯一开口演唱者，以锁定歌曲音轨中的原声音色、语速、咬字和气息演唱，嘴唇、下颌、呼吸、眼神和头肩律动同步。

00:00.000-00:03.560, <Subject 1> (S1) sings:
<d>[Mandarin singing] 真实歌词第一句</d>

[Shot 2] 在 00:03.560 处，句首硬切到低机位中近景。35mm 视感沿肩线平行 Truck，背景空间线形成视差；歌手随重音转向镜头，动作只做一次明确抬手或落肩。

00:03.560-00:07.120, <Subject 1> (S1) sings:
<d>[Mandarin singing] 真实歌词第二句</d>

[Shot 3] 在 00:07.120 处，顺着手势做动作匹配切到三分之四近景。镜头用真实 Dolly 靠近眼睛，再以 Crane Up + Dolly Out 拉回完整场景；最后一句收小动作并把视线留在场景里。

00:07.120-00:10.000, <Subject 1> (S1) sings:
<d>[Mandarin singing] 真实歌词第三句</d>

overall_soundscape:
N/A

non_diegetic_music:
N/A
```

## 男女对唱版关键替换

```text
subject_definitions:
<Subject 1> 是 <Picture 1> 中的男子，只负责男声（S1）；<Subject 2> 是 <Picture 2> 中的女子，只负责女声（S2）。<Subject 3> 是 <Picture 3> 中的共同场景。对唱采用交替单人镜头：每个时间段画面中有且只有当前歌手一个人，另一人完全在画外。

retention_analysis:
<Picture 1>: fully_preserved - 男子身份和外观稳定。
<Picture 2>: fully_preserved - 女子身份和外观稳定。
<Picture 3>: fully_preserved - 共同场景和双人空间关系稳定。
锁定歌曲音轨: fully_copy - 原歌曲含男女声的完整音轨。

detailed_description:
[Shot 1] 开场。镜头从共享场景横移到男声单人近景。画面中有且只有 <Subject 1> (S1) 男声一个人；<Subject 2> (S2) 女声完全在画外，不出现第二张脸、第二张嘴、第二具身体或第二套口型。<Subject 1> 以锁定歌曲音轨中的男声音色、语速、咬字和气息演唱。

00:00.000-00:03.560, <Subject 1> (S1) sings:
<d>[Mandarin singing] 男声歌词</d>

[Shot 2] 在 00:03.560 处，下一句第一个字硬切到女声单人镜头。画面中有且只有 <Subject 2> (S2) 女声一个人；<Subject 1> (S1) 男声在切点前闭唇并完全离开画面。保持共享场景和屏幕方向连续。

00:03.560-00:07.120, <Subject 2> (S2) sings:
<d>[Mandarin singing] 女声歌词</d>
```
