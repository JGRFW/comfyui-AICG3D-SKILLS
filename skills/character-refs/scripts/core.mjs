// 角色参考图的确定性核心：视图与档位、提示词拼装、输入校验、版本与过期、检查门。
// 不调用任何模型——出图在 models.mjs，命令行在 character-refs.mjs。

import { createHash } from 'node:crypto';
import { decode, pngInfo, isPng, withText } from './png.mjs';
import { BUILTIN, LANG_RE, fmt, uiFor, uiMissing } from './i18n.mjs';
import { DEFAULT_LOOK } from './looks.mjs';

export { DEFAULT_LOOK };

/* ------------------------------------------------------------------ */
/* 视图与档位                                                            */
/* ------------------------------------------------------------------ */
/*
 * 一组图只有一个根：正面全身（锚点），纯文生图。其余每一张都只参考锚点
 * （脸、头发、领口的细节额外参考正脸大头照），彼此不互相参考——
 * 一致性来自「同一张锚点」，不来自「同一个模型」，所以派生图可以换模型。
 *
 * 档位按需往上加，不返工：
 *   1 正面全身（锚点）            默认只出这一档
 *   2 正脸大头照 + 90° 侧面 + 背面   大头照最有用（视频测试里唯一看得出收益的一张）
 *   3 四张细节                    头发 / 领口 / 袖口 / 鞋，都是实测通过的部位
 *   4 45° 大头照                  默认不出
 */
export const VIEWS = {
  'front-full': { tier: 1, ratio: '2:3', kind: 'full', label: '正面全身（锚点）', refs: [] },
  'face-front': { tier: 2, ratio: '4:5', kind: 'face', label: '正脸大头照', refs: ['front-full'] },
  'side-full': { tier: 2, ratio: '2:3', kind: 'full', label: '侧面 90°（面朝右）', refs: ['front-full'] },
  'back-full': { tier: 2, ratio: '2:3', kind: 'full', label: '背面', refs: ['front-full'] },
  'face-45': { tier: 4, ratio: '4:5', kind: 'face', label: '45° 大头照（面朝左）', refs: ['front-full'] },
};
export const ANCHOR = 'front-full';
/** 默认出到第二档：锚点 + 正脸大头照 + 90° 侧面 + 背面（视频测试里大头照对保脸最有用，用户定默认就出齐）。 */
export const DEFAULT_TIER = 2;
export const RATIOS = { '2:3': 2 / 3, '4:5': 4 / 5, '1:1': 1 };

/** 细节槽位：默认四个，都是两个测试角色上实测通过的部位。 */
export const DETAIL_SLOTS = {
  hair: { label: '头发 / 发饰', part: 'hair' },
  neck: { label: '领口', part: 'neck' },
  sleeve: { label: '袖口', part: 'body' },
  feet: { label: '鞋', part: 'feet' },
};
/**
 * 自定义细节的部位：模型只写「画什么」，取景由脚本按部位加（和默认槽位一样）。
 * 默认四个槽位是实测稳定的；自定义部位没有实测，确认表和报告里标「未实测」。
 */
// 没有 face：脸上的特征（眼镜、疤、痣）正脸大头照里已经看得清；Qwen 实测 3 种写法 × 2 种子，全部画成整张大头照
export const DETAIL_PARTS = ['hair', 'neck', 'hands', 'waist', 'body', 'feet'];
export const MAX_DETAILS = 8;
/** 这些部位的细节额外挂正脸大头照当参考（脸部像素更多）；其余只挂锚点。 */
const FACE_PARTS = new Set(['hair', 'face', 'neck']);

export function detailViews(outfit) {
  const out = {};
  for (const d of outfit?.details ?? []) {
    const part = d.slot === 'custom' ? d.part : DETAIL_SLOTS[d.slot]?.part;
    out[`detail-${d.slot === 'custom' ? d.id : d.slot}`] = {
      tier: 3, ratio: '1:1', kind: 'detail', part, detail: d, tested: d.slot !== 'custom',
      label: d.slot === 'custom' ? (human(d) || d.id) : DETAIL_SLOTS[d.slot].label,
      refs: FACE_PARTS.has(part) ? ['front-full', 'face-front'] : ['front-full'],
    };
  }
  return out;
}

export const allViews = (outfit) => ({ ...VIEWS, ...detailViews(outfit) });
export const viewsOfTier = (outfit, tier) => Object.entries(allViews(outfit)).filter(([, v]) => v.tier === tier).map(([k]) => k);

/* ------------------------------------------------------------------ */
/* 画风层（按项目存；出锚点时整份快照进 frozen）                            */
/* ------------------------------------------------------------------ */
// 预设表在 looks.mjs；这里只用默认的那一个当缺省值。
const BASE_NEG = 'text, watermark, border, multiple people, extra limbs, deformed hands, props, scenery, colored background, oversaturated colors';
const FACE_NEG = BASE_NEG + ', waist, torso, arms, hands, full body, legs, feet, wide shot, medium shot';

/* ------------------------------------------------------------------ */
/* 小工具                                                                */
/* ------------------------------------------------------------------ */
export const CJK = /[㐀-鿿぀-ヿ가-힯]/;
export const sha256 = (x) => createHash('sha256').update(x).digest('hex');
const sentence = (s) => {
  const t = String(s ?? '').trim();
  return !t ? '' : /[.!?]$/.test(t) ? t : t + '.';
};
const clause = (s) => String(s ?? '').trim().replace(/[.。;；]+$/, '');
/** 去掉句末标点与开头冠词，好接在 the same / her 后面。 */
const bare = (s) => clause(s).replace(/^(a|an|the)\s+/i, '');
/** 句首大写的普通词放进句中要小写（One thick braid → one thick braid）；专有名词（第二个字母也大写的缩写等）不动。 */
const lowerFirst = (s) => { const t = clause(s); return /^[A-Z][a-z]/.test(t) && !/^(I|Chinese|Japanese|Korean)\b/.test(t) ? t[0].toLowerCase() + t.slice(1) : t; };
const en = (field) => clause(field?.en ?? field);
/** 给人看的那段描述：新字段 text，旧输入的 zh 照样认。 */
export const human = (field) => String(field?.text ?? field?.zh ?? '').trim();

export function pronouns(gender) {
  return gender === 'male' ? { s: 'he', o: 'him', p: 'his' } : { s: 'she', o: 'her', p: 'her' };
}
export function nounOf(age, gender) {
  const f = gender !== 'male';
  if (age >= 60) return f ? 'old woman' : 'old man';
  if (age < 30) return f ? 'young woman' : 'young man';
  return f ? 'woman' : 'man';
}

/** 皮肤缺省按年龄给——皮肤粗糙程度是角色属性，不是画风。 */
/** 缺省皮肤按年龄分三档；给人看的文字按语言从文案表取（skinBand）。 */
export const skinBand = (age) => (age < 25 ? 'young' : age < 50 ? 'adult' : 'old');
export function defaultSkin(age) {
  if (age < 25) return { en: 'Young skin with faint pores on the nose and cheeks and a slightly uneven natural tone, no makeup', zh: '年轻皮肤，鼻翼脸颊有细微毛孔，肤色自然略不匀，素颜' };
  if (age < 50) return { en: 'Natural adult skin with visible pores and a slightly uneven tone', zh: '成年人的自然皮肤，可见毛孔，肤色略不匀' };
  return { en: 'Aged, weathered skin with visible pores, age spots and wrinkles that follow the expression lines', zh: '上了年纪的皮肤，风吹日晒，有老年斑，皱纹顺表情肌走' };
}

/** 背面描述缺省：背面才看得到的东西——头发从后面看、衣服背面、脚跟。 */
export function defaultBackCue(c, outfit) {
  const { p } = pronouns(c.identity.gender);
  return {
    en: `the back of ${p} head with ${p} hair as seen from behind (${lowerFirst(en(c.hair))}), the back of ${p} ${bare(en(outfit.top))} and of ${p} ${bare(en(outfit.bottom))}, and ${p} heels`,
    zh: '从后面看到的发型、上衣与下装的背面、脚跟',
  };
}

/** 角色 + 造型合并出实际参与拼提示词的各层（overrides 覆盖角色层，缺省值在这里补上）。 */
export function resolveLayers(asset, outfitId = 'default') {
  const outfit = asset.outfits?.[outfitId];
  if (!outfit) throw new Error(`没有造型 ${outfitId}`);
  const c = { ...asset.layers, ...(outfit.overrides ?? {}) };
  return {
    identity: c.identity, face: c.face, hair: c.hair, build: c.build ?? null,
    skin: c.skin ?? { ...defaultSkin(c.identity.age), source: 'default', auto: 'skin' },
    top: outfit.top, bottom: outfit.bottom, details: outfit.details ?? [],
    backCue: outfit.backCue ?? c.backCue ?? { ...defaultBackCue(c, outfit), source: 'default', auto: 'back' },
  };
}

/** 文字层指纹：只算参与出图的英文。改了它，照旧文字出的图就过期。 */
/**
 * 某一张图的文字指纹：人本身的描述（身份、脸、头发、身形、皮肤、上下装、背面）+ 细节图自己那一条细节。
 * 细节只决定「拍哪些特写」，不算进其他视图——加一个细节只多出一张图，不会让整组过期；
 * 改某条细节的文字，只有那张细节图过期。要改角色本身的样子，改外貌和服装字段。
 */
export function viewLayersHash(L, spec) {
  const base = [L.identity.age, L.identity.gender, en(L.identity), en(L.face), en(L.hair), en(L.build), en(L.skin),
    en(L.top), en(L.bottom), en(L.backCue)];
  const d = spec?.detail;
  return sha256(JSON.stringify(d ? [...base, [d.slot, d.id ?? null, d.part ?? null, en(d)]] : base)).slice(0, 16);
}

// medium 只在 drawn 时计入，老资产（写实、没有 medium 字段）的指纹不变
export const lookHash = (look) => sha256(JSON.stringify([look.style, look.clean, look.neg, ...(look.medium === 'drawn' ? ['drawn'] : [])])).slice(0, 16);

/* ------------------------------------------------------------------ */
/* 提示词                                                                */
/* ------------------------------------------------------------------ */
/*
 * 逐字沿用实测通过的写法（Qwen 两个角色 × 多个种子达标，同一套在 GPT 上也一次跑通）：
 *  - 改图模型只有第一句明确要求时才改构图：大头照以 “Zoom in to an extreme close-up head-and-shoulders
 *    portrait, passport-photo framing” 开头，并写可量化的取景（头顶贴上边、下巴在正中、下边切锁骨）；
 *  - 背面用 “Rotate the camera 180 degrees around …” + 只有背面看得到的特征；
 *  - 细节图第一句 “Zoom in to an extreme close-up of only …”，一致性只写一句，**不列整套服装**——
 *    列了整套，模型就把整个人画出来（第一轮细节图 8/8 失败的原因）。
 */
export function buildPrompt(asset, outfitId, viewId, lookArg = null) {
  const outfit = asset.outfits[outfitId];
  const look = lookArg ?? outfit.look ?? DEFAULT_LOOK;   // 不传就用这个造型自己的画风快照
  const L = resolveLayers(asset, outfitId);
  const v = allViews(outfit)[viewId];
  if (!v) throw new Error(`没有视图 ${viewId}（可用：${Object.keys(allViews(outfit)).join(' / ')}）`);
  const { s, o, p } = pronouns(L.identity.gender);
  const who = `this same ${nounOf(L.identity.age, L.identity.gender)}`;
  const S = s[0].toUpperCase() + s.slice(1);
  const details = L.details.map((d) => en(d));
  // 画出来的画风（动漫等）不写皮肤层：毛孔、雀斑这类照片质感会把画面往写实拽
  const drawn = look.medium === 'drawn';
  const look_ = [sentence(en(L.identity)), sentence(en(L.face)), sentence(en(L.hair)), L.build ? sentence(en(L.build)) : '',
    sentence(`${S} wears ${en(L.top)}; ${en(L.bottom)}`), ...details.map(sentence), drawn ? '' : sentence(en(L.skin))].filter(Boolean).join(' ');
  // 一致性清单要短，并按视图取层（实测）：大头照只保留脸、头发、上装——写了下装和鞋，模型就拉远镜头去画；
  // 细节只在锚点里写一次，派生图从锚点里看得到，不再重复（列多了同样把镜头往全身带）。
  const same = (x) => `the same ${bare(en(x))}`;
  const keepList = (items) => `Keep ${o} exactly the same person as in the reference image: ${items.join(', ')}. ${look.style} ${look.clean}`;
  const keepFace = keepList(['same face, eyes and eyebrows', lowerFirst(en(L.hair)), same(L.top)]);
  const keep = keepList(['same face, eyes and eyebrows', lowerFirst(en(L.hair)), same(L.top), same(L.bottom)]);
  const tight = `Framing: the top of ${p} head is just below the top edge of the image, ${p} chin sits at the vertical middle of the image, ` +
    `and the bottom edge of the image cuts across ${p} collarbones.`;
  const reframe = `Framing reminder: the bottom edge of the image cuts across ${p} collarbones, so ${p} arms, sleeves and cuffs are out of frame.`;
  const neg = BASE_NEG + ', ' + look.neg;
  const faceNeg = FACE_NEG + ', ' + look.neg;

  let text, negative;
  switch (viewId) {
    case 'front-full':
      // 正面要写成几何：只写 facing the camera，动漫画风会按「官方角色图」的习惯画成微侧身，
      // 派生图照着锚点改，大头照也跟着侧过去（实测）。
      text = `Full-body front view: ${s} stands straight and faces the camera squarely, shoulders, hips and feet square to the camera, ` +
        `${p} face pointing straight at the camera with ${p} nose on the vertical centre line of ${p} face and both ears equally visible, ` +
        `arms relaxed at ${p} sides, the whole figure from head to feet visible and centered, with margin above the head and below the feet. ` +
        `${look_} ${look.style} ${look.clean}`;
      negative = neg + ', cropped feet, cropped head, three-quarter view, turned body, head turned to the side, contrapposto, dynamic pose';
      break;
    case 'face-front':
      // 取景在前、几何在后、结尾再重申一次取景：正面的几何描述写长了会冲淡开头的「拉近」，镜头又退回半身（实测）
      text = `Zoom in to an extreme close-up head-and-shoulders portrait, passport-photo framing, of ${who} facing the camera squarely. ` +
        `${tight} ${S} faces straight at the camera: ${p} nose is on the vertical centre line of the image and both ears are equally visible. ` +
        `${keepFace} ${reframe}`;
      negative = faceNeg + ', three-quarter view, head turned to the side, profile, tilted head';
      break;
    case 'face-45':
      text = `Zoom in to an extreme close-up head-and-shoulders portrait, passport-photo framing, of ${who}, and turn ${p} head and ` +
        `shoulders about 45 degrees toward the left side of the image: a three-quarter view with ${p} nose pointing toward the left edge ` +
        `of the image, ${p} left ear visible and ${p} right ear hidden. ${tight} ${keepFace}`;
      negative = faceNeg + ', frontal face, looking at camera, symmetrical face';
      break;
    case 'side-full':
      text = `Full-body side profile of ${who}: ${p} whole body and ${p} head both face the right edge of the image, looking straight ` +
        `ahead to the right, not at the camera. Only the right side of ${p} face is visible. Head to feet in frame. ${keep}`;
      negative = neg + ', looking at camera, front view, three-quarter view, both eyes visible, cropped feet';
      break;
    case 'back-full':
      text = `Rotate the camera 180 degrees around ${o}: a full-body back view. ${S} stands with ${p} back to the camera and ${p} face is ` +
        `completely hidden. We see ${en(L.backCue)}. Head to feet in frame. ${keep}`;
      negative = neg + ', face, eyes, nose, front view, buttons, pockets, looking at camera';
      break;
    default: {
      const d = v.detail;
      const age = L.identity.age;
      const skin = `Any visible skin is the skin of a ${age}-year-old.`;
      const byKey = {
        hair: `Zoom in to an extreme close-up ${drawn ? 'view' : 'macro photo'} of only ${en(d)}. It fills the entire frame and ${p} face is not visible; individual hair strands and fine texture are sharp.`,
        neck: `Zoom in to an extreme close-up of only ${p} neckline: ${en(d)} fill the entire frame. The frame is cropped below ${p} chin, so ${p} face is not visible. ${skin}`,
        sleeve: `Zoom in to an extreme close-up of only one sleeve cuff at the wrist: ${en(d)}. The cuff fills the entire frame; no face and no full body. ${skin}`,
        feet: `Zoom in to an extreme close-up of only ${p} feet and ankles: ${en(d)}, on a plain white floor. Only the feet and ankles are visible; no face and no upper body. ${skin}`,
        // 以下是自定义部位的取景（未实测的写法同样守「第一句只写这个部位、写清画面边界」）
        hands: `Zoom in to an extreme close-up of only ${p} hand: ${en(d)}. The hand fills the entire frame; no face and no full body. ${skin}`,
        waist: `Zoom in to an extreme close-up of only ${p} waist: ${en(d)}. It fills the entire frame; no face, no head and no legs.`,
        body: `Zoom in to an extreme close-up of only ${en(d)}. It fills the entire frame; no face and no full body. ${skin}`,
      };
      // 默认槽位按槽位取景；自定义按部位；老输入里自己写了整句（以 Zoom in 开头）的原样使用
      const legacy = d.slot === 'custom' && /^Zoom in to /.test(String(d.en ?? ''));
      const frame = legacy ? sentence(en(d)) : byKey[d.slot === 'custom' ? d.part : d.slot];
      const two = v.refs.length > 1;
      text = `${frame} Same person, same clothing and materials as in the reference image${two ? 's' : ''}. ${look.style} ` +
        'Plain white background wherever any background shows. No text, no watermark.';
      negative = neg + (v.part === 'face' ? ', full body, wide shot, whole face' : ', face, head, portrait, full body, standing figure, wide shot, medium shot');
    }
  }
  return { view: viewId, text, negative, ratio: v.ratio, refs: v.refs };
}

/* ------------------------------------------------------------------ */
/* 一次性输入：模型分类补全 → 这里校验 → 确认表                             */
/* ------------------------------------------------------------------ */
export const SOURCES = { stated: '原话', inferred: '推断', default: '默认' };
const STYLE_WORDS = /\b(photo-?realistic|hyper-?realistic|anime|manga|cartoon|illustration|3d render|oil painting|watercolou?r|ghibli|cinematic|film still)\b/i;

export function intakeProblems(x) {
  const p = [];
  const need = (f, label) => {
    if (!f || typeof f !== 'object') { p.push(`缺 ${label}`); return; }
    if (!String(f.en ?? '').trim()) p.push(`${label} 缺英文（en）——出图用英文`);
    if (!human(f)) p.push(`${label} 缺给人看的描述（text，用 lang 指定的语言）——确认表和报告要用`);
    if (f.source && !SOURCES[f.source]) p.push(`${label} 的 source 只能是 ${Object.keys(SOURCES).join(' / ')}`);
    if (CJK.test(String(f.en ?? ''))) p.push(`${label} 的英文里混了中日韩字符`);
    if (STYLE_WORDS.test(String(f.en ?? ''))) p.push(`${label} 写了画风词（${String(f.en).match(STYLE_WORDS)[0]}）——画风由项目画风层统一加，角色描述里不写`);
    if (x?.name && String(f.en ?? '').includes(x.name)) p.push(`${label} 的英文里出现了角色名——出图提示词禁人名`);
    if (/\((inferred|推断)\)/i.test(String(f.en ?? ''))) p.push(`${label} 的英文里写了推断标记——标记只进确认表，写进提示词会被画出来`);
  };
  if (!String(x?.name ?? '').trim()) p.push('缺 name（角色名）');
  const lang = x?.lang ?? 'zh';
  if (!LANG_RE.test(String(lang))) p.push(`lang 要写语言代码（zh / en / ja / fr …），现在是 ${lang}`);
  else if (!BUILTIN.includes(lang)) {
    const miss = uiMissing(x?.ui);
    if (miss.length) p.push(`lang ${lang} 不是内置语言（${BUILTIN.join(' / ')}），要带完整的 ui（运行 ui-template ${lang} 翻译后放进 ui 字段）；缺 ${miss.length} 项，如 ${miss.slice(0, 3).join('、')}`);
  }
  const id = x?.identity;
  need(id, 'identity 身份');
  if (id) {
    if (!Number.isInteger(id.age) || id.age < 1 || id.age > 110) p.push('identity.age 必须是整数岁');
    if (!['female', 'male'].includes(id.gender)) p.push('identity.gender 只能是 female / male');
    if (id.source === 'default') p.push('身份（年龄、性别、年代）不能用默认值——推不出来就问用户，这三样错了整组图都错');
  }
  need(x?.face, 'face 脸型五官');
  need(x?.hair, 'hair 发型');
  for (const k of ['build', 'skin', 'backCue']) if (x?.[k]) need(x[k], k);
  const o = x?.outfit;
  if (!o) p.push('缺 outfit（造型）');
  else {
    need(o.top, 'outfit.top 上装');
    need(o.bottom, 'outfit.bottom 下装');
    const seen = new Set();
    if ((o.details ?? []).length > MAX_DETAILS) p.push(`细节最多 ${MAX_DETAILS} 个（现在 ${o.details.length} 个）——挑最能认出这个角色的`);
    for (const [i, d] of (o.details ?? []).entries()) {
      const label = `outfit.details[${i}]`;
      if (d.slot !== 'custom' && !DETAIL_SLOTS[d.slot]) p.push(`${label} 的 slot 只能是 ${Object.keys(DETAIL_SLOTS).join(' / ')} / custom`);
      const key = d.slot === 'custom' ? `custom:${d.id}` : d.slot;
      if (seen.has(key)) p.push(`${label} 的槽位 ${key} 重复`);
      seen.add(key);
      if (d.slot === 'custom') {
        if (!/^[a-z0-9-]+$/.test(String(d.id ?? ''))) p.push(`${label} 自定义细节要有 id（小写字母、数字、连字符）`);
        if (d.part === 'face') p.push(`${label} 脸上的特征（眼镜、疤、痣）不单独出细节图：正脸大头照里已经看得清，Qwen 实测也只会画成整张大头照——写进 face 字段就够了`);
        else if (!DETAIL_PARTS.includes(d.part)) p.push(`${label} 自定义细节要写 part：${DETAIL_PARTS.join(' / ')}`);
        if (DETAIL_SLOTS[d.id]) p.push(`${label} 的 id 不能和默认槽位同名（${d.id}）`);
      }
      const e = String(d.en ?? '');
      if (!/^Zoom in to /.test(e) && /\b(close-?up|zoom|macro|extreme)\b/i.test(e)) p.push(`${label} 只写部位本身，不写 close-up / zoom 这类取景词——取景由脚本按部位加`);
      need(d, label);
    }
  }
  return p;
}

/** 终端显示宽度：中日韩与全角算 2 格，其余（含 °）算 1 格。 */
export const displayWidth = (s) => [...s].reduce((n, ch) => n + (/[\u1100-\u115f\u2e80-\ua4cf\uac00-\ud7a3\uf900-\ufaff\ufe30-\ufe4f\uff00-\uff60\uffe0-\uffe6]/.test(ch) ? 2 : 1), 0);
export const padDisplay = (s, w) => s + ' '.repeat(Math.max(0, w - displayWidth(s)));

/** 确认表：给人看，按 lang 出，每项标来源。缺省值也列出来，标「默认」。 */
export function confirmTable(x) {
  const ui = uiFor(x.lang ?? 'zh', x.ui);
  const tag = (f) => (f?.source && f.source !== 'stated' ? `  〔${ui.sources[f.source]}〕` : '') + (f?.slot === 'custom' ? `  〔${ui.untested}〕` : '');
  const id = x.identity;
  const skin = x.skin ?? { text: ui.defaultSkin[skinBand(id.age)], source: 'default' };
  const back = x.backCue ?? { text: ui.defaultBack, source: 'default' };
  const F = ui.fields;
  const rows = [
    [F.identity, fmt(ui.identityLine, { text: human(id), age: id.age, gender: ui[id.gender] ?? id.gender }), id],
    [F.face, human(x.face), x.face], [F.hair, human(x.hair), x.hair],
    ...(x.build ? [[F.build, human(x.build), x.build]] : []),
    [F.top, human(x.outfit.top), x.outfit.top], [F.bottom, human(x.outfit.bottom), x.outfit.bottom],
    [F.skin, human(skin), skin], [F.backCue, human(back), back],
    ...(x.outfit.details ?? []).map((d) => [fmt(F.detail, { x: d.slot === 'custom' ? d.id : ui.slots[d.slot] }), human(d), d]),
  ];
  const w = Math.max(...rows.map(([k]) => displayWidth(k)));
  return [fmt(ui.confirmTitle, { name: x.name, outfit: x.outfit.label ?? ui.outfitDefault }),
    ...rows.map(([k, v, f]) => `  ${padDisplay(k, w)}  ${v}${tag(f)}`)].join('\n');
}

/** 由确认过的输入建角色资产。 */
export function assetFromIntake(intake, look = DEFAULT_LOOK) {
  const x = structuredClone(intake);   // 资产不和输入共用对象，改资产不会改到输入
  look = structuredClone(look);
  const id = x.outfit.id ?? 'default';
  const layers = { identity: x.identity, face: x.face, hair: x.hair };
  for (const k of ['build', 'skin', 'backCue']) if (x[k]) layers[k] = x[k];
  return {
    name: x.name,
    ...(x.source ? { source: x.source } : {}),
    lang: x.lang ?? 'zh',                   // 确认表与报告的语言；提示词永远英文
    ...(x.ui ? { ui: x.ui } : {}),          // 非内置语言的自译文案
    layers,
    outfits: {
      [id]: {
        label: x.outfit.label ?? uiFor(x.lang ?? 'zh', x.ui).outfitDefault,
        top: x.outfit.top, bottom: x.outfit.bottom, details: x.outfit.details ?? [],
        overrides: x.outfit.overrides ?? {},
        look: { ...look },                  // 画风快照：之后项目改画风，不影响这组图
        views: {},
        upgrades: [],
      },
    },
  };
}

/* ------------------------------------------------------------------ */
/* 版本与过期                                                            */
/* ------------------------------------------------------------------ */
/*
 * 过期不存标记，每次现算：看这张图记下的「文字指纹、画风指纹、参考图版本与文件指纹」
 * 和现在是否一致。于是——
 *   重出锚点 → 其余全部过期（它们的 refs 指向旧锚点）
 *   重出大头照 → 只有挂了大头照的那几张细节过期
 *   改了文字描述 → 全部过期（锚点也是）
 * 过期只标记，不删除；要不要重出由人决定。
 */
export const current = (outfit, viewId) => {
  const v = outfit.views?.[viewId];
  return v ? v.versions.find((x) => x.v === v.current) ?? null : null;
};

/** 过期原因（结构化，报告按语言翻译）：{code: layers | look | ref-missing | ref-changed, view?, v?} */
export function staleCodes(asset, outfitId, viewId) {
  const outfit = asset.outfits[outfitId];
  const cur = current(outfit, viewId);
  if (!cur) return [];
  const why = [];
  const L = resolveLayers(asset, outfitId);
  if (cur.layersHash !== viewLayersHash(L, allViews(outfit)[viewId])) why.push({ code: 'layers' });
  if (cur.lookHash !== lookHash(outfit.look)) why.push({ code: 'look' });
  for (const r of cur.refs ?? []) {
    const now = current(outfit, r.view);
    if (!now) why.push({ code: 'ref-missing', view: r.view });
    else if (now.v !== r.v || now.sha256 !== r.sha256) why.push({ code: 'ref-changed', view: r.view, v: now.v });
  }
  return why;
}
const STALE_KEY = { layers: 'layers', look: 'look', 'ref-missing': 'refMissing', 'ref-changed': 'refChanged' };
export const staleText = (c, ui) => fmt(ui.stale[STALE_KEY[c.code]], c);

/** 过期原因的文字（命令行用中文；报告用 staleCodes + staleText 按语言出）。 */
export const staleReasons = (asset, outfitId, viewId, ui = uiFor('zh')) => staleCodes(asset, outfitId, viewId).map((c) => staleText(c, ui));

/** 锚点是否可以用来派生：确认过（true）或配置为自动确认（'auto'），且没过期。 */
export function anchorUsable(asset, outfitId) {
  const a = current(asset.outfits[outfitId], ANCHOR);
  if (!a) return { ok: false, why: '还没有锚点（正面全身），先出第一档' };
  if (!a.confirmed) return { ok: false, why: '锚点还没确认——看过图后运行 confirm；不想每次确认，在配置里关掉 confirmAnchor' };
  const s = staleReasons(asset, outfitId, ANCHOR);
  if (s.length) return { ok: false, why: `锚点已过期：${s.join('；')}——先重出锚点` };
  return { ok: true };
}

/**
 * 解析一张图该挂哪些参考图：永远取「当前有效」的那一版，不看它是哪个模型出的。
 * 大头照缺失或过期时退回只挂锚点，不阻塞——记录里能看出少了一张。
 */
export function resolveRefs(asset, outfitId, prompt) {
  const outfit = asset.outfits[outfitId];
  const refs = [];
  const notes = [];
  for (const rv of prompt.refs) {
    const cur = current(outfit, rv);
    if (!cur || staleReasons(asset, outfitId, rv).length) {
      if (rv === ANCHOR) throw new Error('锚点不可用');
      notes.push(`${rv} 缺失或已过期，这张只挂锚点`);
      continue;
    }
    refs.push({ view: rv, v: cur.v, sha256: cur.sha256, file: cur.file });
  }
  return { refs, notes };
}

/* ------------------------------------------------------------------ */
/* 检查门（全部代码判断）                                                 */
/* ------------------------------------------------------------------ */
// 三家视频模型（H3 / Wan / Seedance）对参考图要求的交集：单边 300–5760、宽高比 0.4–2.5、≤ 20MB
export const LIMITS = { minSide: 300, maxSide: 5760, minRatio: 0.4, maxRatio: 2.5, maxBytes: 20 * 2 ** 20, ratioTol: 0.02, white: 0.95 };

function borderWhite(img, upperOnly) {
  const { width: w, height: h, bpp, px } = img;
  const band = Math.max(2, Math.round(Math.min(w, h) * 0.02));
  let white = 0, n = 0;
  for (let y = 0; y < (upperOnly ? h / 2 : h); y++) {
    for (let x = 0; x < w; x++) {
      if (x >= band && x < w - band && y >= band && y < h - band) continue;
      const i = (y * w + x) * bpp;
      n++;
      const g = bpp < 3;
      const transparent = (bpp === 2 || bpp === 4) && px[i + bpp - 1] < 128;   // 透明的边按白算（落盘前本来也会铺白）
      if (transparent || (px[i] >= 235 && (g || (px[i + 1] >= 235 && px[i + 2] >= 235)))) white++;
    }
  }
  return white / n;
}

/**
 * @returns [{id, label, ok, detail}] —— 跳过的门也列出来并写明原因，不静默。
 */
export function gates(buf, ratio, kind) {
  const out = [];
  const add = (id, label, ok, detail = '') => out.push({ id, label, ok, detail });
  if (!isPng(buf)) {
    add('format', '文件是 PNG', false, '不是 PNG，尺寸与背景无法检查');
    return out;
  }
  const { width: w, height: h } = pngInfo(buf);
  const r = w / h;
  add('size', `单边 ${LIMITS.minSide}–${LIMITS.maxSide} 像素`, Math.min(w, h) >= LIMITS.minSide && Math.max(w, h) <= LIMITS.maxSide, `${w}×${h}`);
  add('ratio-range', `宽高比 ${LIMITS.minRatio}–${LIMITS.maxRatio}`, r >= LIMITS.minRatio && r <= LIMITS.maxRatio, r.toFixed(3));
  add('ratio-target', `比例为 ${ratio}`, Math.abs(r - RATIOS[ratio]) <= LIMITS.ratioTol, r.toFixed(3));
  add('bytes', '文件 ≤ 20MB', buf.length <= LIMITS.maxBytes, `${(buf.length / 2 ** 20).toFixed(1)}MB`);
  if (kind === 'detail') {
    add('white', '背景够白', true, '细节图画面多是衣物，不查背景（跳过）');
  } else {
    const img = decode(buf);
    if (!img) add('white', '背景够白', true, '非 8 位 PNG，无法解像素（跳过）');
    else {
      const wr = borderWhite(img, kind === 'face');
      add('white', kind === 'face' ? '上边与两侧上半够白' : '四边够白', wr >= LIMITS.white, `${Math.round(wr * 100)}% 近白`);
    }
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* 落一版图（真实出图与自测共用）                                           */
/* ------------------------------------------------------------------ */
/**
 * 把一张新出的图记成这个视图的新版本：打 iTXt 标识、算指纹、跑门、记下参考图的版本与指纹。
 * 旧版本不删——重出只是多一版，要退回就把 current 改回去。
 * @param confirmMode 仅锚点：'wait'（等人确认）| 'auto'（配置为不确认）
 * @returns {{version, buf}} buf 是打过标识、应写盘的字节
 */
export function recordVersion(asset, oid, view, { buf, model, seed = null, prompt, refs = [], notes = [], confirmMode = 'wait', now = new Date() }) {
  const outfit = asset.outfits[oid];
  const spec = allViews(outfit)[view];
  const slot = (outfit.views[view] ??= { current: 0, versions: [] });
  const v = Math.max(0, ...slot.versions.map((x) => x.v)) + 1;
  const id = `${asset.name}/${oid}/${view}/v${v}`;
  const out = isPng(buf) ? withText(buf, { 'shuohao:id': id, 'shuohao:model': model, 'shuohao:refs': refs.map((r) => `${r.view}/v${r.v}`).join(',') }) : buf;
  const g = gates(out, spec.ratio, spec.kind);
  const version = {
    v, id, file: `${oid}/${view}.v${v}.png`, sha256: sha256(out), model, seed,
    prompt: prompt.text, negative: prompt.negative,
    refs: refs.map(({ view: rv, v: rvv, sha256: rs }) => ({ view: rv, v: rvv, sha256: rs })), notes,
    layersHash: viewLayersHash(resolveLayers(asset, oid), spec), lookHash: lookHash(outfit.look),
    gates: g, createdAt: now.toISOString(),
    // 配置为自动确认时，也只放行过了门的锚点：没过门的锚点要人看过再 confirm，或者重出
    ...(view === ANCHOR ? { confirmed: confirmMode === 'auto' && g.every((x) => x.ok) ? 'auto' : false } : {}),
  };
  slot.versions.push(version);
  slot.current = v;
  return { version, buf: out };
}
