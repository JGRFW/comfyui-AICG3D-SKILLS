# asset.json

一个角色一个文件，放在 `<输出目录>/<角色名>/asset.json`，图片路径都相对它。**由脚本读写，不要手改 `views`。**
要改描述：改 intake 重新 `new`（新资产），或直接改 `layers` / 造型里的文字——改完所有照旧文字出的图都会标成过期。

```jsonc
{
  "name": "阿禾",                     // 只用于文件名、标识和报告，不进提示词
  "source": "样例 · 茶山",             // 可省
  "lang": "zh",                       // 确认表与报告的语言；没有这个字段按 zh
  "ui": { … },                        // 只有非内置语言才有：自译的界面文案
  "layers": {                         // 角色层：换造型也不变的
    "identity": { "age": 16, "gender": "female", "en": "…", "text": "…", "source": "stated" },
    "face":  { "en": "…", "text": "…", "source": "stated" },   // en 进提示词；text 给人看（旧资产是 zh，照样认）
    "hair":  { … },
    "build": { … },                   // 可省
    "skin":  { … },                   // 可省，省了按年龄补
    "backCue": { … }                  // 可省，省了按发型与服装拼
  },
  "outfits": {                        // 造型层；v1 只有 default
    "default": {
      "label": "常态 · 采茶装",
      "top":    { "en": "…", "text": "…", "source": "stated" },
      "bottom": { … },
      "details": [ { "slot": "hair", "en": "…", "text": "…", "source": "stated" }, … ],
      "overrides": {},                // 这套造型要改的角色层，比如换发型：{ "hair": { … } }
      "look": { "id": "anime", "label": { "zh": "动漫", "en": "Anime", "ja": "アニメ" }, "medium": "drawn",
                "style": "…", "clean": "…", "neg": "…" },   // 画风快照；medium: photo 照片 / drawn 画出来的
      "upgrades": [ { "tier": 2, "reason": "E03 有面部特写", "at": "…" } ],
      "views": {
        "front-full": {
          "current": 2,               // 当前生效的版本
          "versions": [ { … v1 … }, { … v2 … } ]   // 重出只追加，不删
        }
      }
    }
  }
}
```

## 一个版本

```jsonc
{
  "v": 1,
  "id": "阿禾/default/front-full/v1",          // 标识：角色/造型/视图/版本
  "file": "default/front-full.v1.png",
  "sha256": "…",                               // 写入标识之后的文件哈希
  "model": "qwen",                             // 这张使用的模型；同组混用只提醒
  "seed": 1980929016,
  "prompt": "…", "negative": "…",              // 实际发出去的提示词
  "refs": [ { "view": "front-full", "v": 1, "sha256": "…" } ],   // 实际挂了哪几张参考图
  "notes": [],                                 // 比如「face-front 缺失或已过期，这张只挂锚点」
  "layersHash": "…",                           // 出图时的文字描述指纹
  "lookHash": "…",                             // 出图时的画风快照指纹
  "gates": [ { "id": "size", "label": "…", "ok": true, "detail": "1056×1584" }, … ],
  "createdAt": "…",
  "confirmed": true, "confirmedAt": "…"        // 只有锚点有：false 待确认 / true 已确认 / "auto" 配置为不确认
}
```

同样的标识、模型、参考图也写进 PNG 的 iTXt 字段（`shuohao:id`、`shuohao:model`、`shuohao:refs`）。

## 视图

| id | 档位 | 比例 | 参考图 |
| --- | --- | --- | --- |
| `front-full` | 1（锚点） | 2:3 | 无 |
| `face-front` | 2 | 4:5 | 锚点 |
| `side-full` | 2 | 2:3 | 锚点 |
| `back-full` | 2 | 2:3 | 锚点 |
| `detail-hair` / `detail-neck` | 3 | 1:1 | 锚点 + 大头照 |
| `detail-sleeve` / `detail-feet` | 3 | 1:1 | 锚点 |
| `detail-<id>`（自定义） | 3 | 1:1 | `part` 为 hair / neck 挂锚点 + 大头照，其余只挂锚点；标「未实测」 |
| `face-45` | 4 | 4:5 | 锚点 |

## 过期

一张图的当前版本满足任一条就过期（`check` exit 1，报告标红框）：

- 文字描述指纹变了：改了人本身的描述（身份、年龄、性别、脸、头发、身形、皮肤、上下装、背面）→ 全部过期；
  改了某条细节 → 只有那张细节图过期；加、删细节 → 不影响其他图
- 画风快照变了
- 它参考的某张图换了版本（重出锚点 → 其余全部过期；重出大头照 → 挂了大头照的细节过期）

只标记，不删除；重出这一张就好。锚点重出后要重新确认。
