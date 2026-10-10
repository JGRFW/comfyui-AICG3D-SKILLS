// 画风预设表。画风层只管「怎么画」（介质、线条、光、背景），不管「画谁」——长相、服装在角色层。
// 建角色时整份快照进造型（outfit.look），之后改这里不影响已有角色；要换就 restyle，换完全组标过期。
//
// 每个预设：
//   id       稳定的英文 id，写进资产
//   names    命令行认的名字（中英日都行，不分大小写）
//   label    给人看的名字 { zh, en, ja }
//   medium   'photo'（照片：角色的皮肤层进提示词）| 'drawn'（画出来的：不写毛孔、颗粒这类照片质感）
//   style / clean / neg   拼进提示词的三段英文
//
// 加新预设：照下面的格式加一项，再用真模型把四档跑一遍、看过图再合并——没实测过的预设不要放进来。

// 写实（方案四）：用户确认过的基线（2026-09-26）。只写相机、光、介质；皮肤粗糙到什么程度是角色属性，不写在这里——
// 统一写「泛红、小瑕疵」会把 19 岁的角色画成病容（实测）。不写 photorealistic：它会把画面往 CG 渲染带。
const REALISTIC = {
  id: 'realistic-photo',
  names: ['realistic-photo', 'realistic', 'photo', '写实', '写实照片', '真人', '実写'],
  label: { zh: '写实照片', en: 'Realistic photo', ja: '写実写真' },
  medium: 'photo',
  style: 'A real photograph, not a render: shot on a full-frame digital camera with an 85mm portrait lens at f/5.6, natural true-to-life ' +
    "colors and white balance. Natural skin texture with the pores and fine lines the person's age calls for, a no-makeup look, " +
    'no retouching, no beauty filter. Real fabric with natural creases. Subtle film grain.',
  clean: 'White seamless paper backdrop lit to pure white. A soft directional key light from the front-left with a weaker fill, so the face ' +
    'and clothes have gentle natural shadows and volume. Exactly one person, empty hands, no props, no text, no watermark.',
  neg: 'CGI, 3D render, digital painting, illustration, anime, airbrushed skin, smooth plastic skin, waxy skin, doll face, ' +
    'beauty filter, overly symmetrical face, oversharpened, HDR, glossy, over-saturated, flat lighting, porcelain skin, big anime eyes',
};

// 动漫：日式电视动画的角色设定稿质感。不写 model sheet / turnaround——写了模型会在一张图里画多个视图。
const ANIME = {
  id: 'anime',
  names: ['anime', 'cartoon', '动漫', '卡通', '動漫', '二次元', 'アニメ'],
  label: { zh: '动漫', en: 'Anime', ja: 'アニメ' },
  medium: 'drawn',
  style: 'A clean 2D Japanese anime illustration, like official character art for a TV anime: crisp confident line art of even weight, ' +
    'cel shading with one soft shadow tone and a few sharp highlights, flat clean colors, anime-style eyes with clear highlights, ' +
    'a small simplified nose and mouth, hair drawn in smooth clumps with glossy highlight bands. Fabric folds drawn as simple lines.',
  clean: 'Plain pure white background, evenly lit, with at most a faint soft shadow under the feet. Exactly one character, empty hands, ' +
    'no props, no text, no watermark.',
  neg: 'photograph, photorealistic, realistic skin texture, pores, film grain, 3D render, CGI, semi-realistic, painterly, watercolor, ' +
    'sketch, rough lines, messy lines, heavy shading, gradient background, character sheet, multiple views, chibi, super deformed',
};

export const LOOKS = [REALISTIC, ANIME];
// 默认动漫（用户 2026-09-26 定）；写实用 --look 写实
export const DEFAULT_LOOK_ID = 'anime';

const norm = (s) => String(s ?? '').trim().toLowerCase();

/** 按名字找预设（中英日都认）；找不到返回 null。 */
export function findLook(name) {
  const n = norm(name);
  return LOOKS.find((l) => l.id === n || l.names.some((x) => norm(x) === n)) ?? null;
}

/** 写进资产的快照：去掉命令行才用的 names，其余原样。 */
export function lookSnapshot(preset) {
  const { names, ...rest } = preset;
  return structuredClone(rest);
}

export const DEFAULT_LOOK = lookSnapshot(findLook(DEFAULT_LOOK_ID));

/** 画风层的名字：预设按语言取，自定义画风取它自己的 label（字符串或 {zh,en,…}）。 */
export function lookName(look, lang = 'zh') {
  const l = look?.label;
  if (!l) return look?.id ?? '';
  if (typeof l === 'string') return l;
  return l[lang] ?? l.en ?? l.zh ?? Object.values(l)[0] ?? look.id;
}

/** 自定义画风文件的问题清单。 */
export function lookProblems(look) {
  const p = [];
  for (const k of ['style', 'clean', 'neg']) if (!String(look?.[k] ?? '').trim()) p.push(`画风层缺 ${k}`);
  if (look?.medium && !['photo', 'drawn'].includes(look.medium)) p.push('medium 只能是 photo / drawn');
  if (!/white/i.test(String(look?.clean ?? ''))) p.push('clean 里要写白色背景（white background）——检查门查背景白度，视频模型也要干净的参考图');
  return p;
}
