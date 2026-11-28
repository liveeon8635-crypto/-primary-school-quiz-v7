"""英语 3、4、6 年级通用知识地图（每套 4 大知识域 × 4 节点 = 16 节点）、10 类题型题库与听说读写 4 大专项.

设计原则：
- 保持 4 大知识域 id 与五年级一致（phonics 语音与自然拼读、vocab 核心高频词汇、grammar 核心语法与句型、reading 情景交际与语篇），前端样式与交互组件可直接复用。
- 每个节点至少配备 6 道高质量题目，覆盖地图轻辅助题型（listen_choice / phonics_choice / word_tiles / sentence_bank / reading_choice / listen_tf）与专项强应试题型（speak_read / word_spell / sentence_fill / sentence_order）。
- 年龄段交互适配数据（Age-Tier UX Adaptation）：
  - 对所有 word_spell 和 sentence_fill 题：提供 firstLetterHint（如首字母 + 下划线词长提示 `a _ _ l e (5个字母)`）与 assistChunks（供三年级 G3 点击辅助填入的字母块或词形候选项，含正确项与 2~3 个干扰项）。
  - G3 的听力与跟读文本简洁清晰（单词或 3~6 词短句），G4 为标准句，G6 为多时态复合句。
"""
from __future__ import annotations

import hashlib
from typing import Any

LEVEL_LABELS = {"basic": "基础", "medium": "中等", "hard": "提高"}

TYPE_POINTS = {
    "listen_choice": 2,
    "listen_tf": 2,
    "phonics_choice": 2,
    "speak_read": 3,
    "word_tiles": 2,
    "word_spell": 3,
    "sentence_bank": 2,
    "sentence_fill": 3,
    "sentence_order": 3,
    "reading_choice": 2,
}

TYPE_LABELS = {
    "listen_choice": "听音选择",
    "listen_tf": "听音判断",
    "phonics_choice": "语音辨音",
    "speak_read": "开口跟读",
    "word_tiles": "拼块填空",
    "word_spell": "单词拼写",
    "sentence_bank": "选词填空",
    "sentence_fill": "句子填空",
    "sentence_order": "连词成句",
    "reading_choice": "阅读交际",
}

ENGLISH_DOMAINS: list[dict[str, Any]] = [
    {"id": "phonics", "name": "语音与自然拼读", "icon": "🔊", "color": "#a8242e"},
    {"id": "vocab", "name": "核心高频词汇", "icon": "🔤", "color": "#1e6b52"},
    {"id": "grammar", "name": "核心语法与句型", "icon": "🧩", "color": "#b4690e"},
    {"id": "reading", "name": "情景交际与语篇", "icon": "📖", "color": "#2f4f8f"},
]

# ---------------- 三年级（G3）16 个知识节点 ----------------
ENGLISH_G3_NODES: list[dict[str, Any]] = [
    # phonics
    {"key": "G3-E1-1", "name": "26个字母大小写与顺序", "domain": "phonics", "icon": "🔤", "grade": 3},
    {"key": "G3-E1-2", "name": "五个元音字母短音（a/e/i/o/u）", "domain": "phonics", "icon": "🎵", "grade": 3},
    {"key": "G3-E1-3", "name": "常见辅音起始音（b/p/d/t/g/k）", "domain": "phonics", "icon": "🗣️", "grade": 3},
    {"key": "G3-E1-4", "name": "CVC简单词自然拼读", "domain": "phonics", "icon": "✨", "grade": 3},
    # vocab
    {"key": "G3-E2-1", "name": "学习文具与缤纷色彩", "domain": "vocab", "icon": "🖍️", "grade": 3},
    {"key": "G3-E2-2", "name": "身体部位与可爱动物", "domain": "vocab", "icon": "🐼", "grade": 3},
    {"key": "G3-E2-3", "name": "数字1-20与食物水果", "domain": "vocab", "icon": "🍎", "grade": 3},
    {"key": "G3-E2-4", "name": "家庭成员与日常玩具", "domain": "vocab", "icon": "🧸", "grade": 3},
    # grammar
    {"key": "G3-E3-1", "name": "问候与自我介绍（I'm / What's your name）", "domain": "grammar", "icon": "👋", "grade": 3},
    {"key": "G3-E3-2", "name": "远近指代（This is / That is）", "domain": "grammar", "icon": "👉", "grade": 3},
    {"key": "G3-E3-3", "name": "喜好与饮食表达（I like / Have some）", "domain": "grammar", "icon": "🥛", "grade": 3},
    {"key": "G3-E3-4", "name": "数量询问与外貌特征（How many / tall / short）", "domain": "grammar", "icon": "🦒", "grade": 3},
    # reading
    {"key": "G3-E4-1", "name": "日常礼貌问候与道别", "domain": "reading", "icon": "💬", "grade": 3},
    {"key": "G3-E4-2", "name": "感谢道歉与分享食物交际", "domain": "reading", "icon": "🍰", "grade": 3},
    {"key": "G3-E4-3", "name": "询问年龄与物品数量对话", "domain": "reading", "icon": "🎂", "grade": 3},
    {"key": "G3-E4-4", "name": "启蒙绘本短篇理解", "domain": "reading", "icon": "📖", "grade": 3},
]

# ---------------- 四年级（G4）16 个知识节点 ----------------
ENGLISH_G4_NODES: list[dict[str, Any]] = [
    # phonics
    {"key": "G4-E1-1", "name": "相对开音节（a-e/i-e/o-e/u-e）", "domain": "phonics", "icon": "🎵", "grade": 4},
    {"key": "G4-E1-2", "name": "r音节字母组合（ar/er/ir/or/ur）", "domain": "phonics", "icon": "🎶", "grade": 4},
    {"key": "G4-E1-3", "name": "常见字母组合（al/le/ow）", "domain": "phonics", "icon": "🗣️", "grade": 4},
    {"key": "G4-E1-4", "name": "双音节词听音拼读", "domain": "phonics", "icon": "✨", "grade": 4},
    # vocab
    {"key": "G4-E2-1", "name": "教室设施与校园功能室", "domain": "vocab", "icon": "🏫", "grade": 4},
    {"key": "G4-E2-2", "name": "时间作息与天气冷暖", "domain": "vocab", "icon": "⛅", "grade": 4},
    {"key": "G4-E2-3", "name": "农场动物与新鲜果蔬", "domain": "vocab", "icon": "🥕", "grade": 4},
    {"key": "G4-E2-4", "name": "服装鞋帽与购物价格", "domain": "vocab", "icon": "👗", "grade": 4},
    # grammar
    {"key": "G4-E3-1", "name": "方位介词与 Where is/are", "domain": "grammar", "icon": "🧭", "grade": 4},
    {"key": "G4-E3-2", "name": "时间表达与 It's time for/to", "domain": "grammar", "icon": "⏰", "grade": 4},
    {"key": "G4-E3-3", "name": "物品归属 Whose 与名词所有格", "domain": "grammar", "icon": "🎒", "grade": 4},
    {"key": "G4-E3-4", "name": "远近复数 these/those 与 How much", "domain": "grammar", "icon": "🏷️", "grade": 4},
    # reading
    {"key": "G4-E4-1", "name": "天气询问与穿衣出行交际", "domain": "reading", "icon": "🧥", "grade": 4},
    {"key": "G4-E4-2", "name": "校园场所问路与礼貌引导", "domain": "reading", "icon": "🗺️", "grade": 4},
    {"key": "G4-E4-3", "name": "商店购物询价与试穿对话", "domain": "reading", "icon": "🛍️", "grade": 4},
    {"key": "G4-E4-4", "name": "校园与农场生活短文阅读", "domain": "reading", "icon": "📖", "grade": 4},
]

# ---------------- 六年级（G6）16 个知识节点 ----------------
ENGLISH_G6_NODES: list[dict[str, Any]] = [
    # phonics
    {"key": "G6-E1-1", "name": "规则动词过去式 -ed 尾音辨析", "domain": "phonics", "icon": "🔊", "grade": 6},
    {"key": "G6-E1-2", "name": "名词复数/三单 -s/-es 与不发音字母（kn/wr）", "domain": "phonics", "icon": "🎶", "grade": 6},
    {"key": "G6-E1-3", "name": "多音节词重音与句子升降调", "domain": "phonics", "icon": "🗣️", "grade": 6},
    {"key": "G6-E1-4", "name": "小升初高频核心词听音拼写", "domain": "phonics", "icon": "✨", "grade": 6},
    # vocab
    {"key": "G6-E2-1", "name": "交通出行方式与城市建筑", "domain": "vocab", "icon": "🚇", "grade": 6},
    {"key": "G6-E2-2", "name": "业余爱好与职业理想", "domain": "vocab", "icon": "🎨", "grade": 6},
    {"key": "G6-E2-3", "name": "情绪感受与健康就医建议", "domain": "vocab", "icon": "🩺", "grade": 6},
    {"key": "G6-E2-4", "name": "假期旅行与今昔变化对比", "domain": "vocab", "icon": "✈️", "grade": 6},
    # grammar
    {"key": "G6-E3-1", "name": "一般将来时（be going to / will）", "domain": "grammar", "icon": "🚀", "grade": 6},
    {"key": "G6-E3-2", "name": "一般过去时（规则与高频不规则动词）", "domain": "grammar", "icon": "⏳", "grade": 6},
    {"key": "G6-E3-3", "name": "形容词与副词比较级（-er / more）", "domain": "grammar", "icon": "⚖️", "grade": 6},
    {"key": "G6-E3-4", "name": "祈使句与情态动词 should / must", "domain": "grammar", "icon": "🚦", "grade": 6},
    # reading
    {"key": "G6-E4-1", "name": "问路指路与交通规则交际", "domain": "reading", "icon": "🗺️", "grade": 6},
    {"key": "G6-E4-2", "name": "周末假期计划与过去经历对话", "domain": "reading", "icon": "💬", "grade": 6},
    {"key": "G6-E4-3", "name": "跨时态长短文阅读与推理判断", "domain": "reading", "icon": "🔍", "grade": 6},
    {"key": "G6-E4-4", "name": "小升初完形选词与语境综合推断", "domain": "reading", "icon": "📝", "grade": 6},
]

GRADE_NODES_MAP: dict[int, list[dict[str, Any]]] = {
    3: ENGLISH_G3_NODES,
    4: ENGLISH_G4_NODES,
    6: ENGLISH_G6_NODES,
}


def make_audio_id(text: str, voice: str = "en-US-JennyNeural") -> str:
    raw = f"{voice}|{text.strip()}".encode("utf-8")
    return "en_" + hashlib.sha1(raw).hexdigest()[:14]


def _shuffle_deterministic(items: list[str], seed: int) -> list[str]:
    out = list(items)
    n = len(out)
    for i in range(n - 1, 0, -1):
        j = (seed * 31 + i * 17 + 7) % (i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def make_first_letter_hint(word: str) -> str:
    """生成首字母 + 下划线词长提示，例如 'apple' -> 'a _ _ _ e (5个字母)'."""
    w = str(word or "").strip()
    if not w:
        return ""
    if len(w) == 1:
        return f"{w[0]} (1个字母)"
    if len(w) <= 3:
        pattern = w[0] + " " + " ".join("_" for _ in w[1:])
        return f"{pattern} ({len(w)}个字母)"
    pattern = w[0] + " " + " ".join("_" for _ in w[1:-1]) + " " + w[-1]
    return f"{pattern} ({len(w)}个字母)"


def make_default_assist_chunks(answer: str, qtype: str, seed: int = 1) -> list[str]:
    """为 word_spell 或 sentence_fill 生成候选辅助块（含正确项与 2~3 个干扰项）."""
    w = str(answer or "").strip()
    if not w:
        return []
    low = w.lower()
    distractors: list[str] = []
    if qtype == "word_spell":
        # 生成拼写形近干扰项
        if len(w) >= 3:
            swapped = w[0] + w[2] + w[1] + w[3:]
            if swapped.lower() != low:
                distractors.append(swapped)
        vowel_map = {"a": "e", "e": "i", "i": "a", "o": "u", "u": "o"}
        mutated = list(w)
        for idx in range(1, len(mutated)):
            ch = mutated[idx].lower()
            if ch in vowel_map:
                mutated[idx] = vowel_map[ch]
                break
        cand2 = "".join(mutated)
        if cand2.lower() != low and cand2 not in distractors:
            distractors.append(cand2)
        cand3 = w + ("e" if not low.endswith("e") else "s")
        if cand3.lower() != low and cand3 not in distractors:
            distractors.append(cand3)
        for fb in ("apple", "book", "cat", "dog", "pen"):
            if len(distractors) >= 3:
                break
            if fb != low and fb not in distractors:
                distractors.append(fb)
    else:
        # sentence_fill 词形候选项
        if low in ("am", "is", "are"):
            distractors = [x for x in ("am", "is", "are", "be") if x != low]
        elif low.endswith("s"):
            base = w[:-1]
            distractors = [base, base + "ing", base + "ed"]
        elif low.endswith("ed"):
            base = w[:-2]
            distractors = [base, base + "s", base + "ing"]
        else:
            distractors = [w + "s", w + "ing", w + "ed"]
    pool = [w] + distractors[:3]
    return _shuffle_deterministic(pool, seed + len(w))


def _q(
    qid: str,
    node_key: str,
    qtype: str,
    level: str,
    text: str,
    answer: str,
    explanation: str,
    *,
    grade: int,
    options: list[str] | None = None,
    correct_index: int | None = None,
    audio_text: str | None = None,
    audio_voice: str = "en-US-JennyNeural",
    hint: str = "",
    tiles: list[str] | None = None,
    word_bank: list[str] | None = None,
    accept_answers: list[str] | None = None,
    speak_target: str | None = None,
    fallback_options: list[str] | None = None,
    fallback_correct_index: int | None = None,
    passage: str | None = None,
    first_letter_hint: str | None = None,
    assist_chunks: list[str] | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": qid,
        "nodeKey": node_key,
        "grade": grade,
        "questionType": qtype,
        "typeLabel": TYPE_LABELS.get(qtype, qtype),
        "level": level,
        "levelLabel": LEVEL_LABELS.get(level, level),
        "marks": TYPE_POINTS.get(qtype, 2),
        "text": text,
        "answer": answer,
        "explanation": explanation,
    }
    if options is not None:
        item["options"] = list(options)
        item["correctIndex"] = int(correct_index or 0)
    if audio_text:
        aid = make_audio_id(audio_text, audio_voice)
        item["audioId"] = aid
        item["audioUrl"] = f"/assets/english-audio/{aid}.mp3"
        item["audioText"] = audio_text
        item["audioVoice"] = audio_voice
    if hint:
        item["hint"] = hint
    if tiles is not None:
        item["tiles"] = list(tiles)
    if word_bank is not None:
        item["wordBank"] = list(word_bank)
    if accept_answers:
        item["acceptAnswers"] = list(accept_answers)
    if speak_target:
        item["speakTarget"] = speak_target
    if fallback_options is not None:
        item["fallbackOptions"] = list(fallback_options)
        item["fallbackCorrectIndex"] = int(fallback_correct_index or 0)
    if passage:
        item["passage"] = passage
    if qtype in ("word_spell", "sentence_fill"):
        flh = first_letter_hint or make_first_letter_hint(answer)
        chunks = assist_chunks if assist_chunks is not None else make_default_assist_chunks(answer, qtype, seed=len(qid))
        item["firstLetterHint"] = flh
        item["assistChunks"] = list(chunks)
        if not item.get("hint"):
            item["hint"] = f"提示：{flh}"
    return item


def _word_tile_q(
    qid: str,
    node_key: str,
    grade: int,
    level: str,
    word: str,
    cn: str,
    extra_letters: list[str],
    explanation: str,
    seed: int = 1,
    audio_text: str | None = None,
) -> dict[str, Any]:
    letters = list(word.lower()) + [c.lower() for c in extra_letters]
    tiles = _shuffle_deterministic(letters, seed + len(word))
    masked = word[0] + " " + " ".join("_" for _ in word[1:])
    return _q(
        qid,
        node_key,
        "word_tiles",
        level,
        f"点击字母拼块，拼出表示「{cn}」的单词（提示：{masked}）：",
        word,
        explanation,
        grade=grade,
        tiles=tiles,
        hint=f"首字母 {word[0]}，共 {len(word)} 个字母",
        audio_text=audio_text,
    )


def _word_spell_q(
    qid: str,
    node_key: str,
    grade: int,
    level: str,
    word: str,
    prompt: str,
    explanation: str,
    *,
    hint: str = "",
    audio_text: str | None = None,
    first_letter_hint: str | None = None,
    assist_chunks: list[str] | None = None,
) -> dict[str, Any]:
    return _q(
        qid,
        node_key,
        "word_spell",
        level,
        prompt,
        word,
        explanation,
        grade=grade,
        hint=hint,
        audio_text=audio_text,
        first_letter_hint=first_letter_hint,
        assist_chunks=assist_chunks,
    )


def _sentence_order_q(
    qid: str,
    node_key: str,
    grade: int,
    level: str,
    chunks: list[str],
    answer: str,
    cn: str,
    explanation: str,
    seed: int = 1,
) -> dict[str, Any]:
    shuffled = _shuffle_deterministic(chunks, seed + len(chunks))
    if " ".join(shuffled).lower() == answer.lower() and len(shuffled) > 1:
        shuffled[0], shuffled[-1] = shuffled[-1], shuffled[0]
    return _q(
        qid,
        node_key,
        "sentence_order",
        level,
        f"连词成句（点击词块按顺序排列，表达「{cn}」）：",
        answer,
        explanation,
        grade=grade,
        word_bank=shuffled,
        hint="注意句首首字母与句末标点",
    )


# ==============================================================================
# 三年级（G3）题库构建（16 节点 × 6 题 = 96 题）
# 复用已生成的静态音频 audioText（如 cat, book,bike, happy 等），保证离线 MP3 100% 存在！
# ==============================================================================
def _build_g3_questions() -> dict[str, list[dict[str, Any]]]:
    bank: dict[str, list[dict[str, Any]]] = {n["key"]: [] for n in ENGLISH_G3_NODES}

    # G3-E1-1 26个字母大小写与顺序
    bank["G3-E1-1"] = [
        _q("g3-e11-1", "G3-E1-1", "phonics_choice", "basic",
           "按照 26 个英文字母表顺序，字母 Dd 后面的一个字母是：", "Ee",
           "字母顺序为 Aa Bb Cc Dd Ee Ff Gg，Dd 后面是 Ee。",
           grade=3, options=["Cc", "Ee", "Ff", "Gg"], correct_index=1),
        _q("g3-e11-2", "G3-E1-1", "phonics_choice", "basic",
           "大写字母 Q 对应的小写字母是哪一个？", "q",
           "注意区分小写字母 p、q、b、d：Q 的小写是 q。",
           grade=3, options=["p", "q", "b", "d"], correct_index=1),
        _q("g3-e11-3", "G3-E1-1", "listen_choice", "basic",
           "听录音，选出你听到的单词的首字母：", "b",
           "录音单词是 book，以字母 b 开头。",
           grade=3, options=["b", "d", "p", "q"], correct_index=0, audio_text="book"),
        _q("g3-e11-4", "G3-E1-1", "sentence_bank", "medium",
           "按字母表顺序点选缺失的字母：Hh -> Ii -> ____ -> Kk", "Jj",
           "H I J K 连续排列，中间缺少 Jj。",
           grade=3, word_bank=["Gg", "Jj", "Ll", "Mm"]),
        _word_tile_q("g3-e11-5", "G3-E1-1", 3, "medium", "book", "书本", ["d", "p"],
                     "book 由 b-o-o-k 四个字母组成，意为“书本”。", seed=311, audio_text="book"),
        _q("g3-e11-6", "G3-E1-1", "speak_read", "medium",
           "听示范并跟读单词：", "book",
           "清晰读出单词 book /bʊk/。",
           grade=3, audio_text="book", speak_target="book",
           fallback_options=["book 首字母是 b", "book 首字母是 d", "book 首字母是 p", "book 首字母是 k"],
           fallback_correct_index=0),
    ]

    # G3-E1-2 五个元音字母短音（a/e/i/o/u）
    bank["G3-E1-2"] = [
        _q("g3-e12-1", "G3-E1-2", "phonics_choice", "basic",
           "下列哪个字母属于英语中的 5 个元音字母（a, e, i, o, u）？", "Uu",
           "5 个元音字母是 Aa, Ee, Ii, Oo, Uu。",
           grade=3, options=["Bb", "Kk", "Uu", "Tt"], correct_index=2),
        _q("g3-e12-2", "G3-E1-2", "phonics_choice", "basic",
           "选出单词 c[a]t 和 b[a]g 中元音字母 a 的共同短音特点：", "都发短元音 /æ/（大口音）",
           "cat 和 bag 都是闭音节 CVC 单词，a 发短音 /æ/。",
           grade=3, options=["都发短元音 /æ/（大口音）", "都发 /iː/", "都发 /uː/", "都不发音"], correct_index=0,
           audio_text="cake, name, cat, lake"),
        _q("g3-e12-3", "G3-E1-2", "listen_choice", "basic",
           "听录音，选出录音中最后一个闭音节短音词：", "cup",
           "录音依次为 cute, use, tube, cup，最后一个词是含短音 u /ʌ/ 的 cup。",
           grade=3, options=["cute", "use", "tube", "cup"], correct_index=3,
           audio_text="cute, use, tube, cup"),
        _q("g3-e12-4", "G3-E1-2", "phonics_choice", "medium",
           "选出划线元音发音与 d[o]g 相同的一项：", "b[o]x",
           "dog 和 box 中的字母 o 都发短音 /ɒ/，而 nose / home 发长音 /əʊ/。",
           grade=3, options=["n[o]se", "h[o]me", "b[o]x", "c[u]te"], correct_index=2,
           audio_text="nose"),
        _word_spell_q("g3-e12-5", "G3-E1-2", 3, "medium", "cat",
                      "根据中文与辅助字母块，拼写表示「小猫」的单词（c _ t）：",
                      "cat 含短元音 a，拼写为 c-a-t。",
                      first_letter_hint="c _ t (3个字母)",
                      assist_chunks=["cat", "cut", "cot", "cap"]),
        _q("g3-e12-6", "G3-E1-2", "speak_read", "medium",
           "听录音示范并朗读这四个对比词：", "cute, use, tube, cup",
           "注意区分开音节 u 与最后一个闭音节短音 cup。",
           grade=3, audio_text="cute, use, tube, cup", speak_target="cute use tube cup",
           fallback_options=["cup 中 u 发短音 /ʌ/", "cup 与 cute 元音相同", "use 中 u 发 /æ/", "tube 中 u 不发音"],
           fallback_correct_index=0),
    ]

    # G3-E1-3 常见辅音起始音（b/p/d/t/g/k）
    bank["G3-E1-3"] = [
        _q("g3-e13-1", "G3-E1-3", "listen_choice", "basic",
           "听录音，选出你听到的以 b 开头的单词：", "bike",
           "bike 以辅音 b 开头，起始音为 /b/。",
           grade=3, options=["bike", "kite", "dog", "pen"], correct_index=0, audio_text="bike"),
        _q("g3-e13-2", "G3-E1-3", "phonics_choice", "basic",
           "单词 [p]ig 和 [p]en 的起始辅音都是：", "/p/",
           "pig 和 pen 都以字母 p 开头，发清辅音 /p/。",
           grade=3, options=["/b/", "/p/", "/d/", "/t/"], correct_index=1),
        _q("g3-e13-3", "G3-E1-3", "phonics_choice", "medium",
           "选出起始辅音与其他三个不同的单词：", "duck",
           "bag / book / bike 都以 /b/ 开头，duck 以 /d/ 开头。",
           grade=3, options=["bag", "book", "duck", "bike"], correct_index=2),
        _word_tile_q("g3-e13-4", "G3-E1-3", 3, "medium", "clock", "时钟", ["b", "t"],
                     "clock 以辅音 c 开头，发 /k/ 音。", seed=313, audio_text="clock"),
        _word_spell_q("g3-e13-5", "G3-E1-3", 3, "hard", "dog",
                      "点击辅助块或用键盘拼写表示「小狗」的单词（d _ g）：",
                      "dog 起始音为 /d/，结尾音为 /g/，拼写 d-o-g。",
                      first_letter_hint="d _ g (3个字母)",
                      assist_chunks=["dog", "dig", "bag", "pig"]),
        _q("g3-e13-6", "G3-E1-3", "speak_read", "medium",
           "听示范并跟读单词：", "clock",
           "注意 clock 开头的清辅音 /kl/ 与尾音 /k/。",
           grade=3, audio_text="clock", speak_target="clock",
           fallback_options=["clock 开头音包含 /k/", "clock 开头音是 /b/", "clock 开头音是 /d/", "clock 开头音是 /p/"],
           fallback_correct_index=0),
    ]

    # G3-E1-4 CVC简单词自然拼读
    bank["G3-E1-4"] = [
        _q("g3-e14-1", "G3-E1-4", "phonics_choice", "basic",
           "用自然拼读法把 /b/ + /æ/ + /g/ 拼在一起，得到的单词是：", "bag",
           "b(/b/) + a(/æ/) + g(/g/) 拼成 bag（书包）。",
           grade=3, options=["bag", "big", "bug", "leg"], correct_index=0),
        _q("g3-e14-2", "G3-E1-4", "phonics_choice", "basic",
           "CVC 单词 p-i-g 中间的元音字母是：", "i",
           "p-i-g 是辅音-元音-辅音（CVC）结构，中间元音是 i。",
           grade=3, options=["p", "i", "g", "a"], correct_index=1),
        _q("g3-e14-3", "G3-E1-4", "listen_choice", "medium",
           "听录音，选出包含闭音节 CVC 单词 c-a-t 的那一组录音中的短音词：", "cat",
           "c-a-t 拼读为 /kæt/（猫）。",
           grade=3, options=["cake", "name", "cat", "lake"], correct_index=2,
           audio_text="cake, name, cat, lake"),
        _word_tile_q("g3-e14-4", "G3-E1-4", 3, "medium", "pen", "钢笔", ["a", "i"],
                     "p-e-n 拼读为 pen（钢笔）。", seed=314, audio_text="tea, eat, bread, read"),
        _word_spell_q("g3-e14-5", "G3-E1-4", 3, "hard", "red",
                      "根据自然拼读规则，拼写表示「红色」的 CVC 单词（r _ d）：",
                      "r(/r/) + e(/e/) + d(/d/) -> red（红色）。",
                      first_letter_hint="r _ d (3个字母)",
                      assist_chunks=["red", "rad", "rid", "bed"]),
        _q("g3-e14-6", "G3-E1-4", "speak_read", "medium",
           "听示范并跟读单词：", "happy",
           "happy 开头 h-a-p 含短元音 /æ/，大声跟读 happy。",
           grade=3, audio_text="happy", speak_target="happy",
           fallback_options=["happy 含有短音 /æ/", "happy 与 bike 元音相同", "happy 只有 2 个字母", "happy 首字母是 p"],
           fallback_correct_index=0),
    ]

    # G3-E2-1 学习文具与缤纷色彩
    bank["G3-E2-1"] = [
        _q("g3-e21-1", "G3-E2-1", "listen_choice", "basic",
           "听录音，选出你听到的学习用品：", "书本 (book)",
           "book 意为“书本”。",
           grade=3, options=["书本 (book)", "尺子 (ruler)", "铅笔 (pencil)", "橡皮 (eraser)"],
           correct_index=0, audio_text="book"),
        _q("g3-e21-2", "G3-E2-1", "reading_choice", "basic",
           "晴朗天空和大海通常是什么颜色？", "blue（蓝色）",
           "blue 表示蓝色，red 是红色，yellow 是黄色，green 是绿色。",
           grade=3, options=["red（红色）", "blue（蓝色）", "yellow（黄色）", "black（黑色）"], correct_index=1),
        _word_tile_q("g3-e21-3", "G3-E2-1", 3, "basic", "ruler", "尺子", ["a", "n"],
                     "ruler 意为“尺子”，拼写 r-u-l-e-r。", seed=321),
        _q("g3-e21-4", "G3-E2-1", "sentence_bank", "medium",
           "选词填空：I have a new ____. I use it to write.", "pencil",
           "用来写字（write）的文具是铅笔（pencil）。",
           grade=3, word_bank=["pencil", "apple", "tiger", "milk"]),
        _word_spell_q("g3-e21-5", "G3-E2-1", 3, "hard", "green",
                      "根据中文提示，点选或拼写表示「绿色」的单词（g _ _ _ n）：",
                      "green 意为“绿色”，中间有两个 e。",
                      first_letter_hint="g _ _ _ n (5个字母)",
                      assist_chunks=["green", "gran", "grean", "blue"]),
        _q("g3-e21-6", "G3-E2-1", "listen_tf", "medium",
           "听录音判断：录音中提到的黄牛是黄色（yellow）的。", "T",
           "录音：I see a yellow cow near the house. 提到了 a yellow cow（黄色的牛）。",
           grade=3, options=["正确 (T)", "错误 (F)"], correct_index=0,
           audio_text="I see a yellow cow near the house."),
    ]

    # G3-E2-2 身体部位与可爱动物
    bank["G3-E2-2"] = [
        _q("g3-e22-1", "G3-E2-2", "listen_choice", "basic",
           "听录音，选出与录音单词对应的身体部位：", "鼻子 (nose)",
           "nose 意为“鼻子”。",
           grade=3, options=["眼睛 (eye)", "耳朵 (ear)", "鼻子 (nose)", "嘴巴 (mouth)"],
           correct_index=2, audio_text="nose"),
        _q("g3-e22-2", "G3-E2-2", "listen_choice", "basic",
           "听录音，选出你听到的农场动物：", "绵羊 (sheep)",
           "sheep 意为“绵羊”。",
           grade=3, options=["绵羊 (sheep)", "熊猫 (panda)", "猴子 (monkey)", "老虎 (tiger)"],
           correct_index=0, audio_text="sheep"),
        _word_tile_q("g3-e22-3", "G3-E2-2", 3, "basic", "panda", "大熊猫", ["e", "o"],
                     "panda 意为“大熊猫”，拼写 p-a-n-d-a。", seed=322),
        _q("g3-e22-4", "G3-E2-2", "sentence_bank", "medium",
           "选词填空：Look at the elephant! It has two big ____.", "ears",
           "大象有两只大耳朵（ears）。",
           grade=3, word_bank=["ears", "books", "pens", "cakes"]),
        _word_spell_q("g3-e22-5", "G3-E2-2", 3, "hard", "nose",
                      "根据录音与中文「鼻子」，拼写单词（n _ _ e）：",
                      "nose 拼写为 n-o-s-e。",
                      audio_text="nose",
                      first_letter_hint="n _ _ e (4个字母)",
                      assist_chunks=["nose", "noze", "nuse", "face"]),
        _q("g3-e22-6", "G3-E2-2", "reading_choice", "medium",
           "Look at the bird! It has two small eyes and it can fly. What animal is it?", "A bird（小鸟）",
           "题目描述有两只小眼睛且会飞（can fly），是小鸟（A bird）。",
           grade=3, options=["A fish（鱼）", "A bird（小鸟）", "A pig（猪）", "A dog（狗）"], correct_index=1),
    ]

    # G3-E2-3 数字1-20与食物水果
    bank["G3-E2-3"] = [
        _q("g3-e23-1", "G3-E2-3", "reading_choice", "basic",
           "算一算：three + four = ?", "seven",
           "3 (three) + 4 (four) = 7 (seven)。",
           grade=3, options=["five", "six", "seven", "eight"], correct_index=2),
        _q("g3-e23-2", "G3-E2-3", "listen_choice", "basic",
           "听录音，选出你听到的餐食单词：", "三明治 (sandwich)",
           "录音单词是 sandwich（三明治）。",
           grade=3, options=["苹果 (apple)", "牛奶 (milk)", "三明治 (sandwich)", "蛋糕 (cake)"],
           correct_index=2, audio_text="sandwich"),
        _word_tile_q("g3-e23-3", "G3-E2-3", 3, "basic", "apple", "苹果", ["o", "i"],
                     "apple 意为“苹果”，拼写 a-p-p-l-e。", seed=323),
        _q("g3-e23-4", "G3-E2-3", "sentence_bank", "medium",
           "选词填空：I'm hungry. I'd like some ____ and eggs.", "bread",
           "肚子饿了想吃面包（bread）和鸡蛋。",
           grade=3, word_bank=["bread", "ruler", "crayon", "chair"]),
        _word_spell_q("g3-e23-5", "G3-E2-3", 3, "hard", "ten",
                      "根据中文提示，拼写数字「十（10）」的英文单词（t _ n）：",
                      "数字 10 的英文是 ten。",
                      first_letter_hint="t _ n (3个字母)",
                      assist_chunks=["ten", "tin", "tan", "two"]),
        _q("g3-e23-6", "G3-E2-3", "listen_tf", "medium",
           "听录音判断：录音中提到午餐有三条新鲜的鱼（three fresh fish）。", "T",
           "录音：She has three fresh fish for lunch. 与描述一致。",
           grade=3, options=["正确 (T)", "错误 (F)"], correct_index=0,
           audio_text="She has three fresh fish for lunch."),
    ]

    # G3-E2-4 家庭成员与日常玩具
    bank["G3-E2-4"] = [
        _q("g3-e24-1", "G3-E2-4", "reading_choice", "basic",
           "“爸爸的妈妈”在英语里应该怎么称呼？", "grandma / grandmother",
           "奶奶或外婆用 grandma 或 grandmother 表示。",
           grade=3, options=["sister", "brother", "grandma / grandmother", "uncle"], correct_index=2),
        _q("g3-e24-2", "G3-E2-4", "listen_choice", "basic",
           "听录音，选出你听到的日常骑行玩具/工具：", "自行车 (bike)",
           "录音单词为 bike（自行车）。",
           grade=3, options=["风筝 (kite)", "皮球 (ball)", "玩偶 (doll)", "自行车 (bike)"],
           correct_index=3, audio_text="bike"),
        _word_tile_q("g3-e24-3", "G3-E2-4", 3, "basic", "kite", "风筝", ["a", "o"],
                     "kite 意为“风筝”，拼写 k-i-t-e。", seed=324),
        _q("g3-e24-4", "G3-E2-4", "sentence_bank", "medium",
           "选词填空：This woman is my ____. She loves me very much.", "mother",
           "This woman（这位女士）对应家庭成员 mother（妈妈）。",
           grade=3, word_bank=["mother", "father", "brother", "grandpa"]),
        _word_spell_q("g3-e24-5", "G3-E2-4", 3, "hard", "ball",
                      "点选辅助块或拼写表示「皮球」的玩具单词（b _ _ l）：",
                      "ball 意为“球”，拼写 b-a-l-l。",
                      first_letter_hint="b _ _ l (4个字母)",
                      assist_chunks=["ball", "bell", "bill", "doll"]),
        _q("g3-e24-6", "G3-E2-4", "listen_tf", "medium",
           "听录音判断：录音中的小宝宝在时钟旁边玩耍。", "T",
           "录音：The funny baby plays by the clock. 与描述完全一致。",
           grade=3, options=["正确 (T)", "错误 (F)"], correct_index=0,
           audio_text="The funny baby plays by the clock."),
    ]

    # G3-E3-1 问候与自我介绍（I'm / What's your name）
    bank["G3-E3-1"] = [
        _q("g3-e31-1", "G3-E3-1", "sentence_bank", "basic",
           "选词填空：Hello! I ____ Sarah.", "am",
           "第一人称 I 后面搭配 be 动词 am（缩写为 I'm）。",
           grade=3, word_bank=["am", "is", "are", "be"]),
        _q("g3-e31-2", "G3-E3-1", "reading_choice", "basic",
           "— What's your name?  — ____", "My name's Mike.",
           "询问对方姓名 What's your name? 应回答 My name's... 或 I'm...",
           grade=3, options=["My name's Mike.", "I'm fine, thank you.", "It's a dog.", "Goodbye!"], correct_index=0),
        _q("g3-e31-3", "G3-E3-1", "sentence_bank", "medium",
           "选词填空：What ____ your name?", "is",
           "your name 是单数，疑问句用 What is your name?",
           grade=3, word_bank=["is", "am", "are", "do"]),
        _q("g3-e31-4", "G3-E3-1", "sentence_fill", "medium",
           "根据提示填入合适的物主代词：Hello! ____ (我的) name is Chen Jie.", "My",
           "表示“我的名字”用 My name，注意句首大写。",
           grade=3, first_letter_hint="M _ (2个字母)", assist_chunks=["My", "I", "Me", "Your"]),
        _sentence_order_q("g3-e31-5", "G3-E3-1", 3, "hard",
                          ["What", "is", "your", "name?"],
                          "What is your name?",
                          "你叫什么名字？",
                          "询问姓名的基本句型：What is your name?", seed=331),
        _q("g3-e31-6", "G3-E3-1", "listen_choice", "medium",
           "听录音，录音中自我介绍的男孩名字叫什么？", "Jack",
           "录音第一句：Hi, I am Jack.",
           grade=3, options=["Tom", "Jack", "Mike", "Wu Binbin"], correct_index=1,
           audio_text="Hi, I am Jack. On the weekend, I love drawing cartoons and playing football."),
    ]

    # G3-E3-2 远近指代（This is / That is）
    bank["G3-E3-2"] = [
        _q("g3-e32-1", "G3-E3-2", "sentence_bank", "basic",
           "选词填空（指着近处的铅笔）：____ is my pencil.", "This",
           "指代近处的单数物品用 This is...（这是……）。",
           grade=3, word_bank=["This", "These", "Are", "We"]),
        _q("g3-e32-2", "G3-E3-2", "reading_choice", "basic",
           "— What's that over there?  — ____ a cute panda.", "It's",
           "回答 What's this / that? 时，统一用 It's a/an... 作答，不重复 this/that。",
           grade=3, options=["This", "That", "It's", "They're"], correct_index=2),
        _q("g3-e32-3", "G3-E3-2", "sentence_bank", "medium",
           "选词填空（指着远处树上的小鸟）：Look! ____ is a bird in the tree.", "That",
           "指代远处的单数人或物用 That is...（那是……）。",
           grade=3, word_bank=["That", "Those", "Am", "They"]),
        _q("g3-e32-4", "G3-E3-2", "sentence_fill", "medium",
           "填入正确的 be 动词：This ____ my new classroom.", "is",
           "This 指代单数，后面接 is。",
           grade=3, first_letter_hint="i _ (2个字母)", assist_chunks=["is", "am", "are", "be"]),
        _sentence_order_q("g3-e32-5", "G3-E3-2", 3, "hard",
                          ["This", "is", "my", "friend."],
                          "This is my friend.",
                          "这是我的朋友。",
                          "介绍身边人的标准句型：This is my friend.", seed=332),
        _q("g3-e32-6", "G3-E3-2", "listen_choice", "basic",
           "听录音，选出你听到的指示代词：", "this",
           "录音依次朗读 three, thin, this, math，其中包含指示代词 this。",
           grade=3, options=["this", "those", "they", "there"], correct_index=0,
           audio_text="three, thin, this, math"),
    ]

    # G3-E3-3 喜好与饮食表达（I like / Have some）
    bank["G3-E3-3"] = [
        _q("g3-e33-1", "G3-E3-3", "sentence_bank", "basic",
           "选词填空：I ____ apples and bananas.", "like",
           "表达“我喜欢某物”用 I like + 复数名词/不可数名词。",
           grade=3, word_bank=["like", "likes", "am", "is"]),
        _q("g3-e33-2", "G3-E3-3", "reading_choice", "basic",
           "朋友来家里做客，你想请他喝些牛奶，可以说：", "Have some milk, please.",
           "Have some... 表示热情邀请对方吃/喝某物。",
           grade=3, options=["Have some milk, please.", "I don't like milk.", "Where is the milk?", "How old are you?"],
           correct_index=0),
        _q("g3-e33-3", "G3-E3-3", "reading_choice", "medium",
           "— Do you like pears?  — ____", "Yes, I do.",
           "Do you like...? 的肯定回答是 Yes, I do.，否定回答是 No, I don't.",
           grade=3, options=["Yes, I am.", "Yes, I do.", "No, I can't.", "It's a pear."], correct_index=1),
        _q("g3-e33-4", "G3-E3-3", "sentence_fill", "medium",
           "补全句子：Have ____ (一些) bread and juice, please.", "some",
           "Have some + 食物/饮品，表示“吃/喝一些……吧”。",
           grade=3, first_letter_hint="s _ _ e (4个字母)", assist_chunks=["some", "same", "come", "one"]),
        _sentence_order_q("g3-e33-5", "G3-E3-3", 3, "hard",
                          ["I", "like", "orange", "juice."],
                          "I like orange juice.",
                          "我喜欢橙汁。",
                          "主语 I + 谓语 like + 宾语 orange juice.", seed=333),
        _q("g3-e33-6", "G3-E3-3", "listen_choice", "medium",
           "听录音，选出说话人最喜欢喝的饮品：", "orange juice（橙汁）",
           "录音：My favourite drink is orange juice.",
           grade=3, options=["milk（牛奶）", "water（水）", "orange juice（橙汁）", "tea（茶）"],
           correct_index=2, audio_text="My favourite drink is orange juice."),
    ]

    # G3-E3-4 数量询问与外貌特征（How many / tall / short）
    bank["G3-E3-4"] = [
        _q("g3-e34-1", "G3-E3-4", "sentence_bank", "basic",
           "选词填空：Look at the giraffe! It is so ____.", "tall",
           "长颈鹿（giraffe）非常高（tall）。",
           grade=3, word_bank=["tall", "short", "small", "thin"]),
        _q("g3-e34-2", "G3-E3-4", "reading_choice", "basic",
           "— How many kites do you see?  — ____", "I see twelve.",
           "How many...? 询问数量，回答应包含具体数字（I see twelve.）。",
           grade=3, options=["It's red.", "I see twelve.", "Yes, I do.", "My name's Lily."], correct_index=1),
        _q("g3-e34-3", "G3-E3-4", "sentence_bank", "medium",
           "选词填空：How ____ crayons do you have?", "many",
           "crayons 是可数名词复数，询问“多少支”用 How many。",
           grade=3, word_bank=["many", "old", "nice", "fine"]),
        _q("g3-e34-4", "G3-E3-4", "sentence_fill", "medium",
           "根据反义词提示填空：The father is tall, and the baby is ____ (矮的).", "short",
           "tall（高的）对应反义词 short（矮的/短的）。",
           grade=3, first_letter_hint="s _ _ _ t (5个字母)", assist_chunks=["short", "shirt", "small", "long"]),
        _sentence_order_q("g3-e34-5", "G3-E3-4", 3, "hard",
                          ["It", "has", "a", "long", "nose."],
                          "It has a long nose.",
                          "它有一个长鼻子。",
                          "描述动物外貌特征：It has a + 形容词 + 身体部位.", seed=334),
        _q("g3-e34-6", "G3-E3-4", "listen_choice", "medium",
           "听录音，录音中提到的教室里有多少张课桌（desks）？", "Twenty (20)",
           "录音：Look at our classroom. There is one big whiteboard and twenty desks inside.",
           grade=3, options=["One (1)", "Ten (10)", "Twelve (12)", "Twenty (20)"],
           correct_index=3,
           audio_text="Look at our classroom. There is one big whiteboard and twenty desks inside."),
    ]

    # G3-E4-1 日常礼貌问候与道别
    bank["G3-E4-1"] = [
        _q("g3-e41-1", "G3-E4-1", "reading_choice", "basic",
           "— Good morning, Miss White!  — ____", "Good morning!",
           "早上问好 Good morning! 的礼貌回应也是 Good morning!",
           grade=3, options=["Good morning!", "Good afternoon!", "Good night!", "Goodbye!"], correct_index=0),
        _q("g3-e41-2", "G3-E4-1", "reading_choice", "basic",
           "— Nice to meet you!  — ____", "Nice to meet you, too.",
           "初次见面问好 Nice to meet you! 应回答 Nice to meet you, too.",
           grade=3, options=["Thank you.", "Nice to meet you, too.", "I'm eight.", "Here you are."], correct_index=1),
        _q("g3-e41-3", "G3-E4-1", "sentence_bank", "medium",
           "补全对话：— How are you?  — I'm ____, thank you.", "fine",
           "回应 How are you?（你好吗？）常用 I'm fine, thank you.",
           grade=3, word_bank=["fine", "five", "red", "tall"]),
        _q("g3-e41-4", "G3-E4-1", "reading_choice", "medium",
           "放学和同学挥手道别时，我们可以说：", "Goodbye! / See you!",
           "道别用 Goodbye! 或 See you!",
           grade=3, options=["Hello!", "Good morning!", "Goodbye! / See you!", "What's this?"], correct_index=2),
        _q("g3-e41-5", "G3-E4-1", "listen_choice", "basic",
           "听录音，录音中的单词表示哪种心情？", "开心的 (happy)",
           "happy 意为“开心的、快乐的”。",
           grade=3, options=["开心的 (happy)", "伤心的 (sad)", "生气的 (angry)", "饥饿的 (hungry)"],
           correct_index=0, audio_text="happy"),
        _q("g3-e41-6", "G3-E4-1", "speak_read", "medium",
           "听示范并跟读单词：", "polite",
           "有礼貌地问候他人，跟读单词 polite（有礼貌的）。",
           grade=3, audio_text="polite", speak_target="polite",
           fallback_options=["早上问好说 Good morning!", "早上问好说 Good night!", "道别时说 Nice to meet you!", "询问姓名说 How old are you?"],
           fallback_correct_index=0),
    ]

    # G3-E4-2 感谢道歉与分享食物交际
    bank["G3-E4-2"] = [
        _q("g3-e42-1", "G3-E4-2", "reading_choice", "basic",
           "— Here you are.  — ____", "Thank you!",
           "别人递给你东西说 Here you are.（给你），要礼貌说 Thank you!（谢谢你）。",
           grade=3, options=["Thank you!", "You're welcome.", "I'm sorry.", "No, I don't."], correct_index=0),
        _q("g3-e42-2", "G3-E4-2", "reading_choice", "basic",
           "— Thank you!  — ____", "You're welcome.",
           "回应别人的感谢用 You're welcome.（不用谢/不客气）。",
           grade=3, options=["Here you are.", "You're welcome.", "Nice to meet you.", "Goodbye."], correct_index=1),
        _q("g3-e42-3", "G3-E4-2", "listen_choice", "medium",
           "听问句，选出最恰当的答语：", "Some water, please.",
           "录音问：What would you like to drink?（你想喝什么？）应回答饮品。",
           grade=3, options=["Some water, please.", "I am nine.", "It's a dog.", "Good morning."],
           correct_index=0, audio_text="What would you like to drink?"),
        _q("g3-e42-4", "G3-E4-2", "sentence_bank", "medium",
           "补全对话：— Can I have some water, ____?  — Sure. Here you are.", "please",
           "礼貌请求时在句尾加上 please（请）。",
           grade=3, word_bank=["please", "thanks", "sorry", "hello"]),
        _q("g3-e42-5", "G3-E4-2", "speak_read", "medium",
           "听示范并礼貌跟读点餐句：", "I would like some salad and tea, please.",
           "注意句末 please 的礼貌语调。",
           grade=3, audio_text="I would like some salad and tea, please.",
           speak_target="I would like some salad and tea please",
           fallback_options=["请求食物句尾加 please 更礼貌", "感谢别人说 You're welcome.", "回应感谢说 Here you are.", "分享食物说 Goodbye."],
           fallback_correct_index=0),
        _sentence_order_q("g3-e42-6", "G3-E4-2", 3, "hard",
                          ["Can", "I", "have", "some", "milk?"],
                          "Can I have some milk?",
                          "我能喝一些牛奶吗？",
                          "礼貌索要食物/饮品的常用句型：Can I have some...?", seed=342),
    ]

    # G3-E4-3 询问年龄与物品数量对话
    bank["G3-E4-3"] = [
        _q("g3-e43-1", "G3-E4-3", "reading_choice", "basic",
           "— How old are you?  — ____", "I'm nine years old.",
           "How old are you? 询问年龄，回答 I'm + 数字 (+ years old).",
           grade=3, options=["I'm fine.", "I'm nine years old.", "I see nine.", "It's nine o'clock."], correct_index=1),
        _q("g3-e43-2", "G3-E4-3", "reading_choice", "basic",
           "— Happy birthday to you!  — ____", "Thank you!",
           "别人祝你生日快乐（Happy birthday!），应回答 Thank you!",
           grade=3, options=["Happy birthday!", "Thank you!", "I'm eight.", "Me too."], correct_index=1),
        _q("g3-e43-3", "G3-E4-3", "sentence_bank", "medium",
           "补全对话：— How ____ are you, Sam?  — I'm eight.", "old",
           "How old are you? 表示“你几岁了？”。",
           grade=3, word_bank=["old", "many", "nice", "tall"]),
        _q("g3-e43-4", "G3-E4-3", "reading_choice", "medium",
           "— How many plates?  — ____", "Five.",
           "询问盘子数量 How many plates? 直接用数字 Five. 回答。",
           grade=3, options=["Five.", "Fine.", "Red.", "Sure."], correct_index=0),
        _q("g3-e43-5", "G3-E4-3", "listen_tf", "medium",
           "听录音判断：录音中提到书桌上有一台电脑。", "T",
           "录音：There is a computer on the desk. 数量为一台（a computer）。",
           grade=3, options=["正确 (T)", "错误 (F)"], correct_index=0,
           audio_text="There is a computer on the desk."),
        _sentence_order_q("g3-e43-6", "G3-E4-3", 3, "hard",
                          ["How", "old", "are", "you?"],
                          "How old are you?",
                          "你几岁了？",
                          "询问年龄的核心句型：How old are you?", seed=343),
    ]

    # G3-E4-4 启蒙绘本短篇理解
    p_g3_1 = (
        "Hello! I'm Lily. I'm eight years old. "
        "I have a cute cat. Its name is Mimi. "
        "Mimi is white. It has two big eyes. It likes fish very much!"
    )
    p_g3_2 = (
        "Look at my schoolbag! It is blue and yellow. "
        "I have three books, two pencils and one red ruler in my bag."
    )
    bank["G3-E4-4"] = [
        _q("g3-e44-1", "G3-E4-4", "reading_choice", "basic",
           "阅读绘本短文，Lily 今年几岁了？", "Eight (8岁)",
           "原文第二句：I'm eight years old.",
           grade=3, options=["Seven (7岁)", "Eight (8岁)", "Nine (9岁)", "Ten (10岁)"],
           correct_index=1, passage=p_g3_1),
        _q("g3-e44-2", "G3-E4-4", "reading_choice", "basic",
           "阅读绘本短文，小猫 Mimi 是什么颜色的？", "White（白色）",
           "原文：Mimi is white.",
           grade=3, options=["Black（黑色）", "Yellow（黄色）", "White（白色）", "Brown（棕色）"],
           correct_index=2, passage=p_g3_1),
        _q("g3-e44-3", "G3-E4-4", "reading_choice", "medium",
           "阅读绘本短文，小猫 Mimi 最喜欢吃什么？", "Fish（鱼）",
           "原文末句：It likes fish very much!",
           grade=3, options=["Apples（苹果）", "Fish（鱼）", "Bread（面包）", "Cake（蛋糕）"],
           correct_index=1, passage=p_g3_1),
        _q("g3-e44-4", "G3-E4-4", "reading_choice", "medium",
           "阅读短文，书包（schoolbag）里面有几本书？", "Three books（3本书）",
           "原文：I have three books, two pencils and one red ruler in my bag.",
           grade=3, options=["One book", "Two books", "Three books（3本书）", "Four books"],
           correct_index=2, passage=p_g3_2),
        _q("g3-e44-5", "G3-E4-4", "sentence_bank", "medium",
           "根据短文选词填空：The ruler in the schoolbag is ____.", "red",
           "原文提到 one red ruler（一把红色的尺子）。",
           grade=3, word_bank=["red", "green", "black", "white"], passage=p_g3_2),
        _q("g3-e44-6", "G3-E4-4", "listen_choice", "hard",
           "听录音，判断 Leo 在学校是一个怎样的小朋友？", "既勤奋又乐于助人",
           "录音：Leo is hard-working and helpful at school.",
           grade=3, options=["害羞又安静", "既勤奋又乐于助人", "不爱做作业", "每天迟到"],
           correct_index=1, audio_text="Leo is hard-working and helpful at school."),
    ]

    return bank


# ==============================================================================
# 四年级（G4）题库构建（16 节点 × 6 题 = 96 题）
# ==============================================================================
def _build_g4_questions() -> dict[str, list[dict[str, Any]]]:
    bank: dict[str, list[dict[str, Any]]] = {n["key"]: [] for n in ENGLISH_G4_NODES}

    # G4-E1-1 相对开音节（a-e/i-e/o-e/u-e）
    bank["G4-E1-1"] = [
        _q("g4-e11-1", "G4-E1-1", "phonics_choice", "basic",
           "选出划线部分发音不同的一项：", "c[a]t",
           "cake / name / lake 是 a-e 相对开音节，发 /eɪ/；cat 是闭音节，发 /æ/。",
           grade=4, options=["c[a]ke", "n[a]me", "c[a]t", "l[a]ke"], correct_index=2,
           audio_text="cake, name, cat, lake"),
        _q("g4-e11-2", "G4-E1-1", "listen_choice", "basic",
           "听录音，选出你听到的 i-e 相对开音节单词：", "bike",
           "bike 中 i-e 发 /aɪ/。",
           grade=4, options=["big", "bike", "six", "pig"], correct_index=1, audio_text="bike"),
        _q("g4-e11-3", "G4-E1-1", "phonics_choice", "medium",
           "选出与 n[o]se 中 o-e 发音相同的单词：", "note",
           "nose 和 note 都是 o-e 相对开音节，发 /əʊ/；not / box / dog 发 /ɒ/。",
           grade=4, options=["not", "box", "note", "dog"], correct_index=2, audio_text="nose"),
        _word_tile_q("g4-e11-4", "G4-E1-1", 4, "medium", "make", "制作", ["i", "o"],
                     "make 是 a-e 结构开音节单词，拼写 m-a-k-e。", seed=411, audio_text="make"),
        _word_spell_q("g4-e11-5", "G4-E1-1", 4, "hard", "cute",
                      "根据中文「可爱的」与首字母提示，拼写 u-e 开音节单词：",
                      "cute 是 u-e 相对开音节词，u 发 /juː/。",
                      first_letter_hint="c _ _ e (4个字母)",
                      assist_chunks=["cute", "cut", "cate", "cube"]),
        _q("g4-e11-6", "G4-E1-1", "speak_read", "medium",
           "听示范并跟读下面的相对开音节句子：", "I ride my nice bike home.",
           "注意 ride / nice / bike 中的 i-e 与 home 中的 o-e 发音饱满。",
           grade=4, audio_text="I ride my nice bike home.",
           speak_target="I ride my nice bike home",
           fallback_options=["ride 与 nice 元音相同", "home 与 hot 元音相同", "bike 与 big 元音相同", "make 与 cat 元音相同"],
           fallback_correct_index=0),
    ]

    # G4-E1-2 r音节字母组合（ar/er/ir/or/ur）
    bank["G4-E1-2"] = [
        _q("g4-e12-1", "G4-E1-2", "phonics_choice", "basic",
           "选出划线部分与 c[ar] 发音相同的单词：", "f[ar]m",
           "car 和 farm 中的 ar 都发 /ɑː/。",
           grade=4, options=["f[ar]m", "w[ar]m", "b[ir]d", "n[ur]se"], correct_index=0),
        _q("g4-e12-2", "G4-E1-2", "phonics_choice", "basic",
           "单词 g[ir]l、b[ir]d 和 n[ur]se 中划线部分的共同发音是：", "/ɜː/",
           "ir 和 ur 在重读音节中通常都发长音 /ɜː/。",
           grade=4, options=["/ɑː/", "/ɔː/", "/ɜː/", "/eɪ/"], correct_index=2),
        _q("g4-e12-3", "G4-E1-2", "listen_choice", "medium",
           "听录音，选出末尾含有非重读 er（/ə/）字母组合的单词：", "flower",
           "flower 末尾是 er 组合，发轻音 /ə/。",
           grade=4, options=["flower", "clock", "house", "sheep"], correct_index=0, audio_text="flower"),
        _word_tile_q("g4-e12-4", "G4-E1-2", 4, "medium", "bird", "小鸟", ["a", "u"],
                     "bird 中含 r 音节组合 ir，拼写 b-i-r-d。", seed=412),
        _word_spell_q("g4-e12-5", "G4-E1-2", 4, "hard", "nurse",
                      "根据中文「护士」和首字母提示拼写含 ur 的单词：",
                      "nurse 中间含字母组合 ur，末尾有不发音的 e。",
                      first_letter_hint="n _ _ _ e (5个字母)",
                      assist_chunks=["nurse", "nirse", "norse", "nice"]),
        _q("g4-e12-6", "G4-E1-2", "phonics_choice", "hard",
           "选出划线部分 or 发音与其他三项不同的一项（注意 w 后的 or）：", "h[or]se",
           "work / word / world 中 w 后的 or 发 /ɜː/，而 horse 中 or 发 /ɔː/。",
           grade=4, options=["w[or]k", "w[or]d", "h[or]se", "w[or]ld"], correct_index=2),
    ]

    # G4-E1-3 常见字母组合（al/le/ow）
    bank["G4-E1-3"] = [
        _q("g4-e13-1", "G4-E1-3", "phonics_choice", "basic",
           "单词 t[al]l、b[al]l 和 w[al]l 中的字母组合 al 发音为：", "/ɔː/ 或 /ɔːl/",
           "al 在 l 前通常发长音 /ɔː/。",
           grade=4, options=["/æ/", "/ɔː/ 或 /ɔːl/", "/eɪ/", "/aɪ/"], correct_index=1),
        _q("g4-e13-2", "G4-E1-3", "phonics_choice", "basic",
           "选出与 app[le] 和 tab[le] 词尾结构及发音相同的单词：", "litt[le]",
           "apple / table / little 词尾都是成音节 -le，发 /l/。",
           grade=4, options=["litt[le]", "c[ar]", "sn[ow]", "rul[er]"], correct_index=0),
        _q("g4-e13-3", "G4-E1-3", "listen_choice", "medium",
           "听录音，选出与录音单词 window 中 ow 发音相同的词：", "snow",
           "window 和 snow 中 ow 都发 /əʊ/；cow / how / now 中 ow 发 /aʊ/。",
           grade=4, options=["cow", "how", "snow", "now"], correct_index=2, audio_text="window"),
        _word_tile_q("g4-e13-4", "G4-E1-3", 4, "medium", "window", "窗户", ["a", "e"],
                     "window 以字母组合 ow 结尾，拼写 w-i-n-d-o-w。", seed=413, audio_text="window"),
        _word_spell_q("g4-e13-5", "G4-E1-3", 4, "hard", "table",
                      "根据中文「桌子」与首字母提示，拼写以 -le 结尾的单词：",
                      "table 以成音节 -le 结尾，拼写 t-a-b-l-e。",
                      first_letter_hint="t _ _ _ e (5个字母)",
                      assist_chunks=["table", "tabel", "tall", "apple"]),
        _q("g4-e13-6", "G4-E1-3", "speak_read", "medium",
           "听示范并跟读，注意 yellow 与 cow 中 ow 的不同发音：",
           "I see a yellow cow near the house.",
           "yellow 中 ow 发 /əʊ/，cow 中 ow 发 /aʊ/。",
           grade=4, audio_text="I see a yellow cow near the house.",
           speak_target="I see a yellow cow near the house",
           fallback_options=["yellow 与 window 的 ow 发音相同", "yellow 与 cow 的 ow 发音相同", "window 与 cow 的 ow 发音相同", "house 与 snow 元音相同"],
           fallback_correct_index=0),
    ]

    # G4-E1-4 双音节词听音拼读
    bank["G4-E1-4"] = [
        _q("g4-e14-1", "G4-E1-4", "listen_choice", "basic",
           "听录音，选出你听到的天气双音节形容词：", "rainy",
           "rain + y -> rainy（多雨的）。",
           grade=4, options=["rainy", "sunny", "windy", "cloudy"], correct_index=0, audio_text="rainy"),
        _q("g4-e14-2", "G4-E1-4", "listen_choice", "basic",
           "听录音，选出由 play + ground 组成的校园场所合成词：", "playground",
           "playground 意为“操场”。",
           grade=4, options=["classroom", "playground", "library", "garden"], correct_index=1, audio_text="playground"),
        _word_tile_q("g4-e14-3", "G4-E1-4", 4, "medium", "flower", "花朵", ["a", "i"],
                     "fl-ow-er 拼读为 flower（花朵）。", seed=414, audio_text="flower"),
        _q("g4-e14-4", "G4-E1-4", "phonics_choice", "medium",
           "双音节词 sun-ny、win-dy、hap-py 词尾的字母 y 发什么音？", "/i/",
           "双音节词词尾非重读的 y 通常发短音 /i/。",
           grade=4, options=["/aɪ/", "/i/", "/eɪ/", "/əʊ/"], correct_index=1, audio_text="happy"),
        _word_spell_q("g4-e14-5", "G4-E1-4", 4, "hard", "rainy",
                      "听录音，根据首字母提示拼写表示「多雨的」单词：",
                      "rain（雨）+ y -> rainy（多雨的）。",
                      audio_text="rainy",
                      first_letter_hint="r _ _ _ y (5个字母)",
                      assist_chunks=["rainy", "rany", "rain", "windy"]),
        _q("g4-e14-6", "G4-E1-4", "speak_read", "medium",
           "听示范并跟读下面的双音节自然拼读句子：",
           "The funny baby plays by the clock.",
           "注意双音节词 funny 和 baby 的重音在第一个音节。",
           grade=4, audio_text="The funny baby plays by the clock.",
           speak_target="The funny baby plays by the clock",
           fallback_options=["funny 与 baby 词尾 y 都发 /i/", "funny 词尾 y 发 /aɪ/", "baby 只有一个音节", "clock 是双音节词"],
           fallback_correct_index=0),
    ]

    # G4-E2-1 教室设施与校园功能室
    bank["G4-E2-1"] = [
        _q("g4-e21-1", "G4-E2-1", "listen_choice", "basic",
           "听录音，选出同学们上体育课和踢球的地方：", "操场 (playground)",
           "playground 意为“操场”。",
           grade=4, options=["图书馆 (library)", "美术教室 (art room)", "操场 (playground)", "音乐教室 (music room)"],
           correct_index=2, audio_text="playground"),
        _q("g4-e21-2", "G4-E2-1", "reading_choice", "basic",
           "We can read many storybooks quietly in the ____.", "library",
           "可以安静看很多故事书的功能室是图书馆（library）。",
           grade=4, options=["library", "gym", "washroom", "playground"], correct_index=0),
        _word_tile_q("g4-e21-3", "G4-E2-1", 4, "basic", "window", "窗户", ["e", "u"],
                     "教室里的窗户是 window。", seed=421, audio_text="window"),
        _q("g4-e21-4", "G4-E2-1", "sentence_bank", "medium",
           "选词填空：Go to the ____. Water the beautiful flowers.", "garden",
           "浇花（Water the flowers）应该去花园（garden）。",
           grade=4, word_bank=["garden", "library", "computer", "blackboard"]),
        _word_spell_q("g4-e21-5", "G4-E2-1", 4, "hard", "library",
                      "根据中文「图书馆」和首字母提示拼写单词：",
                      "library 意为“图书馆”，拼写 l-i-b-r-a-r-y。",
                      first_letter_hint="l _ _ _ _ _ y (7个字母)",
                      assist_chunks=["library", "libary", "librery", "garden"]),
        _q("g4-e21-6", "G4-E2-1", "listen_tf", "medium",
           "听录音判断：我们的教室里有一块大白板（whiteboard）和二十张课桌。", "T",
           "录音：Look at our classroom. There is one big whiteboard and twenty desks inside.",
           grade=4, options=["正确 (T)", "错误 (F)"], correct_index=0,
           audio_text="Look at our classroom. There is one big whiteboard and twenty desks inside."),
    ]

    # G4-E2-2 时间作息与天气冷暖
    bank["G4-E2-2"] = [
        _q("g4-e22-1", "G4-E2-2", "listen_choice", "basic",
           "听录音，选出录音描述的天气状况：", "下雨的 (rainy)",
           "rainy 意为“下雨的、多雨的”。",
           grade=4, options=["晴朗的 (sunny)", "下雨的 (rainy)", "多云的 (cloudy)", "下雪的 (snowy)"],
           correct_index=1, audio_text="rainy"),
        _q("g4-e22-2", "G4-E2-2", "reading_choice", "basic",
           "It's 7:00 a.m. It's time to eat ____.", "breakfast",
           "早上 7 点是吃早餐（breakfast）的时间；lunch 是午餐，dinner 是晚餐。",
           grade=4, options=["breakfast", "lunch", "dinner", "bed"], correct_index=0),
        _word_tile_q("g4-e22-3", "G4-E2-2", 4, "basic", "lunch", "午餐", ["a", "e"],
                     "lunch 意为“午餐”，拼写 l-u-n-c-h。", seed=422, audio_text="lunch"),
        _q("g4-e22-4", "G4-E2-2", "sentence_bank", "medium",
           "选词填空：It's 26 degrees outside. It's ____ and sunny.", "warm",
           "26 度且晴朗，气候温暖舒适，选 warm（暖和的）。",
           grade=4, word_bank=["warm", "snowy", "freezing", "rainy"]),
        _word_spell_q("g4-e22-5", "G4-E2-2", 4, "hard", "sunny",
                      "根据中文「晴朗的」与首字母提示拼写天气单词：",
                      "sun 双写 n 加 y -> sunny（晴朗的）。",
                      first_letter_hint="s _ _ _ y (5个字母)",
                      assist_chunks=["sunny", "suny", "windy", "snowy"]),
        _q("g4-e22-6", "G4-E2-2", "reading_choice", "medium",
           "It's 9:30 p.m. It's time to ____.", "go to bed",
           "晚上 9:30 是上床睡觉（go to bed）的时间。",
           grade=4, options=["get up", "go to school", "have lunch", "go to bed"], correct_index=3),
    ]

    # G4-E2-3 农场动物与新鲜果蔬
    bank["G4-E2-3"] = [
        _q("g4-e23-1", "G4-E2-3", "listen_choice", "basic",
           "听录音，选出你在农场里听到的动物：", "绵羊 (sheep)",
           "sheep 意为“绵羊”，注意单复数同形。",
           grade=4, options=["母鸡 (hen)", "奶牛 (cow)", "绵羊 (sheep)", "马 (horse)"],
           correct_index=2, audio_text="sheep"),
        _q("g4-e23-2", "G4-E2-3", "reading_choice", "basic",
           "Rabbits love eating orange ____. They are healthy vegetables.", "carrots",
           "小兔子最爱吃的橙色蔬菜是胡萝卜（carrots）。",
           grade=4, options=["carrots", "potatoes", "onions", "bananas"], correct_index=0),
        _word_tile_q("g4-e23-3", "G4-E2-3", 4, "basic", "fresh", "新鲜的", ["a", "o"],
                     "fresh 意为“新鲜的”，常用来形容农场果蔬。", seed=423, audio_text="fresh"),
        _q("g4-e23-4", "G4-E2-3", "sentence_bank", "medium",
           "选词填空：Look at these red ____. They are juicy and sweet.", "tomatoes",
           "红色的多汁蔬菜/水果是西红柿（tomatoes）。",
           grade=4, word_bank=["tomatoes", "potatoes", "horses", "goats"]),
        _word_spell_q("g4-e23-5", "G4-E2-3", 4, "hard", "horse",
                      "根据中文「马」与首字母提示拼写农场动物单词：",
                      "horse 意为“马”，拼写 h-o-r-s-e。",
                      first_letter_hint="h _ _ _ e (5个字母)",
                      assist_chunks=["horse", "house", "hose", "sheep"]),
        _q("g4-e23-6", "G4-E2-3", "listen_tf", "medium",
           "听录音判断：房子附近有一头黄色的奶牛（cow）。", "T",
           "录音：I see a yellow cow near the house.",
           grade=4, options=["正确 (T)", "错误 (F)"], correct_index=0,
           audio_text="I see a yellow cow near the house."),
    ]

    # G4-E2-4 服装鞋帽与购物价格
    bank["G4-E2-4"] = [
        _q("g4-e24-1", "G4-E2-4", "reading_choice", "basic",
           "It's cold outside. Put on your warm ____.", "coat",
           "外面很冷，应该穿上暖和的外套/大衣（coat）。",
           grade=4, options=["shorts", "T-shirt", "coat", "sunglasses"], correct_index=2),
        _q("g4-e24-2", "G4-E2-4", "reading_choice", "basic",
           "The dress is 500 yuan. It's too ____!", "expensive",
           "一条裙子 500 元太贵了（expensive）；cheap 意为“便宜的”。",
           grade=4, options=["cheap", "expensive", "small", "short"], correct_index=1),
        _word_tile_q("g4-e24-3", "G4-E2-4", 4, "basic", "shirt", "衬衫", ["a", "e"],
                     "shirt 意为“衬衫”，拼写 s-h-i-r-t。", seed=424),
        _q("g4-e24-4", "G4-E2-4", "sentence_bank", "medium",
           "选词填空：Look at those ____. They are nice and cheap, only 15 yuan.", "gloves",
           "those 后接复数名词 gloves（手套）。",
           grade=4, word_bank=["gloves", "hat", "scarf", "dress"]),
        _word_spell_q("g4-e24-5", "G4-E2-4", 4, "hard", "cheap",
                      "根据中文「便宜的」和首字母提示拼写单词：",
                      "cheap 意为“便宜的”，ch + ea + p。",
                      first_letter_hint="c _ _ _ p (5个字母)",
                      assist_chunks=["cheap", "cheep", "chap", "sheep"]),
        _q("g4-e24-6", "G4-E2-4", "listen_choice", "medium",
           "听录音，选出周末经常需要清洗（wash）的物品：", "衣服 (clothes)",
           "日常固定搭配 wash my clothes（洗衣服）。",
           grade=4, options=["书桌 (desks)", "衣服 (clothes)", "黑板 (blackboard)", "作业 (homework)"],
           correct_index=1, audio_text="what"),
    ]

    # G4-E3-1 方位介词与 Where is/are
    bank["G4-E3-1"] = [
        _q("g4-e31-1", "G4-E3-1", "sentence_bank", "basic",
           "选词填空：— ____ is the teachers' office?  — It's on the second floor.", "Where",
           "答语是地点楼层 on the second floor，提问“在哪里”用 Where。",
           grade=4, word_bank=["Where", "What", "Who", "Whose"]),
        _q("g4-e31-2", "G4-E3-1", "reading_choice", "basic",
           "The library is on the ____ floor.", "first",
           "表示“在一楼”需使用序数词 the first floor。",
           grade=4, options=["one", "first", "two", "three"], correct_index=1),
        _q("g4-e31-3", "G4-E3-1", "listen_choice", "medium",
           "听录音，选出你听到的方位介词：", "between（在……之间）",
           "录音单词为 between。",
           grade=4, options=["on（在……上面）", "under（在……下面）", "between（在……之间）", "in（在……里面）"],
           correct_index=2, audio_text="between"),
        _q("g4-e31-4", "G4-E3-1", "sentence_fill", "medium",
           "用 is 或 are 填空：Where ____ my new shoes?", "are",
           "主语 my new shoes 是复数，be 动词用 are。",
           grade=4, first_letter_hint="a _ e (3个字母)", assist_chunks=["are", "is", "am", "be"]),
        _sentence_order_q("g4-e31-5", "G4-E3-1", 4, "hard",
                          ["It", "is", "next", "to", "the", "library."],
                          "It is next to the library.",
                          "它紧挨着图书馆。",
                          "next to 是固定短语，表示“紧挨着、在……旁边”。", seed=431),
        _q("g4-e31-6", "G4-E3-1", "listen_tf", "medium",
           "听录音判断：电脑在书桌的下面（under the desk）。", "F",
           "录音：There is a computer on the desk. 是在书桌上面（on），不是下面。",
           grade=4, options=["正确 (T)", "错误 (F)"], correct_index=1,
           audio_text="There is a computer on the desk."),
    ]

    # G4-E3-2 时间表达与 It's time for/to
    bank["G4-E3-2"] = [
        _q("g4-e32-1", "G4-E3-2", "sentence_bank", "basic",
           "选词填空：It's 12:00. It's time ____ lunch.", "for",
           "lunch 是名词，遵循“It's time for + 名词”规则，填 for。",
           grade=4, word_bank=["for", "to", "at", "in"]),
        _q("g4-e32-2", "G4-E3-2", "sentence_bank", "basic",
           "选词填空：It's 7:30. It's time ____ go to school.", "to",
           "go to school 是动词原形短语，遵循“It's time to + 动词原形”规则，填 to。",
           grade=4, word_bank=["to", "for", "on", "of"]),
        _q("g4-e32-3", "G4-E3-2", "reading_choice", "medium",
           "— What time is it now?  — ____", "It's nine o'clock.",
           "询问具体几点钟 What time is it? 回答 It's... o'clock.",
           grade=4, options=["It's sunny.", "It's nine o'clock.", "It's on the desk.", "It's fifty yuan."],
           correct_index=1),
        _q("g4-e32-4", "G4-E3-2", "sentence_fill", "medium",
           "根据句型规则填入 for 或 to：It's time ____ English class.", "for",
           "English class 是名词短语，用 It's time for...",
           grade=4, first_letter_hint="f _ r (3个字母)", assist_chunks=["for", "to", "at", "in"]),
        _sentence_order_q("g4-e32-5", "G4-E3-2", 4, "hard",
                          ["It", "is", "time", "to", "get", "up."],
                          "It is time to get up.",
                          "到起床的时间了。",
                          "It is time to + 动词原形短语 get up.", seed=432),
        _q("g4-e32-6", "G4-E3-2", "listen_choice", "basic",
           "听录音，选出能够帮我们看时间的物品：", "clock（时钟）",
           "录音单词是 clock（时钟）。",
           grade=4, options=["clock（时钟）", "bridge（桥）", "forest（森林）", "flower（花朵）"],
           correct_index=0, audio_text="clock"),
    ]

    # G4-E3-3 物品归属 Whose 与名词所有格
    bank["G4-E3-3"] = [
        _q("g4-e33-1", "G4-E3-3", "sentence_bank", "basic",
           "选词填空：— ____ coat is this?  — It's mine.", "Whose",
           "答语 It's mine.（它是我的）表明问句在询问“谁的”，用 Whose。",
           grade=4, word_bank=["Whose", "Who", "Where", "What"]),
        _q("g4-e33-2", "G4-E3-3", "reading_choice", "basic",
           "This is ____ hat. It's very pretty.", "Sarah's",
           "修饰名词 hat 表示“莎拉的帽子”，需用名词所有格 Sarah's。",
           grade=4, options=["Sarah", "Sarah's", "she", "hers"], correct_index=1),
        _q("g4-e33-3", "G4-E3-3", "reading_choice", "medium",
           "— Are these yours, Mike?  — ____", "Yes, they are.",
           "Are these...? 的肯定回答用代词 they：Yes, they are.",
           grade=4, options=["Yes, it is.", "Yes, they are.", "No, it isn't.", "Yes, I am."], correct_index=1),
        _q("g4-e33-4", "G4-E3-3", "sentence_fill", "medium",
           "用所给词的适当形式填空：This red schoolbag is ____ (my).", "mine",
           "横线后没有名词，应使用名词性物主代词 mine（相当于 my schoolbag）。",
           grade=4, first_letter_hint="m _ _ e (4个字母)", assist_chunks=["mine", "my", "me", "I"]),
        _sentence_order_q("g4-e33-5", "G4-E3-3", 4, "hard",
                          ["Whose", "pants", "are", "those?"],
                          "Whose pants are those?",
                          "那条裤子是谁的？",
                          "pants 是复数名词，结构为：Whose + 复数名词 + are those?", seed=433),
        _q("g4-e33-6", "G4-E3-3", "listen_choice", "medium",
           "听录音，区分疑问词：录音读出的是哪个词？", "what",
           "录音单词是 what（什么），注意与 who / whose 区分。",
           grade=4, options=["who", "whose", "what", "where"], correct_index=2, audio_text="what"),
    ]

    # G4-E3-4 远近复数 these/those 与 How much
    bank["G4-E3-4"] = [
        _q("g4-e34-1", "G4-E3-4", "sentence_bank", "basic",
           "选词填空：What are ____? They are tomatoes.", "these",
           "are 和复数答语 They are... 提示主语为复数指示代词 these（这些）。",
           grade=4, word_bank=["these", "this", "that", "it"]),
        _q("g4-e34-2", "G4-E3-4", "reading_choice", "basic",
           "— ____ is this skirt?  — It's 65 yuan.", "How much",
           "答语是价格 65 yuan，询问价格用 How much。",
           grade=4, options=["How many", "How much", "How old", "What time"], correct_index=1),
        _q("g4-e34-3", "G4-E3-4", "reading_choice", "medium",
           "— Are those horses?  — ____ They are donkeys.", "No, they aren't.",
           "Are those...? 的否定简略回答是 No, they aren't.",
           grade=4, options=["No, they aren't.", "No, those aren't.", "No, it isn't.", "Yes, they are."],
           correct_index=0),
        _q("g4-e34-4", "G4-E3-4", "sentence_fill", "medium",
           "用 that 的复数形式填空：Look at ____ (那些) sheep on the hill!", "those",
           "that（那个）的复数形式是 those（那些）。",
           grade=4, first_letter_hint="t _ _ _ e (5个字母)", assist_chunks=["those", "these", "that", "this"]),
        _sentence_order_q("g4-e34-5", "G4-E3-4", 4, "hard",
                          ["How", "much", "is", "this", "shirt?"],
                          "How much is this shirt?",
                          "这件衬衫多少钱？",
                          "询问单数商品价格：How much is + 单数名词?", seed=434),
        _q("g4-e34-6", "G4-E3-4", "sentence_fill", "hard",
           "用所给词的复数形式填空：There are ten ____ (sheep) on the farm.", "sheep",
           "sheep（绵羊）单复数同形，复数仍然是 sheep。",
           grade=4, first_letter_hint="s _ _ _ p (5个字母)", assist_chunks=["sheep", "sheeps", "ship", "shep"]),
    ]

    # G4-E4-1 天气询问与穿衣出行交际
    bank["G4-E4-1"] = [
        _q("g4-e41-1", "G4-E4-1", "reading_choice", "basic",
           "— What's the weather like in Beijing?  — ____", "It's sunny and warm.",
           "询问天气 What's the weather like...? 应回答天气状况 It's sunny and warm.",
           grade=4, options=["It's sunny and warm.", "It's on the first floor.", "It's 80 yuan.", "It's mine."],
           correct_index=0),
        _q("g4-e41-2", "G4-E4-1", "reading_choice", "basic",
           "— Can I go outside now, Mum?  — ____ It's raining heavily outside.", "No, you can't.",
           "外面正下大雨，妈妈不同意现在出去，回答 No, you can't.",
           grade=4, options=["Yes, you can.", "No, you can't.", "Yes, it is.", "Here you are."], correct_index=1),
        _q("g4-e41-3", "G4-E4-1", "sentence_bank", "medium",
           "补全交际句：It's hot inside. ____ off your hat and coat.", "Take",
           "take off 是固定短语，表示“脱下（衣帽）”；put on 表示“穿上”。",
           grade=4, word_bank=["Take", "Put", "Have", "Go"]),
        _q("g4-e41-4", "G4-E4-1", "listen_choice", "medium",
           "听录音，根据听到的天气词选择出门最需要携带的物品：", "An umbrella（雨伞）",
           "录音单词为 rainy（下雨的），出门需要带雨伞（An umbrella）。",
           grade=4, options=["Sunglasses（太阳镜）", "An umbrella（雨伞）", "Shorts（短裤）", "Ice cream（冰激凌）"],
           correct_index=1, audio_text="rainy"),
        _sentence_order_q("g4-e41-5", "G4-E4-1", 4, "hard",
                          ["What", "is", "the", "weather", "like", "today?"],
                          "What is the weather like today?",
                          "今天天气怎么样？",
                          "询问天气的标准句型：What is the weather like today?", seed=441),
        _q("g4-e41-6", "G4-E4-1", "reading_choice", "medium",
           "— Is it cold in Harbin in winter?  — ____", "Yes, it is. It's snowy.",
           "Is it...? 询问天气的一般疑问句，肯定回答是 Yes, it is.",
           grade=4, options=["Yes, it is. It's snowy.", "Yes, I can.", "No, they aren't.", "It's 7 o'clock."],
           correct_index=0),
    ]

    # G4-E4-2 校园场所问路与礼貌引导
    bank["G4-E4-2"] = [
        _q("g4-e42-1", "G4-E4-2", "reading_choice", "basic",
           "— Do you have a music room?  — ____ It's on the second floor.", "Yes, we do.",
           "Do you have...? 的肯定回答是 Yes, we do. / Yes, I do.",
           grade=4, options=["Yes, we do.", "Yes, it is.", "No, we aren't.", "Thank you."], correct_index=0),
        _q("g4-e42-2", "G4-E4-2", "reading_choice", "basic",
           "当你在校园里为来访客人带路时，可以礼貌地做出手势说：", "This way, please.",
           "This way, please. 意为“这边请”，是礼貌引导客人的常用语。",
           grade=4, options=["This way, please.", "Hurry up!", "Be quiet!", "How much is it?"], correct_index=0),
        _q("g4-e42-3", "G4-E4-2", "sentence_bank", "medium",
           "补全对话：— ____ me. Where is the computer room?  — It's next to the library.", "Excuse",
           "问路前先礼貌打招呼用 Excuse me.（劳驾/打扰一下）。",
           grade=4, word_bank=["Excuse", "Sorry", "Thank", "Help"]),
        _q("g4-e42-4", "G4-E4-2", "listen_choice", "medium",
           "听问句，选出关于美术老师最恰当的描述：", "She is kind and funny.",
           "录音问：What is your art teacher like? 应回答老师的性格特征。",
           grade=4, options=["She is in the gym.", "She is kind and funny.", "It's on the first floor.", "Yes, we do."],
           correct_index=1, audio_text="What is your art teacher like?"),
        _q("g4-e42-5", "G4-E4-2", "listen_choice", "hard",
           "听问句，选出最恰当的答语：", "No, there aren't.",
           "录音问：Are there any tall buildings in the park? 对应回答 No, there aren't.",
           grade=4, options=["No, they aren't.", "No, there aren't.", "Yes, it is.", "Yes, we do."],
           correct_index=1, audio_text="Are there any tall buildings in the park?"),
        _sentence_order_q("g4-e42-6", "G4-E4-2", 4, "hard",
                          ["Where", "is", "the", "art", "room?"],
                          "Where is the art room?",
                          "美术教室在哪里？",
                          "询问地点：Where is + the + 场所名称?", seed=442),
    ]

    # G4-E4-3 商店购物询价与试穿对话
    bank["G4-E4-3"] = [
        _q("g4-e43-1", "G4-E4-3", "reading_choice", "basic",
           "走进服装店时，售货员通常会热情地对你说：", "Can I help you?",
           "Can I help you?（我能为您效劳吗？/您想买点什么？）是商店服务员的标准迎客用语。",
           grade=4, options=["Can I help you?", "Can you help me?", "How much are you?", "What time is it?"],
           correct_index=0),
        _q("g4-e43-2", "G4-E4-3", "reading_choice", "basic",
           "— Can I try them on?  — ____", "Sure. Here you are.",
           "顾客询问“我能试穿一下吗？”，店员应礼貌同意：Sure. Here you are.",
           grade=4, options=["Sure. Here you are.", "No, I don't.", "They are sheep.", "It's sunny."], correct_index=0),
        _q("g4-e43-3", "G4-E4-3", "sentence_bank", "medium",
           "补全购物对话：— The shoes are nice and cheap. I'll ____ them!  — Thank you.", "take",
           "购物时决定买下某物常用 I'll take it / them!（我买了！）。",
           grade=4, word_bank=["take", "make", "play", "read"]),
        _q("g4-e43-4", "G4-E4-3", "reading_choice", "medium",
           "— How do you like this blue skirt?  — ____", "It's very pretty.",
           "How do you like...? 询问“你觉得……怎么样？”，回答评价 It's very pretty.",
           grade=4, options=["It's very pretty.", "Yes, I do.", "It's on the bed.", "I have two."], correct_index=0),
        _q("g4-e43-5", "G4-E4-3", "speak_read", "medium",
           "听示范并礼貌跟读：", "I would like some salad and tea, please.",
           "在餐厅或商店选购时，用 I would like..., please. 表达礼貌得体。",
           grade=4, audio_text="I would like some salad and tea, please.",
           speak_target="I would like some salad and tea please",
           fallback_options=["售货员迎客说 Can I help you?", "询问价格用 How many?", "决定买下说 I'll eat them.", "试穿衣服说 Take off."],
           fallback_correct_index=0),
        _sentence_order_q("g4-e43-6", "G4-E4-3", 4, "hard",
                          ["Can", "I", "try", "them", "on?"],
                          "Can I try them on?",
                          "我能试穿一下它们吗？",
                          "代词 them 放在短语 try... on 中间：Can I try them on?", seed=443),
    ]

    # G4-E4-4 校园与农场生活短文阅读
    p_g4_farm = (
        "Welcome to Uncle Wang's farm! It is big and nice. "
        "Look! These are tomatoes and green beans. They are very fresh. "
        "Over there, you can see twelve sheep and five horses. "
        "It's 12:00 now. It's time for lunch!"
    )
    p_g4_school = (
        "Hi, I'm Amy. It is 9:00 a.m. and it's sunny today. "
        "Our classroom is on the first floor. The library is on the second floor, next to the art room. "
        "At 10:00, it's time for PE class. We go to the big playground and play football."
    )
    bank["G4-E4-4"] = [
        _q("g4-e44-1", "G4-E4-4", "reading_choice", "basic",
           "根据短文内容，Uncle Wang 的农场里有哪些蔬菜？", "Tomatoes and green beans",
           "原文：These are tomatoes and green beans.",
           grade=4, options=["Apples and bananas", "Tomatoes and green beans", "Potatoes and onions", "Cakes and bread"],
           correct_index=1, passage=p_g4_farm),
        _q("g4-e44-2", "G4-E4-4", "reading_choice", "basic",
           "根据短文内容，农场里有多少只绵羊（sheep）？", "Twelve (12只)",
           "原文：you can see twelve sheep and five horses.",
           grade=4, options=["Five (5只)", "Ten (10只)", "Twelve (12只)", "Twenty (20只)"],
           correct_index=2, passage=p_g4_farm),
        _q("g4-e44-3", "G4-E4-4", "reading_choice", "medium",
           "阅读校园短文，Amy 学校的图书馆在几楼？", "On the second floor（二楼）",
           "原文：The library is on the second floor, next to the art room.",
           grade=4, options=["On the first floor（一楼）", "On the second floor（二楼）", "Near the playground", "In the garden"],
           correct_index=1, passage=p_g4_school),
        _q("g4-e44-4", "G4-E4-4", "reading_choice", "medium",
           "阅读校园短文，上午 10:00 到了上什么课的时间？", "PE class（体育课）",
           "原文：At 10:00, it's time for PE class.",
           grade=4, options=["Music class", "Art class", "English class", "PE class（体育课）"],
           correct_index=3, passage=p_g4_school),
        _q("g4-e44-5", "G4-E4-4", "sentence_bank", "medium",
           "根据校园短文选词填空：The library is ____ to the art room.", "next",
           "原文：next to the art room（紧挨着美术教室）。",
           grade=4, word_bank=["next", "under", "in", "between"], passage=p_g4_school),
        _q("g4-e44-6", "G4-E4-4", "listen_choice", "hard",
           "听录音短文，判断说话人周六上午经常和朋友做什么运动？", "Play football（踢足球）",
           "录音：I often play football with my friends on Saturday morning.",
           grade=4, options=["Swim（游泳）", "Play football（踢足球）", "Fly a kite（放风筝）", "Read books（看书）"],
           correct_index=1, audio_text="I often play football with my friends on Saturday morning."),
    ]

    return bank


# ==============================================================================
# 六年级（G6）题库构建（16 节点 × 6 题 = 96 题）
# ==============================================================================
def _build_g6_questions() -> dict[str, list[dict[str, Any]]]:
    bank: dict[str, list[dict[str, Any]]] = {n["key"]: [] for n in ENGLISH_G6_NODES}

    # G6-E1-1 规则动词过去式 -ed 尾音辨析
    bank["G6-E1-1"] = [
        _q("g6-e11-1", "G6-E1-1", "phonics_choice", "basic",
           "选出规则动词过去式词尾 -ed 发音与其他三项不同的一项：", "visited",
           "watched / washed / cooked 中清辅音后 -ed 发 /t/；visited 以 /t/ 结尾，-ed 发 /ɪd/。",
           grade=6, options=["watch[ed]", "wash[ed]", "cook[ed]", "visit[ed]"], correct_index=3),
        _q("g6-e11-2", "G6-E1-1", "phonics_choice", "basic",
           "单词 play[ed]、clean[ed] 和 stay[ed] 词尾的 -ed 都发什么音？", "/d/",
           "在元音和浊辅音（非 /d/）后面，-ed 发浊辅音 /d/。",
           grade=6, options=["/t/", "/d/", "/ɪd/", "/e/"], correct_index=1),
        _q("g6-e11-3", "G6-E1-1", "phonics_choice", "medium",
           "选出划线部分 -ed 发音与 want[ed] 相同的一项：", "need[ed]",
           "以 /t/ 或 /d/ 音结尾的规则动词（want / need），加 -ed 后发 /ɪd/。",
           grade=6, options=["jump[ed]", "help[ed]", "need[ed]", "liv[ed]"], correct_index=2),
        _word_tile_q("g6-e11-4", "G6-E1-1", 6, "medium", "washed", "洗（过去式）", ["i", "t"],
                     "wash 的过去式是 washed，词尾 -ed 在 /ʃ/ 后发 /t/。", seed=611),
        _word_spell_q("g6-e11-5", "G6-E1-1", 6, "hard", "visited",
                      "写出动词 visit 的过去式（词尾 -ed 发 /ɪd/ 音）：",
                      "visit 直接加 -ed -> visited。",
                      first_letter_hint="v _ _ _ _ _ d (7个字母)",
                      assist_chunks=["visited", "visitted", "visits", "visiting"]),
        _q("g6-e11-6", "G6-E1-1", "speak_read", "hard",
           "听示范并跟读下面的周末活动复合句：",
           "I often play football with my friends on Saturday morning.",
           "注意连读 play football with my friends 与句末降调。",
           grade=6, audio_text="I often play football with my friends on Saturday morning.",
           speak_target="I often play football with my friends on Saturday morning",
           fallback_options=["played 中 -ed 发 /d/", "played 中 -ed 发 /ɪd/", "watched 中 -ed 发 /ɪd/", "visited 中 -ed 发 /t/"],
           fallback_correct_index=0),
    ]

    # G6-E1-2 名词复数/三单 -s/-es 与不发音字母（kn/wr）
    bank["G6-E1-2"] = [
        _q("g6-E12-1", "G6-E1-2", "phonics_choice", "basic",
           "单词 [kn]ow、[kn]ife 和 [kn]ee 开头的字母组合 kn 中，哪个字母不发音？", "k",
           "字母组合 kn 在词首时，k 不发音，只发 /n/。",
           grade=6, options=["k", "n", "o", "w"], correct_index=0),
        _q("g6-E12-2", "G6-E1-2", "phonics_choice", "basic",
           "选出含有不发音字母 w 的一项：", "[wr]ite",
           "wr 在词首时（write / wrong / wrist），w 不发音，只发 /r/。",
           grade=6, options=["[w]indow", "[w]ater", "[wr]ite", "[w]inter"], correct_index=2, audio_text="window"),
        _q("g6-E12-3", "G6-E1-2", "phonics_choice", "medium",
           "选出词尾 -s/-es 发音为 /ɪz/ 的一项：", "watch[es]",
           "在 /s/, /z/, /ʃ/, /tʃ/, /dʒ/ 后，-es 发 /ɪz/，如 watches / boxes / buses。",
           grade=6, options=["book[s]", "map[s]", "bag[s]", "watch[es]"], correct_index=3),
        _q("g6-E12-4", "G6-E1-2", "listen_choice", "medium",
           "听录音，选出中间含有不发音字母 d 的星期单词：", "Wednesday",
           "Wednesday 中的第一个 d 不发音，读作 /ˈwenzdeɪ/。",
           grade=6, options=["Tuesday", "Wednesday", "Thursday", "Friday"],
           correct_index=1, audio_text="Wednesday"),
        _word_spell_q("g6-E12-5", "G6-E1-2", 6, "hard", "Wednesday",
                      "听录音，准确拼写含有不发音字母 d 的「星期三」英文单词：",
                      "Wednesday 注意首字母大写以及中间不发音的 d（W-e-d-n-e-s-d-a-y）。",
                      audio_text="Wednesday",
                      first_letter_hint="W _ _ _ _ _ _ _ y (9个字母)",
                      assist_chunks=["Wednesday", "Wenesday", "Wednsday", "Thursday"]),
        _q("g6-E12-6", "G6-E1-2", "speak_read", "hard",
           "听示范并跟读，注意三单 has 与辅音连缀的清晰发音：",
           "She has three fresh fish for lunch.",
           "has 词尾 s 发浊音 /z/，fresh / fish 词尾 sh 发 /ʃ/。",
           grade=6, audio_text="She has three fresh fish for lunch.",
           speak_target="She has three fresh fish for lunch",
           fallback_options=["knife 中首字母 k 不发音", "write 中首字母 r 不发音", "Wednesday 中 s 不发音", "books 词尾 s 发 /ɪz/"],
           fallback_correct_index=0),
    ]

    # G6-E1-3 多音节词重音与句子升降调
    bank["G6-E1-3"] = [
        _q("g6-e13-1", "G6-E1-3", "phonics_choice", "basic",
           "英语口语中，一般疑问句（如 Are you going to the bookstore?）句末通常用什么语调？", "升调 (↗)",
           "用 Yes / No 回答的一般疑问句句末通常用升调 (↗)。",
           grade=6, options=["升调 (↗)", "降调 (↘)", "先降后升", "平调不变化"], correct_index=0),
        _q("g6-e13-2", "G6-E1-3", "phonics_choice", "basic",
           "特殊疑问句（如 Where are you going tomorrow?）和陈述句句末通常用什么语调？", "降调 (↘)",
           "由 What / Where / When / How 等引导的特殊疑问句和陈述句通常用降调 (↘)。",
           grade=6, options=["升调 (↗)", "降调 (↘)", "全部高音", "只读疑问词"], correct_index=1),
        _q("g6-e13-3", "G6-E1-3", "listen_choice", "medium",
           "听录音，判断多音节词 delicious（美味的）的重音落在第几个音节？", "第二个音节 (de-'li-cious)",
           "delicious 读作 /dɪˈlɪʃəs/，重音在第二个音节 li 上。",
           grade=6, options=["第一个音节 ('de-li-cious)", "第二个音节 (de-'li-cious)", "第三个音节 (de-li-'cious)", "没有重音"],
           correct_index=1, audio_text="delicious"),
        _q("g6-e13-4", "G6-E1-3", "listen_choice", "medium",
           "听问句录音，判断该句在口语朗读时句尾应采用什么语调：", "升调 (↗) — 一般疑问句",
           "录音原句：Are there any tall buildings in the park? 是一般疑问句，句末用升调。",
           grade=6, options=["升调 (↗) — 一般疑问句", "降调 (↘) — 感叹句", "降调 (↘) — 祈使句", "平调"],
           correct_index=0, audio_text="Are there any tall buildings in the park?"),
        _word_tile_q("g6-e13-5", "G6-E1-3", 6, "medium", "helpful", "乐于助人的", ["a", "i"],
                     "help-ful 重音在第一个音节 help 上。", seed=613, audio_text="helpful"),
        _q("g6-e13-6", "G6-E1-3", "speak_read", "hard",
           "听示范并跟读，注意句子的重音节奏与句末语调：",
           "Leo is hard-working and helpful at school.",
           "陈述句句末用降调，hard-working 和 helpful 的核心重音要清晰。",
           grade=6, audio_text="Leo is hard-working and helpful at school.",
           speak_target="Leo is hard-working and helpful at school",
           fallback_options=["一般疑问句通常用升调", "特殊疑问句通常用升调", "陈述句通常用升调", "delicious 重音在第一音节"],
           fallback_correct_index=0),
    ]

    # G6-E1-4 小升初高频核心词听音拼写
    bank["G6-E1-4"] = [
        _q("g6-e14-1", "G6-E1-4", "listen_choice", "basic",
           "听录音，选出你听到的小升初核心形容词：", "delicious",
           "delicious 意为“美味的、可口的”。",
           grade=6, options=["different", "difficult", "delicious", "dangerous"],
           correct_index=2, audio_text="delicious"),
        _q("g6-e14-2", "G6-E1-4", "listen_choice", "basic",
           "听录音，选出你听到的自然景观名词：", "forest",
           "forest 意为“森林”。",
           grade=6, options=["forest", "factory", "ferry", "feature"],
           correct_index=0, audio_text="forest"),
        _word_tile_q("g6-e14-3", "G6-E1-4", 6, "medium", "bridge", "桥梁", ["a", "t"],
                     "bridge 中 dge 发 /dʒ/，拼写 b-r-i-d-g-e。", seed=614, audio_text="bridge"),
        _word_spell_q("g6-e14-4", "G6-E1-4", 6, "medium", "clever",
                      "听录音，拼写出表示「聪明的」核心词汇：",
                      "clever 拼写为 c-l-e-v-e-r。",
                      audio_text="clever",
                      first_letter_hint="c _ _ _ _ r (6个字母)",
                      assist_chunks=["clever", "cliver", "clevar", "clean"]),
        _word_spell_q("g6-e14-5", "G6-E1-4", 6, "hard", "delicious",
                      "听录音，拼写出表示「美味的」多音节形容词：",
                      "de-li-cious 拼写为 d-e-l-i-c-i-o-u-s。",
                      audio_text="delicious",
                      first_letter_hint="d _ _ _ _ _ _ _ s (9个字母)",
                      assist_chunks=["delicious", "delicous", "delitious", "different"]),
        _word_spell_q("g6-e14-6", "G6-E1-4", 6, "hard", "between",
                      "听录音，拼写出表示「在（两者）之间」的介词：",
                      "be-tween 拼写为 b-e-t-w-e-e-n。",
                      audio_text="between",
                      first_letter_hint="b _ _ _ _ _ n (7个字母)",
                      assist_chunks=["between", "betwin", "betwen", "beside"]),
    ]

    # G6-E2-1 交通出行方式与城市建筑
    bank["G6-E2-1"] = [
        _q("g6-e21-1", "G6-E2-1", "reading_choice", "basic",
           "I want to buy a new English dictionary. I should go to the ____.", "bookstore",
           "买字典应该去书店（bookstore）；cinema 是电影院，hospital 是医院。",
           grade=6, options=["cinema", "hospital", "bookstore", "post office"], correct_index=2),
        _q("g6-e21-2", "G6-E2-1", "reading_choice", "basic",
           "My home is very close to our school, so I usually go to school ____.", "on foot",
           "家离学校很近，通常步行上学（on foot）；其他交通工具用 by + 交通工具。",
           grade=6, options=["by plane", "on foot", "by ship", "by train"], correct_index=1),
        _word_tile_q("g6-e21-3", "G6-E2-1", 6, "medium", "subway", "地铁", ["e", "i"],
                     "by subway 意为“乘地铁”，拼写 s-u-b-w-a-y。", seed=621),
        _q("g6-e21-4", "G6-E2-1", "sentence_bank", "medium",
           "选词填空：If you want to send a postcard, you can go to the ____.", "post office",
           "寄明信片（send a postcard）应该去邮局（post office）。",
           grade=6, word_bank=["post office", "science museum", "supermarket", "cinema"]),
        _word_spell_q("g6-e21-5", "G6-E2-1", 6, "hard", "museum",
                      "根据中文「博物馆」与首字母提示拼写城市建筑单词：",
                      "museum 意为“博物馆”，拼写 m-u-s-e-u-m。",
                      first_letter_hint="m _ _ _ _ m (6个字母)",
                      assist_chunks=["museum", "muesum", "musium", "cinema"]),
        _q("g6-e21-6", "G6-E2-1", "listen_choice", "medium",
           "听录音，选出说话人回家采用的绿色出行方式：", "Ride a bike（骑自行车）",
           "录音：I ride my nice bike home.",
           grade=6, options=["By bus（乘公交）", "By taxi（乘出租车）", "Ride a bike（骑自行车）", "By subway（乘地铁）"],
           correct_index=2, audio_text="I ride my nice bike home."),
    ]

    # G6-E2-2 业余爱好与职业理想
    bank["G6-E2-2"] = [
        _q("g6-e22-1", "G6-E2-2", "reading_choice", "basic",
           "My uncle works on a rescue plane. He flies planes. He is a ____.", "pilot",
           "开飞机（flies planes）的职业是飞行员（pilot）。",
           grade=6, options=["pilot", "coach", "fisherman", "postman"], correct_index=0),
        _q("g6-e22-2", "G6-E2-2", "listen_choice", "basic",
           "听录音，选出 Jack 在周末的两项业余爱好：", "Drawing cartoons and playing football",
           "录音：Hi, I am Jack. On the weekend, I love drawing cartoons and playing football.",
           grade=6, options=[
               "Reading stories and doing kung fu",
               "Drawing cartoons and playing football",
               "Singing and dancing",
               "Swimming and climbing mountains",
           ], correct_index=1,
           audio_text="Hi, I am Jack. On the weekend, I love drawing cartoons and playing football."),
        _word_tile_q("g6-e22-3", "G6-E2-2", 6, "medium", "pilot", "飞行员", ["a", "e"],
                     "pilot 意为“飞行员”，拼写 p-i-l-o-t。", seed=622),
        _q("g6-e22-4", "G6-E2-2", "sentence_bank", "medium",
           "选词填空：Sarah likes science very much. She wants to be a ____ in the future.", "scientist",
           "喜欢科学（science），未来想成为一名科学家（scientist）。",
           grade=6, word_bank=["scientist", "singer", "postman", "cleaner"]),
        _word_spell_q("g6-e22-5", "G6-E2-2", 6, "hard", "hobbies",
                      "用 hobby 的复数形式填空：What are Peter's ____ (业余爱好)?",
                      "hobby 以“辅音字母 + y”结尾，变复数改 y 为 i 加 -es -> hobbies。",
                      first_letter_hint="h _ _ _ _ _ s (7个字母)",
                      assist_chunks=["hobbies", "hobbys", "hobbyes", "hobby"]),
        _q("g6-e22-6", "G6-E2-2", "listen_choice", "medium",
           "听问句，选出最符合才艺与爱好语境的回答：", "I can play basketball.",
           "录音问：What can you do for the party? 回答会打篮球或才艺。",
           grade=6, options=["I can play basketball.", "He is a doctor.", "By subway.", "Next Wednesday."],
           correct_index=0, audio_text="What can you do for the party?"),
    ]

    # G6-E2-3 情绪感受与健康就医建议
    bank["G6-E2-3"] = [
        _q("g6-e23-1", "G6-E2-3", "reading_choice", "basic",
           "The mouse is very ____ of the big cat.", "afraid",
           "be afraid of 是固定短语，表示“害怕……”。",
           grade=6, options=["angry", "afraid", "happy", "worried"], correct_index=1),
        _q("g6-e23-2", "G6-E2-3", "reading_choice", "basic",
           "If you feel very angry, you should ____ and count to ten.", "take a deep breath",
           "感到生气时的情绪调节建议：take a deep breath（深呼吸）并数到十。",
           grade=6, options=["take a deep breath", "eat lots of ice cream", "wear a thin T-shirt", "run at a red light"],
           correct_index=0),
        _word_tile_q("g6-e23-3", "G6-E2-3", 6, "medium", "angry", "生气的", ["e", "o"],
                     "angry 意为“生气的”，拼写 a-n-g-r-y。", seed=623),
        _q("g6-e23-4", "G6-E2-3", "sentence_bank", "medium",
           "选词填空：Tom has a bad cold and a fever. He should ____ a doctor.", "see",
           "固定搭配 see a doctor 表示“看医生、就医”。",
           grade=6, word_bank=["see", "look", "watch", "read"]),
        _word_spell_q("g6-e23-5", "G6-E2-3", 6, "hard", "worried",
                      "根据中文「担心的、发愁的」和首字母提示拼写情绪形容词：",
                      "be worried about 表示“为……担心”，拼写 w-o-r-r-i-e-d。",
                      first_letter_hint="w _ _ _ _ _ d (7个字母)",
                      assist_chunks=["worried", "worryed", "woried", "afraid"]),
        _q("g6-e23-6", "G6-E2-3", "listen_tf", "medium",
           "听录音判断：录音中提到那个有趣的宝宝心情很开心（funny / happy）。", "T",
           "录音单词为 happy（开心的）。",
           grade=6, options=["正确 (T)", "错误 (F)"], correct_index=0, audio_text="happy"),
    ]

    # G6-E2-4 假期旅行与今昔变化对比
    bank["G6-E2-4"] = [
        _q("g6-e24-1", "G6-E2-4", "reading_choice", "basic",
           "We went to Sanya last winter holiday and ____ lots of beautiful pictures.", "took",
           "take pictures 表示“拍照”，last winter holiday 是过去时间，用过去式 took。",
           grade=6, options=["take", "takes", "took", "taking"], correct_index=2),
        _q("g6-e24-2", "G6-E2-4", "reading_choice", "basic",
           "Twenty years ago, there was no ____ in my old school. We couldn't play basketball inside on rainy days.", "gym",
           "雨天不能在室内打篮球，说明二十年前学校里没有体育馆（gym）。",
           grade=6, options=["gym", "sky", "river", "moon"], correct_index=0),
        _word_tile_q("g6-e24-3", "G6-E2-4", 6, "medium", "gift", "礼物", ["a", "e"],
                     "buy gifts 意为“买礼物”，gift 拼写 g-i-f-t。", seed=624),
        _q("g6-e24-4", "G6-E2-4", "sentence_bank", "medium",
           "选词填空：Before, I was quiet and short. ____, I am very active and tall in class.", "Now",
           "Before（以前）与 Now（现在）构成今昔变化对比。",
           grade=6, word_bank=["Now", "Ago", "Yesterday", "Last"]),
        _word_spell_q("g6-e24-5", "G6-E2-4", 6, "hard", "bought",
                      "写出动词 buy（购买）的不规则过去式（提示：假期买礼物 ____ gifts）：",
                      "buy 的过去式是 bought（b-o-u-g-h-t）。",
                      first_letter_hint="b _ _ _ _ t (6个字母)",
                      assist_chunks=["bought", "buyed", "brought", "buys"]),
        _q("g6-e24-6", "G6-E2-4", "listen_tf", "medium",
           "听录音判断：这座自然公园里没有任何高楼大厦。", "F",
           "录音是疑问句 Are there any tall buildings in the park? 并非肯定陈述句；若问是否提问高楼，注意审题：录音是在询问公园里有没有高楼。",
           grade=6, options=["录音是在提问公园里是否有高楼 (T)", "录音说公园里有一百栋高楼 (F)"],
           correct_index=0, audio_text="Are there any tall buildings in the park?"),
    ]

    # G6-E3-1 一般将来时（be going to / will）
    bank["G6-E3-1"] = [
        _q("g6-e31-1", "G6-E3-1", "sentence_bank", "basic",
           "选词填空：I am going to ____ my grandparents this evening.", "visit",
           "be going to 后面接动词原形 visit。",
           grade=6, word_bank=["visit", "visits", "visited", "visiting"]),
        _q("g6-e31-2", "G6-E3-1", "reading_choice", "basic",
           "They ____ have an art lesson tomorrow morning.", "are going to",
           "tomorrow morning 表将来，主语 They 为复数，用 are going to（或 will）。",
           grade=6, options=["is going to", "are going to", "am going to", "went to"], correct_index=1),
        _q("g6-e31-3", "G6-E3-1", "reading_choice", "medium",
           "— What are you going to do next weekend?  — ____", "I'm going to see a film.",
           "问句用 be going to 询问下周末计划，答语也用 I'm going to...",
           grade=6, options=[
               "I went to the park.",
               "I'm going to see a film.",
               "I'm reading a book now.",
               "Yes, I am.",
           ], correct_index=1),
        _q("g6-e31-4", "G6-E3-1", "sentence_fill", "medium",
           "用所给动词的适当形式填空：She will ____ (take) a trip to Hangzhou next month.", "take",
           "助动词 will 后面接动词原形 take。",
           grade=6, first_letter_hint="t _ _ e (4个字母)", assist_chunks=["take", "takes", "took", "taking"]),
        _sentence_order_q("g6-e31-5", "G6-E3-1", 6, "hard",
                          ["Where", "are", "you", "going", "tonight?"],
                          "Where are you going tonight?",
                          "你今晚打算去哪里？",
                          "一般将来时特殊疑问句：Where + are + you + going + 将来时间?", seed=631),
        _q("g6-e31-6", "G6-E3-1", "sentence_fill", "hard",
           "用 be 动词（am / is / are）填空：____ your brother going to play basketball tomorrow?", "Is",
           "主语 your brother 是第三人称单数，句首首字母大写填 Is。",
           grade=6, first_letter_hint="I _ (2个字母)", assist_chunks=["Is", "Are", "Am", "Do"],
           accept_answers=["Is"]),
    ]

    # G6-E3-2 一般过去时（规则与高频不规则动词）
    bank["G6-E3-2"] = [
        _q("g6-e32-1", "G6-E3-2", "sentence_bank", "basic",
           "选词填空：Mike ____ his room and washed his clothes yesterday.", "cleaned",
           "yesterday 是过去时间标志词，clean 的过去式是 cleaned。",
           grade=6, word_bank=["cleaned", "clean", "cleans", "cleaning"]),
        _q("g6-e32-2", "G6-E3-2", "reading_choice", "basic",
           "— Did you go to Turpan last summer?  — ____", "Yes, we did.",
           "Did you...? 引导的一般过去时疑问句，肯定回答是 Yes, I/we did.",
           grade=6, options=["Yes, we do.", "Yes, we did.", "Yes, we were.", "No, we don't."], correct_index=1),
        _q("g6-e32-3", "G6-E3-2", "reading_choice", "medium",
           "We didn't ____ cycling yesterday because it rained all day.", "go",
           "助动词 didn't 后面必须还原为动词原形 go。",
           grade=6, options=["go", "went", "goes", "going"], correct_index=0),
        _q("g6-e32-4", "G6-E3-2", "sentence_fill", "medium",
           "用所给词的适当形式填空：I ____ (see) an interesting film with my parents last night.", "saw",
           "last night 表示昨晚（过去时），see 的不规则过去式是 saw。",
           grade=6, first_letter_hint="s _ w (3个字母)", assist_chunks=["saw", "seed", "sees", "seen"]),
        _q("g6-e32-5", "G6-E3-2", "sentence_fill", "hard",
           "用所给词的适当形式填空：There ____ (be) no tall buildings in this village ten years ago.", "were",
           "ten years ago 表过去，主语 tall buildings 是复数，There be 的过去式复数用 were。",
           grade=6, first_letter_hint="w _ _ e (4个字母)", assist_chunks=["were", "was", "are", "is"]),
        _sentence_order_q("g6-e32-6", "G6-E3-2", 6, "hard",
                          ["What", "did", "you", "do", "last", "weekend?"],
                          "What did you do last weekend?",
                          "你上周末做了什么？",
                          "一般过去时特殊疑问句：What + did + 主语 + do + 过去时间?", seed=632),
    ]

    # G6-E3-3 形容词与副词比较级（-er / more）
    bank["G6-E3-3"] = [
        _q("g6-e33-1", "G6-E3-3", "sentence_bank", "basic",
           "选词填空：I am 1.65 metres. My sister is 1.60 metres. I am ____ than her.", "taller",
           "标志词 than 提示使用比较级，tall 的比较级是 taller。",
           grade=6, word_bank=["taller", "tall", "tallest", "short"]),
        _q("g6-e33-2", "G6-E3-3", "reading_choice", "basic",
           "An elephant is much ____ than a monkey.", "heavier",
           "heavy 以“辅音字母 + y”结尾，变比较级改 y 为 i 加 -er -> heavier。",
           grade=6, options=["heavy", "heavier", "heavyer", "more heavy"], correct_index=1),
        _q("g6-e33-3", "G6-E3-3", "reading_choice", "medium",
           "Look! Your feet are bigger than ____.", "mine",
           "比较对象必须一致：你的脚（Your feet）和“我的脚（mine = my feet）”比较。",
           grade=6, options=["I", "my", "me", "mine"], correct_index=3),
        _q("g6-e33-4", "G6-E3-3", "sentence_fill", "medium",
           "用所给形容词的比较级填空：Summer is ____ (hot) than spring.", "hotter",
           "hot 是重读闭音节词（辅元辅），双写末尾 t 再加 -er -> hotter。",
           grade=6, first_letter_hint="h _ _ _ _ r (6个字母)", assist_chunks=["hotter", "hoter", "more hot", "hottest"]),
        _q("g6-e33-5", "G6-E3-3", "sentence_fill", "hard",
           "用所给词的比较级填空：Who is ____ (thin), Amy or Sarah?", "thinner",
           "两者（Amy or Sarah）比较用比较级，thin 双写 n 加 -er -> thinner。",
           grade=6, first_letter_hint="t _ _ _ _ _ r (7个字母)", assist_chunks=["thinner", "thiner", "thin", "thinnest"]),
        _sentence_order_q("g6-e33-6", "G6-E3-3", 6, "hard",
                          ["You", "are", "older", "than", "me."],
                          "You are older than me.",
                          "你比我年纪大。",
                          "比较级核心句型：A + be + 比较级 + than + B.", seed=633),
    ]

    # G6-E3-4 祈使句与情态动词 should / must
    bank["G6-E3-4"] = [
        _q("g6-e34-1", "G6-E3-4", "sentence_bank", "basic",
           "选词填空：It's a red light now. We ____ stop and wait.", "must",
           "交通规则红灯必须停下等待，用语气最强的情态动词 must（必须）。",
           grade=6, word_bank=["must", "can't", "would", "aren't"]),
        _q("g6-e34-2", "G6-E3-4", "reading_choice", "basic",
           "____ go at the red light! It's very dangerous.", "Don't",
           "否定祈使句以 Don't + 动词原形开头，表示“不要闯红灯！”。",
           grade=6, options=["Not", "No", "Don't", "Doesn't"], correct_index=2),
        _q("g6-e34-3", "G6-E3-4", "reading_choice", "medium",
           "You feel cold. You should ____ warm clothes.", "wear",
           "情态动词 should 后面接动词原形 wear。",
           grade=6, options=["wear", "wears", "wearing", "wore"], correct_index=0),
        _q("g6-e34-4", "G6-E3-4", "sentence_fill", "medium",
           "用所给动词的适当形式填空：Please ____ (turn) left at the hospital.", "turn",
           "祈使句 Please 后直接用动词原形 turn。",
           grade=6, first_letter_hint="t _ _ n (4个字母)", assist_chunks=["turn", "turns", "turned", "turning"]),
        _sentence_order_q("g6-e34-5", "G6-E3-4", 6, "hard",
                          ["Slow", "down", "and", "stop", "at", "a", "yellow", "light."],
                          "Slow down and stop at a yellow light.",
                          "黄灯时请减速并停下。",
                          "肯定祈使句：Slow down and stop + 介词短语 at a yellow light.", seed=634),
        _q("g6-e34-6", "G6-E3-4", "sentence_fill", "hard",
           "根据交通标志常识填空：____ (Do not 的缩写) touch the door in the subway!", "Don't",
           "否定祈使句句首用 Don't（首字母大写）。",
           grade=6, first_letter_hint="D _ _ ' t (5个字符)", assist_chunks=["Don't", "Doesn't", "Didn't", "Not"],
           accept_answers=["Don't", "Do not"]),
    ]

    # G6-E4-1 问路指路与交通规则交际
    bank["G6-E4-1"] = [
        _q("g6-e41-1", "G6-E4-1", "reading_choice", "basic",
           "— Excuse me, how can I get to the science museum?  — ____",
           "Go straight and turn right at the cinema.",
           "How can I get to...? 询问怎么去某地，应回答指路路线（直走并在电影院右转）。",
           grade=6, options=[
               "Go straight and turn right at the cinema.",
               "It's a big museum.",
               "I'm going there tomorrow.",
               "Yes, there is.",
           ], correct_index=0),
        _q("g6-e41-2", "G6-E4-1", "reading_choice", "basic",
           "— How do you come to school every day?  — ____", "I usually come by bike.",
           "How do you come to school? 询问上学交通方式，回答 I usually come by bike.",
           grade=6, options=[
               "I usually come by bike.",
               "At 7:30 in the morning.",
               "Turn left at the bookstore.",
               "Because it's near.",
           ], correct_index=0),
        _q("g6-e41-3", "G6-E4-1", "sentence_bank", "medium",
           "补全交通规则交际：In the USA, people on bikes must wear a ____.", "helmet",
           "骑自行车必须佩戴头盔（helmet）以保护安全。",
           grade=6, word_bank=["helmet", "scarf", "skirt", "dictionary"]),
        _q("g6-e41-4", "G6-E4-1", "listen_choice", "medium",
           "听录音，选出录音中提到的过河建筑物：", "bridge（桥）",
           "录音单词是 bridge（桥）。",
           grade=6, options=["bridge（桥）", "hospital（医院）", "factory（工厂）", "hotel（酒店）"],
           correct_index=0, audio_text="bridge"),
        _sentence_order_q("g6-e41-5", "G6-E4-1", 6, "hard",
                          ["How", "can", "we", "get", "there?"],
                          "How can we get there?",
                          "我们怎样才能到达那里？",
                          "问路高频句型：How can we get there?（get there 中间不加 to）。", seed=641),
        _q("g6-e41-6", "G6-E4-1", "reading_choice", "medium",
           "— Is the post office far from here?  — ____ You can walk there in three minutes.",
           "No, it isn't.",
           "走路三分钟就能到，说明不远，回答 No, it isn't.",
           grade=6, options=["Yes, it is.", "No, it isn't.", "No, there isn't.", "Yes, I can."], correct_index=1),
    ]

    # G6-E4-2 周末假期计划与过去经历对话
    bank["G6-E4-2"] = [
        _q("g6-e42-1", "G6-E4-2", "reading_choice", "basic",
           "— How was your weekend, Chen Jie?  — ____", "It was good, thank you.",
           "How was your weekend? 询问刚过去的周末过得怎么样，用过去式回答 It was good.",
           grade=6, options=[
               "It was good, thank you.",
               "I'm going to the park.",
               "By train.",
               "He is a pilot.",
           ], correct_index=0),
        _q("g6-e42-2", "G6-E4-2", "reading_choice", "basic",
           "— Where did you go over your winter holiday?  — ____", "I went to Harbin with my family.",
           "Where did you go...? 询问过去去了哪里，回答应包含过去式 went + 地点。",
           grade=6, options=[
               "I went to Harbin with my family.",
               "I bought some gifts.",
               "I go there by plane.",
               "Next Monday.",
           ], correct_index=0),
        _q("g6-e42-3", "G6-E4-2", "sentence_bank", "medium",
           "补全对话：— ____ are you going to buy in the bookstore?  — A comic book.", "What",
           "答语是物品 A comic book（一本漫画书），提问“买什么”用 What。",
           grade=6, word_bank=["What", "Where", "When", "How"]),
        _q("g6-e42-4", "G6-E4-2", "reading_choice", "medium",
           "— When are you going to the cinema?  — ____", "This evening.",
           "When 提问时间，be going to 表将来，选将来时间短语 This evening.",
           grade=6, options=["Yesterday morning.", "This evening.", "To the bookstore.", "By bus."],
           correct_index=1),
        _q("g6-e42-5", "G6-E4-2", "listen_choice", "medium",
           "听录音，判断说话人周六上午常和谁一起踢足球？", "With his friends（和他的朋友们）",
           "录音：I often play football with my friends on Saturday morning.",
           grade=6, options=[
               "With his parents",
               "With his friends（和他的朋友们）",
               "With his art teacher",
               "By himself",
           ], correct_index=1,
           audio_text="I often play football with my friends on Saturday morning."),
        _sentence_order_q("g6-e42-6", "G6-E4-2", 6, "hard",
                          ["How", "did", "you", "go", "there?"],
                          "How did you go there?",
                          "你是怎么去那里的？",
                          "询问过去出行方式：How + did + you + go there?", seed=642),
    ]

    # G6-E4-3 跨时态长短文阅读与推理判断
    p_g6_cross = (
        "Hello, I'm Wu Binbin. Five years ago, I was short and quiet. I couldn't ride a bike well. "
        "Now I am 1.64 metres tall, and I go cycling with my friends every weekend. "
        "Last Saturday, we rode bikes to Green Forest Park and took many pictures. "
        "Tomorrow is Sunday. I am going to visit the science museum by subway. I want to see the talking robots!"
    )
    bank["G6-E4-3"] = [
        _q("g6-e43-1", "G6-E4-3", "reading_choice", "basic",
           "阅读跨时态短文，五年前（Five years ago）Wu Binbin 是怎样的？", "Short and quiet, and couldn't ride a bike well",
           "原文第二句：Five years ago, I was short and quiet. I couldn't ride a bike well.",
           grade=6, options=[
               "1.64 metres tall and very active",
               "Short and quiet, and couldn't ride a bike well",
               "Went cycling every weekend",
               "Worked in a science museum",
           ], correct_index=1, passage=p_g6_cross),
        _q("g6-e43-2", "G6-E4-3", "reading_choice", "basic",
           "根据短文，Wu Binbin 上周六（Last Saturday）去了哪里？", "Green Forest Park",
           "原文：Last Saturday, we rode bikes to Green Forest Park and took many pictures.",
           grade=6, options=["The science museum", "The bookstore", "Green Forest Park", "The cinema"],
           correct_index=2, passage=p_g6_cross),
        _q("g6-e43-3", "G6-E4-3", "reading_choice", "medium",
           "根据短文，Wu Binbin 明天（Tomorrow）打算怎么去科学博物馆？", "By subway（乘地铁）",
           "原文：I am going to visit the science museum by subway.",
           grade=6, options=["By bike", "On foot", "By subway（乘地铁）", "By bus"],
           correct_index=2, passage=p_g6_cross),
        _q("g6-e43-4", "G6-E4-3", "reading_choice", "medium",
           "阅读推理判断：Wu Binbin likes riding a bike now.", "正确 (T)",
           "原文提到 Now... I go cycling with my friends every weekend，说明他现在很喜欢骑行。",
           grade=6, options=["正确 (T)", "错误 (F)"], correct_index=0, passage=p_g6_cross),
        _q("g6-e43-5", "G6-E4-3", "listen_choice", "hard",
           "听录音，选出录音中关于 Jack 周末爱好的正确信息：", "He loves drawing cartoons and playing football.",
           "录音：Hi, I am Jack. On the weekend, I love drawing cartoons and playing football.",
           grade=6, options=[
               "He loves playing the piano and swimming.",
               "He loves drawing cartoons and playing football.",
               "He hates sports on the weekend.",
               "He only watches TV at home.",
           ], correct_index=1,
           audio_text="Hi, I am Jack. On the weekend, I love drawing cartoons and playing football."),
        _q("g6-e43-6", "G6-E4-3", "listen_tf", "hard",
           "听录音判断：Leo 在学校里表现得很懒惰，从不帮助同学。", "F",
           "录音：Leo is hard-working and helpful at school. 他既勤奋又乐于助人，题干说法错误。",
           grade=6, options=["正确 (T)", "错误 (F)"], correct_index=1,
           audio_text="Leo is hard-working and helpful at school."),
    ]

    # G6-E4-4 小升初完形选词与语境综合推断
    cloze_g6_1 = (
        "Last summer holiday, Lisa went to Xinjiang with her parents. "
        "They went there by plane because it is very far from their city. "
        "They ____ sweet grapes and rode horses there."
    )
    cloze_g6_2 = (
        "Next month, we are going to leave our primary school and go to middle school. "
        "We feel a little sad to say goodbye, ____ we are also excited about our new school life!"
    )
    bank["G6-E4-4"] = [
        _q("g6-e44-1", "G6-E4-4", "sentence_bank", "basic",
           "结合短文过去时语境完形选词（吃了甜葡萄）：", "ate",
           "短文讲述 Last summer holiday 的经历，时态为一般过去时，eat 的过去式是 ate。",
           grade=6, word_bank=["ate", "eat", "eats", "eating"], passage=cloze_g6_1),
        _q("g6-e44-2", "G6-E4-4", "sentence_bank", "basic",
           "结合毕业短文语境选出最恰当的连词：", "but",
           "前半句“有点伤感（a little sad）”与后半句“也很兴奋（also excited）”构成转折关系，填 but。",
           grade=6, word_bank=["but", "because", "or", "so"], passage=cloze_g6_2),
        _q("g6-e44-3", "G6-E4-4", "reading_choice", "medium",
           "David wants to be strong and healthy, so he ____ every day.", "does more exercise",
           "想要变得强壮健康，应该每天多锻炼（does more exercise）。",
           grade=6, options=[
               "eats lots of candy",
               "goes to bed very late",
               "does more exercise",
               "never eats vegetables",
           ], correct_index=2),
        _q("g6-e44-4", "G6-E4-4", "reading_choice", "medium",
           "It's 7:50 a.m. School starts at 8:00 a.m., and the bus is still not here. Sarah feels ____.", "worried",
           "还有 10 分钟就上课了但公交车还没来，推断 Sarah 心情是焦急担心的（worried）。",
           grade=6, options=["happy", "worried", "excited", "polite"], correct_index=1),
        _q("g6-e44-5", "G6-E4-4", "sentence_fill", "hard",
           "语境综合词形填空：Yesterday was my mother's birthday. I ____ (make) a birthday card for her.", "made",
           "Yesterday 提示一般过去时，make 的不规则过去式是 made。",
           grade=6, first_letter_hint="m _ _ e (4个字母)", assist_chunks=["made", "maked", "makes", "making"]),
        _q("g6-e44-6", "G6-E4-4", "reading_choice", "hard",
           "Look at the traffic sign: a bicycle inside a red circle with a slash (斜杠). It means: ____",
           "No bikes! / Don't ride a bike here.",
           "红色圆圈加斜杠盖住自行车代表禁止骑自行车通行（No bikes!）。",
           grade=6, options=[
               "You must ride a bike here.",
               "No bikes! / Don't ride a bike here.",
               "There is a bike shop.",
               "Turn right here.",
           ], correct_index=1),
    ]

    return bank


# ==============================================================================
# G3 / G4 / G6 听说读写 4 大专项定义（共 12 个新增专项）
# ==============================================================================
ENGLISH_G3_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g3-listening-sprint",
        "subject": "英语",
        "grade": 3,
        "ability": "listening",
        "abilityLabel": "听",
        "title": "听 · 三年级启蒙听力专项",
        "subtitle": "字母起始音、核心词汇与日常简短交际听辨，每题限播 3 遍 + 单题 25 秒宽松作答",
        "icon": "🎧",
        "timingMode": "per_question",
        "perQuestionSec": 25,
        "maxPlays": 3,
        "timeLimitSec": 450,
        "questionCount": 10,
        "nodeKeys": [
            "G3-E1-1", "G3-E1-2", "G3-E1-3", "G3-E1-4",
            "G3-E2-1", "G3-E2-2", "G3-E2-3", "G3-E2-4",
            "G3-E3-1", "G3-E3-3", "G3-E3-4", "G3-E4-2", "G3-E4-3", "G3-E4-4",
        ],
        "typeMix": {"listen_choice": 7, "listen_tf": 3},
    },
    {
        "slug": "g3-speaking-phonics-sprint",
        "subject": "英语",
        "grade": 3,
        "ability": "speaking",
        "abilityLabel": "说",
        "title": "说 · 三年级自然拼读与跟读专项",
        "subtitle": "26字母、五个短元音与 CVC 简单词拼读跟读，每题限播 3 遍 + 单题 25 秒启蒙节奏",
        "icon": "🎙️",
        "timingMode": "per_question",
        "perQuestionSec": 25,
        "maxPlays": 3,
        "timeLimitSec": 450,
        "questionCount": 10,
        "nodeKeys": ["G3-E1-1", "G3-E1-2", "G3-E1-3", "G3-E1-4", "G3-E4-1", "G3-E4-2"],
        "typeMix": {"phonics_choice": 6, "speak_read": 4},
    },
    {
        "slug": "g3-reading-sprint",
        "subject": "英语",
        "grade": 3,
        "ability": "reading",
        "abilityLabel": "读",
        "title": "读 · 三年级日常交际与绘本专项",
        "subtitle": "礼貌问候、分享食物、询问年龄数量与启蒙绘本短篇，10 分钟整体倒计时",
        "icon": "📖",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": [
            "G3-E2-1", "G3-E2-2", "G3-E2-3", "G3-E2-4",
            "G3-E3-1", "G3-E3-2", "G3-E3-3", "G3-E3-4",
            "G3-E4-1", "G3-E4-2", "G3-E4-3", "G3-E4-4",
        ],
        "typeMix": {"reading_choice": 7, "sentence_bank": 3},
    },
    {
        "slug": "g3-writing-sprint",
        "subject": "英语",
        "grade": 3,
        "ability": "writing",
        "abilityLabel": "写",
        "title": "写 · 三年级拼块拼词与启蒙连词专项",
        "subtitle": "字母拼块、词池选词、带辅助块单词拼写与启蒙连词成句，适配三年级认知",
        "icon": "✍️",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 3,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": [
            "G3-E1-1", "G3-E1-2", "G3-E1-3", "G3-E1-4",
            "G3-E2-1", "G3-E2-2", "G3-E2-3", "G3-E2-4",
            "G3-E3-1", "G3-E3-2", "G3-E3-3", "G3-E3-4",
            "G3-E4-2", "G3-E4-3",
        ],
        "typeMix": {"word_tiles": 3, "sentence_bank": 2, "word_spell": 3, "sentence_order": 2},
    },
]

ENGLISH_G4_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g4-listening-sprint",
        "subject": "英语",
        "grade": 4,
        "ability": "listening",
        "abilityLabel": "听",
        "title": "听 · 四年级校园与生活听力专项",
        "subtitle": "开音节听辨、天气作息、校园问路与农场词汇，每题限播 2 遍 + 单题 22 秒过渡节奏",
        "icon": "🎧",
        "timingMode": "per_question",
        "perQuestionSec": 22,
        "maxPlays": 2,
        "timeLimitSec": 400,
        "questionCount": 10,
        "nodeKeys": [
            "G4-E1-1", "G4-E1-2", "G4-E1-3", "G4-E1-4",
            "G4-E2-1", "G4-E2-2", "G4-E2-3", "G4-E2-4",
            "G4-E3-1", "G4-E3-2", "G4-E3-3",
            "G4-E4-1", "G4-E4-2", "G4-E4-4",
        ],
        "typeMix": {"listen_choice": 7, "listen_tf": 3},
    },
    {
        "slug": "g4-speaking-phonics-sprint",
        "subject": "英语",
        "grade": 4,
        "ability": "speaking",
        "abilityLabel": "说",
        "title": "说 · 四年级开音节与组合辨音专项",
        "subtitle": "相对开音节、r音节（ar/er/ir/or/ur）与 al/le/ow 辨音跟读，单题 22 秒 + 限播 2 遍",
        "icon": "🎙️",
        "timingMode": "per_question",
        "perQuestionSec": 22,
        "maxPlays": 2,
        "timeLimitSec": 400,
        "questionCount": 10,
        "nodeKeys": ["G4-E1-1", "G4-E1-2", "G4-E1-3", "G4-E1-4", "G4-E4-3"],
        "typeMix": {"phonics_choice": 7, "speak_read": 3},
    },
    {
        "slug": "g4-reading-sprint",
        "subject": "英语",
        "grade": 4,
        "ability": "reading",
        "abilityLabel": "读",
        "title": "读 · 四年级校园购物与短文阅读专项",
        "subtitle": "天气穿衣交际、校园场所问路、商店询价试穿与农场短文理解，10 分钟整体倒计时",
        "icon": "📖",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": [
            "G4-E2-1", "G4-E2-2", "G4-E2-3", "G4-E2-4",
            "G4-E3-1", "G4-E3-2", "G4-E3-3", "G4-E3-4",
            "G4-E4-1", "G4-E4-2", "G4-E4-3", "G4-E4-4",
        ],
        "typeMix": {"reading_choice": 7, "sentence_bank": 3},
    },
    {
        "slug": "g4-writing-sprint",
        "subject": "英语",
        "grade": 4,
        "ability": "writing",
        "abilityLabel": "写",
        "title": "写 · 四年级首字母拼词与语法造句专项",
        "subtitle": "首字母提示单词拼写、方位/时间/所有格填空与连词成句，11 分钟整体倒计时",
        "icon": "✍️",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 2,
        "timeLimitSec": 660,
        "questionCount": 10,
        "nodeKeys": [
            "G4-E1-1", "G4-E1-2", "G4-E1-3", "G4-E1-4",
            "G4-E2-1", "G4-E2-2", "G4-E2-3", "G4-E2-4",
            "G4-E3-1", "G4-E3-2", "G4-E3-3", "G4-E3-4",
            "G4-E4-1", "G4-E4-2", "G4-E4-3",
        ],
        "typeMix": {"word_spell": 3, "sentence_fill": 4, "sentence_order": 3},
    },
]

ENGLISH_G6_SPRINTS: list[dict[str, Any]] = [
    {
        "slug": "g6-listening-sprint",
        "subject": "英语",
        "grade": 6,
        "ability": "listening",
        "abilityLabel": "听",
        "title": "听 · 六年级小升初听力综合专项",
        "subtitle": "核心词听辨、日常交通与爱好问答、跨时态语篇听力理解，每题限播 2 遍 + 单题 20 秒",
        "icon": "🎧",
        "timingMode": "per_question",
        "perQuestionSec": 20,
        "maxPlays": 2,
        "timeLimitSec": 360,
        "questionCount": 10,
        "nodeKeys": [
            "G6-E1-2", "G6-E1-3", "G6-E1-4",
            "G6-E2-1", "G6-E2-2", "G6-E2-3", "G6-E2-4",
            "G6-E4-1", "G6-E4-2", "G6-E4-3",
        ],
        "typeMix": {"listen_choice": 7, "listen_tf": 3},
    },
    {
        "slug": "g6-speaking-phonics-sprint",
        "subject": "英语",
        "grade": 6,
        "ability": "speaking",
        "abilityLabel": "说",
        "title": "说 · 六年级尾音重音与语调跟读专项",
        "subtitle": "过去式 -ed 尾音、不发音字母 kn/wr、多音节重音与升降调跟读，单题 20 秒 + 限播 2 遍",
        "icon": "🎙️",
        "timingMode": "per_question",
        "perQuestionSec": 20,
        "maxPlays": 2,
        "timeLimitSec": 360,
        "questionCount": 10,
        "nodeKeys": ["G6-E1-1", "G6-E1-2", "G6-E1-3", "G6-E1-4"],
        "typeMix": {"phonics_choice": 7, "speak_read": 3},
    },
    {
        "slug": "g6-reading-sprint",
        "subject": "英语",
        "grade": 6,
        "ability": "reading",
        "abilityLabel": "读",
        "title": "读 · 六年级跨时态阅读与完形专项",
        "subtitle": "问路指路交际、一般将来/过去时对话、跨时态长短文推理与小升初完形，10 分钟整体倒计时",
        "icon": "📖",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 0,
        "timeLimitSec": 600,
        "questionCount": 10,
        "nodeKeys": [
            "G6-E2-1", "G6-E2-2", "G6-E2-3", "G6-E2-4",
            "G6-E3-1", "G6-E3-2", "G6-E3-3", "G6-E3-4",
            "G6-E4-1", "G6-E4-2", "G6-E4-3", "G6-E4-4",
        ],
        "typeMix": {"reading_choice": 7, "sentence_bank": 3},
    },
    {
        "slug": "g6-writing-sprint",
        "subject": "英语",
        "grade": 6,
        "ability": "writing",
        "abilityLabel": "写",
        "title": "写 · 六年级小升初词汇与多时态语法专项",
        "subtitle": "高频核心词拼写、过去式/将来时/比较级严判填空与连词成句，12 分钟整体倒计时",
        "icon": "✍️",
        "timingMode": "overall",
        "perQuestionSec": 0,
        "maxPlays": 2,
        "timeLimitSec": 720,
        "questionCount": 10,
        "nodeKeys": [
            "G6-E1-1", "G6-E1-2", "G6-E1-4",
            "G6-E2-1", "G6-E2-2", "G6-E2-3", "G6-E2-4",
            "G6-E3-1", "G6-E3-2", "G6-E3-3", "G6-E3-4",
            "G6-E4-1", "G6-E4-2", "G6-E4-4",
        ],
        "typeMix": {"word_spell": 3, "sentence_fill": 4, "sentence_order": 3},
    },
]

GRADE_SPRINTS_MAP: dict[int, list[dict[str, Any]]] = {
    3: ENGLISH_G3_SPRINTS,
    4: ENGLISH_G4_SPRINTS,
    6: ENGLISH_G6_SPRINTS,
}

G3_QUESTION_BANK = _build_g3_questions()
G4_QUESTION_BANK = _build_g4_questions()
G6_QUESTION_BANK = _build_g6_questions()

EXTRA_QUESTION_BANKS: dict[int, dict[str, list[dict[str, Any]]]] = {
    3: G3_QUESTION_BANK,
    4: G4_QUESTION_BANK,
    6: G6_QUESTION_BANK,
}

__all__ = [
    "ENGLISH_DOMAINS",
    "ENGLISH_G3_NODES",
    "ENGLISH_G3_SPRINTS",
    "ENGLISH_G4_NODES",
    "ENGLISH_G4_SPRINTS",
    "ENGLISH_G6_NODES",
    "ENGLISH_G6_SPRINTS",
    "EXTRA_QUESTION_BANKS",
    "G3_QUESTION_BANK",
    "G4_QUESTION_BANK",
    "G6_QUESTION_BANK",
    "GRADE_NODES_MAP",
    "GRADE_SPRINTS_MAP",
    "make_default_assist_chunks",
    "make_first_letter_hint",
]
