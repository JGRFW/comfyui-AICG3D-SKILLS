// 给人看的文案：报告界面与确认表。内置中文、英文、日文；其他语言由模型照 ui-template 现场翻一份，
// 写进 intake 的 ui 字段（或 render --ui 传文件）。命令行的提示信息是给 agent 看的，不在这里。
//
// 模板里的 {n} {v} {name} 之类占位符由 fmt() 填。

export const UI = {
  zh: {
    htmlLang: 'zh-CN',
    title: '角色参考图',
    lead: '一张确认过的正面全身照（锚点）为根，其余每张都只参考它。',
    staleLegend: '红框 = 已过期：锚点、参考图或文字描述变了，这张要重出。鼠标移到图上可以看原因。',
    layout: '版面', without: '无细节图', with: '有细节图',
    views: {
      'front-full': '正面全身（锚点）', 'face-front': '正脸大头照', 'side-full': '侧面 90°（面朝右）',
      'back-full': '背面', 'face-45': '45° 大头照（面朝左）',
    },
    slots: { hair: '头发 / 发饰', neck: '领口', sleeve: '袖口', feet: '鞋' },
    fields: {
      identity: '身份', face: '脸型五官', hair: '发型', build: '身形', top: '上装', bottom: '下装',
      skin: '皮肤', backCue: '背面', detail: '细节 · {x}',
    },
    sources: { stated: '原话', inferred: '推断', default: '默认' }, untested: '未实测',
    identityLine: '{text}（{age} 岁 · {gender}）', female: '女', male: '男',
    outfitDefault: '常态',
    confirmTitle: '{name} · {outfit} · 待确认',
    descSummary: '角色描述（确认表）',
    notGenerated: '未生成 · 第 {n} 档',
    noAnchor: '还没有锚点', anchorConfirmed: '锚点已确认', anchorAuto: '锚点未经人工确认（配置为自动）', anchorPending: '锚点待确认',
    tier1Only: '第一档 · 只有锚点', tierN: '第 {n} 档', look: '画风：{x}',
    looks: { 'realistic-photo': '写实照片', anime: '动漫' },
    face45Extra: '45° 大头照（第四档，不进版面）',
    mixed: '这组图混用了 {x}：一致性来自同一张锚点，可以混用，请多看一眼质感是否衔接。',
    allViews: '全部视图',
    th: { view: '视图', tier: '档', version: '版本', model: '模型', seed: '种子', id: '标识', state: '状态' },
    stNone: '未生成', stStale: '已过期', stGate: '门未过',
    stale: { layers: '文字描述改过了', look: '画风快照变了', refMissing: '参考图 {view} 不见了', refChanged: '参考图 {view} 已换成 v{v}' },
    gates: {
      format: '文件是 PNG', size: '单边 300–5760 像素', 'ratio-range': '宽高比 0.4–2.5', 'ratio-target': '比例为 {x}',
      bytes: '文件 ≤ 20MB', whiteFull: '四边够白', whiteFace: '上边与两侧上半够白', white: '背景够白',
    },
    defaultSkin: {
      young: '年轻皮肤，鼻翼脸颊有细微毛孔，肤色自然略不匀，素颜',
      adult: '成年人的自然皮肤，可见毛孔，肤色略不匀',
      old: '上了年纪的皮肤，风吹日晒，有老年斑，皱纹顺表情肌走',
    },
    defaultBack: '从后面看到的发型、上衣与下装的背面、脚跟',
  },
  en: {
    htmlLang: 'en',
    title: 'Character references',
    lead: 'One confirmed front full-body image (the anchor) is the root; every other image references only it.',
    staleLegend: 'Red outline = stale: the anchor, a reference image or the text description changed, so this image needs regenerating. Hover over it to see why.',
    layout: 'Layout', without: 'Without details', with: 'With details',
    views: {
      'front-full': 'Front full body (anchor)', 'face-front': 'Front headshot', 'side-full': '90° profile (facing right)',
      'back-full': 'Back', 'face-45': '45° headshot (facing left)',
    },
    slots: { hair: 'Hair / accessory', neck: 'Neckline', sleeve: 'Cuff', feet: 'Shoes' },
    fields: {
      identity: 'Identity', face: 'Face', hair: 'Hair', build: 'Build', top: 'Top', bottom: 'Bottom',
      skin: 'Skin', backCue: 'Back', detail: 'Detail · {x}',
    },
    sources: { stated: 'stated', inferred: 'inferred', default: 'default' }, untested: 'untested',
    identityLine: '{text} ({age} · {gender})', female: 'female', male: 'male',
    outfitDefault: 'Everyday',
    confirmTitle: '{name} · {outfit} · to confirm',
    descSummary: 'Character description (confirmation table)',
    notGenerated: 'Not generated · tier {n}',
    noAnchor: 'No anchor yet', anchorConfirmed: 'Anchor confirmed', anchorAuto: 'Anchor not reviewed by a person (auto-confirm)', anchorPending: 'Anchor awaiting confirmation',
    tier1Only: 'Tier 1 · anchor only', tierN: 'Tier {n}', look: 'Style: {x}',
    looks: { 'realistic-photo': 'Realistic photo', anime: 'Anime' },
    face45Extra: '45° headshot (tier 4, outside the sheet)',
    mixed: 'This set mixes {x}. Consistency comes from sharing one anchor, so mixing is fine — just check the images still match in texture.',
    allViews: 'All views',
    th: { view: 'View', tier: 'Tier', version: 'Version', model: 'Model', seed: 'Seed', id: 'Label', state: 'Status' },
    stNone: 'Not generated', stStale: 'Stale', stGate: 'Failed checks',
    stale: { layers: 'text description changed', look: 'style snapshot changed', refMissing: 'reference {view} is missing', refChanged: 'reference {view} is now v{v}' },
    gates: {
      format: 'File is a PNG', size: 'Each side 300–5760 px', 'ratio-range': 'Aspect ratio 0.4–2.5', 'ratio-target': 'Ratio is {x}',
      bytes: 'File ≤ 20 MB', whiteFull: 'All four edges white', whiteFace: 'Top and upper sides white', white: 'Background white',
    },
    defaultSkin: {
      young: 'Young skin with faint pores on the nose and cheeks and a slightly uneven natural tone, no makeup',
      adult: 'Natural adult skin with visible pores and a slightly uneven tone',
      old: 'Aged, weathered skin with visible pores, age spots and wrinkles that follow the expression lines',
    },
    defaultBack: 'The hair seen from behind, the back of the top and bottom, and the heels',
  },
  ja: {
    htmlLang: 'ja',
    title: 'キャラクター参照画像',
    lead: '確認済みの正面全身画像（アンカー）を起点に、他の画像はすべてそれだけを参照します。',
    staleLegend: '赤枠 = 期限切れ：アンカー・参照画像・テキスト記述が変更されたため、作り直しが必要です。画像にカーソルを合わせると理由が表示されます。',
    layout: 'レイアウト', without: 'ディテールなし', with: 'ディテールあり',
    views: {
      'front-full': '正面全身（アンカー）', 'face-front': '正面バストアップ', 'side-full': '真横 90°（右向き）',
      'back-full': '背面', 'face-45': '45° バストアップ（左向き）',
    },
    slots: { hair: '髪 / 髪飾り', neck: '襟元', sleeve: '袖口', feet: '靴' },
    fields: {
      identity: '人物', face: '顔立ち', hair: '髪型', build: '体格', top: 'トップス', bottom: 'ボトムス',
      skin: '肌', backCue: '背面', detail: 'ディテール · {x}',
    },
    sources: { stated: '原文', inferred: '推定', default: '既定' }, untested: '未検証',
    identityLine: '{text}（{age} 歳 · {gender}）', female: '女性', male: '男性',
    outfitDefault: '普段着',
    confirmTitle: '{name} · {outfit} · 確認待ち',
    descSummary: 'キャラクター記述（確認表）',
    notGenerated: '未生成 · 第 {n} 段階',
    noAnchor: 'アンカー未生成', anchorConfirmed: 'アンカー確認済み', anchorAuto: 'アンカーは人の確認なし（自動確認の設定）', anchorPending: 'アンカー確認待ち',
    tier1Only: '第 1 段階 · アンカーのみ', tierN: '第 {n} 段階', look: '画風：{x}',
    looks: { 'realistic-photo': '写実写真', anime: 'アニメ' },
    face45Extra: '45° バストアップ（第 4 段階、シート外）',
    mixed: 'このセットは {x} を混用しています。一貫性は同じアンカーから来るので混用は可能ですが、質感がつながっているか確認してください。',
    allViews: '全ビュー',
    th: { view: 'ビュー', tier: '段階', version: '版', model: 'モデル', seed: 'シード', id: '識別子', state: '状態' },
    stNone: '未生成', stStale: '期限切れ', stGate: 'チェック不合格',
    stale: { layers: 'テキスト記述が変更された', look: '画風スナップショットが変わった', refMissing: '参照画像 {view} がない', refChanged: '参照画像 {view} が v{v} に更新された' },
    gates: {
      format: 'PNG ファイル', size: '各辺 300–5760 px', 'ratio-range': 'アスペクト比 0.4–2.5', 'ratio-target': '比率 {x}',
      bytes: 'ファイル ≤ 20MB', whiteFull: '四辺が白い', whiteFace: '上辺と両側上半分が白い', white: '背景が白い',
    },
    defaultSkin: {
      young: '若い肌、小鼻と頬にかすかな毛穴、自然でわずかにむらのある肌色、すっぴん',
      adult: '大人の自然な肌、毛穴が見え、肌色にわずかなむら',
      old: '年を重ねた日焼けした肌、毛穴、シミ、表情に沿ったしわ',
    },
    defaultBack: '後ろから見た髪型、トップスとボトムスの背面、かかと',
  },
};

export const BUILTIN = Object.keys(UI);
export const LANG_RE = /^[a-z]{2,3}(-[A-Za-z0-9]+)*$/;

/** 把 base 的每个叶子键列出来（a.b.c），用来检查自译的 ui 是否齐全。 */
function leaves(o, pre = '') {
  return Object.entries(o).flatMap(([k, v]) => (v && typeof v === 'object' ? leaves(v, `${pre}${k}.`) : [`${pre}${k}`]));
}
const get = (o, path) => path.split('.').reduce((x, k) => (x == null ? x : x[k]), o);

function merge(base, over) {
  const out = structuredClone(base);
  for (const [k, v] of Object.entries(over ?? {})) {
    if (k.startsWith('_')) continue;
    out[k] = v && typeof v === 'object' && !Array.isArray(v) && typeof out[k] === 'object' ? merge(out[k], v) : v;
  }
  return out;
}

/** 自译 ui 缺了哪些键（非内置语言必须齐全，否则报告半中半英）。 */
export function uiMissing(ui) {
  return leaves(UI.en).filter((p) => typeof get(ui ?? {}, p) !== 'string' || !get(ui, p).trim());
}

/**
 * 取某语言的文案。内置语言可以只覆盖一部分；其他语言必须给齐全的 ui，否则抛错。
 * @param lang 语言代码，默认 zh
 * @param custom intake / asset 里的 ui，或 render --ui 读进来的
 */
export function uiFor(lang = 'zh', custom = null) {
  if (UI[lang]) return custom ? merge(UI[lang], custom) : UI[lang];
  const miss = uiMissing(custom);
  if (miss.length) throw new Error(`语言 ${lang} 不是内置语言（${BUILTIN.join(' / ')}），要给一份完整的 ui（ui-template ${lang}）；缺 ${miss.length} 项，如 ${miss.slice(0, 4).join('、')}`);
  return merge(UI.en, custom);
}

/** 填占位符 {x}。 */
export const fmt = (s, vars = {}) => String(s).replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));

/** 给模型翻译用的骨架：英文原文 + 说明。 */
export function uiTemplate(lang) {
  return {
    _说明: [
      `把每个值翻译成 ${lang}，保留 {n} {x} {name} 这类占位符原样不动；键名不要改。`,
      '翻好后整块放进 intake.json 顶层的 ui 字段（同时写 "lang": "' + lang + '"），或存成文件用 render --ui 传入。',
    ],
    ...structuredClone(UI.en),
    htmlLang: lang,
  };
}
