"""英语通用知识地图（去教材版本强绑定）与多题型自带题引擎.

设计原则：
- 按小学五年级通用课标核心知识域组织 4 大岛屿、16 个节点（语音与自然拼读 / 核心高频词汇 / 核心语法与句型 / 情景交际与语篇），不强绑定教材版本。
- 支持 10 类英语核心题型：
  - 地图轻辅助：listen_choice（听音选择）、phonics_choice（辨音/拼读选择）、word_tiles（字母拼块单词填空）、sentence_bank（词池点选句子填空）、reading_choice（情景/阅读单选）。
  - 专项强应试：listen_tf（听音判断）、speak_read（示范跟读/语音识别，老设备可降级辨音）、word_spell（键盘单词拼写/首字母填空）、sentence_fill（键盘语法/词形填空）、sentence_order（连词成句词块排序）。
- 所有带音频题目均声明确定性 audioId 与 audioText，由 scripts/build_english_arena_audio.py 离线预生成静态 MP3。
"""
from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Iterable

SUBJECT_ENGLISH = "英语"
DEFAULT_GRADE = 5

LIGHT_STATES = {
    "unexplored": "未探索",
    "exploring": "探索中",
    "lit": "已点亮",
    "mastered": "精通",
}

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

MAP_FRIENDLY_TYPES = {
    "listen_choice",
    "phonics_choice",
    "word_tiles",
    "sentence_bank",
    "reading_choice",
    "listen_tf",
}

ENGLISH_G5_DOMAINS: list[dict[str, Any]] = [
    {"id": "phonics", "name": "语音与自然拼读", "icon": "🔊", "color": "#a8242e"},
    {"id": "vocab", "name": "核心高频词汇", "icon": "🔤", "color": "#1e6b52"},
    {"id": "grammar", "name": "核心语法与句型", "icon": "🧩", "color": "#b4690e"},
    {"id": "reading", "name": "情景交际与语篇", "icon": "📖", "color": "#2f4f8f"},
]

ENGLISH_G5_NODES: list[dict[str, Any]] = [
    # E1 语音与自然拼读
    {"key": "E1-1", "name": "元音字母与开闭音节", "domain": "phonics", "icon": "🎵"},
    {"key": "E1-2", "name": "常见元音组合（ee/ea/oo/ow/ou）", "domain": "phonics", "icon": "🎶"},
    {"key": "E1-3", "name": "辅音组合发音（ch/sh/th/wh/ng）", "domain": "phonics", "icon": "🗣️"},
    {"key": "E1-4", "name": "自然拼读听音拼词", "domain": "phonics", "icon": "✨"},
    # E2 核心高频词汇
    {"key": "E2-1", "name": "人物性格与日常职业", "domain": "vocab", "icon": "🧑‍🤝‍🧑"},
    {"key": "E2-2", "name": "饮食口味与健康生活", "domain": "vocab", "icon": "🥗"},
    {"key": "E2-3", "name": "星期课程与周末活动", "domain": "vocab", "icon": "📅"},
    {"key": "E2-4", "name": "居家方位与自然景物", "domain": "vocab", "icon": "🏞️"},
    # E3 核心语法与句型
    {"key": "E3-1", "name": "be 动词与人称代词", "domain": "grammar", "icon": "🔗"},
    {"key": "E3-2", "name": "名词单复数与 a/an/some/any", "domain": "grammar", "icon": "📦"},
    {"key": "E3-3", "name": "一般现在时与三单/频率副词", "domain": "grammar", "icon": "⏱️"},
    {"key": "E3-4", "name": "情态动词 can 与 There be 句型", "domain": "grammar", "icon": "🏗️"},
    # E4 情景交际与语篇
    {"key": "E4-1", "name": "日常问答与礼貌交际", "domain": "reading", "icon": "💬"},
    {"key": "E4-2", "name": "特殊疑问句（What/Where/When/Who）", "domain": "reading", "icon": "❓"},
    {"key": "E4-3", "name": "短文细节定位与判断", "domain": "reading", "icon": "🔍"},
    {"key": "E4-4", "name": "完形选词与语境推断", "domain": "reading", "icon": "📝"},
]

NODE_BY_KEY = {n["key"]: n for n in ENGLISH_G5_NODES}
DOMAIN_BY_ID = {d["id"]: d for d in ENGLISH_G5_DOMAINS}


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


def _q(
    qid: str,
    node_key: str,
    qtype: str,
    level: str,
    text: str,
    answer: str,
    explanation: str,
    *,
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
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": qid,
        "nodeKey": node_key,
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
    return item


def _word_tile_q(
    qid: str,
    node_key: str,
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
        tiles=tiles,
        hint=f"首字母 {word[0]}，共 {len(word)} 个字母",
        audio_text=audio_text or word,
    )


def _word_spell_q(
    qid: str,
    node_key: str,
    level: str,
    word: str,
    prompt: str,
    explanation: str,
    *,
    hint: str = "",
    audio_text: str | None = None,
) -> dict[str, Any]:
    return _q(
        qid,
        node_key,
        "word_spell",
        level,
        prompt,
        word,
        explanation,
        hint=hint,
        audio_text=audio_text,
    )


def _sentence_order_q(
    qid: str,
    node_key: str,
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
        word_bank=shuffled,
        hint="注意句首首字母与句末标点",
    )


def _build_question_bank() -> dict[str, list[dict[str, Any]]]:
    bank: dict[str, list[dict[str, Any]]] = {n["key"]: [] for n in ENGLISH_G5_NODES}

    # ---------------- E1-1 元音字母与开闭音节 ----------------
    bank["E1-1"] = [
        _q("e11-1", "E1-1", "phonics_choice", "basic",
           "选出划线部分发音不同的一项：", "cat",
           "cake / name / lake 中 a 在开音节发 /eɪ/，cat 中 a 在闭音节发 /æ/。",
           options=["c[a]ke", "n[a]me", "c[a]t", "l[a]ke"], correct_index=2,
           audio_text="cake, name, cat, lake"),
        _q("e11-2", "E1-1", "listen_choice", "basic",
           "听录音，选出你听到的单词：", "bike",
           "bike 中字母 i 在开音节发字母本身音 /aɪ/，与 big /ɪ/ 不同。",
           options=["big", "bike", "bit", "bag"], correct_index=1, audio_text="bike"),
        _q("e11-3", "E1-1", "phonics_choice", "medium",
           "选出与 nose 中字母 o 发音相同的单词：", "home",
           "nose 和 home 都是相对开音节，字母 o 发 /əʊ/；box/dog/hot 发 /ɒ/。",
           options=["box", "dog", "home", "hot"], correct_index=2, audio_text="nose"),
        _q("e11-4", "E1-1", "word_tiles", "medium",
           "听录音并点击字母拼块，拼出你听到的开音节单词（提示：m _ _ e，制作）：", "make",
           "make 是 a-e 开音节词，a 发 /eɪ/，末尾 e 不发音。",
           tiles=_shuffle_deterministic(["m", "a", "k", "e", "i", "t"], 11),
           hint="a-e 结构，共 4 个字母", audio_text="make"),
        _q("e11-5", "E1-1", "phonics_choice", "hard",
           "选出划线部分发音不同的一项：", "cup",
           "cute / use / tube 中 u 发 /juː/，cup 中 u 在闭音节发 /ʌ/。",
           options=["c[u]te", "[u]se", "t[u]be", "c[u]p"], correct_index=3,
           audio_text="cute, use, tube, cup"),
        _q("e11-6", "E1-1", "speak_read", "medium",
           "请先听示范，然后清晰朗读下面这组开音节词句：",
           "I ride my nice bike home.",
           "注意 ride / nice / bike 中的 i-e 发 /aɪ/，home 中的 o-e 发 /əʊ/。",
           audio_text="I ride my nice bike home.",
           speak_target="I ride my nice bike home",
           fallback_options=["ride 与 nice 发音相同", "ride 与 big 发音相同", "home 与 hot 发音相同", "bike 与 bit 发音相同"],
           fallback_correct_index=0),
    ]

    # ---------------- E1-2 常见元音组合（ee/ea/oo/ow/ou） ----------------
    bank["E1-2"] = [
        _q("e12-1", "E1-2", "phonics_choice", "basic",
           "选出划线部分发音不同的一项：", "bread",
           "tea / eat / read 中 ea 发长音 /iː/，bread 中 ea 发短音 /e/。",
           options=["t[ea]", "[ea]t", "br[ea]d", "r[ea]d"], correct_index=2,
           audio_text="tea, eat, bread, read"),
        _q("e12-2", "E1-2", "listen_choice", "basic",
           "听录音，选出包含正确字母组合的单词：", "book",
           "book 中 oo 发短音 /ʊ/，结合录音可准确辨认。",
           options=["book", "boat", "back", "bike"], correct_index=0, audio_text="book"),
        _q("e12-3", "E1-2", "phonics_choice", "medium",
           "选出与 window 中 ow 发音相同的单词：", "snow",
           "window 和 snow 中 ow 发 /əʊ/；cow / flower / down 中 ow 发 /aʊ/。",
           options=["cow", "snow", "flower", "down"], correct_index=1, audio_text="window"),
        _q("e12-4", "E1-2", "word_tiles", "medium",
           "听录音并点击拼块，拼出单词（提示：h _ _ _ e，房子）：", "house",
           "house 中 ou 发 /aʊ/，拼写为 h-o-u-s-e。",
           tiles=_shuffle_deterministic(["h", "o", "u", "s", "e", "w"], 12),
           hint="含元音组合 ou，共 5 个字母", audio_text="house"),
        _q("e12-5", "E1-2", "phonics_choice", "hard",
           "选出划线部分 oo 发音不同的一项：", "food",
           "good / look / foot 中 oo 发短音 /ʊ/，food 中 oo 发长音 /uː/。",
           options=["g[oo]d", "l[oo]k", "f[oo]d", "f[oo]t"], correct_index=2,
           audio_text="good, look, food, foot"),
        _q("e12-6", "E1-2", "speak_read", "medium",
           "听示范并跟读，注意 ee/ea 和 ow 的发音：",
           "I see a yellow cow near the house.",
           "see 发 /iː/，yellow 中 ow 发 /əʊ/，cow 和 house 发 /aʊ/。",
           audio_text="I see a yellow cow near the house.",
           speak_target="I see a yellow cow near the house",
           fallback_options=["yellow 与 snow 发音相同", "cow 与 snow 发音相同", "see 与 bread 发音相同", "house 与 window 发音相同"],
           fallback_correct_index=0),
    ]

    # ---------------- E1-3 辅音组合发音（ch/sh/th/wh/ng） ----------------
    bank["E1-3"] = [
        _q("e13-1", "E1-3", "listen_choice", "basic",
           "听录音，选出你听到的单词：", "sheep",
           "sheep 以 sh 开头，发 /ʃ/，注意区分 cheap /tʃ/。",
           options=["cheap", "sheep", "sleep", "keep"], correct_index=1, audio_text="sheep"),
        _q("e13-2", "E1-3", "phonics_choice", "basic",
           "选出划线部分发音不同的一项：", "this",
           "three / thin / math 中 th 发清辅音 /θ/，this 中 th 发浊辅音 /ð/。",
           options=["[th]ree", "[th]in", "[th]is", "ma[th]"], correct_index=2,
           audio_text="three, thin, this, math"),
        _q("e13-3", "E1-3", "phonics_choice", "medium",
           "选出与 what 中 wh 发音不同的单词：", "who",
           "what / where / white 中 wh 发 /w/，who 中 wh 发 /h/。",
           options=["where", "white", "who", "when"], correct_index=2, audio_text="what"),
        _q("e13-4", "E1-3", "word_tiles", "medium",
           "听录音并点击拼块，拼出单词（提示：l _ _ _ h，午餐）：", "lunch",
           "lunch 末尾是辅音组合 ch，发 /tʃ/。",
           tiles=_shuffle_deterministic(["l", "u", "n", "c", "h", "s"], 13),
           hint="含辅音组合 ch，共 5 个字母", audio_text="lunch"),
        _q("e13-5", "E1-3", "phonics_choice", "hard",
           "选出划线部分发音相同的组合：s[i]ng / l[o]ng 的共同尾音对应哪个词？", "young",
           "sing / long / young 末尾均含 ng，发鼻音 /ŋ/。",
           options=["young", "hand", "rain", "nice"], correct_index=0, audio_text="sing, long, young"),
        _q("e13-6", "E1-3", "speak_read", "hard",
           "听示范并跟读，咬准 th 与 sh 的发音：",
           "She has three fresh fish for lunch.",
           "she / fresh / fish 发 /ʃ/，three 发清音 /θ/，lunch 尾音发 /tʃ/。",
           audio_text="She has three fresh fish for lunch.",
           speak_target="She has three fresh fish for lunch",
           fallback_options=["she 与 fish 都有 /ʃ/", "three 与 this 发音相同", "lunch 与 fish 尾音相同", "who 与 what 开头音相同"],
           fallback_correct_index=0),
    ]

    # ---------------- E1-4 自然拼读听音拼词 ----------------
    bank["E1-4"] = [
        _q("e14-1", "E1-4", "listen_choice", "basic",
           "听录音，根据自然拼读规则选出对应的单词：", "rainy",
           "rainy 由 ai(/eɪ/) + n + y(/i/) 拼读构成，意为“多雨的”。",
           options=["rainy", "sunny", "windy", "snowy"], correct_index=0, audio_text="rainy"),
        _q("e14-2", "E1-4", "phonics_choice", "basic",
           "听录音，单词 pl__ground 缺少的字母组合是？", "ay",
           "playground 中 ay 发 /eɪ/，组合为 play + ground。",
           options=["ay", "oo", "ir", "ur"], correct_index=0, audio_text="playground"),
        _q("e14-3", "E1-4", "word_tiles", "medium",
           "听录音并点击拼块，拼出你听到的单词（提示：c _ _ _ k，时钟）：", "clock",
           "clock 开头 cl 发 /kl/，末尾 ck 发 /k/。",
           tiles=_shuffle_deterministic(["c", "l", "o", "c", "k", "p"], 14),
           hint="cl 开头、ck 结尾，共 5 个字母", audio_text="clock"),
        _q("e14-4", "E1-4", "listen_choice", "medium",
           "听录音，选出单词末尾发音与录音一致的词：", "party",
           "happy / sunny / party 末尾 y 发短音 /i/，与 fly /aɪ/ 不同。",
           options=["fly", "sky", "party", "shy"], correct_index=2, audio_text="happy"),
        _word_spell_q("e14-5", "E1-4", "hard", "flower",
                      "听录音，用键盘直接拼写出你听到的单词（花朵）：",
                      "flower = fl + ow(/aʊ/) + er(/ə/)。",
                      hint="首字母 f，共 6 个字母", audio_text="flower"),
        _q("e14-6", "E1-4", "speak_read", "medium",
           "听示范并跟读下面的自然拼读句子：",
           "The funny baby plays by the clock.",
           "注意 funny / baby 末尾 y 发 /i/，plays 中 ay 发 /eɪ/。",
           audio_text="The funny baby plays by the clock.",
           speak_target="The funny baby plays by the clock",
           fallback_options=["baby 与 funny 尾音相同", "baby 与 fly 尾音相同", "clock 与 boat 元音相同", "play 与 bread 元音相同"],
           fallback_correct_index=0),
    ]

    # ---------------- E2-1 人物性格与日常职业 ----------------
    bank["E2-1"] = [
        _q("e21-1", "E2-1", "listen_choice", "basic",
           "听录音，选出与录音意思一致的中文：", "乐于助人的",
           "helpful 意为“乐于助人的”，常用来描述热心帮助他人的朋友。",
           options=["害羞的", "乐于助人的", "严格的", "勤奋的"], correct_index=1, audio_text="helpful"),
        _word_tile_q("e21-2", "E2-1", "basic", "polite", "有礼貌的", ["a", "r"],
                     "polite 意为“有礼貌的”，拼写 p-o-l-i-t-e。", seed=21),
        _q("e21-3", "E2-1", "reading_choice", "medium",
           "Tom always says 'please' and 'thank you'. He is very ____.", "polite",
           "常说请和谢谢体现了“有礼貌的（polite）”。",
           options=["shy", "polite", "strict", "old"], correct_index=1),
        _q("e21-4", "E2-1", "sentence_bank", "medium",
           "从词池中选出合适的词填入句子：My new math teacher is very ____, so we all like her.", "kind",
           "大家都喜欢她，应选“和蔼友善的（kind）”。",
           word_bank=["kind", "angry", "thirsty", "heavy"]),
        _word_spell_q("e21-5", "E2-1", "hard", "clever",
                      "根据中文和首字母提示，用键盘拼写单词：聪明的（c_____）",
                      "clever 意为“聪明的”，拼写 c-l-e-v-e-r。",
                      hint="首字母 c，共 6 个字母", audio_text="clever"),
        _q("e21-6", "E2-1", "listen_tf", "medium",
           "听录音判断对错：录音中的男孩既勤奋又乐于助人。", "T",
           "录音原句：Leo is hard-working and helpful at school. 描述与中文一致，选正确。",
           options=["正确 (T)", "错误 (F)"], correct_index=0,
           audio_text="Leo is hard-working and helpful at school."),
    ]

    # ---------------- E2-2 饮食口味与健康生活 ----------------
    bank["E2-2"] = [
        _q("e22-1", "E2-2", "listen_choice", "basic",
           "听录音，选出你听到的食物或饮品：", "sandwich",
           "sandwich 意为“三明治”，发音清晰可辨。",
           options=["salad", "sandwich", "hamburger", "ice cream"], correct_index=1, audio_text="sandwich"),
        _word_tile_q("e22-2", "E2-2", "basic", "fresh", "新鲜的", ["t", "o"],
                     "fresh 意为“新鲜的”，常修饰蔬菜水果。", seed=22),
        _q("e22-3", "E2-2", "sentence_bank", "medium",
           "选词填空：Vegetables are ____. We should eat them every day.", "healthy",
           "蔬菜是“健康的（healthy）”，适合每天吃。",
           word_bank=["healthy", "salty", "thirsty", "strict"]),
        _q("e22-4", "E2-2", "reading_choice", "medium",
           "I like apples. They are ____ and juicy.", "sweet",
           "形容苹果香甜多汁用 sweet（甜的）。",
           options=["hot", "sweet", "shy", "tall"], correct_index=1),
        _word_spell_q("e22-5", "E2-2", "hard", "delicious",
                      "听录音并根据中文提示拼写单词：美味的（d________）",
                      "delicious 意为“美味的”，拼写 d-e-l-i-c-i-o-u-s。",
                      hint="首字母 d，共 9 个字母", audio_text="delicious"),
        _q("e22-6", "E2-2", "listen_tf", "medium",
           "听录音判断对错：Amy 最喜欢的饮品是冰激凌。", "F",
           "录音原句：My favourite drink is orange juice. 她最喜欢的饮品是橙汁，不是冰激凌。",
           options=["正确 (T)", "错误 (F)"], correct_index=1,
           audio_text="My favourite drink is orange juice."),
    ]

    # ---------------- E2-3 星期课程与周末活动 ----------------
    bank["E2-3"] = [
        _q("e23-1", "E2-3", "listen_choice", "basic",
           "听录音，选出对应的星期单词：", "Thursday",
           "Thursday 意为“星期四”，注意不要与 Tuesday（星期二）混淆。",
           options=["Tuesday", "Thursday", "Saturday", "Sunday"], correct_index=1, audio_text="Thursday"),
        _word_tile_q("e23-2", "E2-3", "basic", "Friday", "星期五", ["n", "s"],
                     "Friday 意为“星期五”，星期名词首字母须大写。", seed=23),
        _q("e23-3", "E2-3", "sentence_bank", "medium",
           "选词填空：I often ____ my clothes on the weekend.", "wash",
           "固定搭配 wash my clothes 表示“洗衣服”。",
           word_bank=["wash", "watch", "play", "read"]),
        _q("e23-4", "E2-3", "reading_choice", "medium",
           "We have English, maths and ____ on Mondays.", "science",
           "与 English、maths 并列的课程应为 science（科学）。",
           options=["science", "forest", "bridge", "salad"], correct_index=0),
        _word_spell_q("e23-5", "E2-3", "hard", "Wednesday",
                      "根据中文与首字母提示，用键盘拼写星期单词：星期三（W________）",
                      "Wednesday 注意中间不发音的 d，首字母 W 须大写。",
                      hint="首字母大写 W，共 9 个字母", audio_text="Wednesday"),
        _q("e23-6", "E2-3", "listen_choice", "hard",
           "听短对话，判断 Mike 周六上午通常做什么？", "踢足球",
           "录音：I often play football with my friends on Saturday morning.",
           options=["做作业", "看电视", "踢足球", "洗衣服"], correct_index=2,
           audio_text="I often play football with my friends on Saturday morning."),
    ]

    # ---------------- E2-4 居家方位与自然景物 ----------------
    bank["E2-4"] = [
        _q("e24-1", "E2-4", "listen_choice", "basic",
           "听录音，选出你听到的方位介词：", "between",
           "between 表示“在两者之间”。",
           options=["beside", "behind", "between", "above"], correct_index=2, audio_text="between"),
        _word_tile_q("e24-2", "E2-4", "basic", "bridge", "桥", ["a", "t"],
                     "bridge 意为“桥”，拼写 b-r-i-d-g-e。", seed=24),
        _q("e24-3", "E2-4", "sentence_bank", "medium",
           "选词填空：There is a clean ____ in the nature park.", "river",
           "自然公园里有一条清澈的河流（river）。",
           word_bank=["river", "clock", "photo", "bottle"]),
        _q("e24-4", "E2-4", "reading_choice", "medium",
           "The ball is ____ the two boxes.", "between",
           "在两个盒子之间应使用方位介词 between。",
           options=["in", "between", "on", "above"], correct_index=1),
        _word_spell_q("e24-5", "E2-4", "hard", "forest",
                      "根据中文与首字母提示拼写单词：森林（f_____）",
                      "forest 意为“森林”，拼写 f-o-r-e-s-t。",
                      hint="首字母 f，共 6 个字母", audio_text="forest"),
        _q("e24-6", "E2-4", "listen_tf", "medium",
           "听录音判断对错：书桌上面有一台电脑。", "T",
           "录音：There is a computer on the desk. 与题干描述一致。",
           options=["正确 (T)", "错误 (F)"], correct_index=0,
           audio_text="There is a computer on the desk."),
    ]

    # ---------------- E3-1 be 动词与人称代词 ----------------
    bank["E3-1"] = [
        _q("e31-1", "E3-1", "sentence_bank", "basic",
           "选词填空：She ____ my English teacher.", "is",
           "主语 She 为第三人称单数，be 动词用 is。",
           word_bank=["am", "is", "are", "be"]),
        _q("e31-2", "E3-1", "sentence_bank", "basic",
           "选词填空：Tom and I ____ good friends.", "are",
           "Tom and I 表示复数主语（两个人），be 动词用 are。",
           word_bank=["am", "is", "are", "be"]),
        _q("e31-3", "E3-1", "reading_choice", "medium",
           "选出语法完全正确的一项：", "They are helpful.",
           "They 搭配 are；He 搭配 is；I 搭配 am。",
           options=["They is helpful.", "He are funny.", "They are helpful.", "I is quiet."], correct_index=2),
        _q("e31-4", "E3-1", "sentence_fill", "medium",
           "用 be 动词（am / is / are）的适当形式填空：____ your parents strict?", "Are",
           "主语 your parents 为复数，句首首字母需大写，填 Are。",
           hint="注意句首首字母大写", accept_answers=["Are"]),
        _sentence_order_q("e31-5", "E3-1", "hard",
                          ["Is", "he", "funny", "and", "kind?"],
                          "Is he funny and kind?",
                          "他又有趣又友善吗？",
                          "be 动词提前构成一般疑问句：Is he funny and kind?", seed=31),
        _q("e31-6", "E3-1", "sentence_fill", "hard",
           "用所给词的适当形式填空：Miss White is ____ (we) music teacher.", "our",
           "修饰名词 music teacher 需用形容词性物主代词 our（我们的）。",
           hint="填形容词性物主代词"),
    ]

    # ---------------- E3-2 名词单复数与 a/an/some/any ----------------
    bank["E3-2"] = [
        _q("e32-1", "E3-2", "sentence_bank", "basic",
           "选词填空：I would like ____ apple and a banana.", "an",
           "apple 以元音音素 /æ/ 开头，不定冠词用 an。",
           word_bank=["a", "an", "some", "any"]),
        _q("e32-2", "E3-2", "sentence_bank", "basic",
           "选词填空：Are there ____ tall buildings in the village?", "any",
           "疑问句中表示“一些”通常用 any，肯定句常用 some。",
           word_bank=["a", "an", "some", "any"]),
        _q("e32-3", "E3-2", "reading_choice", "medium",
           "选出复数变化正确的一组单词：", "boxes, tomatoes",
           "box 以 x 结尾加 -es；tomato 以 o 结尾有生命加 -es。",
           options=["boxs, tomatos", "boxes, tomatoes", "boxs, tomatoes", "boxes, tomatos"], correct_index=1),
        _q("e32-4", "E3-2", "sentence_fill", "medium",
           "用所给词的适当形式填空：I'd like two ____ (sandwich), please.", "sandwiches",
           "sandwich 以 ch 结尾，变复数加 -es -> sandwiches。",
           hint="注意以 ch 结尾的名词复数规则"),
        _q("e32-5", "E3-2", "sentence_fill", "hard",
           "用所给词的适当形式填空：There are many ____ (child) in the park.", "children",
           "child 为不规则复数，复数形式是 children。",
           hint="不规则复数变化"),
        _sentence_order_q("e32-6", "E3-2", "medium",
                          ["Would", "you", "like", "some", "tea?"],
                          "Would you like some tea?",
                          "你想要一些茶吗？",
                          "表礼貌邀请的疑问句 Would you like... 中用 some 不用 any。", seed=32),
    ]

    # ---------------- E3-3 一般现在时与三单/频率副词 ----------------
    bank["E3-3"] = [
        _q("e33-1", "E3-3", "sentence_bank", "basic",
           "选词填空：I often ____ books on Sundays.", "read",
           "主语 I 为第一人称，一般现在时动词用原形 read。",
           word_bank=["read", "reads", "reading", "to read"]),
        _q("e33-2", "E3-3", "sentence_bank", "basic",
           "选词填空：She ____ football after school.", "plays",
           "主语 She 为第三人称单数，一般现在时动词加 -s -> plays。",
           word_bank=["play", "plays", "playing", "played"]),
        _q("e33-3", "E3-3", "reading_choice", "medium",
           "____ you often wash your clothes on the weekend?", "Do",
           "实义动词 wash 的一般疑问句，主语为 you，句首用助动词 Do。",
           options=["Are", "Is", "Do", "Does"], correct_index=2),
        _q("e33-4", "E3-3", "sentence_fill", "medium",
           "用所给词的适当形式填空：He often ____ (watch) TV on Saturday evening.", "watches",
           "主语 He 是三单，watch 以 ch 结尾，三单加 -es -> watches。",
           hint="第三人称单数 + ch 结尾"),
        _q("e33-5", "E3-3", "sentence_fill", "hard",
           "用所给词的适当形式填空：Amy ____ (go) to school by bike every day.", "goes",
           "主语 Amy 是三单，go 的第三人称单数形式是 goes。",
           hint="第三人称单数变化"),
        _sentence_order_q("e33-6", "E3-3", "hard",
                          ["Do", "you", "often", "play", "sports?"],
                          "Do you often play sports?",
                          "你经常做运动吗？",
                          "一般现在时一般疑问句结构：Do + 主语 + 频率副词 + 动词原形？", seed=33),
    ]

    # ---------------- E3-4 情态动词 can 与 There be 句型 ----------------
    bank["E3-4"] = [
        _q("e34-1", "E3-4", "sentence_bank", "basic",
           "选词填空：I can ____ English songs for the party.", "sing",
           "情态动词 can 后面必须接动词原形 sing。",
           word_bank=["sing", "sings", "singing", "sang"]),
        _q("e34-2", "E3-4", "sentence_bank", "basic",
           "选词填空：There ____ a clock and two plants in my room.", "is",
           "There be 句型遵循“就近原则”，离 be 最近的是单数 a clock，故用 is。",
           word_bank=["is", "are", "am", "have"]),
        _q("e34-3", "E3-4", "reading_choice", "medium",
           "— Can you play the pipa?  — ____", "Yes, I can.",
           "Can you...? 的肯定简略回答是 Yes, I can.",
           options=["Yes, I do.", "Yes, I am.", "Yes, I can.", "No, I don't."], correct_index=2),
        _q("e34-4", "E3-4", "sentence_fill", "medium",
           "用所给词的适当形式填空：He can ____ (swim) very fast.", "swim",
           "情态动词 can 后的动词永远保持原形，不受主语人称影响。",
           hint="情态动词后用原形"),
        _q("e34-5", "E3-4", "sentence_fill", "hard",
           "用 is 或 are 填空：There ____ two lakes and a hill in the park.", "are",
           "There be 句型就近原则：离 be 最近的是复数 two lakes，故填 are。",
           hint="注意 There be 就近原则"),
        _sentence_order_q("e34-6", "E3-4", "hard",
                          ["There", "are", "many", "trees", "here."],
                          "There are many trees here.",
                          "这里有许多树。",
                          "There be 肯定句结构：There are + 复数名词 + 地点。", seed=34),
    ]

    # ---------------- E4-1 日常问答与礼貌交际 ----------------
    bank["E4-1"] = [
        _q("e41-1", "E4-1", "listen_choice", "basic",
           "听问句，选出最恰当的答语：", "I'd like some water.",
           "录音问：What would you like to drink?（你想喝什么？）应回答饮品。",
           options=["I'd like some noodles.", "I'd like some water.", "I can dance.", "It's Monday."],
           correct_index=1, audio_text="What would you like to drink?"),
        _q("e41-2", "E4-1", "reading_choice", "basic",
           "— Thank you very much!  — ____", "You're welcome.",
           "回应感谢的标准礼貌答语是 You're welcome.（不客气）。",
           options=["You're welcome.", "Me too.", "No problem, I'm hungry.", "Good idea."], correct_index=0),
        _q("e41-3", "E4-1", "listen_choice", "medium",
           "听问句，选出最恰当的答语：", "She is kind and funny.",
           "录音问：What's your art teacher like?（你的美术老师怎么样？）应回答性格/外貌特征。",
           options=["She likes apples.", "She is kind and funny.", "She is in the library.", "She has art on Friday."],
           correct_index=1, audio_text="What is your art teacher like?"),
        _q("e41-4", "E4-1", "sentence_bank", "medium",
           "补全对话：— Can you do any kung fu?  — ____, I can't. But I can draw cartoons.", "No",
           "后面是 I can't，表示否定回答，应填 No。",
           word_bank=["Yes", "No", "OK", "Sure"]),
        _q("e41-5", "E4-1", "speak_read", "medium",
           "听示范并礼貌跟读下面的点餐交际句：",
           "I would like some salad and tea, please.",
           "注意 would like 连读自然，句末 please 语调上扬显礼貌。",
           audio_text="I would like some salad and tea, please.",
           speak_target="I would like some salad and tea please",
           fallback_options=["询问想吃什么用 What would you like?", "回答想喝茶用 Yes, I can.", "感谢别人用 You're welcome.", "问星期几用 Who is she?"],
           fallback_correct_index=0),
        _q("e41-6", "E4-1", "listen_choice", "hard",
           "听问句，选出最恰当的答语：", "No, there aren't.",
           "录音问：Are there any tall buildings in the park? 应使用 There be 对应简答。",
           options=["No, they aren't.", "No, there isn't.", "No, there aren't.", "Yes, I can."],
           correct_index=2, audio_text="Are there any tall buildings in the park?"),
    ]

    # ---------------- E4-2 特殊疑问句（What/Where/When/Who） ----------------
    bank["E4-2"] = [
        _q("e42-1", "E4-2", "sentence_bank", "basic",
           "选词填空：— ____ is your maths teacher?  — Mr Li.", "Who",
           "答语是人名 Mr Li，提问“谁”用 Who。",
           word_bank=["Who", "What", "Where", "When"]),
        _q("e42-2", "E4-2", "sentence_bank", "basic",
           "选词填空：— ____ is the water bottle?  — It's on the desk.", "Where",
           "答语是地点方位 on the desk，提问“在哪里”用 Where。",
           word_bank=["Who", "What", "Where", "How"]),
        _q("e42-3", "E4-2", "reading_choice", "medium",
           "— ____ do you have on Tuesdays?  — We have Chinese, English and PE.", "What",
           "询问课程内容用 What do you have...?",
           options=["Who", "Where", "What", "When"], correct_index=2),
        _q("e42-4", "E4-2", "listen_choice", "medium",
           "听问句，选出最恰当的答语：", "I can play basketball.",
           "录音问：What can you do for the party? 回答能做的才艺活动。",
           options=["I can play basketball.", "I'm twelve.", "It's near the lake.", "Yes, I do."],
           correct_index=0, audio_text="What can you do for the party?"),
        _q("e42-5", "E4-2", "sentence_fill", "hard",
           "根据答语补全疑问词：— ____ do you usually get up?  — At 7:00 a.m.", "When",
           "答语是具体时间点 At 7:00 a.m.，提问时间用 When（句首大写）。",
           hint="提问时间，首字母大写"),
        _sentence_order_q("e42-6", "E4-2", "hard",
                          ["What", "is", "your", "favourite", "food?"],
                          "What is your favourite food?",
                          "你最喜欢的食物是什么？",
                          "特殊疑问句语序：疑问词 What + be 动词 is + 主语 your favourite food?", seed=42),
    ]

    # ---------------- E4-3 短文细节定位与判断 ----------------
    passage_1 = (
        "Hello, I am Lily. I study in Sunshine Primary School. "
        "My favourite day is Wednesday, because we have music and PE on that day. "
        "Our music teacher is Miss Chen. She is young and kind. "
        "After school, I often play ping-pong with my best friend Amy."
    )
    passage_2 = (
        "Welcome to Green Nature Park! It is quiet and clean. "
        "There is a big lake in the middle of the park. You can see many ducks on the lake. "
        "Behind the lake, there is a high hill and a green forest. "
        "There aren't any tall buildings here."
    )
    bank["E4-3"] = [
        _q("e43-1", "E4-3", "reading_choice", "basic",
           "根据短文内容，Lily 最喜欢星期几？", "Wednesday",
           "原文第二句明确提到：My favourite day is Wednesday.",
           options=["Monday", "Tuesday", "Wednesday", "Friday"], correct_index=2, passage=passage_1),
        _q("e43-2", "E4-3", "reading_choice", "basic",
           "根据短文内容，Miss Chen 的性格和外貌是怎样的？", "Young and kind",
           "原文第四句：She is young and kind.",
           options=["Old and strict", "Young and kind", "Shy and quiet", "Tall and strict"],
           correct_index=1, passage=passage_1),
        _q("e43-3", "E4-3", "reading_choice", "medium",
           "根据短文判断对错：Green Nature Park 里有很多高楼大厦。", "错误 (F)",
           "原文末句：There aren't any tall buildings here. 明确说明没有高楼。",
           options=["正确 (T)", "错误 (F)"], correct_index=1, passage=passage_2),
        _q("e43-4", "E4-3", "reading_choice", "medium",
           "根据短文，湖的后面有什么？", "A hill and a forest",
           "原文：Behind the lake, there is a high hill and a green forest.",
           options=["Many tall buildings", "A hill and a forest", "A school", "A bridge and a shop"],
           correct_index=1, passage=passage_2),
        _q("e43-5", "E4-3", "listen_choice", "hard",
           "听短文，回答问题：Jack 周末最喜欢做什么？", "画漫画和踢足球",
           "录音：Hi, I'm Jack. On the weekend, I love drawing cartoons and playing football.",
           options=["看电视和读书", "画漫画和踢足球", "游泳和唱歌", "做饭和洗衣服"],
           correct_index=1,
           audio_text="Hi, I am Jack. On the weekend, I love drawing cartoons and playing football."),
        _q("e43-6", "E4-3", "listen_choice", "hard",
           "听短文，回答问题：录音中提到的教室里一共有几块白板？", "One",
           "录音：Look at our classroom. There is one big whiteboard and twenty desks inside.",
           options=["One", "Two", "Twelve", "Twenty"], correct_index=0,
           audio_text="Look at our classroom. There is one big whiteboard and twenty desks inside."),
    ]

    # ---------------- E4-4 完形选词与语境推断 ----------------
    cloze_1 = (
        "My bedroom is small but nice. There is a bed near the window. "
        "A big desk is beside the bed. My schoolbag is ____ the chair."
    )
    cloze_2 = (
        "Tomorrow is Saturday. I don't go to school. In the morning, I will do my homework. "
        "In the afternoon, I will go to the park and ____ my bike with my brother."
    )
    bank["E4-4"] = [
        _q("e44-1", "E4-4", "sentence_bank", "basic",
           "结合短文语境选词填空（书包放在椅子上）：", "on",
           "表示物体在椅子表面上用介词 on。",
           word_bank=["on", "between", "in front", "at"], passage=cloze_1),
        _q("e44-2", "E4-4", "sentence_bank", "basic",
           "结合短文语境选词填空（骑自行车）：", "ride",
           "固定搭配 ride my bike 表示“骑自行车”。",
           word_bank=["ride", "read", "wash", "cook"], passage=cloze_2),
        _q("e44-3", "E4-4", "reading_choice", "medium",
           "I'm very ____. I'd like to drink a glass of water.", "thirsty",
           "后句说想喝一杯水，推断前句是“口渴的（thirsty）”。",
           options=["hungry", "thirsty", "helpful", "clever"], correct_index=1),
        _q("e44-4", "E4-4", "reading_choice", "medium",
           "It's very hot today, so I want to eat some ____.", "ice cream",
           "天气很热想吃消暑食物，选 ice cream（冰激凌）。",
           options=["hot soup", "ice cream", "warm tea", "spicy chicken"], correct_index=1),
        _q("e44-5", "E4-4", "sentence_bank", "hard",
           "语境完形选词：My robot Robin is very ____. He can speak both Chinese and English!", "clever",
           "会说中英双语体现机器人“很聪明（clever）”。",
           word_bank=["clever", "shy", "thirsty", "quiet"]),
        _q("e44-6", "E4-4", "reading_choice", "hard",
           "Ben never forgets to say 'Good morning' to his teachers. We know Ben is ____.", "polite",
           "从不忘记向老师问好说明 Ben 非常有礼貌（polite）。",
           options=["strict", "polite", "lazy", "thirsty"], correct_index=1),
    ]

    return bank


QUESTION_BANK = _build_question_bank()


def collect_audio_specs() -> list[dict[str, str]]:
    """收集题库中全部需要预生成的静态 MP3 音频条目（按 audioId 去重）."""
    seen: dict[str, dict[str, str]] = {}
    for qs in QUESTION_BANK.values():
        for q in qs:
            aid = q.get("audioId")
            txt = q.get("audioText")
            if aid and txt and aid not in seen:
                seen[aid] = {
                    "audioId": aid,
                    "text": txt,
                    "voice": q.get("audioVoice", "en-US-JennyNeural"),
                }
    return list(seen.values())


def get_map_blueprint() -> dict[str, Any]:
    return {
        "subject": SUBJECT_ENGLISH,
        "grade": DEFAULT_GRADE,
        "domains": [dict(d) for d in ENGLISH_G5_DOMAINS],
        "nodes": [dict(n) for n in ENGLISH_G5_NODES],
    }


def generate_node_questions(
    node_key: str,
    *,
    count: int = 5,
    seed: int = 0,
    exclude_ids: Iterable[str] = (),
    types: set[str] | None = None,
    map_friendly: bool = False,
) -> list[dict[str, Any]]:
    """按节点生成确定性题目列表（地图优先轻辅助题型，专项按 types 精准筛选）."""
    pool = QUESTION_BANK.get(node_key)
    if not pool:
        raise ValueError(f"Unknown English node: {node_key}")
    excluded = set(exclude_ids)
    filtered = [q for q in pool if q["id"] not in excluded]
    if types:
        filtered = [q for q in filtered if q["questionType"] in types]
    elif map_friendly:
        friendly = [q for q in filtered if q["questionType"] in MAP_FRIENDLY_TYPES]
        if len(friendly) >= count:
            filtered = friendly
        else:
            rest = [q for q in filtered if q not in friendly]
            filtered = friendly + rest
    if not filtered:
        return []
    n = len(filtered)
    shift = abs(int(seed)) % n
    ordered = filtered[shift:] + filtered[:shift]
    return [copy.deepcopy(q) for q in ordered[:count]]


def public_question(q: dict[str, Any]) -> dict[str, Any]:
    """脱敏返回给前端作答的题目结构（不暴露标准答案与解析）."""
    keep = (
        "id", "nodeKey", "questionType", "typeLabel", "level", "levelLabel",
        "marks", "text", "options", "audioId", "audioUrl", "hint",
        "tiles", "wordBank", "speakTarget", "fallbackOptions", "passage",
    )
    return {k: copy.deepcopy(q[k]) for k in keep if k in q}


def _norm_text(s: str) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _norm_words(s: str) -> list[str]:
    cleaned = re.sub(r"[^a-zA-Z0-9'\s]", " ", str(s or "").lower())
    return [w for w in cleaned.split() if w]


def grade_answer(
    question: dict[str, Any],
    *,
    selected_index: int | None = None,
    text_answer: str = "",
) -> bool:
    """精确判分 10 类英语题型（含跟读词级命中率与老设备辨音降级）."""
    qt = question.get("questionType", "")
    ans = str(question.get("answer", ""))

    # 1. 客观选择题（含听音选、听音判断、辨音选、阅读交际单选）
    if qt in ("listen_choice", "listen_tf", "phonics_choice", "reading_choice"):
        if selected_index is None:
            return False
        return int(selected_index) == int(question.get("correctIndex", -1))

    # 2. 跟读题：优先支持语音识别文本比对（词命中率 >= 75%），老设备支持降级辨音选项
    if qt == "speak_read":
        raw = _norm_text(text_answer)
        if raw.startswith("__fallback__:"):
            try:
                idx = int(raw.split(":", 1)[1])
            except ValueError:
                return False
            return idx == int(question.get("fallbackCorrectIndex", -1))
        if selected_index is not None and not raw:
            return int(selected_index) == int(question.get("fallbackCorrectIndex", -1))
        target_words = _norm_words(question.get("speakTarget") or ans)
        spoken_words = _norm_words(raw)
        if not target_words or not spoken_words:
            return False
        spoken_set = set(spoken_words)
        hit = sum(1 for w in target_words if w in spoken_set)
        return (hit / len(target_words)) >= 0.75

    # 3. 拼块单词填空 / 键盘单词拼写 / 词池句子填空 / 键盘语法填空 / 连词成句
    got = _norm_text(text_answer)
    if not got:
        return False

    accepts = [ans] + list(question.get("acceptAnswers") or [])
    if qt == "word_tiles":
        # 拼块单词填空：星期等专有名词允许大小写宽容，或精确匹配字母
        return any(got.lower() == _norm_text(a).lower() for a in accepts)

    if qt == "sentence_order":
        # 连词成句：允许句末标点前无多余空格，严格校验词序
        got_clean = re.sub(r"\s+([?.!,])", r"\1", got)
        return any(got_clean.lower() == _norm_text(a).lower() for a in accepts)

    if qt in ("word_spell", "sentence_fill"):
        # 强应试：严判单复数/三单/时态；句首/星期专有名词支持精确匹配，其余单词忽略纯首字母大小写误触
        for a in accepts:
            na = _norm_text(a)
            if got == na:
                return True
            if na and na[0].islower() and got.lower() == na.lower():
                return True
        return False

    if qt == "sentence_bank":
        return any(got.lower() == _norm_text(a).lower() for a in accepts)

    return got.lower() == _norm_text(ans).lower()


def compute_light_state(
    *,
    attempts: int,
    correct: int,
    hard_correct: int,
    best_quiz_rate_pct: int,
    sprint_boost_stars: int,
    needs_repair: bool,
) -> dict[str, Any]:
    """与数学地图完全一致的四态点亮状态机."""
    stars = 0
    state = "unexplored"
    if attempts > 0 or sprint_boost_stars > 0:
        state = "exploring"
    if best_quiz_rate_pct >= 80 or sprint_boost_stars >= 1:
        state = "lit"
        stars = max(1, min(3, sprint_boost_stars or 1))
    if (best_quiz_rate_pct >= 100 and hard_correct >= 1) or sprint_boost_stars >= 3 or (best_quiz_rate_pct >= 80 and correct >= 8):
        state = "mastered"
        stars = 3
    elif state == "lit" and (best_quiz_rate_pct >= 90 or sprint_boost_stars >= 2):
        stars = max(stars, 2)
    return {
        "state": state,
        "stateLabel": LIGHT_STATES[state],
        "stars": stars,
        "needsRepair": bool(needs_repair),
    }


__all__ = [
    "DEFAULT_GRADE",
    "DOMAIN_BY_ID",
    "ENGLISH_G5_DOMAINS",
    "ENGLISH_G5_NODES",
    "LEVEL_LABELS",
    "LIGHT_STATES",
    "NODE_BY_KEY",
    "QUESTION_BANK",
    "SUBJECT_ENGLISH",
    "TYPE_LABELS",
    "TYPE_POINTS",
    "collect_audio_specs",
    "compute_light_state",
    "generate_node_questions",
    "get_map_blueprint",
    "grade_answer",
    "make_audio_id",
    "public_question",
]
